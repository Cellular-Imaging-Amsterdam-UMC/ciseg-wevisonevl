from dataclasses import asdict
from pathlib import Path
import json
import time
from uuid import uuid4
import numpy as np
from PIL import Image
import zarr

from . import __version__
from .settings import UPSTREAM_COMMIT
from .io import discover, inspect_store, write_labels, write_json, publish_store
from .inference import Predictor, render_rgb, combine_masks
from .projection import prepare_output
from .measurements import MeasurementCSV
from .outputs import replace_completed_run


def preflight(input_dir, output_dir, settings, prompts):
    settings.validate(prompts)
    stores = discover(input_dir)
    output_dir = Path(output_dir).resolve()
    if (output_dir/'measurements.csv').exists() and not settings.overwrite:
        raise FileExistsError(f'Measurements already exist; choose a new output folder: {output_dir}')
    if settings.overwrite:
        csv_path = output_dir/'measurements.csv'
        if csv_path.is_symlink() or csv_path.is_junction() or csv_path.exists() and not csv_path.is_file():
            raise ValueError('Cannot replace measurements: expected a regular measurements.csv file')
    jobs = []
    for store in stores:
        store = store.resolve()
        if store == output_dir or store in output_dir.parents or output_dir in store.parents:
            raise ValueError("Input and output stores must be separate; output cannot contain or be inside a source")
        output = output_dir / (store.name.removesuffix(".ome.zarr") + "__wevisonevl.ome.zarr")
        if output.exists() and not settings.overwrite:
            raise FileExistsError(f"Output already exists; choose an empty output folder: {output}")
        if settings.overwrite and (output.is_symlink() or output.is_junction()):
            raise ValueError(f'Refusing to replace a linked output store: {output}')
        if settings.overwrite and output.exists() and (not output.is_dir() or not (output/'wevisone-run.json').is_file()):
            raise ValueError(f'Refusing to replace a folder without a CISegWeVisOneVL run report: {output}')
        fields = inspect_store(store, prompts, check_label_names=settings.input_labels == 'keep')
        selected_channels = {c for prompt in prompts for c in prompt.channels}
        for field in fields:
            field.render_options(settings.normalization, selected_channels)
        jobs.append((store, output, fields))
    return jobs


