"""Stage 4: independent per-item judgment and simple bank diagnostics."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from tqdm.auto import tqdm

from .io import ModelCall, call_model, render


_BLANK = re.compile(r"_{2,}|\[\s*blank\s*\]|<\s*blank\s*>", re.IGNORECASE)


def answer_span_consistency(candidate: dict[str, Any]) -> tuple[bool, str]:
    """Catch obvious repeated text or punctuation around a response slot.

    This intentionally does not try to parse English. It acts only when there
    is one visible blank and an accepted answer begins by repeating the final
    learner-facing phrase already printed immediately before that blank, or
    ends in punctuation already printed immediately after the blank.
    """

    matches = list(_BLANK.finditer(candidate["prompt"]))
    if len(matches) != 1:
        return True, "not_applicable: expected exactly one recognised response slot"
    suffix = candidate["prompt"][matches[0].end() :].lstrip()
    suffix_match = re.match(r"[\"'’”\)\]]*([.!?])", suffix)
    if suffix_match:
        printed_punctuation = suffix_match.group(1)
        for answer in candidate["accepted_answers"]:
            if answer.rstrip().endswith(printed_punctuation):
                return (
                    False,
                    "accepted answer repeats punctuation already printed "
                    f"immediately after the response slot: {printed_punctuation!r}",
                )

    prefix = candidate["prompt"][: matches[0].start()]
    prefix = re.split(r"[:.!?][\"'’”]?\s*", prefix)[-1]
    prefix = prefix.strip(" \t\n\r\"'“‘()[]")
    prefix_tokens = re.findall(r"[a-z]+", prefix.casefold())
    if not prefix_tokens:
        return True, "passed: no text immediately precedes the response slot"

    visible_prefix = " ".join(prefix_tokens)
    for answer in candidate["accepted_answers"]:
        answer_tokens = re.findall(r"[a-z]+", answer.casefold())
        if (
            len(answer_tokens) > len(prefix_tokens)
            and " ".join(answer_tokens[: len(prefix_tokens)]) == visible_prefix
        ):
            return (
                False,
                "accepted answer repeats text already printed immediately before "
                f"the response slot: {prefix!r}",
            )
    return True, "passed: accepted answers do not repeat the visible slot prefix"


def validate_items(
    candidates: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    prompt: str,
    validation_criteria: dict[str, Any],
    *,
    model: str,
    reasoning_effort: str,
    model_call: ModelCall = call_model,
    evidence_dir: Path | None = None,
    show_progress: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Judge candidates independently; accept only items passing every required criterion."""

    if validation_criteria.get("acceptance_rule") != "all_required_criteria_pass":
        raise ValueError(
            "active validation supports acceptance_rule=all_required_criteria_pass"
        )
    criteria = validation_criteria["criteria"]
    cells_by_id = {cell["cell_id"]: cell for cell in cells}
    accepted = []
    judgments = []
    candidate_rows = tqdm(
        candidates,
        desc="Validating items",
        disable=not show_progress,
        unit="item",
    )
    for candidate in candidate_rows:
        if candidate["cell_id"] not in cells_by_id:
            raise ValueError(f"item refers to unknown GrammarCell: {candidate['item_id']}")
        span_passed, span_note = answer_span_consistency(candidate)
        structural_checks = {
            "answer_span_consistency": {
                "passed": span_passed,
                "note": span_note,
            }
        }
        if not span_passed:
            judgments.append(
                {
                    "item_id": candidate["item_id"],
                    "deterministic_checks": structural_checks,
                    "judgments": {},
                    "accepted": False,
                    "rejection_stage": "deterministic_precheck",
                }
            )
            continue
        visible_item = {
            name: candidate[name]
            for name in (
                "item_id",
                "format",
                "prompt",
                "target_answer",
                "accepted_answers",
            )
        }
        model_input = {
            "visible_item": visible_item,
            "target_cell": cells_by_id[candidate["cell_id"]]["features"],
            "criteria": criteria,
        }
        prompt_text = render(prompt, model_input)
        parsed = model_call(
            prompt_text,
            model=model,
            reasoning_effort=reasoning_effort,
            input_data=model_input,
            stage="validation",
            call_key=candidate["item_id"],
            evidence_dir=evidence_dir / "calls" / candidate["item_id"] if evidence_dir else None,
        )
        result = parsed["judgments"]
        if set(result) != set(criteria):
            raise ValueError("validator did not judge every declared criterion")
        passed = all(
            result[name]["passed"]
            for name, declaration in criteria.items()
            if declaration["required"]
        )
        judgments.append(
            {
                "item_id": candidate["item_id"],
                "deterministic_checks": structural_checks,
                "judgments": result,
                "accepted": passed,
                "rejection_stage": None if passed else "independent_model_judgment",
            }
        )
        if passed:
            accepted.append(candidate.copy())
    return accepted, judgments


