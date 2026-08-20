"""Deterministic Phase-A KC candidate construction and development diagnostics."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .io import stable_id
from .kc import evaluate_rule
from .realisation import imperative_subtype, lexical_nodes, realise, validate_spec
from .records import CENTRAL_MODALS, DIMENSIONS


QUESTION_VALUES = ("polar_question", "subject_wh_question", "non_subject_wh_question")
SUBJECTS = (
    {"text": "I", "person": 1, "number": "singular"},
    {"text": "we", "person": 1, "number": "plural"},
    {"text": "you", "person": 2, "number": "singular"},
    {"text": "you all", "person": 2, "number": "plural"},
    {"text": "the technician", "person": 3, "number": "singular"},
    {"text": "the technicians", "person": 3, "number": "plural"},
)
PASSIVE_SUBJECTS = (
    {"text": "the machine", "person": 3, "number": "singular"},
    {"text": "the machines", "person": 3, "number": "plural"},
)


# Candidate declarations

def _candidate(
    kc_id: str,
    name: str,
    definition: str,
    activation_rule: dict[str, Any],
    *,
    represents: list[str],
    dimensions: list[str],
    origin: str = "canonical",
    hypothesis_group: str | None = None,
    taxonomy_parent_kc_ids: list[str] | None = None,
    requires_selected_kc_ids: list[str] | None = None,
    interaction_order: int = 1,
    rule_complexity: int = 1,
    granularity_rank: int = 0,
    residual_fact_patterns: list[str] | None = None,
    required_conditions: list[str] | None = None,
    includes: list[str] | None = None,
    excludes: list[str] | None = None,
    realization_dependencies: list[str] | None = None,
    near_neighbours: list[str] | None = None,
    rationale: str = "Deterministically generated Phase-A structural hypothesis.",
) -> dict[str, Any]:
    candidate_id = stable_id("CAND", kc_id, activation_rule, represents, dimensions)
    return {
        "candidate_id": candidate_id,
        "kc_id": kc_id,
        "name": name,
        "definition": definition,
        "family": "interaction" if interaction_order > 1 else origin,
        "origin": origin,
        "hypothesis_group": hypothesis_group,
        "scope_claim": "cell",
        "activation_rule": activation_rule,
        "represents": sorted(represents),
        "canonical_dimensions": sorted(dimensions),
        "taxonomy_parent_kc_ids": sorted(taxonomy_parent_kc_ids or []),
        "requires_selected_kc_ids": sorted(requires_selected_kc_ids or []),
        "interaction_order": interaction_order,
        "rule_complexity": rule_complexity,
        "granularity_rank": granularity_rank,
        "residual_fact_patterns": sorted(residual_fact_patterns or []),
        "required_conditions": required_conditions or [],
        "includes": includes or [],
        "excludes": excludes or [],
        "realization_dependencies": realization_dependencies or [],
        "near_neighbours": near_neighbours or [],
        "rationale": rationale,
    }


def canonical_candidates() -> list[dict[str, Any]]:
    """Return the small declared canonical and operation-evidence candidate pool."""

    candidates = [
        _candidate(
            "KC_FINITE_PRESENT", "present finite-form selection",
            "Select present finite morphology and agreement conditions.",
            {"cell": {"tense": "present"}}, represents=["tense:present"], dimensions=["tense"],
            hypothesis_group="finite_tense", required_conditions=["tense=present"],
            includes=["present finite cells"], excludes=["past", "modal clauses", "imperatives"],
            realization_dependencies=["finite agreement site"], near_neighbours=["KC_FINITE_PAST"],
        ),
        _candidate(
            "KC_FINITE_PAST", "past finite-form selection",
            "Select past finite morphology on the operator or main verb.",
            {"cell": {"tense": "past"}}, represents=["tense:past"], dimensions=["tense"],
            hypothesis_group="finite_tense", required_conditions=["tense=past"],
            includes=["past finite cells"], excludes=["present", "modal clauses", "imperatives"],
            realization_dependencies=["finite agreement site"], near_neighbours=["KC_FINITE_PRESENT"],
        ),
        _candidate(
            "KC_ASPECT_PERFECT", "perfect component", "Construct perfect HAVE and its participial dependency.",
            {"cell": {"aspect": ["perfect", "perfect_progressive"]}},
            represents=["aspect:perfect"], dimensions=["aspect"], hypothesis_group="aspect_granularity",
            required_conditions=["aspect contains perfect"], includes=["perfect", "perfect_progressive"],
            excludes=["none", "progressive-only"], realization_dependencies=["perfect>past_participle"],
        ),
        _candidate(
            "KC_ASPECT_PROGRESSIVE", "progressive component", "Construct progressive BE and its participial dependency.",
            {"cell": {"aspect": ["progressive", "perfect_progressive"]}},
            represents=["aspect:progressive"], dimensions=["aspect"], hypothesis_group="aspect_granularity",
            required_conditions=["aspect contains progressive"], includes=["progressive", "perfect_progressive"],
            excludes=["none", "perfect-only"], realization_dependencies=["progressive>present_participle"],
        ),
        _candidate(
            "KC_ASPECT_PERFECT_PROGRESSIVE_ATOMIC", "atomic perfect-progressive",
            "Treat perfect-progressive as one atomic aspect hypothesis rather than only as two components.",
            {"cell": {"aspect": "perfect_progressive"}},
            represents=["aspect:perfect", "aspect:progressive"], dimensions=["aspect"],
            hypothesis_group="aspect_granularity", rule_complexity=2, granularity_rank=1,
            required_conditions=["aspect=perfect_progressive"], includes=["perfect_progressive"],
            excludes=["perfect-only", "progressive-only"], realization_dependencies=["multi-auxiliary chain"],
        ),
        _candidate(
            "KC_BE_PASSIVE", "canonical BE-passive", "Construct passive BE and a lexical past participle.",
            {"cell": {"voice": "passive"}}, represents=["voice:passive"], dimensions=["voice"],
            required_conditions=["voice=passive"], includes=["BE-passive"], excludes=["active"],
            realization_dependencies=["passive>past_participle"],
        ),
        _candidate(
            "KC_NEGATION", "negative polarity", "Express canonical negative polarity.",
            {"cell": {"polarity": "negative"}}, represents=["polarity:negative"], dimensions=["polarity"],
            required_conditions=["polarity=negative"], includes=["negative clauses"], excludes=["positive clauses"],
            realization_dependencies=["negation host or imperative negative construction"],
        ),
        _candidate(
            "KC_QUESTION_GENERIC", "generic question formation", "Treat all direct question types as one parent KC.",
            {"cell": {"clause": list(QUESTION_VALUES)}},
            represents=[f"clause:{value}" for value in QUESTION_VALUES], dimensions=["clause"],
            hypothesis_group="question_granularity", granularity_rank=0,
            required_conditions=["clause is a direct question"], includes=list(QUESTION_VALUES),
            excludes=["declarative", "imperative"], realization_dependencies=["question clause structure"],
        ),
        _candidate(
            "KC_POLAR_QUESTION", "polar-question formation", "Form a direct yes/no question.",
            {"cell": {"clause": "polar_question"}}, represents=["clause:polar_question"], dimensions=["clause"],
            hypothesis_group="question_granularity", taxonomy_parent_kc_ids=["KC_QUESTION_GENERIC"], granularity_rank=1,
            required_conditions=["clause=polar_question"], includes=["polar_question"],
            excludes=["WH questions"], realization_dependencies=["operator-subject order"],
        ),
        _candidate(
            "KC_SUBJECT_WH", "subject-WH formation", "Realize a WH phrase as grammatical subject.",
            {"cell": {"clause": "subject_wh_question"}}, represents=["clause:subject_wh_question"], dimensions=["clause"],
            hypothesis_group="question_granularity", taxonomy_parent_kc_ids=["KC_QUESTION_GENERIC"], granularity_rank=1,
            required_conditions=["clause=subject_wh_question"], includes=["subject WH"],
            excludes=["non-subject WH"], realization_dependencies=["WH subject realization"],
        ),
        _candidate(
            "KC_NON_SUBJECT_WH", "non-subject-WH formation", "Front an object or adjunct WH phrase.",
            {"cell": {"clause": "non_subject_wh_question"}}, represents=["clause:non_subject_wh_question"], dimensions=["clause"],
            hypothesis_group="question_granularity", taxonomy_parent_kc_ids=["KC_QUESTION_GENERIC"], granularity_rank=1,
            required_conditions=["clause=non_subject_wh_question"], includes=["object and adjunct WH"],
            excludes=["subject WH"], realization_dependencies=["WH fronting", "question order"],
        ),
        _candidate(
            "KC_IMPERATIVE", "imperative clause formation", "Realize a base-form imperative construction.",
            {"cell": {"clause": "imperative"}}, represents=["clause:imperative"], dimensions=["clause"],
            required_conditions=["clause=imperative"], includes=["source-licensed imperative subtypes"],
            excludes=["declaratives", "questions"], realization_dependencies=["imperative subtype"],
        ),
    ]

    modal_values = sorted(CENTRAL_MODALS)
    candidates.append(
        _candidate(
            "KC_MODAL_CENTRAL", "generic central modal", "Use any central modal followed by a base-form chain.",
            {"cell": {"modal": modal_values}}, represents=[f"modal:{value}" for value in modal_values], dimensions=["modal"],
            hypothesis_group="modal_granularity", granularity_rank=0,
            required_conditions=["modal is central"], includes=modal_values, excludes=["modal=none"],
            realization_dependencies=["modal>base_form"],
        )
    )
    for value in modal_values:
        candidates.append(
            _candidate(
                f"KC_MODAL_{value.upper()}", f"central modal {value.upper()}",
                f"Use central modal {value.upper()} followed by a base-form chain.",
                {"cell": {"modal": value}}, represents=[f"modal:{value}"], dimensions=["modal"],
                hypothesis_group="modal_granularity", taxonomy_parent_kc_ids=["KC_MODAL_CENTRAL"], granularity_rank=1,
                required_conditions=[f"modal={value}"], includes=[value], excludes=["other modal values"],
                realization_dependencies=["modal>base_form"],
            )
        )

    # Operation-derived alternatives are evaluated over nuisance-realisation grids.
    candidates.extend(
        [
            _candidate(
                "KC_OP_DO_SUPPORT", "realisation evidence: DO-support", "Insert finite DO when the realization lacks an inherent operator.",
                {"operation": "do_support"}, represents=[], dimensions=["clause", "polarity"], origin="operation",
                hypothesis_group="operator_realisation", realization_dependencies=["predicate frame", "operator availability"],
            ),
            _candidate(
                "KC_OP_OPERATOR_INVERSION", "realisation evidence: operator inversion", "Place the finite operator before the subject.",
                {"operation": "operator_inversion"},
                represents=["clause:polar_question", "clause:non_subject_wh_question"], dimensions=["clause"], origin="operation",
                hypothesis_group="question_granularity", granularity_rank=2,
                realization_dependencies=["finite operator", "subject"],
            ),
            _candidate(
                "KC_OP_NEGATION_PLACEMENT", "realisation evidence: operator negation", "Place NOT after a finite operator.",
                {"operation": "negation"}, represents=["polarity:negative"], dimensions=["polarity"], origin="operation",
                hypothesis_group="negation_realisation", granularity_rank=2,
                realization_dependencies=["finite operator"],
            ),
            _candidate(
                "KC_OP_BE_PASSIVE", "realisation evidence: BE-passive", "Observe the BE-passive auxiliary/participle operation.",
                {"operation": "be_passive"}, represents=["voice:passive"], dimensions=["voice"], origin="operation",
                hypothesis_group="passive_realisation", granularity_rank=2,
                realization_dependencies=["passive-compatible predicate"],
            ),
            _candidate(
                "KC_OP_CENTRAL_MODAL", "realisation evidence: central modal", "Observe a central-modal base-chain operation.",
                {"operation": "central_modal"}, represents=[f"modal:{value}" for value in modal_values], dimensions=["modal"],
                origin="operation", hypothesis_group="modal_granularity", granularity_rank=2,
                realization_dependencies=["modal>base_form"],
            ),
        ]
    )
    return candidates


def add_interaction_candidates(
    candidates: list[dict[str, Any]], config: dict[str, Any]
) -> list[dict[str, Any]]:
    by_kc = {row["kc_id"]: row for row in candidates}
    result = list(candidates)
    for spec in config.get("interaction_candidates", []):
        parent_ids = list(spec["parents"])
        if len(parent_ids) != 2 or any(parent not in by_kc for parent in parent_ids):
            raise ValueError(f"invalid interaction parents: {parent_ids}")
        parents = [by_kc[parent] for parent in parent_ids]
        result.append(
            _candidate(
                spec["kc_id"], spec["name"], spec["definition"],
                {"all": [parent["activation_rule"] for parent in parents]},
                represents=[], dimensions=sorted({dimension for parent in parents for dimension in parent["canonical_dimensions"]}),
                origin="interaction", hypothesis_group=spec.get("hypothesis_group", "interaction_structure"),
                requires_selected_kc_ids=parent_ids, interaction_order=2,
                rule_complexity=1 + sum(parent["rule_complexity"] for parent in parents), granularity_rank=3,
                residual_fact_patterns=spec.get("residual_fact_patterns", []),
                required_conditions=[f"parents={','.join(parent_ids)}"], includes=["supported parent conjunction"],
                excludes=["unsupported conjunctions"], realization_dependencies=spec.get("residual_fact_patterns", []),
                rationale="Generated conjunction; eligibility additionally requires supported residual realization structure.",
            )
        )
    by_kc = {row["kc_id"]: row for row in result}
    by_id = {row["kc_id"]: row["candidate_id"] for row in result}
    for row in result:
        row["taxonomy_parent_ids"] = [by_id[value] for value in row.pop("taxonomy_parent_kc_ids")]
        row["requires_selected_ids"] = [by_id[value] for value in row.pop("requires_selected_kc_ids")]
        if any(value not in by_kc for value in row.get("near_neighbours", [])):
            # Near-neighbour labels are descriptive and may refer to baseline-only KCs.
            row["near_neighbours"] = list(row["near_neighbours"])
    return result


# Canonical facts and contrasts

def salient_facts(cell: dict[str, str]) -> list[str]:
    facts: list[str] = []
    if cell["tense"] in {"present", "past"}:
        facts.append(f"tense:{cell['tense']}")
    if cell["aspect"] in {"perfect", "perfect_progressive"}:
        facts.append("aspect:perfect")
    if cell["aspect"] in {"progressive", "perfect_progressive"}:
        facts.append("aspect:progressive")
    if cell["voice"] == "passive":
        facts.append("voice:passive")
    if cell["polarity"] == "negative":
        facts.append("polarity:negative")
    if cell["clause"] != "declarative":
        facts.append(f"clause:{cell['clause']}")
    if cell["modal"] != "none":
        facts.append(f"modal:{cell['modal']}")
    return sorted(facts)


def minimal_contrasts(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    contrasts = []
    ordered = sorted(cells, key=lambda row: row["canonical_cell_id"])
    for index, left in enumerate(ordered):
        for right in ordered[index + 1 :]:
            changed = [dimension for dimension in DIMENSIONS if left["cell"][dimension] != right["cell"][dimension]]
            if len(changed) == 1:
                dimension = changed[0]
                contrasts.append(
                    {
                        "contrast_id": stable_id("CONTRAST", left["canonical_cell_id"], right["canonical_cell_id"], dimension),
                        "left_cell_id": left["canonical_cell_id"],
                        "right_cell_id": right["canonical_cell_id"],
                        "changed_dimension": dimension,
                        "left_value": left["cell"][dimension],
                        "right_value": right["cell"][dimension],
                    }
                )
    return contrasts


# Nuisance-realisation evidence

def normalized_realisation_facts(cell: dict[str, str], derivation: dict[str, Any]) -> list[str]:
    facts = set(derivation["operations"])
    site = derivation["agreement_site"]
    facts.add(f"agreement_site:{site}")
    roles = (["modal"] if cell["modal"] != "none" else []) + [role for _lemma, role in lexical_nodes(cell)]
    for left, right in zip(roles, roles[1:]):
        facts.add(f"chain_edge:{left}>{right}")
    if "negation" in derivation["operations"]:
        facts.add(f"negation_host:{site}")
    if "operator_inversion" in derivation["operations"]:
        facts.add(f"inverted_operator:{site}")
    if "do_support" in derivation["operations"] and "operator_inversion" in derivation["operations"]:
        facts.add("dependency:inverted_operator:do")
    if "do_support" in derivation["operations"] and "negation" in derivation["operations"]:
        facts.add("dependency:negation_host:do")
    if "operator_inversion" in derivation["operations"] and "negation" in derivation["operations"]:
        facts.add("dependency:inverted_negative_operator")
    return sorted(facts)


def nuisance_opportunities(
    cell_row: dict[str, Any], frames: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Enumerate a deterministic valid grid without consulting held-out cells."""

    cell_id, cell = cell_row["canonical_cell_id"], cell_row["cell"]
    source_ids = list(cell_row.get("source_descriptor_ids") or ["SOURCE_FIXTURE"])
    notes = cell_row.get("source_mapping_notes") or {source_ids[0]: None}
    source_cases = [(source_id, notes.get(source_id)) for source_id in source_ids]
    if cell["clause"] == "imperative":
        unique: dict[str, tuple[str, str | None]] = {}
        for source_id, note in source_cases:
            unique.setdefault(imperative_subtype(note), (source_id, note))
        source_cases = [unique[key] for key in sorted(unique)]
    else:
        source_cases = [source_cases[0]]

    if cell["clause"] == "subject_wh_question":
        wh_values = [{"phrase": "who", "role": "subject"}]
    elif cell["clause"] == "non_subject_wh_question":
        wh_values = [{"phrase": "what", "role": "object"}, {"phrase": "when", "role": "adjunct"}]
    else:
        wh_values = [None]

    opportunities = []
    for frame_id in sorted(frames):
        frame = frames[frame_id]
        for source_id, note in source_cases:
            subtype = imperative_subtype(note) if cell["clause"] == "imperative" else None
            for wh in wh_values:
                subjects = SUBJECTS
                if cell["voice"] == "passive":
                    subjects = PASSIVE_SUBJECTS
                elif cell["clause"] == "imperative":
                    subjects = ({"text": "you", "person": 2, "number": "singular"},)
                elif cell["clause"] == "subject_wh_question":
                    subjects = ({"text": "who", "person": 3, "number": "singular"},)
                for subject in subjects:
                    spec = {
                        "realization_id": stable_id("REAL", "kc-selection-grid", cell_id, frame_id, source_id, subject, wh, subtype),
                        "canonical_cell_id": cell_id,
                        "source_descriptor_id": source_id,
                        "predicate_frame_id": frame_id,
                        "subject": dict(subject),
                        "wh": wh,
                        "imperative_subtype": subtype,
                        "let_pronoun": "them" if subtype == "let_pronoun" else None,
                    }
                    errors = validate_spec(spec, cell, frame, note)
                    if errors:
                        continue
                    derivation = realise(spec, cell, frame)
                    operation_facts = normalized_realisation_facts(cell, derivation)
                    opportunities.append(
                        {
                            "canonical_cell_id": cell_id,
                            "cell": cell,
                            "realization_spec": spec,
                            "realization_operations": operation_facts,
                            "operation_facts": operation_facts,
                        }
                    )
    if not opportunities:
        raise RuntimeError(f"no valid nuisance realizations for development cell {cell_id}")
    return opportunities


