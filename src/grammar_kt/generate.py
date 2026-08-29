"""Stage 3: direct LLM generation from GrammarCells to candidate items."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tqdm.auto import tqdm

from .io import ModelCall, call_model, render


def generate_item_candidate(
    cell: dict[str, Any],
    prompt: str,
    rulebook: str,
    design: dict[str, Any],
    item_format: dict[str, Any],
    *,
    candidate_index: int,
    model: str,
    reasoning_effort: str,
    model_call: ModelCall = call_model,
    evidence_dir: Path | None = None,
) -> dict[str, Any]:
    """Generate one declared candidate position for a fixed GrammarCell."""

    generation_design = design["generation"]
    count = int(generation_design["candidates_per_cell"])
    if count < 1:
        raise ValueError("candidates_per_cell must be positive")
    if not 1 <= candidate_index <= count:
        raise ValueError(
            f"candidate_index must be between 1 and {count}: {candidate_index}"
        )

    model_input = {
        "target_cell": {"cell_id": cell["cell_id"], "features": cell["features"]},
        "candidate_position": {"index": candidate_index, "count": count},
        "item_format": item_format,
        "design": {
            "design_id": design["design_id"],
            **generation_design,
        },
    }
    prompt_text = render(prompt, {**model_input, "rulebook": rulebook})
    item_id = f"candidate_{cell['cell_id']}_{candidate_index:02d}"
    parsed = model_call(
        prompt_text,
        model=model,
        reasoning_effort=reasoning_effort,
        input_data=model_input,
        stage="generation",
        call_key=f"{cell['cell_id']}_{candidate_index}",
        evidence_dir=evidence_dir / "calls" / item_id if evidence_dir else None,
    )
    expected_fields = {"prompt", "target_answer", "accepted_answers"}
    if set(parsed) != expected_fields:
        raise ValueError(
            "generator output must contain exactly prompt, target_answer, "
            f"and accepted_answers: {item_id}"
        )
    if (
        not isinstance(parsed["prompt"], str)
        or not parsed["prompt"].strip()
        or not isinstance(parsed["target_answer"], str)
        or not parsed["target_answer"].strip()
        or not isinstance(parsed["accepted_answers"], list)
        or not parsed["accepted_answers"]
        or any(
            not isinstance(answer, str) or not answer.strip()
            for answer in parsed["accepted_answers"]
        )
    ):
        raise ValueError(f"generator returned an invalid item payload: {item_id}")
    return {
        "item_id": item_id,
        "cell_id": cell["cell_id"],
        "format": item_format["format_id"],
        "prompt": parsed["prompt"],
        "target_answer": parsed["target_answer"],
        "accepted_answers": parsed["accepted_answers"],
        "generation_metadata": {
            "candidate_index": candidate_index,
            "candidate_count": count,
            "model": model,
        },
    }


def generate_items(
    cells: list[dict[str, Any]],
    prompt: str,
    rulebook: str,
    design: dict[str, Any],
    item_format: dict[str, Any],
    *,
    model: str,
    reasoning_effort: str,
    model_call: ModelCall = call_model,
    evidence_dir: Path | None = None,
    show_progress: bool = False,
) -> list[dict[str, Any]]:
    """Generate independent candidates from each fixed GrammarCell.

    Source-to-cell links remain in the canonical artifacts but are deliberately
    outside the generation input. Candidate generation also receives no KC,
    learner, fold, simulation, or outcome information.
    """

    count = int(design["generation"]["candidates_per_cell"])
    if count < 1:
        raise ValueError("candidates_per_cell must be positive")
    candidates = []

    work = [
        (cell, variant)
        for cell in sorted(cells, key=lambda row: row["cell_id"])
        for variant in range(1, count + 1)
    ]
    item_rows = tqdm(
        work,
        desc="Generating items",
        disable=not show_progress,
        unit="item",
    )
    for cell, variant in item_rows:
        candidates.append(
            generate_item_candidate(
                cell,
                prompt,
                rulebook,
                design,
                item_format,
                candidate_index=variant,
                model=model,
                reasoning_effort=reasoning_effort,
                model_call=model_call,
                evidence_dir=evidence_dir,
            )
        )
    return candidates
