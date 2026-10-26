import json
import os
import re
from pathlib import Path
from types import SimpleNamespace
import numpy as np
from PIL import Image

from .settings import MODELS, Settings


class PredictionError(RuntimeError):
    def __init__(self, message, result):
        super().__init__(message)
        self.details = {"response": result.response, "prompt": result.prompt,
                        "parsed_boxes": result.boxes, "decoded_masks": len(result.masks)}


def is_absent_response(response):
    return bool(re.fullmatch(r"(?:None|<ref>[^<>]*</ref>\s*<box>\s*None\s*</box>)", response.strip(), flags=re.IGNORECASE))


def display_window_limits(window, channel):
    """Read the saved display window, rather than the allowed min/max bounds."""
    values = [window.get(key) for key in ("start", "end")] if isinstance(window, dict) else []
    if (len(values) != 2 or any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in values)
            or not np.isfinite(values).all() or values[1] <= values[0]
            or not np.isfinite(float(values[1]) - float(values[0]))):
        raise ValueError(f"Channel {channel} needs finite OME-Zarr omero.channels window.start < window.end; choose percentile or full data-type range if unavailable")
    return tuple(map(float, values))


def unsigned_dtype_limits(dtype):
    dtype = np.dtype(dtype)
    if dtype.kind != "u":
        raise ValueError("Full data-type range requires unsigned integer source pixels, such as uint8 or uint16; choose metadata or percentile for floating-point inputs")
    return 0., float(np.iinfo(dtype).max)


def render_rgb(planes, channels, normalization, *, windows=None, source_dtype=None):
    """Render a model-only RGB view; retain original microscopy pixels."""
    rendered, limits = [], []
    for channel in channels:
        original = planes[channel - 1]
        if not np.isfinite(original).all():
            raise ValueError(f"Channel {channel} contains NaN or infinite pixels")
        if normalization == "dtype":
            lo, hi = unsigned_dtype_limits(source_dtype if source_dtype is not None else original.dtype)
        elif normalization == "metadata":
            lo, hi = display_window_limits((windows or {}).get(channel), channel)
        elif normalization == "percentile":
            lo, hi = map(float, np.percentile(original, [1, 99.8]))
        else:
            raise ValueError("Choose percentile, dtype or metadata normalization")
        precision = np.float32 if normalization == "percentile" else np.float64
        span = max(hi - lo, 1e-12) if normalization == "percentile" else hi - lo
        scaled = np.clip((original.astype(precision) - lo) / span, 0, 1)
        rendered.append(np.rint(scaled * 255).astype(np.uint8))
        limits.append({"channel": channel, "low": lo, "high": hi})
    if len(rendered) == 1:
        rendered *= 3
    return Image.fromarray(np.stack(rendered, axis=-1)), limits


