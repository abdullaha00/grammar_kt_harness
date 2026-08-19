"""Deterministic RealizationSpec realiser and validator."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .io import ROOT, read_json, read_jsonl, repo_path, stable_id, write_jsonl
from .records import grammar_cell


REALISATION_DIR = ROOT / "modules" / "realisation"
LEXICON = REALISATION_DIR / "lexicons" / "default.jsonl"


# Morphology

def finite_be(tense: str, subject: dict) -> str:
    if tense == "past":
        return "was" if subject["number"] == "singular" and subject["person"] in {1, 3} else "were"
    if subject["person"] == 1 and subject["number"] == "singular":
        return "am"
    return "is" if subject["person"] == 3 and subject["number"] == "singular" else "are"


def finite_aux(lemma: str, tense: str, subject: dict) -> str:
    if lemma == "be":
        return finite_be(tense, subject)
    if lemma == "have":
        if tense == "past":
            return "had"
        return "has" if subject["person"] == 3 and subject["number"] == "singular" else "have"
    if lemma == "do":
        if tense == "past":
            return "did"
        return "does" if subject["person"] == 3 and subject["number"] == "singular" else "do"
    raise ValueError(f"unsupported auxiliary: {lemma}")


def inflect(lemma: str, requested: str, tense: str, subject: dict, frame: dict) -> str:
    if lemma == "be":
        values = {"base": "be", "past_participle": "been", "present_participle": "being"}
    elif lemma == "have":
        values = {"base": "have", "past_participle": "had", "present_participle": "having"}
    elif lemma == "main":
        values = {
            "base": frame["base"],
            "past_participle": frame["past_participle"],
            "present_participle": frame["present_participle"],
        }
    else:
        raise ValueError(lemma)
    if requested == "finite":
        if lemma in {"be", "have"}:
            return finite_aux(lemma, tense, subject)
        if frame["frame_type"] == "copular":
            return finite_be(tense, subject)
        if tense == "past":
            return frame["past"]
        return frame["third_singular"] if subject["person"] == 3 and subject["number"] == "singular" else frame["base"]
    return values[requested]


# Auxiliary-chain construction

def lexical_nodes(cell: dict) -> list[tuple[str, str]]:
    nodes: list[tuple[str, str]] = []
    if cell["aspect"] in {"perfect", "perfect_progressive"}:
        nodes.append(("have", "perfect"))
    if cell["aspect"] in {"progressive", "perfect_progressive"}:
        nodes.append(("be", "progressive"))
    if cell["voice"] == "passive":
        nodes.append(("be", "passive"))
    nodes.append(("main", "main"))
    return nodes


def inflect_chain(cell: dict, spec: dict, frame: dict, imperative: bool = False) -> tuple[list[str], str]:
    nodes = lexical_nodes(cell)
    words: list[str] = []
    agreement_site = "none"
    previous_role: str | None = None
    if cell["modal"] != "none":
        words.append(cell["modal"])
        previous_role = "modal"
        agreement_site = "modal"
    for index, (lemma, role) in enumerate(nodes):
        if previous_role == "modal" or imperative and index == 0:
            requested = "base"
        elif previous_role == "perfect":
            requested = "past_participle"
        elif previous_role == "progressive":
            requested = "present_participle"
        elif previous_role == "passive":
            requested = "past_participle"
        elif index == 0:
            requested = "finite"
            agreement_site = lemma if lemma != "main" else "main_verb"
        else:
            raise ValueError("unlicensed chain relation")
        words.append(inflect(lemma, requested, cell["tense"], spec["subject"], frame))
        previous_role = role
    return words, agreement_site


# RealizationSpec validation

def validate_spec(spec: dict, cell: dict, frame: dict, source_note: str | None) -> list[str]:
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
    if set(subject) != {"text", "person", "number"} or subject.get("person") not in {1, 2, 3} or subject.get("number") not in {"singular", "plural"}:
        errors.append("invalid subject conditions")
    clause, wh = cell["clause"], spec.get("wh")
    if clause == "subject_wh_question" and (not isinstance(wh, dict) or wh.get("role") != "subject"):
        errors.append("subject-WH clause requires subject WH conditions")
    elif clause == "non_subject_wh_question" and (not isinstance(wh, dict) or wh.get("role") not in {"object", "adjunct"}):
        errors.append("non-subject-WH clause requires object/adjunct WH conditions")
    elif clause not in {"subject_wh_question", "non_subject_wh_question"} and wh is not None:
        errors.append("WH conditions supplied to non-WH clause")
    subtype = spec.get("imperative_subtype")
    if clause == "imperative" and subtype not in {"ordinary", "emphatic_do", "lets", "lets_not", "let_pronoun"}:
        errors.append("imperative subtype missing")
    if clause != "imperative" and subtype is not None:
        errors.append("imperative subtype supplied to non-imperative")
    if (subtype == "let_pronoun") != (spec.get("let_pronoun") is not None):
        errors.append("let_pronoun conditional value invalid")
    if cell["voice"] == "passive" and not frame["passive_compatible"]:
        errors.append("predicate frame is not passive-compatible")
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


# Clause realization

def realise(spec: dict, cell: dict, frame: dict) -> dict:
    # Morphology and auxiliary/verb chain
    imperative = cell["clause"] == "imperative"
    chain, agreement_site = inflect_chain(cell, spec, frame, imperative=imperative)

    # Passive, aspect, and modal operations
    operations: list[str] = []
    object_text = frame["object"]
    complement = frame["complement"]
    if cell["voice"] == "passive":
        operations.append("be_passive")
        object_text = None
    if cell["aspect"] != "none":
        operations.append(cell["aspect"])
    if cell["modal"] != "none":
        operations.append("central_modal")

    # Imperative subtype and surface form
    if imperative:
        subtype = spec["imperative_subtype"]
        base_chain, _ = inflect_chain(cell, spec, frame, imperative=True)
        if subtype == "ordinary":
            tokens = (["do", "not"] if cell["polarity"] == "negative" else []) + base_chain
            if cell["polarity"] == "negative": operations.append("do_support_negation")
        elif subtype == "emphatic_do":
            tokens = ["do"] + base_chain
            operations.append("emphatic_do")
        elif subtype == "lets":
            tokens = ["let's"] + base_chain
            operations.append("lets")
        elif subtype == "lets_not":
            tokens = ["let's", "not"] + base_chain
            operations.append("lets_not")
        else:
            tokens = ["let", spec["let_pronoun"]] + base_chain
            operations.append("let_pronoun")
        if object_text:
            tokens.extend(object_text.split())
        if complement:
            tokens.extend(complement.split())
        surface = " ".join(tokens).capitalize() + "."
        return {"surface": surface, "auxiliary_chain": tokens[:-1] if len(tokens) > 1 else [], "agreement_site": "none", "operations": sorted(set(operations)), "tokens": tokens}

    # Do-support and negation
    inherent_operator = bool(chain[:-1]) or cell["modal"] != "none" or frame["frame_type"] == "copular"
    requires_operator = cell["polarity"] == "negative" or cell["clause"] in {"polar_question", "non_subject_wh_question"}
    if requires_operator and not inherent_operator:
        chain = [finite_aux("do", cell["tense"], spec["subject"]), frame["base"]]
        agreement_site = "do"
        operations.append("do_support")
    if cell["polarity"] == "negative":
        chain.insert(1, "not")
        operations.append("negation")

    # Arguments, inversion, and WH structure
    arguments: list[str] = []
    if object_text and not (spec["wh"] and spec["wh"]["role"] == "object"):
        arguments.extend(object_text.split())
    if complement:
        arguments.extend(complement.split())
    subject_tokens = spec["subject"]["text"].split()
    interior_subject_tokens = subject_tokens[:]
    if interior_subject_tokens and interior_subject_tokens[0] in {"The", "A", "An"}:
        interior_subject_tokens[0] = interior_subject_tokens[0].lower()
    clause = cell["clause"]
    if clause == "declarative":
        tokens = subject_tokens + chain + arguments
    elif clause == "polar_question":
        tokens = [chain[0]] + interior_subject_tokens + chain[1:] + arguments
        operations.append("operator_inversion")
    elif clause == "subject_wh_question":
        tokens = spec["wh"]["phrase"].split() + chain + arguments
        operations.append("subject_wh")
    elif clause == "non_subject_wh_question":
        tokens = spec["wh"]["phrase"].split() + [chain[0]] + interior_subject_tokens + chain[1:] + arguments
        operations.extend(["non_subject_wh", "operator_inversion"])
    else:
        raise ValueError(f"unsupported clause: {clause}")

    # Surface sentence
    punctuation = "?" if clause.endswith("question") else "."
    surface = " ".join(tokens)
    surface = surface[0].upper() + surface[1:] + punctuation
    aux_count = len(chain) - 1
    auxiliary_chain = chain[:aux_count]
    return {"surface": surface, "auxiliary_chain": auxiliary_chain, "agreement_site": agreement_site, "operations": sorted(set(operations)), "tokens": tokens}


# RealizationSpec construction

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


def build_cases(cells: list[dict[str, Any]], edges: list[dict[str, Any]], held_out: set[str]) -> list[dict[str, Any]]:
    """Choose the deterministic lexical conditions used to realise each cell."""

    by_cell: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        by_cell.setdefault(edge["canonical_cell_id"], []).append(edge)

    # Give every canonical cell one realization from its first supporting descriptor.
    selected: list[tuple[dict[str, Any], dict[str, Any]]] = []
    for cell_row in sorted(cells, key=lambda row: row["canonical_cell_id"]):
        edge = sorted(by_cell[cell_row["canonical_cell_id"]], key=lambda row: row["egp_id"])[0]
        selected.append((cell_row, edge))

    # Preserve additional source-noted imperative subtypes as separate realizations.
    existing = {
        (cell_row["canonical_cell_id"], edge["egp_id"])
        for cell_row, edge in selected
    }
    for cell_row in cells:
        if cell_row["cell"]["clause"] != "imperative":
            continue
        for edge in sorted(by_cell[cell_row["canonical_cell_id"]], key=lambda row: row["egp_id"]):
            key = (cell_row["canonical_cell_id"], edge["egp_id"])
            if edge.get("source_note") and key not in existing:
                selected.append((cell_row, edge))

    # Construct each complete RealizationSpec in the same chronological pass.
    cases = []
    for serial, (cell_row, edge) in enumerate(selected, 1):
        cell = cell_row["cell"]
        frame = (
            "FRAME_LIKE" if cell["modal"] == "would" else
            "FRAME_REPAIR" if cell["voice"] == "passive" else
            "FRAME_WORK" if cell["aspect"] in {"progressive", "perfect_progressive"} else
            "FRAME_WRITE" if serial % 2 else "FRAME_INSPECT"
        )
        subject = {"text": "The machine", "person": 3, "number": "singular"} if cell["voice"] == "passive" else (
            {"text": "The technician", "person": 3, "number": "singular"} if serial % 2 else
            {"text": "The technicians", "person": 3, "number": "plural"}
        )
        subtype = imperative_subtype(edge.get("source_note")) if cell["clause"] == "imperative" else None
        basis = f"{cell_row['canonical_cell_id']}|{edge['egp_id']}|{frame}|{subtype}|{serial}"
        cases.append(
            {
                "split": "held_out" if cell_row["canonical_cell_id"] in held_out else "development",
                "spec": {
                    "realization_id": stable_id("REAL", basis),
                    "canonical_cell_id": cell_row["canonical_cell_id"],
                    "source_descriptor_id": edge["egp_id"],
                    "predicate_frame_id": frame,
                    "subject": subject,
                    "wh": None,
                    "imperative_subtype": subtype,
                    "let_pronoun": "them" if subtype == "let_pronoun" else None,
                },
            }
        )
    return cases


# Full stage

def run(run_dir: Path, settings: dict[str, Any]) -> dict[str, Any]:
    output = run_dir / "realisation"
    output.mkdir(parents=True, exist_ok=False)
    cells = read_jsonl(run_dir / "canonical" / "canonical_cells.jsonl")
    edges = read_jsonl(run_dir / "canonical" / "source_cell_edges.jsonl")
    choices = read_json(repo_path(settings["split_config"]))
    held_out = set(choices["held_out_cell_ids"])
    frames = {row["predicate_frame_id"]: row for row in read_jsonl(LEXICON)}
    cell_by_id = {row["canonical_cell_id"]: grammar_cell(row["cell"]) for row in cells}
    by_cell: dict[str, list[dict[str, Any]]] = {}
    for edge in edges:
        by_cell.setdefault(edge["canonical_cell_id"], []).append(edge)
    realised = []
    for case in sorted(build_cases(cells, edges, held_out), key=lambda row: row["spec"]["realization_id"]):
        spec = case["spec"]
        cell, frame = cell_by_id[spec["canonical_cell_id"]], frames[spec["predicate_frame_id"]]
        edge = next(row for row in by_cell[spec["canonical_cell_id"]] if row["egp_id"] == spec["source_descriptor_id"])
        errors = validate_spec(spec, cell, frame, edge.get("source_note"))
        if errors:
            raise RuntimeError(f"invalid realisation {spec['realization_id']}: {'; '.join(errors)}")
        realised.append({"split": case["split"], "spec": spec, "cell": cell, "source_note": edge.get("source_note"), "derivation": realise(spec, cell, frame)})
    write_jsonl(output / "realisations.jsonl", realised)
    write_jsonl(output / "cell_splits.jsonl", [{"canonical_cell_id": cell_id, "split": "held_out" if cell_id in held_out else "development"} for cell_id in sorted(cell_by_id)])
    return {"realisations": len(realised), "canonical_cells": len(cell_by_id), "held_out_cells": len(held_out)}