def run(input_dir, output_dir, settings, prompts, *, predictor_factory=Predictor):
    started = time.perf_counter()
    jobs = preflight(input_dir, output_dir, settings, prompts)
    print(f"Preflight OK: {len(jobs)} stores, {sum(len(j[2]) for j in jobs)} fields, {len(prompts)} prompts; Z projection={settings.projection}", flush=True)
    predictor = predictor_factory(settings)
    model_loaded = time.perf_counter()
    max_channels=max(field.cyx_shape[0] for _,_,fields in jobs for field in fields)
    if not settings.overwrite:
        with MeasurementCSV(output_dir,max_channels) as measurements:
            return _run_jobs(jobs,settings,prompts,predictor,started,model_loaded,measurements)
    output_dir = Path(output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    staging = output_dir / ('.wevisone-run-'+uuid4().hex+'.partial')
    staging.mkdir()
    staged_jobs = [(source, staging/output.name, fields) for source, output, fields in jobs]
    print('Existing results remain available until the new run has completed.', flush=True)
    with MeasurementCSV(staging,max_channels) as measurements:
        _run_jobs(staged_jobs,settings,prompts,predictor,started,model_loaded,measurements)
    replace_completed_run(staging, output_dir, [output.name for _,output,_ in jobs]+['measurements.csv'])
    outputs = [output for _,output,_ in jobs]
    for output in outputs:
        print(f'DONE: {output}', flush=True)
    print(f'MEASUREMENTS: {output_dir / "measurements.csv"} ({measurements.rows} rows)', flush=True)
    return outputs


def _run_jobs(jobs,settings,prompts,predictor,started,model_loaded,measurements):
    outputs = []
    for store, output, fields in jobs:
        output.parent.mkdir(parents=True, exist_ok=True)
        partial = output.with_name(output.name + ".partial-" + uuid4().hex[:8])
        report = {"version": __version__, "upstream_commit": UPSTREAM_COMMIT,
                  "settings": settings.asdict(), "prompts": [asdict(p) for p in prompts],
                  "source": str(store), "model_snapshot": predictor.manifest,
                  "status": "running", "fields": [], "model_load_seconds": model_loaded - started}
        report['measurements_file']='../measurements.csv'
        try:
            print(f"Preparing images and per-timepoint Z projections: {store.name}", flush=True)
            prepared = prepare_output(store, partial, fields, prompts, settings.projection, settings.input_labels)
            report["input_fields"] = [{"field":f.path,"timepoints":f.timepoints,"source_z_planes":f.z_planes,
                                       "projection":settings.projection if f.z_planes>1 else "none",
                                       "source_axes":f.names,"output_axes":prepared[f.path].names} for f in fields]
            previews = partial / "wevisone_previews"
            previews.mkdir(exist_ok=True)
            for index, field in enumerate(fields):
                print(f"Field {index+1}/{len(fields)}: {field.path or store.name}", flush=True)
                output_field=prepared[field.path]
                for time_index in range(field.timepoints):
                    _segment_frame(predictor,settings,prompts,field,output_field,partial,index,time_index,report,measurements,output.name)
            report["status"] = "complete"
            report["elapsed_seconds"] = time.perf_counter() - started
            write_json(partial / "wevisone-run.json", report)
            root = zarr.open_group(str(partial), mode="a")
            root.attrs["ciseg_wevisonevl"] = {"version": __version__, "status": "complete", "report": "wevisone-run.json", "measurements_file":"../measurements.csv", "model": settings.model, "revision": predictor.manifest.get("revision")}
            # Atomic same-filesystem rename; never publish a partial as a completed store.
            publish_store(partial, output)
            outputs.append(output)
            print(f"DONE: {output}", flush=True)
        except BaseException as exc:
            if partial.is_dir():
                report["status"] = "failed"
                report["error"] = str(exc)
                report["elapsed_seconds"] = time.perf_counter() - started
                if hasattr(exc, "details"):
                    report["failed_prediction"] = exc.details
                write_json(partial / "wevisone-run.json", report)
            raise
    return outputs


def _segment_frame(predictor, settings, prompts, source_field, field, output, index, time_index, report, measurements, output_name):
    print(f"  Timepoint {time_index+1}/{field.timepoints}",flush=True)
    planes=field.pixels([c for p in prompts for c in p.channels],time_index)
    for slot,prompt in enumerate(prompts,1):
        rgb,limits=render_rgb(planes,prompt.channels,settings.normalization,
                              **source_field.render_options(settings.normalization,prompt.channels))
        native_shape=(rgb.height,rgb.width)
        rgb.thumbnail((settings.max_side,settings.max_side),Image.Resampling.LANCZOS)
        tick=time.perf_counter()
        prediction=predictor.predict(rgb,prompt.text)
        labels,count=combine_masks(prediction.masks,native_shape,settings.threshold,settings.min_area,settings.label_mode)
        coverage=float(np.count_nonzero(labels)/labels.size)
        entry={"field":field.path,"time_index":time_index,"slot":slot,"name":prompt.name,"query":prompt.text,
               "projection":settings.projection if source_field.z_planes>1 else "none","source_z_planes":source_field.z_planes,
               "channels":list(prompt.channels),"normalization_limits":limits,
               "model_input_size_xy":list(rgb.size),"native_size_yx":list(native_shape),
               "response":prediction.response,"generated_prompt":prediction.prompt,
               "boxes_normalized_xyxy":prediction.boxes,"predicted_instances":len(prediction.masks),
               "retained_instances":count,"foreground_pixels":int(np.count_nonzero(labels)),"foreground_fraction":coverage,
               "seconds":time.perf_counter()-tick,"overlap_policy":"highest probability; first prediction wins ties",
               "label_mode":settings.label_mode,"threshold":settings.threshold,"model":settings.model,
               "model_revision":predictor.manifest.get("revision")}
        if coverage>.8:
            entry["review_note"]=f"Mask covers {coverage:.1%} of the field. Inspect the overlay for foreground/background confusion."
            print("  REVIEW: "+entry["review_note"],flush=True)
        write_labels(output,field,prompt,labels,entry,time_index)
        measurement_started=time.perf_counter()
        entry['measurement_rows']=measurements.add(labels,field,prompt,source_field,time_index,settings,output_name,planes)
        entry['measurement_seconds']=time.perf_counter()-measurement_started
        prefix=f"field{index+1:04d}_t{time_index:04d}_{prompt.name}"
        preview_path=output/"wevisone_previews"
        rgb.save(preview_path/(prefix+"_input.png"))
        preview_labels=np.asarray(Image.fromarray(labels.astype(np.int32)).resize(rgb.size,Image.Resampling.NEAREST))
        overlay=np.asarray(rgb).copy()
        foreground=preview_labels>0
        overlay[foreground]=(.55*overlay[foreground]+.45*np.array([255,70,180])).astype(np.uint8)
        Image.fromarray(overlay).save(preview_path/(prefix+"_overlay.png"))
        report["fields"].append(entry)
        print(f"  {prompt.name}: {count} retained / {len(prediction.masks)} predicted instances, {entry['seconds']:.1f}s",flush=True)
        write_json(output/"wevisone-run.json",report)
