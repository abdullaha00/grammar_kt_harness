"""Stage 3: direct LLM generation from GrammarCells to candidate items."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tqdm.auto import tqdm

from .io import ModelCall, call_model, render


def _lexical_material(
    cell: dict[str, Any],
    lexicon: list[dict[str, Any]],
    index: int,
) -> dict[str, Any]:
    choices = lexicon
    if cell["features"]["voice"] == "passive":
        choices = [row for row in choices if row["passive_compatible"]]
    return choices[index % len(choices)]


def generate_items(
    cells: list[dict[str, Any]],
    prompt: str,
    rulebook: str,
    design: dict[str, Any],
    item_format: dict[str, Any],
    lexicon: list[dict[str, Any]],
    *,
    model: str,
    reasoning_effort: str,
    model_call: ModelCall = call_model,
    evidence_dir: Path | None = None,
    show_progress: bool = False,
) -> list[dict[str, Any]]:
    """Generate the declared number of item variants for every GrammarCell."""

    count = design["items_per_cell"]
    items = []

    work = [
        (cell_index, cell, variant)
        for cell_index, cell in enumerate(cells)
        for variant in range(1, count + 1)
    ]
    item_rows = tqdm(
        work,
        desc="Generating items",
        disable=not show_progress,
        unit="item",
    )
    for cell_index, cell, variant in item_rows:
        lexical = _lexical_material(cell, lexicon, cell_index + variant - 1)
        model_input = {
            "target_cell": {"cell_id": cell["cell_id"], "features": cell["features"]},
            "source_support": {"source_ids": cell["source_ids"]},
            "item_format": item_format,
            "design": design,
            "lexical_material": lexical,
        }
        prompt_text = render(prompt, {**model_input, "rulebook": rulebook})
        item_id = f"item_{len(items) + 1:03d}"
        parsed = model_call(
            prompt_text,
            model=model,
            reasoning_effort=reasoning_effort,
            input_data=model_input,
            stage="generation",
            call_key=f"{cell['cell_id']}_{variant}",
            evidence_dir=(
                evidence_dir / "calls" / item_id if evidence_dir else None
            ),
        )
        items.append(
            {
                "item_id": item_id,
                "cell_id": cell["cell_id"],
                "format": item_format["format_id"],
                "prompt": parsed["prompt"],
                "target_answer": parsed["target_answer"],
                "accepted_answers": parsed["accepted_answers"],
                "operation_tags": parsed["operation_tags"],
                "generation_metadata": {
                    "variant": variant,
                    "lexeme_id": lexical["lexeme_id"],
                    "cefr": lexical["cefr"],
                    "model": model,
                    "note": parsed["note"],
                },
            }
        )
    return items
