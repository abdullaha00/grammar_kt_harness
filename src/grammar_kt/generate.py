"""Stage 3: direct LLM generation from GrammarCells to candidate items."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .io import ModelCall, call_model, read_jsonl, read_text, read_yaml, render


FORBIDDEN_CONFIG_WORDS = {"kc", "policy", "fold", "simulation", "learner", "event", "kt"}
MODEL_FIELDS = {"prompt", "target_answer", "accepted_answers", "operation_tags", "note"}


def _lexical_material(cell: dict[str, Any], lexicon: list[dict[str, Any]], index: int) -> dict[str, Any]:
    choices = lexicon
    if cell["features"]["voice"] == "passive":
        choices = [row for row in choices if row["passive_compatible"]]
    return choices[index % len(choices)]


def generate_items(
    cells: list[dict[str, Any]],
    config: dict[str, Any],
    *,
    model_call: ModelCall = call_model,
    evidence_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """Generate the declared number of item variants for every GrammarCell."""

    lowered_keys = {key.lower() for key in config}
    if lowered_keys & FORBIDDEN_CONFIG_WORDS:
        raise ValueError("item generation config contains forbidden downstream inputs")
    template = read_text(config["prompt"])
    rulebook = read_text(config["rulebook"])
    design = read_yaml(config["design"])
    item_format = read_yaml(config["format"])
    lexicon = read_jsonl(config["lexicon"])
    count = int(design["items_per_cell"])
    items = []

    for cell_index, cell in enumerate(cells):
        for variant in range(1, count + 1):
            lexical = _lexical_material(cell, lexicon, cell_index + variant - 1)
            model_input = {
                "target_cell": {"cell_id": cell["cell_id"], "features": cell["features"]},
                "source_support": {"source_ids": cell["source_ids"]},
                "item_format": item_format,
                "design": design,
                "lexical_material": lexical,
            }
            prompt = render(template, {**model_input, "rulebook": rulebook})
            item_id = f"item_{len(items) + 1:03d}"
            parsed = model_call(
                prompt,
                model_input,
                config,
                "generation",
                f"{cell['cell_id']}_{variant}",
                evidence_dir / "calls" / item_id if evidence_dir else None,
            )
            if set(parsed) != MODEL_FIELDS:
                raise ValueError("generation result has unexpected fields")
            if not parsed["prompt"] or not parsed["target_answer"] or not parsed["accepted_answers"]:
                raise ValueError("generation result lacks a required item field")
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
                        "cefr": lexical.get("cefr"),
                        "model": config["model"],
                        "note": parsed["note"],
                    },
                }
            )
    return items