def _token_set_distance(first: dict[str, Any], second: dict[str, Any]) -> float:
    """Jaccard distance over lower-cased word types in prompt and answer."""

    def tokens(row: dict[str, Any]) -> set[str]:
        text = f"{row['prompt']} {row['target_answer']}".casefold()
        return set(re.findall(r"[a-z]+", text))

    left = tokens(first)
    right = tokens(second)
    union = left | right
    return 1.0 - len(left & right) / len(union) if union else 0.0


def select_item_bank(
    validator_accepted: list[dict[str, Any]],
    design: dict[str, Any],
) -> list[dict[str, Any]]:
    """Select at most two deterministic, diverse valid variants per cell."""

    selection = design["bank_selection"]
    if selection["first_item"] != "earliest_valid":
        raise ValueError("unsupported first-item selection rule")
    if selection["second_item"] != "maximum_token_set_distance_from_first":
        raise ValueError("unsupported second-item selection rule")
    if selection["distance_text"] != "prompt_and_target_answer":
        raise ValueError("unsupported item-distance text")
    if selection["tie_break"] != "earliest_candidate":
        raise ValueError("unsupported item-selection tie break")
    maximum = int(selection["maximum_items_per_cell"])
    if maximum not in (1, 2):
        raise ValueError("active item selection supports one or two items per cell")
    item_ids = [row["item_id"] for row in validator_accepted]
    if len(item_ids) != len(set(item_ids)):
        raise ValueError("validator-accepted candidate IDs must be unique")

    by_cell: dict[str, list[dict[str, Any]]] = {}
    for candidate in validator_accepted:
        metadata = candidate.get("generation_metadata", {})
        if "candidate_index" not in metadata:
            raise ValueError(
                f"candidate lacks deterministic generation index: {candidate['item_id']}"
            )
        by_cell.setdefault(candidate["cell_id"], []).append(candidate)

    selected = []
    for cell_id, rows in sorted(by_cell.items()):
        rows.sort(
            key=lambda row: (
                int(row["generation_metadata"]["candidate_index"]),
                row["item_id"],
            )
        )
        first = rows[0]
        first_selected = first.copy()
        first_selected["selection_metadata"] = {
            "rank": 1,
            "rule": "earliest_valid",
            "token_set_distance_from_first": 0.0,
        }
        selected.append(first_selected)

        if maximum == 2 and len(rows) > 1:
            second = min(
                rows[1:],
                key=lambda row: (
                    -_token_set_distance(first, row),
                    int(row["generation_metadata"]["candidate_index"]),
                    row["item_id"],
                ),
            )
            second_selected = second.copy()
            second_selected["selection_metadata"] = {
                "rank": 2,
                "rule": "maximum_token_set_distance_from_first",
                "token_set_distance_from_first": _token_set_distance(first, second),
            }
            selected.append(second_selected)
    return selected


def bank_summary(
    candidates: list[dict[str, Any]],
    validator_accepted: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    selected_items: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    selected_items = validator_accepted if selected_items is None else selected_items
    prompts = [row["prompt"].casefold().strip() for row in selected_items]
    tokens = [token for prompt in prompts for token in re.findall(r"[a-z]+", prompt)]
    criteria = list(
        next(
            (row["judgments"] for row in judgments if row["judgments"]),
            {},
        )
    )
    accepted_cells = Counter(row["cell_id"] for row in validator_accepted)
    selected_cells = Counter(row["cell_id"] for row in selected_items)
    return {
        "generated_candidates": len(candidates),
        "validator_accepted_candidates": len(validator_accepted),
        "validator_acceptance_rate": (
            len(validator_accepted) / len(candidates) if candidates else 0.0
        ),
        "selected_bank_items": len(selected_items),
        "selection_rate_among_accepted": (
            len(selected_items) / len(validator_accepted)
            if validator_accepted
            else 0.0
        ),
        "deterministic_precheck_rejections": sum(
            str(row.get("rejection_stage") or "").startswith(
                "deterministic_precheck"
            )
            for row in judgments
        ),
        "grammar_cells": len(cells),
        "validator_covered_cells": len(accepted_cells),
        "covered_cells": len(selected_cells),
        "selected_items_per_cell": dict(sorted(selected_cells.items())),
        "unique_prompt_rate": len(set(prompts)) / len(prompts) if prompts else 0.0,
        "duplicate_prompts": len(prompts) - len(set(prompts)),
        "lexical_types": len(set(tokens)),
        "lexical_tokens": len(tokens),
        "lexical_diversity": len(set(tokens)) / len(tokens) if tokens else 0.0,
        "format_distribution": dict(
            Counter(row["format"] for row in selected_items)
        ),
        "criterion_pass_rates": {
            name: (
                sum(
                    row["judgments"][name]["passed"]
                    for row in judgments
                    if name in row["judgments"]
                )
                / sum(name in row["judgments"] for row in judgments)
                if any(name in row["judgments"] for row in judgments)
                else 0.0
            )
            for name in criteria
        },
    }
