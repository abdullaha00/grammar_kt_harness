"""Stage 4: independent per-item judgment and simple bank diagnostics."""

from __future__ import annotations

import re
from collections import Counter
from pathlib import Path
from typing import Any

from .io import ModelCall, call_model, read_text, read_yaml, render


def validate_items(
    candidates: list[dict[str, Any]],
    cells: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    model_call: ModelCall = call_model,
    evidence_dir: Path | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Judge candidates independently; accept only items passing every required criterion."""

    template = read_text(config["prompt"])
    policy = read_yaml(config["criteria"])
    criteria = policy["criteria"]
    cells_by_id = {cell["cell_id"]: cell for cell in cells}
    accepted = []
    judgments = []
    for candidate in candidates:
        if candidate["cell_id"] not in cells_by_id:
            raise ValueError(f"item refers to unknown GrammarCell: {candidate['item_id']}")
        visible_item = {name: candidate[name] for name in ("item_id", "format", "prompt", "target_answer", "accepted_answers")}
        model_input = {"visible_item": visible_item, "target_cell": cells_by_id[candidate["cell_id"]]["features"], "criteria": criteria}
        prompt = render(template, model_input)
        parsed = model_call(
            prompt,
            model_input,
            config,
            "validation",
            candidate["item_id"],
            evidence_dir / "calls" / candidate["item_id"] if evidence_dir else None,
        )
        result = parsed["judgments"]
        if set(result) != set(criteria):
            raise ValueError("validator did not judge every declared criterion")
        passed = all(result[name]["passed"] for name, declaration in criteria.items() if declaration["required"])
        judgments.append({"item_id": candidate["item_id"], "judgments": result, "accepted": passed})
        if passed:
            accepted.append(candidate.copy())
    return accepted, judgments


def bank_summary(
    candidates: list[dict[str, Any]],
    accepted: list[dict[str, Any]],
    judgments: list[dict[str, Any]],
    cells: list[dict[str, Any]],
) -> dict[str, Any]:
    prompts = [row["prompt"].casefold().strip() for row in accepted]
    tokens = [token for prompt in prompts for token in re.findall(r"[a-z]+", prompt)]
    criteria = list(judgments[0]["judgments"]) if judgments else []
    accepted_cells = Counter(row["cell_id"] for row in accepted)
    return {
        "candidate_items": len(candidates),
        "accepted_items": len(accepted),
        "acceptance_rate": len(accepted) / len(candidates) if candidates else 0.0,
        "grammar_cells": len(cells),
        "covered_cells": len(accepted_cells),
        "items_per_cell": dict(sorted(accepted_cells.items())),
        "unique_prompt_rate": len(set(prompts)) / len(prompts) if prompts else 0.0,
        "duplicate_prompts": len(prompts) - len(set(prompts)),
        "lexical_types": len(set(tokens)),
        "lexical_tokens": len(tokens),
        "lexical_diversity": len(set(tokens)) / len(tokens) if tokens else 0.0,
        "format_distribution": dict(Counter(row["format"] for row in accepted)),
        "cefr_distribution": dict(Counter(row["generation_metadata"].get("cefr") for row in accepted)),
        "criterion_pass_rates": {
            name: sum(row["judgments"][name]["passed"] for row in judgments) / len(judgments) if judgments else 0.0
            for name in criteria
        },
    }
