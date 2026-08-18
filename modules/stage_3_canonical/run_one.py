"""Canonicalize one EGPMapping without consulting any other stage."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from modules.stage_3_canonical.run import build
from shared.utils.config import resolve_experiment
from shared.utils.contracts import validate_value
from shared.utils.experiment import ensure_run_metadata
from shared.utils.io import read_json, read_jsonl, repo_path, write_json
from shared.utils.research import prepare_unit_directory, resolve_run, safe_component


DEFAULT_EGP_ID = "FIX_CANONICAL_SIMPLE"
DEFAULT_INPUT = Path(__file__).resolve().parent / "fixtures" / "core.jsonl"
DEFAULT_EXPERIMENT = "run_one_demo"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("egp_id", nargs="?", help=f"default: {DEFAULT_EGP_ID} from the core fixture")
    parser.add_argument("--experiment", default=DEFAULT_EXPERIMENT)
    parser.add_argument("--input", type=Path, help="EGPMapping JSON or JSONL; otherwise resolve the run input")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    using_default = args.egp_id is None
    egp_id = args.egp_id or DEFAULT_EGP_ID
    safe_component(egp_id)
    resolution = resolve_experiment(args.experiment)
    run_dir, _ = ensure_run_metadata(resolution)
    if args.input:
        path = args.input.resolve()
    elif using_default:
        path = DEFAULT_INPUT
    elif (run_dir / "normalization/final_mappings.jsonl").is_file():
        path = run_dir / "normalization/final_mappings.jsonl"
    elif resolution.parent_resolved:
        parent = resolve_run(resolution.parent_resolved["experiment_id"])
        path = parent / "normalization/final_mappings.jsonl"
    else:
        raise FileNotFoundError("canonical run-one needs normalization output; use --input")
    mapping = (
        next(row for row in read_jsonl(path) if row["egp_id"] == egp_id)
        if path.suffix == ".jsonl" else read_json(path)
    )
    schema = repo_path("modules/stage_2_normalization/schemas/egp_mapping_v1_3.schema.json")
    validate_value(mapping, schema, label="canonical input EGPMapping")
    cells, edges = build([mapping])
    unit = prepare_unit_directory(run_dir / "canonical/units" / egp_id, force=args.force)
    write_json(unit / "input.json", mapping)
    write_json(unit / "output.json", {"canonical_cells": cells, "source_cell_edges": edges})
    write_json(unit / "validation.json", {"valid": True, "complete_mapping_expanded": mapping["result"] == "complete"})
    after = {"canonical_cells": cells, "source_cell_edges": edges}
    print(
        json.dumps(
            {"before": mapping, "after": after, "unit_directory": str(unit)},
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
