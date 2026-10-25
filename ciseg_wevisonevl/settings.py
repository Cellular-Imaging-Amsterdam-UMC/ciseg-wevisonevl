from dataclasses import dataclass, asdict
from pathlib import Path
import math
import os
import re


ROOT = Path(__file__).resolve().parents[1]
UPSTREAM_COMMIT = "40f735b8daed437ece982db9718e9c9856f52a79"
MODELS = {"4B": "tencent/WeVisOne-VL-4B"}
MODEL_REVISIONS = {"4B": "4a7bed92750ac9d8b8a124cede14759036932dc2"}


@dataclass(frozen=True)
class Prompt:
    name: str
    text: str
    channels: tuple[int, ...] = (1,)

    def validate(self):
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{0,63}", self.name):
            raise ValueError("Label name must start with a letter and contain only letters, digits, _ or - (max 64)")
        if not self.text.strip() or len(self.text) > 1000:
            raise ValueError("Each active prompt needs 1-1000 characters")
        if len(self.channels) not in (1, 3) or any(c < 1 for c in self.channels):
            raise ValueError("Channels must be one positive channel or three positive R,G,B channels (one-based)")


@dataclass(frozen=True)
class Settings:
    model: str = "4B"
    models_root: str = os.environ.get("CISEGWEVISONEVL_MODELS", str(ROOT / "models"))
    device: str = "auto"
    threshold: float = 0.5
    max_side: int = 1024
    max_new_tokens: int = 2048
    decoder_batch_size: int = 1
    min_area: int = 0
    normalization: str = "percentile"
    label_mode: str = "instances"
    projection: str = "Max"

    def validate(self, prompts):
        if not 1 <= len(prompts) <= 4:
            raise ValueError("Enable between one and four segmentation prompts")
        for p in prompts:
            p.validate()
        if len({p.name for p in prompts}) != len(prompts):
            raise ValueError("Active label names must be unique")
        if self.model not in MODELS:
            raise ValueError("This workflow uses WeVisOne-VL-4B exclusively")
        if self.device not in ("auto", "cpu", "cuda", "cuda:0"):
            raise ValueError("Choose auto, cuda:0 or cpu")
        if not math.isfinite(self.threshold) or not 0 < self.threshold < 1:
            raise ValueError("Mask threshold must be between 0 and 1")
        if not 128 <= self.max_side <= 2048:
            raise ValueError("Model input maximum side must be 128-2048 pixels")
        if not 32 <= self.max_new_tokens <= 8192:
            raise ValueError("Token limit must be 32-8192")
        if not 1 <= self.decoder_batch_size <= 8 or self.min_area < 0:
            raise ValueError("Invalid decoder batch size or minimum pixel area")
        if self.normalization not in ("percentile", "dtype"):
            raise ValueError("Choose percentile or dtype normalization")
        if self.label_mode not in ("instances", "semantic"):
            raise ValueError("Choose instances or semantic masks")
        if self.projection not in ("Max", "Mean"):
            raise ValueError("Choose Max or Mean for the automatic Z projection")

    def asdict(self):
        return asdict(self)