class Predictor:
    def __init__(self, settings: Settings):
        self.settings = settings
        folder = Path(settings.models_root).resolve() / f"WeVisOne-VL-{settings.model}"
        manifest = folder / "download-manifest.json"
        if not manifest.is_file():
            raise FileNotFoundError("WeVisOne-VL-4B not prepared. Run .venv\\Scripts\\python tools/download_models.py")
        self.manifest = json.loads(manifest.read_text())
        if self.manifest.get("repo_id") != MODELS[settings.model] or not (folder / "mask_decoder.pt").is_file():
            raise ValueError(f"Incomplete model cache: {folder}")
        for item in self.manifest.get("files", []):
            local = folder / item["path"]
            if not local.is_file() or local.stat().st_size != item["size"]:
                raise ValueError(f"Incomplete model snapshot: {local}. Re-run tools/download_models.py with its pinned --revision.")
        # Local snapshots and offline libraries: inference never downloads models.
        os.environ["HF_HUB_OFFLINE"] = "1"
        os.environ["TRANSFORMERS_OFFLINE"] = "1"
        import torch
        from wevisone_vl import WeVisOneVL
        from wevisone_vl.engine import parse_seg_boxes
        device = settings.device
        if device == "auto":
            device = "cuda:0" if torch.cuda.is_available() else "cpu"
        if device.startswith("cuda") and not torch.cuda.is_available():
            raise RuntimeError("CUDA requested but unavailable in this Python environment")
        self.cuda_device = device if device.startswith('cuda') else None
        self.last_gpu_memory = None
        self.engine = WeVisOneVL(str(folder), backend="transformers", device=device,
                                dtype="bfloat16", max_pixels=settings.max_side ** 2,
                                decoder_batch_size=settings.decoder_batch_size)
        original_generate = self.engine.model.generate

        def checked_generate(*args, **kwargs):
            sequences = original_generate(*args, **kwargs)
            input_length = kwargs["input_ids"].shape[1]
            generated = sequences[:, input_length:]
            eos = self.engine.model.generation_config.eos_token_id
            eos = [eos] if isinstance(eos, int) else list(eos or [])
            if generated.shape[1] >= kwargs["max_new_tokens"] and int(generated[0,-1]) not in eos:
                raise RuntimeError("Generation reached the token limit without EOS; increase max_new_tokens or simplify the prompt")
            return sequences

        self.engine.model.generate = checked_generate
        original_decode = self.engine.decode_masks

        def checked_decode(image, prompt, response, boxes=None):
            parsed = parse_seg_boxes(response) if boxes is None else boxes
            count = response.upper().count("<OBJ>")
            if len(parsed) != count:
                result = SimpleNamespace(response=response, prompt=prompt, boxes=parsed, masks=[])
                raise PredictionError(f"Model generated {count} object tokens but {len(parsed)} valid boxes. Refusing misaligned mask decoding; try a more specific prompt or an explicit smaller ROI.", result)
            return original_decode(image, prompt, response, boxes=parsed)

        self.engine.decode_masks = checked_decode

    def predict(self, image, text):
        """Return CPU masks, then release unused CUDA cache between requests."""
        import gc
        import torch
        before = self.gpu_memory()
        try:
            return self._predict(image,text)
        finally:
            after_prediction = self.gpu_memory()
            if self.settings.release_gpu_cache and self.cuda_device:
                gc.collect()
                with torch.cuda.device(self.cuda_device):
                    torch.cuda.synchronize()
                    torch.cuda.empty_cache()
            self.last_gpu_memory = {'before':before,'after_prediction':after_prediction,
                                    'after_cleanup':self.gpu_memory(),
                                    'release_unused_cache':bool(self.settings.release_gpu_cache)}

    def gpu_memory(self):
        if not self.cuda_device:
            return None
        import torch
        return {'allocated_bytes':torch.cuda.memory_allocated(self.cuda_device),
                'reserved_bytes':torch.cuda.memory_reserved(self.cuda_device)}

    def _predict(self, image, text):
        result = self.engine.predict(image, task="segmentation", query=text,
                                     temperature=0., max_new_tokens=self.settings.max_new_tokens)
        # Never silently accept a response cut off at the token budget.
        tokens = self.engine.tokenizer.encode(result.response, add_special_tokens=False)
        if len(tokens) >= self.settings.max_new_tokens:
            raise RuntimeError("Generation reached the token limit; increase max_new_tokens or simplify the prompt")
        count = result.response.upper().count("<OBJ>")
        if count != len(result.masks) or count != len(result.boxes):
            raise PredictionError("Incomplete/malformed model mask response; refusing partial segmentation", result)
        if not count and not is_absent_response(result.response):
            raise PredictionError(f"Unrecognized empty segmentation response: {result.response[:200]}", result)
        return result


def combine_masks(masks, shape, threshold=.5, min_area=0, mode="instances"):
    """Highest probability owns overlap; first prediction wins exact ties."""
    height, width = shape
    labels = np.zeros(shape, np.uint32)
    best = np.full(shape, threshold, np.float32)
    accepted = 0
    for index, mask in enumerate(masks, start=1):
        mask = np.asarray(mask, np.float32)
        if mask.ndim != 2 or not np.isfinite(mask).all() or mask.min() < 0 or mask.max() > 1:
            raise ValueError("Model masks must be finite 2D probabilities in [0,1]")
        if mask.shape != shape:
            mask = np.asarray(Image.fromarray(mask).resize((width, height), Image.Resampling.BILINEAR))
        foreground = mask > threshold
        if foreground.sum() < min_area:
            continue
        owns = foreground & (mask > best)
        labels[owns] = index
        best[owns] = mask[owns]
    # Area filtering after overlap avoids retaining tiny remnants of occluded instances.
    ids, counts = np.unique(labels, return_counts=True)
    for index, area in zip(ids, counts):
        if index and area < min_area:
            labels[labels == index] = 0
    ids = np.unique(labels)
    ids = ids[ids > 0]
    accepted = len(ids)
    remapped = np.zeros_like(labels)
    for new, old in enumerate(ids, start=1):
        remapped[labels == old] = new if mode == "instances" else 1
    return remapped, accepted
