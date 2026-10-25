"""Bilayers entrypoint: exactly four named, independently optional prompt slots."""
import argparse
import json
import sys
from ciseg_wevisonevl.settings import Settings, Prompt
from ciseg_wevisonevl.engine import run, preflight


def build_parser():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--infolder", "--input-dir", required=True)
    parser.add_argument("--outfolder", "--output-dir", required=True)
    parser.add_argument("--local", action="store_true", help="Bilayers compatibility flag; uses local Python")
    parser.add_argument("--parameters", help="JSON object of named workflow parameters")
    parser.add_argument("--preflight-only", action="store_true")
    for name, field in Settings.__dataclass_fields__.items():
        if name == "model":
            continue
        flags = list(dict.fromkeys(["--" + name.replace("_", "-"), "--" + name]))
        parser.add_argument(*flags, dest=name,
                            type=field.type, default=field.default)
    for slot in range(1, 5):
        for key, default in [("prompt", ""),
                             ("name", f"target{slot}"),
                             ("channels", "1")]:
            parser.add_argument(f"--{key}-{slot}", f"--{key}_{slot}", dest=f"{key}_{slot}", default=default)
    return parser


def settings_from_args(args):
    values = vars(args).copy()
    if args.parameters:
        supplied = json.loads(args.parameters)
        allowed = (set(Settings.__dataclass_fields__) - {"model"}) | {f"{k}_{s}" for s in range(1,5) for k in ("prompt", "name", "channels")}
        if not isinstance(supplied, dict) or set(supplied) - allowed:
            raise ValueError("Unknown JSON workflow parameters")
        values.update(supplied)
    settings_values = {}
    for name, field in Settings.__dataclass_fields__.items():
        if name == "model":
            continue
        settings_values[name] = field.type(values[name])
    settings = Settings(**settings_values)
    prompts = []
    for slot in range(1, 5):
        text = str(values[f"prompt_{slot}"]).strip()
        if text:
            channels = tuple(int(v.strip()) for v in str(values[f"channels_{slot}"]).split(","))
            prompts.append(Prompt(str(values[f"name_{slot}"]).strip(), text, channels))
    settings.validate(prompts)
    return settings, prompts


def main(argv=None):
    args = build_parser().parse_args(argv)
    settings, prompts = settings_from_args(args)
    if args.preflight_only:
        jobs = preflight(args.infolder, args.outfolder, settings, prompts)
        print(json.dumps({"stores": len(jobs), "fields": sum(len(j[2]) for j in jobs), "prompts": len(prompts), "valid": True}))
    else:
        run(args.infolder, args.outfolder, settings, prompts)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"ERROR: {type(exc).__name__}: {exc}", file=sys.stderr, flush=True)
        raise SystemExit(1)
