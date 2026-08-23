"""One deterministic validity layer for admissible RealizationSpec conditions."""

from __future__ import annotations

import re
from typing import Any

from .io import stable_id


SUBJECTS = (
    {"text": "I", "person": 1, "number": "singular"},
    {"text": "we", "person": 1, "number": "plural"},
    {"text": "you", "person": 2, "number": "singular"},
    {"text": "you all", "person": 2, "number": "plural"},
    {"text": "the technician", "person": 3, "number": "singular"},
    {"text": "the technicians", "person": 3, "number": "plural"},
)


def imperative_subtype(note: str | None) -> str:
    text = note or ""
    if "LET'S NOT" in text:
        return "lets_not"
    if "LET'S" in text:
        return "lets"
    if "emphatic-DO" in text:
        return "emphatic_do"
    if "LET + third-person pronoun" in text:
        return "let_pronoun"
    return "ordinary"


def source_conditions(cell_row: dict[str, Any]) -> list[dict[str, Any]]:
    """Select source-preserving cases once, including imperative subtypes."""

    source_ids = list(cell_row.get("source_descriptor_ids") or ["SOURCE_FIXTURE"])
    notes = cell_row.get("source_mapping_notes") or {source_ids[0]: None}
    if cell_row["cell"]["clause"] != "imperative":
        source_id = sorted(source_ids)[0]
        return [{"source_descriptor_id": source_id, "source_note": notes.get(source_id), "imperative_subtype": None}]
    by_subtype: dict[str, dict[str, Any]] = {}
    for source_id in sorted(source_ids):
        note = notes.get(source_id)
        subtype = imperative_subtype(note)
        by_subtype.setdefault(
            subtype,
            {
                "source_descriptor_id": source_id,
                "source_note": note,
                "imperative_subtype": subtype,
            },
        )
    return [by_subtype[subtype] for subtype in sorted(by_subtype)]


