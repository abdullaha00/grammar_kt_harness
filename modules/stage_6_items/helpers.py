"""Current controlled-transformation prompt rendering and stable IDs."""

from __future__ import annotations

import hashlib
import json
from typing import Any


def render_prompt(template: str, cell: dict[str, str], spec: dict[str, Any], frame: dict[str, Any]) -> str:
    passive = cell["voice"] == "passive"
    imperative = cell["clause"] == "imperative"
    values = {
        **cell,
        "imperative_subtype": spec["imperative_subtype"] or "NONE",
        "subject": "IMPLICIT YOU" if imperative else spec["subject"]["text"],
        "lemma": frame["lemma"].upper(),
        "object": "NONE" if passive or frame["object"] is None else frame["object"],
        "complement": "NONE",
        "wh_phrase": spec["wh"]["phrase"] if spec["wh"] else "NONE",
        "let_pronoun": spec["let_pronoun"] or "NONE",
        "punctuation_name": "a question mark (?)" if cell["clause"].endswith("question") else "a period (.)",
    }
    return template.format(**values).strip()


def nuisance_signature(spec: dict[str, Any]) -> tuple[Any, ...]:
    return (
        spec["predicate_frame_id"],
        spec["subject"]["text"],
        spec["subject"]["person"],
        spec["subject"]["number"],
        json.dumps(spec["wh"], sort_keys=True),
        spec["imperative_subtype"],
        spec["let_pronoun"],
    )


def item_id(primary_kc_id: str, spec: dict[str, Any], replicate: int) -> str:
    basis = "|".join(
        (
            "CONTROLLED_TRANSFORMATION_v0_1",
            primary_kc_id,
            spec["canonical_cell_id"],
            spec["source_descriptor_id"],
            spec["predicate_frame_id"],
            json.dumps(spec["subject"], sort_keys=True),
            str(spec["imperative_subtype"]),
            str(replicate),
        )
    )
    return "ITEM_" + hashlib.sha256(basis.encode()).hexdigest()[:16].upper()

