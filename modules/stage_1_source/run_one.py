"""Resolve and validate one declared source descriptor."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from shared.utils.config import resolve_experiment
from shared.utils.contracts import validate_value
from shared.utils.experiment import ensure_run_metadata
from shared.utils.io import read_json, read_jsonl, repo_path, write_json
from shared.utils.manifests import describe
from shared.utils.research import prepare_unit_directory, safe_component


DEFAULT_EGP_ID = "FIX_SOURCE_SIMPLE"
DEFAULT_INPUT = Path(__file__).resolve().parent / "fixtures" / "core.jsonl"
DEFAULT_EXPERIMENT = "run_one_demo"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("egp_id", nargs="?", help=f"default: {DEFAULT_EGP_ID} from the core fixture")
    parser.add_argument("--experiment", default=DEFAULT_EXPERIMENT)
    parser.add_argument("--input", type=Path)
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    using_default = args.egp_id is None
    egp_id = args.egp_id or DEFAULT_EGP_ID
    safe_component(egp_id)
    resolution = resolve_experiment(args.experiment)
    config = resolution.resolved
    run_dir, _ = ensure_run_metadata(resolution)
    path = (
        args.input.resolve()
        if args.input else DEFAULT_INPUT
        if using_default else repo_path(config["source"]["path"])
    )
    if path.suffix == ".jsonl":
        record = next(row for row in read_jsonl(path) if row.get("egp_id") == egp_id)
    else:
        record = read_json(path)
    schema = repo_path("modules/stage_1_source/schemas/source_descriptor.schema.json")
    validate_value(record, schema, label="SourceDescriptor")
    unit = prepare_unit_directory(run_dir / "source/units" / egp_id, force=args.force)
    before = {"source": describe(path), "egp_id": egp_id}
    write_json(unit / "input.json", before)
    write_json(unit / "output.json", record)
    write_json(unit / "validation.json", {"valid": True, "schema": describe(schema)})
    print(
        json.dumps(
            {"before": before, "after": record, "unit_directory": str(unit)},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
