#!/usr/bin/env python3
"""Deterministic RealizationSpec v0 realizer and validator."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIMENSIONS = ("tense", "aspect", "voice", "polarity", "clause", "modal")


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


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


def form(lemma: str, requested: str, tense: str, subject: dict, frame: dict) -> str:
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


def lexical_nodes(cell: dict, frame: dict) -> list[tuple[str, str]]:
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
    nodes = lexical_nodes(cell, frame)
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
        words.append(form(lemma, requested, cell["tense"], spec["subject"], frame))
        previous_role = role
    return words, agreement_site


def validate_spec(spec: dict, cell: dict, frame: dict, source_note: str | None) -> list[str]:
    errors: list[str] = []
    expected = {
        "realization_id", "canonical_cell_id", "source_descriptor_id", "predicate_frame_id",
        "subject", "wh", "imperative_subtype", "let_pronoun",
    }
    if set(spec) != expected:
        errors.append("RealizationSpec fields differ from v0 schema")
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


def realize(spec: dict, cell: dict, frame: dict) -> dict:
    imperative = cell["clause"] == "imperative"
    chain, agreement_site = inflect_chain(cell, spec, frame, imperative=imperative)
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

    inherent_operator = bool(chain[:-1]) or cell["modal"] != "none" or frame["frame_type"] == "copular"
    requires_operator = cell["polarity"] == "negative" or cell["clause"] in {"polar_question", "non_subject_wh_question"}
    if requires_operator and not inherent_operator:
        chain = [finite_aux("do", cell["tense"], spec["subject"]), frame["base"]]
        agreement_site = "do"
        inherent_operator = True
        operations.append("do_support")
    if cell["polarity"] == "negative":
        chain.insert(1, "not")
        operations.append("negation")

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
    punctuation = "?" if clause.endswith("question") else "."
    surface = " ".join(tokens)
    surface = surface[0].upper() + surface[1:] + punctuation
    aux_count = len(chain) - 1
    auxiliary_chain = chain[:aux_count]
    return {"surface": surface, "auxiliary_chain": auxiliary_chain, "agreement_site": agreement_site, "operations": sorted(set(operations)), "tokens": tokens}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--split", choices=("development", "held_out"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cells = {row["canonical_cell_id"]: row["cell"] for row in load_jsonl(ROOT / "normalization" / "canonical_cells" / "cells.jsonl")}
    edges = {(row["canonical_cell_id"], row["egp_id"]) for row in load_jsonl(ROOT / "normalization" / "canonical_cells" / "source_edges.jsonl")}
    mappings = {row["egp_id"]: row for row in load_jsonl(ROOT / "normalization" / "source_mappings.jsonl")}
    frames = {row["predicate_frame_id"]: row for row in load_jsonl(ROOT / "realization" / "specification" / "lexicon_v0.jsonl")}
    cases = [row for row in load_jsonl(ROOT / "realization" / "pilots" / "v0" / "input" / "cases.jsonl") if row["split"] == args.split]
    outputs: list[dict] = []
    errors: list[str] = []
    for row in cases:
        spec = row["spec"]
        cid, sid = spec["canonical_cell_id"], spec["source_descriptor_id"]
        if cid not in cells or (cid, sid) not in edges:
            errors.append(f"{spec['realization_id']}: missing source/cell edge")
            continue
        if spec["predicate_frame_id"] not in frames:
            errors.append(f"{spec['realization_id']}: unknown predicate frame")
            continue
        cell, frame = cells[cid], frames[spec["predicate_frame_id"]]
        current = validate_spec(spec, cell, frame, mappings[sid]["note"])
        if current:
            errors.extend(f"{spec['realization_id']}: {error}" for error in current)
            continue
        outputs.append({"spec": spec, "cell": cell, "derivation": realize(spec, cell, frame)})
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors))
        return 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("".join(json.dumps(row, sort_keys=True) + "\n" for row in outputs), encoding="utf-8")
    print(f"OK: realized and validated {len(outputs)} {args.split} cases")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
