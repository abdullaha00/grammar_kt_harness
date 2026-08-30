#!/usr/bin/env python3
"""Build deterministic summaries for the non-human full-v1 item audit.

This script never writes inside data/grammar_kt_full_v1. Manual categorical
judgments live in manual_item_review.tsv; all other fields are joined directly
from the frozen dataset so that reviewed prompts and IDs remain auditable.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


STATUS_FIELDS = (
    "task_comprehensibility",
    "answer_determinacy",
    "response_space_fairness",
    "lexical_context_accessibility",
    "pedagogical_plausibility",
    "format_plausibility",
    "measurement_purity",
    "learner_overall",
    "platform_overall",
)
VALID_STATUSES = {"pass", "concern", "fail", "uncertain"}
VALID_INTERFACES = {"inline_cloze", "whole_response", "chunk_reorder_in_text"}
VALID_DISPOSITIONS = {
    "usable_as_stored",
    "minor_ui_or_context_change",
    "technically_valid_but_artificial",
    "answer_space_problem",
    "rewrite_or_withhold",
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sorted_counts(values: Iterable[str]) -> dict[str, int]:
    return dict(sorted(Counter(values).items()))


def nested_counts(records: list[dict[str, Any]], outer: str, inner: str) -> dict[str, Any]:
    grouped: dict[str, Counter[str]] = defaultdict(Counter)
    for record in records:
        grouped[str(record[outer])][str(record[inner])] += 1
    return {
        key: {subkey: value for subkey, value in sorted(counter.items())}
        for key, counter in sorted(grouped.items())
    }


def load_manual(path: Path) -> dict[str, dict[str, Any]]:
    with path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle, delimiter="\t"))
    if not rows:
        raise ValueError("manual audit ledger is empty")

    by_id: dict[str, dict[str, Any]] = {}
    for row_number, row in enumerate(rows, start=2):
        item_id = row["item_id"]
        if item_id in by_id:
            raise ValueError(f"duplicate item_id on TSV line {row_number}: {item_id}")
        for field in STATUS_FIELDS:
            if row[field] not in VALID_STATUSES:
                raise ValueError(
                    f"invalid {field}={row[field]!r} on TSV line {row_number}"
                )
        if row["interface_family"] not in VALID_INTERFACES:
            raise ValueError(f"invalid interface_family on TSV line {row_number}")
        if row["primary_disposition"] not in VALID_DISPOSITIONS:
            raise ValueError(f"invalid primary_disposition on TSV line {row_number}")
        if row["confidence"] not in {"high", "medium", "low"}:
            raise ValueError(f"invalid confidence on TSV line {row_number}")
        if row["role_disagreement"] not in {"true", "false"}:
            raise ValueError(f"invalid role_disagreement on TSV line {row_number}")
        row["role_disagreement"] = row["role_disagreement"] == "true"
        expected_disagreement = row["learner_overall"] != row["platform_overall"]
        if row["role_disagreement"] != expected_disagreement:
            raise ValueError(
                f"role_disagreement mismatch on TSV line {row_number}: "
                f"expected {expected_disagreement}"
            )
        row["issue_tags"] = [tag for tag in row["issue_tags"].split(";") if tag]
        by_id[item_id] = row
    return by_id


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[4],
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).resolve().parent,
    )
    args = parser.parse_args()
    root = args.repo_root.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    dataset = root / "data/grammar_kt_full_v1"
    audit_dir = Path(__file__).resolve().parent
    paths = {
        "items": dataset / "items/items.jsonl",
        "cells": dataset / "grammar/cells.jsonl",
        "regimes": dataset / "grammar/regime_assignments.jsonl",
        "kcs": dataset / "kcs.jsonl",
        "q_sparse": dataset / "oracle/q_matrix_sparse.jsonl",
        "manifest": dataset / "manifest.json",
        "validator_base": dataset
        / "provenance/items/validator_accepted_candidates.jsonl",
        "validator_unchanged_rescue": dataset
        / "provenance/items/campaigns/unchanged_rescue/validator_accepted_candidates.jsonl",
        "validator_determinacy_intervention": dataset
        / "provenance/items/campaigns/determinacy_intervention/validator_accepted_candidates.jsonl",
        "validator_cue_bounded_imperative": dataset
        / "provenance/items/campaigns/cue_bounded_imperative/validator_accepted_candidates.jsonl",
        "validator_packaging_corrections": dataset
        / "provenance/items/packaging_corrections/validator_accepted_candidates.jsonl",
        "manual_review": audit_dir / "manual_item_review.tsv",
        "rubric": audit_dir / "RUBRIC.md",
        "script": Path(__file__).resolve(),
    }

    items = read_jsonl(paths["items"])
    cells = {row["cell_id"]: row for row in read_jsonl(paths["cells"])}
    regimes = {
        row["cell_id"]: row["grammar_regime"] for row in read_jsonl(paths["regimes"])
    }
    q_rows = {row["item_id"]: row for row in read_jsonl(paths["q_sparse"])}
    kc_rows = {row["id"]: row for row in read_jsonl(paths["kcs"])}
    manual = load_manual(paths["manual_review"])
    validator_union_ids = {
        row["item_id"]
        for key in (
            "validator_base",
            "validator_unchanged_rescue",
            "validator_determinacy_intervention",
            "validator_cue_bounded_imperative",
            "validator_packaging_corrections",
        )
        for row in read_jsonl(paths[key])
    }
    with paths["manifest"].open(encoding="utf-8") as handle:
        dataset_manifest = json.load(handle)

    manifest_relative_paths = {
        "items": "items/items.jsonl",
        "cells": "grammar/cells.jsonl",
        "regimes": "grammar/regime_assignments.jsonl",
        "kcs": "kcs.jsonl",
        "q_sparse": "oracle/q_matrix_sparse.jsonl",
    }
    manifest_hash_match: dict[str, bool] = {}
    for key, relative_path in manifest_relative_paths.items():
        expected_hash = dataset_manifest["artifact_inventory"][relative_path]["sha256"]
        manifest_hash_match[key] = sha256(paths[key]) == expected_hash
    if not all(manifest_hash_match.values()):
        raise ValueError(f"frozen input hash mismatch: {manifest_hash_match}")

    item_ids = [row["item_id"] for row in items]
    if len(item_ids) != len(set(item_ids)):
        raise ValueError("frozen item bank contains duplicate item IDs")
    frozen_ids = set(item_ids)
    if set(manual) != frozen_ids:
        missing = sorted(frozen_ids - set(manual))
        extra = sorted(set(manual) - frozen_ids)
        raise ValueError(f"manual/frozen ID mismatch: missing={missing}, extra={extra}")
    if set(q_rows) != frozen_ids:
        raise ValueError("sparse Q rows do not match item IDs")
    if not frozen_ids <= validator_union_ids:
        raise ValueError(
            "current items missing from prior validator-accepted union: "
            f"{sorted(frozen_ids - validator_union_ids)}"
        )

    enriched: list[dict[str, Any]] = []
    for item in items:
        item_id = item["item_id"]
        cell_id = item["cell_id"]
        if cell_id not in cells or cell_id not in regimes:
            raise ValueError(f"missing cell/regime record for {item_id}")
        q_row = q_rows[item_id]
        unknown_kcs = set(q_row["generator_kc_ids"]) - set(kc_rows)
        if unknown_kcs:
            raise ValueError(f"unknown KCs for {item_id}: {sorted(unknown_kcs)}")
        review = manual[item_id]
        campaign = item["generation_metadata"].get("campaign", "base")
        record = {
            "audit_schema": "full_v1_platform_item_audit_v1",
            "item_id": item_id,
            "cell_id": cell_id,
            "grammar_regime": regimes[cell_id],
            "grammar_features": cells[cell_id]["features"],
            "source_ids": cells[cell_id]["source_ids"],
            "source_support_count": len(cells[cell_id]["source_ids"]),
            "generator_kc_ids": q_row["generator_kc_ids"],
            "q_cardinality": len(q_row["generator_kc_ids"]),
            "stored_format": item["format"],
            "generation_campaign": campaign,
            "selection_rank": item["selection_metadata"]["rank"],
            "token_set_distance_from_first": item["selection_metadata"][
                "token_set_distance_from_first"
            ],
            "prompt": item["prompt"],
            "target_answer": item["target_answer"],
            "accepted_answers": item["accepted_answers"],
            "prompt_word_count": len(item["prompt"].split()),
            "target_exactly_listed_as_accepted_span": item["target_answer"]
            in item["accepted_answers"],
            "prior_linguistic_validator_accepted": item_id in validator_union_ids,
            "audit": review,
        }
        enriched.append(record)

    item_counts_per_cell = Counter(row["cell_id"] for row in items)
    disposition_ids: dict[str, list[str]] = defaultdict(list)
    for record in enriched:
        disposition_ids[record["audit"]["primary_disposition"]].append(record["item_id"])

    dimension_counts = {
        field: sorted_counts(record["audit"][field] for record in enriched)
        for field in STATUS_FIELDS
    }
    by_kc: dict[str, Any] = {}
    for kc_id in sorted(kc_rows):
        supporting = [r for r in enriched if kc_id in r["generator_kc_ids"]]
        by_kc[kc_id] = {
            "item_count": len(supporting),
            "primary_disposition": sorted_counts(
                r["audit"]["primary_disposition"] for r in supporting
            ),
            "learner_overall": sorted_counts(r["audit"]["learner_overall"] for r in supporting),
            "platform_overall": sorted_counts(r["audit"]["platform_overall"] for r in supporting),
        }

    prompts = [record["prompt_word_count"] for record in enriched]
    sorted_prompts = sorted(prompts)
    second_item_distances = sorted(
        r["token_set_distance_from_first"]
        for r in enriched
        if r["selection_rank"] == 2
    )
    summary = {
        "audit_schema": "full_v1_platform_item_audit_summary_v1",
        "status": "PASS",
        "scope": {
            "dataset": "grammar_kt_full_v1",
            "items_reviewed": len(enriched),
            "coverage": "census",
            "unique_cells": len({r["cell_id"] for r in enriched}),
            "unique_generator_kcs": len(kc_rows),
            "review_type": "single-Codex role-separated non-human audit",
            "human_or_learner_evidence": False,
        },
        "bank_structure": {
            "stored_format": sorted_counts(r["stored_format"] for r in enriched),
            "interface_family": sorted_counts(
                r["audit"]["interface_family"] for r in enriched
            ),
            "generation_campaign": sorted_counts(r["generation_campaign"] for r in enriched),
            "grammar_regime": sorted_counts(r["grammar_regime"] for r in enriched),
            "q_cardinality": {
                str(key): value
                for key, value in sorted(Counter(r["q_cardinality"] for r in enriched).items())
            },
            "items_per_cell": {
                str(key): value
                for key, value in sorted(Counter(item_counts_per_cell.values()).items())
            },
            "source_support_count_per_item": {
                str(key): value
                for key, value in sorted(
                    Counter(r["source_support_count"] for r in enriched).items()
                )
            },
            "prompt_word_count": {
                "min": min(prompts),
                "median": sorted_prompts[len(sorted_prompts) // 2],
                "max": max(prompts),
                "over_40": sum(value > 40 for value in prompts),
                "over_60": sum(value > 60 for value in prompts),
            },
            "selected_second_item_token_set_distance": {
                "count": len(second_item_distances),
                "min": min(second_item_distances),
                "median": second_item_distances[len(second_item_distances) // 2],
                "max": max(second_item_distances),
                "below_0_5_item_ids": sorted(
                    r["item_id"]
                    for r in enriched
                    if r["selection_rank"] == 2
                    and r["token_set_distance_from_first"] < 0.5
                ),
            },
            "accepted_answer_count": {
                str(key): value
                for key, value in sorted(
                    Counter(len(r["accepted_answers"]) for r in enriched).items()
                )
            },
            "target_exactly_listed_as_accepted_span": sorted_counts(
                str(r["target_exactly_listed_as_accepted_span"]).lower()
                for r in enriched
            ),
            "prior_linguistic_validator_accepted": sorted_counts(
                str(r["prior_linguistic_validator_accepted"]).lower()
                for r in enriched
            ),
            "cefr_or_intended_proficiency_available_in_item_schema": False,
        },
        "categorical_results": {
            "primary_disposition": sorted_counts(
                r["audit"]["primary_disposition"] for r in enriched
            ),
            "primary_disposition_item_ids": {
                key: sorted(value) for key, value in sorted(disposition_ids.items())
            },
            "dimensions": dimension_counts,
            "confidence": sorted_counts(r["audit"]["confidence"] for r in enriched),
            "role_disagreement": sorted_counts(
                str(r["audit"]["role_disagreement"]).lower() for r in enriched
            ),
            "issue_tags": sorted_counts(
                tag for r in enriched for tag in r["audit"]["issue_tags"]
            ),
        },
        "cross_tabs": {
            "disposition_by_campaign": nested_counts(
                [
                    {
                        "campaign": r["generation_campaign"],
                        "disposition": r["audit"]["primary_disposition"],
                    }
                    for r in enriched
                ],
                "campaign",
                "disposition",
            ),
            "disposition_by_regime": nested_counts(
                [
                    {
                        "regime": r["grammar_regime"],
                        "disposition": r["audit"]["primary_disposition"],
                    }
                    for r in enriched
                ],
                "regime",
                "disposition",
            ),
            "disposition_by_interface_family": nested_counts(
                [
                    {
                        "interface": r["audit"]["interface_family"],
                        "disposition": r["audit"]["primary_disposition"],
                    }
                    for r in enriched
                ],
                "interface",
                "disposition",
            ),
            "disposition_by_q_cardinality": nested_counts(
                [
                    {
                        "q_cardinality": str(r["q_cardinality"]),
                        "disposition": r["audit"]["primary_disposition"],
                    }
                    for r in enriched
                ],
                "q_cardinality",
                "disposition",
            ),
            "disposition_by_source_support_count": nested_counts(
                [
                    {
                        "source_support_count": str(r["source_support_count"]),
                        "disposition": r["audit"]["primary_disposition"],
                    }
                    for r in enriched
                ],
                "source_support_count",
                "disposition",
            ),
        },
        "by_generator_kc": by_kc,
        "reproducibility": {
            "input_sha256": {
                key: sha256(path) for key, path in sorted(paths.items())
            },
            "frozen_inputs_match_dataset_manifest": manifest_hash_match,
            "output_order": "frozen items.jsonl order",
        },
        "limitations": [
            "One Codex pass supplied both role-separated judgments; role disagreement is not independent inter-rater disagreement.",
            "No human learner, teacher, platform-product, or CEFR-level evaluation was performed.",
            "The frozen item schema does not expose intended learner proficiency/CEFR, rendered UI, scoring normalization, feedback, or surface responses.",
            "All 113 stored format labels are controlled_production; descriptive interface families are audit codes, not experimentally crossed formats.",
            "Ordinary terminal-punctuation/whitespace normalization is assumed for item-level fairness; no executable scorer is frozen.",
        ],
    }

    jsonl_path = output_dir / "item_level_audit.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for record in enriched:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")
    summary_path = output_dir / "summary.json"
    with summary_path.open("w", encoding="utf-8") as handle:
        json.dump(summary, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")

    print(
        json.dumps(
            {
                "status": "PASS",
                "items_reviewed": len(enriched),
                "item_level_audit": str(jsonl_path),
                "summary": str(summary_path),
            },
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
