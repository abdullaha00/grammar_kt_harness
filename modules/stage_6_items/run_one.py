"""Generate and deterministically validate the item candidates for one opportunity."""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from modules.stage_6_items.generate import generate_candidates
from modules.stage_6_items.run import evaluate_fixture
from modules.stage_6_items.validate import deterministic_results
from shared.utils.config import resolve_experiment
from shared.utils.experiment import ensure_run_metadata
from shared.utils.io import ROOT, read_json, read_jsonl, repo_path, sha256_file, write_json
from shared.utils.manifests import describe
from shared.utils.research import prepare_unit_directory, resolve_run, safe_component


DEFAULT_OPPORTUNITY_ID = "valid_deterministic_item"
DEFAULT_INPUT = Path(__file__).resolve().parent / "fixtures" / "core.jsonl"
DEFAULT_EXPERIMENT = "run_one_demo"


def _upstream(resolution: Any, run_dir: Path, explicit: str | None) -> Path:
    if explicit:
        return resolve_run(explicit)
    if (run_dir / "kc/cell_kc_projection.jsonl").is_file():
        return run_dir
    if resolution.parent_resolved:
        return resolve_run(resolution.parent_resolved["experiment_id"])
    raise FileNotFoundError("item run-one needs frozen realization/KC output; use --upstream-run")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "opportunity_id",
        nargs="?",
        help=f"default: {DEFAULT_OPPORTUNITY_ID} from the core fixture",
    )
    parser.add_argument("--experiment", default=DEFAULT_EXPERIMENT)
    parser.add_argument("--input", type=Path, help="one item fixture JSONL")
    parser.add_argument("--upstream-run")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()
    using_default = args.opportunity_id is None
    opportunity_id = args.opportunity_id or DEFAULT_OPPORTUNITY_ID
    safe_component(opportunity_id)
    resolution = resolve_experiment(args.experiment)
    config = resolution.resolved
    run_dir, manifest = ensure_run_metadata(resolution)
    fixture_path = args.input.resolve() if args.input else DEFAULT_INPUT if using_default else None
    if fixture_path is not None:
        fixture = next(
            row for row in read_jsonl(fixture_path)
            if opportunity_id in {row.get("fixture_label"), row["spec"].get("realization_id")}
        )
        frames = {
            row["predicate_frame_id"]: row
            for row in read_jsonl(repo_path(config["realization"]["lexicon"]))
        }
        result = evaluate_fixture(fixture, frames)
        unit_dir = prepare_unit_directory(run_dir / "items/units" / opportunity_id, force=args.force)
        before = {"fixture": fixture, "fixture_file": describe(fixture_path)}
        write_json(unit_dir / "input.json", before)
        write_json(
            unit_dir / "configuration.json",
            {
                "experiment_manifest": describe(manifest),
                "mode": "bounded_fixture_validation",
                "lexicon": describe(repo_path(config["realization"]["lexicon"])),
            },
        )
        write_json(unit_dir / "output.json", result)
        print(
            json.dumps(
                {"before": before, "after": result, "unit_directory": str(unit_dir)},
                ensure_ascii=False,
                indent=2,
            )
        )
        return 0 if result["expectation_met"] else 1
    upstream = _upstream(resolution, run_dir, args.upstream_run)
    item_config = {
        **config["items"],
        "_realization": {
            key: config["realization"][key] for key in ("version", "lexicon", "rules")
        },
    }
    projection_path = upstream / "kc/cell_kc_projection.jsonl"
    inventory_path = upstream / "kc/kc_inventory.jsonl"
    realization_path = upstream / "realization/realizations.jsonl"
    projections = read_jsonl(projection_path)
    selected = next(row for row in projections if row["opportunity_id"] == opportunity_id)
    cards = read_jsonl(inventory_path)
    realizations = read_jsonl(realization_path)
    cells = {row["canonical_cell_id"]: row["cell"] for row in projections}
    mappings: dict[str, dict[str, Any]] = {}
    for row in projections:
        for source_id in row["source_descriptor_ids"]:
            mappings[source_id] = {
                "egp_id": source_id,
                "note": row.get("source_mapping_notes", {}).get(source_id),
            }
    lexicon_path = repo_path(config["realization"]["lexicon"])
    frames = {row["predicate_frame_id"]: row for row in read_jsonl(lexicon_path)}
    template_path = repo_path(item_config["generation"]["template"])
    candidates = generate_candidates(
        projections=projections,
        cards=cards,
        realizations=realizations,
        cells=cells,
        mappings=mappings,
        frames=frames,
        template=template_path.read_text(encoding="utf-8"),
        template_hash=sha256_file(template_path),
        replicates=int(item_config["generation"]["replicates_per_kc"]),
        development_replicates=int(item_config["generation"]["development_replicates"]),
    )
    hard = deterministic_results(
        candidates,
        cells=cells,
        edge_sources={row["canonical_cell_id"]: set(row["source_descriptor_ids"]) for row in projections},
        mappings=mappings,
        frames=frames,
        projections={row["canonical_cell_id"]: row["kc_ids"] for row in projections},
        kc_ids={row["kc_id"] for row in cards},
        template=template_path.read_text(encoding="utf-8"),
        template_hash=sha256_file(template_path),
        item_schema=read_json(ROOT / "modules/stage_6_items/schemas/item_spec_v0_1.schema.json"),
    )
    hard_by_id = {row["item_id"]: row for row in hard}
    selected_items = [
        {"item": item, "deterministic_validation": hard_by_id[item["item_id"]]}
        for item in candidates
        if item["provenance"]["opportunity_id"] == opportunity_id
    ]
    unit_dir = prepare_unit_directory(run_dir / "items/units" / opportunity_id, force=args.force)
    before = {
        "opportunity": selected,
        "upstream_artifacts": [describe(projection_path), describe(inventory_path), describe(realization_path)],
    }
    write_json(
        unit_dir / "input.json",
        before,
    )
    write_json(
        unit_dir / "configuration.json",
        {
            "experiment_manifest": describe(manifest),
            "generation": item_config["generation"],
            "template": describe(template_path),
            "lexicon": describe(lexicon_path),
        },
    )
    write_json(unit_dir / "output.json", selected_items)
    print(
        json.dumps(
            {"before": before, "after": {"items": selected_items}, "unit_directory": str(unit_dir)},
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