def _uses_operation(expression: dict[str, Any]) -> bool:
    if "operation" in expression:
        return True
    return any(_uses_operation(part) for part in expression.get("all", []))


# Complete discovery pass

def discover_candidates(
    development_cells: list[dict[str, Any]],
    development_realisations: list[dict[str, Any]],
    frames: dict[str, dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Generate and diagnose candidates using development records only."""

    development_ids = {row["canonical_cell_id"] for row in development_cells}
    leaked = sorted(
        row["spec"]["canonical_cell_id"]
        for row in development_realisations
        if row["spec"]["canonical_cell_id"] not in development_ids
    )
    if leaked:
        raise ValueError(f"non-development realizations supplied to candidate discovery: {leaked}")

    candidates = add_interaction_candidates(canonical_candidates(), config)
    grids = {
        row["canonical_cell_id"]: nuisance_opportunities(row, frames)
        for row in sorted(development_cells, key=lambda value: value["canonical_cell_id"])
    }
    stable_operation_facts_by_cell = {
        cell_id: set.intersection(*(set(row["operation_facts"]) for row in opportunities))
        for cell_id, opportunities in grids.items()
    }
    cells_by_id = {row["canonical_cell_id"]: row for row in development_cells}
    observed_counts = Counter(row["spec"]["canonical_cell_id"] for row in development_realisations)

    activations: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []
    states_by_candidate: dict[str, dict[str, str]] = {}
    always_facts_by_candidate: dict[str, dict[str, set[str]]] = {}

    for candidate in candidates:
        states: dict[str, str] = {}
        stable_facts: dict[str, set[str]] = {}
        for cell_id in sorted(grids):
            opportunities = grids[cell_id]
            results = [evaluate_rule(candidate["activation_rule"], opportunity)[0] for opportunity in opportunities]
            active_count = sum(results)
            state = "always" if active_count == len(results) else "never" if active_count == 0 else "mixed"
            states[cell_id] = state
            active_fact_sets = [set(row["operation_facts"]) for row, active in zip(opportunities, results) if active]
            stable_facts[cell_id] = set.intersection(*active_fact_sets) if active_fact_sets else set()
            activations.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "kc_id": candidate["kc_id"],
                    "canonical_cell_id": cell_id,
                    "data_partition": "development",
                    "activation_state": state,
                    "activated": True if state == "always" else False if state == "never" else None,
                    "active_realizations": active_count,
                    "valid_realizations": len(results),
                }
            )
        states_by_candidate[candidate["candidate_id"]] = states
        always_facts_by_candidate[candidate["candidate_id"]] = stable_facts

    candidate_by_id = {row["candidate_id"]: row for row in candidates}
    minimum_cell_support = int(config.get("minimum_candidate_cell_support", 1))
    minimum_descriptor_support = int(config.get("minimum_candidate_descriptor_support", 1))
    minimum_interaction_support = int(config.get("minimum_interaction_cell_support", 2))

    for candidate in candidates:
        states = states_by_candidate[candidate["candidate_id"]]
        always_cells = [cell_id for cell_id, state in states.items() if state == "always"]
        any_cells = [cell_id for cell_id, state in states.items() if state in {"always", "mixed"}]
        mixed_cells = [cell_id for cell_id, state in states.items() if state == "mixed"]
        descriptor_ids = sorted(
            {
                source_id
                for cell_id in always_cells
                for source_id in cells_by_id[cell_id].get("source_descriptor_ids", [])
            }
        )
        uses_operation = _uses_operation(candidate["activation_rule"])
        scope = "realisation" if mixed_cells else "unverified" if uses_operation and not any_cells else "cell"
        residual_facts = []
        residual_evidence = []
        if candidate["interaction_order"] > 1:
            parent_ids = candidate["requires_selected_ids"]
            parent_only_cells = sorted(
                {
                    cell_id
                    for parent_id in parent_ids
                    for cell_id, parent_state in states_by_candidate[parent_id].items()
                    if parent_state == "always" and states[cell_id] == "never"
                }
            )
            for pattern in candidate["residual_fact_patterns"]:
                stable_in_intersection = bool(always_cells) and all(
                    pattern in always_facts_by_candidate[candidate["candidate_id"]][cell_id]
                    for cell_id in always_cells
                )
                absent_from_parent_only = bool(parent_only_cells) and all(
                    pattern not in stable_operation_facts_by_cell[cell_id]
                    for cell_id in parent_only_cells
                )
                beyond_parents = stable_in_intersection and absent_from_parent_only
                residual_evidence.append(
                    {
                        "fact": pattern,
                        "interaction_cell_ids": sorted(always_cells),
                        "parent_only_cell_ids": parent_only_cells,
                        "stable_in_intersection": stable_in_intersection,
                        "absent_from_parent_only_cells": absent_from_parent_only,
                        "beyond_parents": beyond_parents,
                    }
                )
                if beyond_parents:
                    residual_facts.append(pattern)

        reasons = []
        if len(always_cells) < minimum_cell_support:
            reasons.append("insufficient distinct development-cell support")
        if len(descriptor_ids) < minimum_descriptor_support:
            reasons.append("insufficient distinct development source-descriptor support")
        if scope != "cell":
            reasons.append(f"scope is {scope}, not cell")
        if candidate["interaction_order"] > 1:
            parents = [candidate_by_id[parent_id] for parent_id in candidate["requires_selected_ids"]]
            parent_supports = [
                sum(state == "always" for state in states_by_candidate[parent["candidate_id"]].values())
                for parent in parents
            ]
            if len(always_cells) < minimum_interaction_support:
                reasons.append("insufficient interaction development-cell support")
            if not always_cells or any(len(always_cells) >= support for support in parent_supports):
                reasons.append("interaction is not a strict supported subset of both parents")
            if not residual_facts:
                reasons.append("conjunction has no stable residual realization/dependency fact")
        if not candidate["represents"] and candidate["interaction_order"] == 1:
            reasons.append("diagnostic operation candidate has no salient-fact obligation")

        vector = "".join({"always": "1", "never": "0", "mixed": "M"}[states[cell_id]] for cell_id in sorted(states))
        diagnostics.append(
            {
                "candidate_id": candidate["candidate_id"],
                "kc_id": candidate["kc_id"],
                "data_partition": "development",
                "scope": scope,
                "scope_mixed_cell_ids": sorted(mixed_cells),
                "development_cell_support": len(always_cells),
                "development_any_activation_cell_support": len(any_cells),
                "development_source_descriptor_support": len(descriptor_ids),
                "development_source_descriptor_ids": descriptor_ids,
                "observed_realization_support": sum(observed_counts[cell_id] for cell_id in always_cells),
                "nuisance_realization_support": sum(len(grids[cell_id]) for cell_id in always_cells),
                "activation_vector": vector,
                "activation_vector_hash": stable_id("ACT", vector),
                "residual_realization_facts": sorted(residual_facts),
                "residual_realization_evidence": residual_evidence,
                "introduces_residual_realization_structure": bool(residual_facts),
                "fragile_support": len(always_cells) < 2,
                "base_eligible": not reasons,
                "rejection_reasons": reasons,
            }
        )

    diagnostics_by_id = {row["candidate_id"]: row for row in diagnostics}
    equivalence_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        vector = diagnostics_by_id[candidate["candidate_id"]]["activation_vector"]
        equivalence_groups[vector].append(candidate)

    origin_rank = {"canonical": 0, "operation": 1, "interaction": 2}
    equivalence_classes = []
    for vector, members in sorted(equivalence_groups.items()):
        vector_hash = stable_id("ACT", vector)
        representative = sorted(
            members,
            key=lambda row: (
                not diagnostics_by_id[row["candidate_id"]]["base_eligible"],
                origin_rank[row["origin"]],
                row["granularity_rank"],
                -len(row["represents"]),
                row["rule_complexity"],
                row["kc_id"],
            ),
        )[0]
        class_id = stable_id("EQ", vector_hash, sorted(row["candidate_id"] for row in members))
        member_ids = sorted(row["candidate_id"] for row in members)
        member_kcs = sorted(row["kc_id"] for row in members)
        unidentifiable = len(members) > 1
        by_hypothesis: dict[str, list[str]] = defaultdict(list)
        for member in members:
            if member["hypothesis_group"]:
                by_hypothesis[member["hypothesis_group"]].append(member["kc_id"])
        granularity_groups = [
            {"hypothesis_group": group, "kc_ids": sorted(kc_ids)}
            for group, kc_ids in sorted(by_hypothesis.items())
            if len(kc_ids) > 1
        ]
        equivalence_classes.append(
            {
                "equivalence_class_id": class_id,
                "activation_vector_hash": vector_hash,
                "member_candidate_ids": member_ids,
                "member_kc_ids": member_kcs,
                "representative_candidate_id": representative["candidate_id"],
                "unidentifiable_from_development": unidentifiable,
                "unidentifiable_granularity_alternatives": granularity_groups,
                "reason": "identical development activation vectors" if unidentifiable else None,
                "representative_choice_reason": (
                    "deterministic origin/granularity/complexity tie-break; not evidence that the representative granularity is correct"
                    if unidentifiable else None
                ),
            }
        )
        for member in members:
            diagnostic = diagnostics_by_id[member["candidate_id"]]
            diagnostic["equivalence_class_id"] = class_id
            diagnostic["equivalence_members"] = member_kcs
            diagnostic["unidentifiable_from_development"] = unidentifiable
            diagnostic["equivalence_representative"] = member["candidate_id"] == representative["candidate_id"]
            diagnostic["selection_eligible"] = diagnostic["base_eligible"] and diagnostic["equivalence_representative"]
            if diagnostic["base_eligible"] and not diagnostic["equivalence_representative"]:
                diagnostic["rejection_reasons"].append("collapsed into an identical development activation class")

    for candidate in candidates:
        diagnostic = diagnostics_by_id[candidate["candidate_id"]]
        candidate["scope"] = diagnostic["scope"]
        candidate["equivalence_class_id"] = diagnostic["equivalence_class_id"]
        candidate["selection_eligible"] = diagnostic["selection_eligible"]

    return {
        "candidates": sorted(candidates, key=lambda row: row["candidate_id"]),
        "activations": sorted(activations, key=lambda row: (row["candidate_id"], row["canonical_cell_id"])),
        "diagnostics": sorted(diagnostics, key=lambda row: row["candidate_id"]),
        "equivalence_classes": equivalence_classes,
        "minimal_contrasts": minimal_contrasts(development_cells),
        "development_cell_facts": {
            row["canonical_cell_id"]: salient_facts(row["cell"])
            for row in sorted(development_cells, key=lambda value: value["canonical_cell_id"])
        },
    }
