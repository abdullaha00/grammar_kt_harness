"""Materialize and validate RealizationSpecs for one canonical cell."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from modules.stage_4_realization.engine import realize, validate_spec
from modules.stage_4_realization.run import build_cases
from shared.utils.config import resolve_experiment
from shared.utils.experiment import ensure_run_metadata
from shared.utils.io import read_json, read_jsonl, repo_path, write_json
from shared.utils.manifests import describe
from shared.utils.research import prepare_unit_directory, resolve_run, safe_component


DEFAULT_CELL_ID = "CELL_0000000000000001"
DEFAULT_INPUT = Path(__file__).resolve().parent / "fixtures" / "core.jsonl"
DEFAULT_EXPERIMENT = "run_one_demo"


def _fixture(path: Path, identifier: str) -> dict:
    return next(
        row for row in read_jsonl(path)
        if identifier in {row.get("fixture_label"), row["spec"]["canonical_cell_id"]}
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cell_id", nargs="?", help=f"default: {DEFAULT_CELL_ID} from the core fixture")
    parser.add_argument("--experiment", default=DEFAULT_EXPERIMENT)
    parser.add_argument("--input", type=Path, help="one realization fixture JSONL")
    parser.add_argument("--upstream-run")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    using_default = args.cell_id is None
    cell_id = args.cell_id or DEFAULT_CELL_ID
    safe_component(cell_id)
    resolution = resolve_experiment(args.experiment)
    config = resolution.resolved
    run_dir, _ = ensure_run_metadata(resolution)
    fixture_path = args.input.resolve() if args.input else DEFAULT_INPUT if using_default else None
    if fixture_path is not None:
        fixture = _fixture(fixture_path, cell_id)
        row = {"canonical_cell_id": fixture["spec"]["canonical_cell_id"], "cell": fixture["cell"]}
        relevant_edges = [
            {
                "egp_id": fixture["spec"]["source_descriptor_id"],
                "source_note": fixture.get("source_note"),
            }
        ]
        cases = [{"split": "fixture", "spec": fixture["spec"]}]
        upstream = None
    else:
        if args.upstream_run:
            upstream = resolve_run(args.upstream_run)
        elif (run_dir / "canonical/canonical_cells.jsonl").is_file():
            upstream = run_dir
        elif resolution.parent_resolved:
            upstream = resolve_run(resolution.parent_resolved["experiment_id"])
        else:
            raise FileNotFoundError("realization run-one requires canonical output; use --upstream-run or --input")
        cells = read_jsonl(upstream / "canonical/canonical_cells.jsonl")
        edges = read_jsonl(upstream / "canonical/source_cell_edges.jsonl")
        row = next(value for value in cells if value["canonical_cell_id"] == cell_id)
        relevant_edges = [value for value in edges if value["canonical_cell_id"] == cell_id]
        realization_config_path = repo_path(config["realization"]["config"])
        held_out = set(read_json(realization_config_path)["held_out_cell_ids"])
        cases = [
            value for value in build_cases(cells, edges, held_out)
            if value["spec"]["canonical_cell_id"] == cell_id
        ]
    realization_config_path = repo_path(config["realization"]["config"])
    frames = {
        value["predicate_frame_id"]: value
        for value in read_jsonl(repo_path(config["realization"]["lexicon"]))
    }
    schema_path = repo_path(config["realization"]["schema"])
    schema_validator = Draft202012Validator(read_json(schema_path))
    outputs = []
    validations = []
    for case in cases:
        spec = case["spec"]
        source_edge = next(value for value in relevant_edges if value["egp_id"] == spec["source_descriptor_id"])
        errors = [error.message for error in schema_validator.iter_errors(spec)]
        errors.extend(validate_spec(spec, row["cell"], frames[spec["predicate_frame_id"]], source_edge.get("source_note")))
        validations.append({"realization_id": spec["realization_id"], "valid": not errors, "errors": errors})
        if not errors:
            outputs.append(
                {
                    "split": case["split"],
                    "spec": spec,
                    "cell": row["cell"],
                    "source_note": source_edge.get("source_note"),
                    "derivation": realize(spec, row["cell"], frames[spec["predicate_frame_id"]]),
                }
            )
    unit_dir = prepare_unit_directory(run_dir / "realization/units" / cell_id, force=args.force)
    before = {"canonical_cell": row, "source_cell_edges": relevant_edges}
    if fixture_path is not None:
        before["fixture"] = describe(fixture_path)
        before["realization_spec"] = cases[0]["spec"]
    write_json(unit_dir / "input.json", before)
    write_json(
        unit_dir / "configuration.json",
        {
            "config": describe(realization_config_path),
            "rules": describe(repo_path(config["realization"]["rules"])),
            "schema": describe(schema_path),
            "lexicon": describe(repo_path(config["realization"]["lexicon"])),
            "upstream_run": str(upstream) if upstream else None,
        },
    )
    write_json(unit_dir / "output.json", outputs)
    write_json(unit_dir / "validation.json", {"valid": all(row["valid"] for row in validations), "cases": validations})
    after = {"realizations": outputs, "validation": validations}
    print(
        json.dumps(
            {"before": before, "after": after, "unit_directory": str(unit_dir)},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if all(row["valid"] for row in validations) else 1


if __name__ == "__main__":
    raise SystemExit(main())
