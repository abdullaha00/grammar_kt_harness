#!/usr/bin/env python3
"""Run one scientific operation from a bundled fixture or explicit JSON input."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# Prevent this directory's inspect.py from shadowing Python's standard inspect module.
sys.path.remove(str(Path(__file__).resolve().parent))

from grammar_kt import canonical, items, kc, kc_selection, normalisation, realisation, simulation, source
from grammar_kt.io import ROOT, read_json, read_jsonl, read_yaml, repo_path, write_json
from grammar_kt.records import grammar_cell, kc_opportunity


def main() -> int:
    parser = argparse.ArgumentParser(description="Show one scientific component's input and output.")
    parser.add_argument(
        "stage",
        choices=("source", "normalisation", "canonical", "realisation", "kc_selection", "kc", "items", "simulation"),
    )
    inputs = parser.add_mutually_exclusive_group()
    inputs.add_argument("--fixture", nargs="?", const="", help="fixture label; omit the label for the first fixture")
    inputs.add_argument("--input", type=Path, help="explicit one-record JSON file")
    inputs.add_argument("--egp-id", help="descriptor ID from the declared external source")
    parser.add_argument("--policy", help="KC policy path or short name")
    parser.add_argument("--learner", default="L0001", help="simulation fixture learner ID")
    parser.add_argument("--phase1-only", action="store_true")
    parser.add_argument("--output", type=Path, help="directory for model evidence/debug output")
    args = parser.parse_args()

    settings = read_yaml(ROOT / "experiments" / "base.yaml")

    if args.stage == "simulation":
        if args.input or args.egp_id or args.fixture not in {None, ""}:
            parser.error("simulation uses its declared fixture files; choose a learner with --learner")
        fixture_dir = ROOT / "modules" / "simulation" / "fixtures"
        fixture_items = read_jsonl(fixture_dir / "accepted_items.jsonl")
        kc_ids, q_by_item = simulation.read_q_matrix(fixture_dir / "q_matrix.csv")
        parameters = read_json(settings["simulation"]["parameters"])
        parameters["seed"] = int(settings["simulation"]["seed"])
        event_count = len(fixture_items) * int(parameters["item_passes_per_learner"])
        train_end, validation_end = simulation.split_boundaries(
            event_count,
            float(parameters["train_fraction"]),
            float(parameters["validation_fraction"]),
        )
        observed, _oracle, learners, _learner_oracle = simulation.simulate_records(
            parameters,
            {row["item_id"]: row for row in fixture_items},
            q_by_item,
            kc_ids,
            train_end,
            validation_end,
            target_learner=args.learner,
        )
        before = {
            "learner_id": args.learner,
            "items": str(fixture_dir / "accepted_items.jsonl"),
            "q_matrix": str(fixture_dir / "q_matrix.csv"),
            "parameters": settings["simulation"],
        }
        after = {
            "learner": learners[0],
            "observable_interactions": observed,
            "oracle_retained_separately": True,
            "fixture_items": len(fixture_items),
        }
    else:
        if args.input:
            before = read_json(args.input)
        elif args.egp_id:
            if args.stage not in {"source", "normalisation"}:
                parser.error("--egp-id is only valid for source or normalisation")
            source_settings = settings["source"]
            selected, _metadata, _units = source.select_records(
                source_settings["path"],
                expected_sha256=source_settings["sha256"],
                expected_record_count=int(source_settings["records"]),
                sample_ids_path=source_settings["sample_ids"],
                expected_descriptor_count=int(source_settings["selected_descriptors"]),
                sample_metadata_path=source_settings["sample_metadata"],
                annotation_units_path=source_settings["annotation_units"],
            )
            try:
                before = next(row for row in selected if row["egp_id"] == args.egp_id)
            except StopIteration as error:
                raise KeyError(f"selected EGP descriptor not found: {args.egp_id}") from error
        elif args.stage == "canonical":
            realisation_fixture = read_jsonl(ROOT / "modules" / "realisation" / "fixtures" / "core.jsonl")[0]
            before = {
                "egp_id": args.fixture or "FIX_CANONICAL",
                "result": "complete",
                "cells": [realisation_fixture["cell"]],
                "note": None,
            }
        elif args.stage == "kc_selection":
            before = read_json(ROOT / "modules" / "kc_selection" / "fixtures" / "core.json")
            if args.fixture not in {None, "", before["fixture_label"]}:
                raise KeyError(
                    f"fixture {args.fixture!r} not found; available: {[before['fixture_label']]}"
                )
        else:
            fixture_dir = ROOT / "modules" / args.stage / "fixtures"
            if args.stage == "kc":
                fixture_rows = read_jsonl(fixture_dir / "core.jsonl") + [
                    read_json(fixture_dir / "perfect_progressive.json")
                ]
            else:
                fixture_rows = read_jsonl(fixture_dir / "core.jsonl")
            if args.fixture in {None, ""}:
                before = fixture_rows[0]
            else:
                try:
                    before = next(
                        row
                        for row in fixture_rows
                        if args.fixture
                        in {
                            row.get("fixture_label"),
                            row.get("egp_id"),
                            row.get("canonical_cell_id"),
                            row.get("opportunity_id"),
                            row.get("item_id"),
                        }
                    )
                except StopIteration as error:
                    available = [row.get("fixture_label") for row in fixture_rows]
                    raise KeyError(f"fixture {args.fixture!r} not found; available: {available}") from error

        if args.stage == "source":
            after = source.phase1_record(before)
        elif args.stage == "normalisation":
            method = settings["normalisation"]
            after = normalisation.normalise_one(
                before,
                phase1_template=repo_path(method["phase1_prompt"]).read_text(encoding="utf-8"),
                phase2_template=repo_path(method["phase2_prompt"]).read_text(encoding="utf-8"),
                backend_config=read_yaml(method["backend_config"]),
                max_attempts=int(method["max_attempts"]),
                output=args.output,
                phase1_only=args.phase1_only,
            )
        elif args.stage == "canonical":
            mapping = before.get("output", before)
            cells, edges = canonical.build([mapping])
            after = {"cells": cells, "edges": edges}
        elif args.stage == "realisation":
            if "derivation" in before:
                before = {
                    "spec": before["spec"],
                    "cell": before["cell"],
                    "source_note": before.get("source_note"),
                    "expected_surface": before["derivation"]["surface"],
                }
            frames = {
                row["predicate_frame_id"]: row
                for row in read_jsonl(realisation.LEXICON)
            }
            spec = before["spec"]
            cell = grammar_cell(before["cell"])
            frame = frames[spec["predicate_frame_id"]]
            errors = realisation.validate_spec(spec, cell, frame, before.get("source_note"))
            derivation = realisation.realise(spec, cell, frame) if not errors else None
            if (
                derivation
                and before.get("expected_surface")
                and derivation["surface"] != before["expected_surface"]
            ):
                errors.append(f"surface differs: {derivation['surface']!r}")
            after = {"input": before, "output": derivation, "valid": not errors, "errors": errors}
        elif args.stage == "kc":
            opportunity_fields = (
                "opportunity_id",
                "split",
                "canonical_cell_id",
                "cell",
                "realization_spec",
                "realization_operations",
                "source_descriptor_ids",
                "source_mapping_notes",
            )
            opportunity = kc_opportunity({field: before[field] for field in opportunity_fields})
            policy_label = args.policy or settings["kc"]["policy"]
            if args.policy:
                supplied = Path(policy_label)
                policy_path = (
                    ROOT / "modules" / "kc" / "policies" / supplied.with_suffix(".json")
                    if len(supplied.parts) == 1 and not supplied.suffix
                    else repo_path(supplied)
                )
            else:
                policy_path = repo_path(settings["kc"]["policy"])
            policy = kc.load_policy(policy_path)
            projections, cards = kc.materialize_inventory(policy, [opportunity])
            after = {
                "policy": policy_label,
                "output": projections[0],
                "kc_specs": cards,
                "explanation": kc.apply_policy(policy, opportunity),
            }
        elif args.stage == "kc_selection":
            selection_settings = settings["kc_selection"]
            after = kc_selection.evaluate_fixture(
                before,
                read_json(selection_settings["config"]),
            )
        elif args.stage == "items":
            after = items.evaluate_fixture(before)
        else:
            raise AssertionError(args.stage)

    print("=== BEFORE ===")
    print(json.dumps(before, ensure_ascii=False, indent=2, sort_keys=True))
    print("=== AFTER ===")
    print(json.dumps(after, ensure_ascii=False, indent=2, sort_keys=True))
    if args.output and args.stage != "normalisation":
        write_json(args.output / "result.json", {"before": before, "after": after})
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