def representative_source_conditions(
    cell_row: dict[str, Any], edges: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Reference-stage source cases: one primary plus source-noted imperatives."""

    ordered = sorted(edges, key=lambda row: row["egp_id"])
    if not ordered:
        raise RuntimeError(
            f"canonical cell has no source edge: {cell_row['canonical_cell_id']}"
        )
    selected = [ordered[0]]
    if cell_row["cell"]["clause"] == "imperative":
        selected.extend(
            row
            for row in ordered[1:]
            if row.get("source_note")
        )
    return [
        {
            "source_descriptor_id": row["egp_id"],
            "source_note": row.get("source_note"),
            "imperative_subtype": (
                imperative_subtype(row.get("source_note"))
                if cell_row["cell"]["clause"] == "imperative"
                else None
            ),
        }
        for row in selected
    ]


def wh_conditions(cell: dict[str, str], frame: dict[str, Any]) -> list[dict[str, str] | None]:
    if cell["clause"] == "subject_wh_question":
        return [{"phrase": "who", "role": "subject"}]
    if cell["clause"] == "non_subject_wh_question":
        conditions: list[dict[str, str] | None] = []
        if cell["voice"] == "active" and frame.get("object"):
            conditions.append({"phrase": "what", "role": "object"})
        conditions.append({"phrase": "when", "role": "adjunct"})
        return conditions
    return [None]


def subjects_for(
    cell: dict[str, str], frame: dict[str, Any], wh: dict[str, str] | None
) -> tuple[dict[str, Any], ...]:
    if wh and wh["role"] == "subject":
        return ({"text": wh["phrase"], "person": 3, "number": "singular"},)
    if cell["clause"] == "imperative":
        return ({"text": "you", "person": 2, "number": "singular"},)
    if cell["voice"] == "passive":
        if not frame.get("object"):
            return ()
        return ({"text": frame["object"], "person": 3, "number": "singular"},)
    return SUBJECTS


def validate_spec(
    spec: dict[str, Any], cell: dict[str, str], frame: dict[str, Any], source_note: str | None
) -> list[str]:
    errors: list[str] = []
    expected = {
        "realization_id", "canonical_cell_id", "source_descriptor_id", "predicate_frame_id",
        "subject", "wh", "imperative_subtype", "let_pronoun",
    }
    if set(spec) != expected:
        errors.append("RealizationSpec fields differ from the schema")
    if not re.fullmatch(r"REAL_[A-F0-9]{16}", str(spec.get("realization_id", ""))):
        errors.append("invalid realization_id")
    subject = spec.get("subject", {})
    if (
        set(subject) != {"text", "person", "number"}
        or not isinstance(subject.get("text"), str)
        or not subject.get("text")
        or subject.get("person") not in {1, 2, 3}
        or subject.get("number") not in {"singular", "plural"}
    ):
        errors.append("invalid subject conditions")
    clause, wh = cell["clause"], spec.get("wh")
    if clause == "subject_wh_question":
        if not isinstance(wh, dict) or set(wh) != {"phrase", "role"} or wh.get("role") != "subject":
            errors.append("subject-WH clause requires subject WH conditions")
        elif subject.get("text") != wh.get("phrase"):
            errors.append("subject-WH phrase must be the realized subject")
    elif clause == "non_subject_wh_question":
        if not isinstance(wh, dict) or set(wh) != {"phrase", "role"} or wh.get("role") not in {"object", "adjunct"}:
            errors.append("non-subject-WH clause requires object/adjunct WH conditions")
        elif wh["role"] == "object" and (cell["voice"] != "active" or not frame.get("object")):
            errors.append("object WH requires an active frame with an overt object")
    elif wh is not None:
        errors.append("WH conditions supplied to non-WH clause")
    if isinstance(wh, dict) and (not isinstance(wh.get("phrase"), str) or not wh.get("phrase")):
        errors.append("WH phrase must be non-empty")
    subtype = spec.get("imperative_subtype")
    if clause == "imperative" and subtype not in {"ordinary", "emphatic_do", "lets", "lets_not", "let_pronoun"}:
        errors.append("imperative subtype missing")
    if clause != "imperative" and subtype is not None:
        errors.append("imperative subtype supplied to non-imperative")
    if (subtype == "let_pronoun") != (spec.get("let_pronoun") is not None):
        errors.append("let_pronoun conditional value invalid")
    if cell["voice"] == "passive":
        if not frame.get("passive_compatible"):
            errors.append("predicate frame is not passive-compatible")
        elif clause != "subject_wh_question" and str(subject.get("text", "")).casefold() != str(frame.get("object", "")).casefold():
            errors.append("passive subject must realize the frame patient")
    note = source_note or ""
    noted = None
    if "LET'S NOT" in note:
        noted = "lets_not"
    elif "LET'S" in note:
        noted = "lets"
    elif "emphatic-DO" in note:
        noted = "emphatic_do"
    elif "LET + third-person pronoun" in note:
        noted = "let_pronoun"
    if noted and subtype != noted:
        errors.append(f"imperative subtype does not preserve source note: {noted}")
    return errors


def make_valid_spec(
    cell_row: dict[str, Any],
    frame: dict[str, Any],
    source: dict[str, Any],
    subject: dict[str, Any],
    wh: dict[str, str] | None,
    *,
    identity_parts: tuple[object, ...],
) -> dict[str, Any]:
    subtype = source["imperative_subtype"]
    spec = {
        "realization_id": stable_id("REAL", *identity_parts),
        "canonical_cell_id": cell_row["canonical_cell_id"],
        "source_descriptor_id": source["source_descriptor_id"],
        "predicate_frame_id": frame["predicate_frame_id"],
        "subject": dict(subject),
        "wh": dict(wh) if wh is not None else None,
        "imperative_subtype": subtype,
        "let_pronoun": "them" if subtype == "let_pronoun" else None,
    }
    errors = validate_spec(spec, cell_row["cell"], frame, source.get("source_note"))
    if errors:
        raise ValueError("; ".join(errors))
    return spec


def enumerate_valid_realisations(
    cell_row: dict[str, Any],
    frames: dict[str, dict[str, Any]],
    *,
    identity_namespace: str = "admissible_v0",
) -> list[dict[str, Any]]:
    """Enumerate the shared valid source/frame/subject/WH/subtype space."""

    cell_id, cell = cell_row["canonical_cell_id"], cell_row["cell"]
    rows = []
    for frame_id in sorted(frames):
        frame = frames[frame_id]
        for source in source_conditions(cell_row):
            for wh in wh_conditions(cell, frame):
                for subject in subjects_for(cell, frame, wh):
                    identity = (
                        identity_namespace,
                        cell_id,
                        frame_id,
                        source["source_descriptor_id"],
                        subject,
                        wh,
                        source["imperative_subtype"],
                    )
                    try:
                        spec = make_valid_spec(
                            cell_row, frame, source, subject, wh, identity_parts=identity
                        )
                    except ValueError:
                        continue
                    rows.append(
                        {
                            "spec": spec,
                            "source_note": source.get("source_note"),
                            "frame": frame,
                        }
                    )
    if not rows:
        raise RuntimeError(f"no admissible realizations for {cell_id}")
    return rows
