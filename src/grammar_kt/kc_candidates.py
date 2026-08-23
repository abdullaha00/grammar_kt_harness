"""Deterministic Phase-A KC candidate construction and development diagnostics."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from .io import stable_id
from .kc import evaluate_rule
from .realisation import lexical_nodes, realise
from .realisation_space import enumerate_valid_realisations
from .records import DIMENSIONS
DEFAULT_OBLIGATION_POLICY = (
    "modules/kc_selection/obligations/marked_operational_v0.json"
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


def load_candidate_family(path: str | None = None) -> dict[str, Any]:
    from .io import ROOT, read_json, repo_path

    selected = path or str(
        ROOT / "modules" / "kc_selection" / "candidate_families" / "structural_v0.json"
    )
    family = read_json(repo_path(selected))
    if not isinstance(family.get("candidates"), list):
        raise ValueError("candidate family requires a candidates list")
    return family


def _compile_declared_candidate(record: dict[str, Any], rationale: str) -> dict[str, Any]:
    return _candidate(
        record["kc_id"],
        record["name"],
        record["definition"],
        record["activation_rule"],
        represents=record.get("represents", []),
        dimensions=record.get("canonical_dimensions", []),
        origin=record.get("origin", "canonical"),
        hypothesis_group=record.get("hypothesis_group"),
        taxonomy_parent_kc_ids=record.get("taxonomy_parent_kc_ids"),
        requires_selected_kc_ids=record.get("requires_selected_kc_ids"),
        interaction_order=int(record.get("interaction_order", 1)),
        rule_complexity=int(record.get("rule_complexity", 1)),
        granularity_rank=int(record.get("granularity_rank", 0)),
        residual_fact_patterns=record.get("residual_fact_patterns"),
        required_conditions=record.get("required_conditions"),
        includes=record.get("includes"),
        excludes=record.get("excludes"),
        realization_dependencies=record.get("realization_dependencies"),
        near_neighbours=record.get("near_neighbours"),
        rationale=record.get("rationale", rationale),
    )


def canonical_candidates(family: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Compile the explicit reference family without declaring hypotheses in Python."""

    selected = family or load_candidate_family()
    rationale = selected.get(
        "default_rationale", "Declared Phase-A structural hypothesis."
    )
    candidates = [
        _compile_declared_candidate(record, rationale)
        for record in selected["candidates"]
    ]
    modal = selected["modal_alternatives"]
    values = sorted(modal["values"])
    generic = modal["generic"]
    candidates.append(
        _candidate(
            generic["kc_id"],
            generic["name"],
            generic["definition"],
            {"cell": {"modal": values}},
            represents=[f"modal:{value}" for value in values],
            dimensions=["modal"],
            hypothesis_group=generic.get("hypothesis_group"),
            granularity_rank=int(generic.get("granularity_rank", 0)),
            required_conditions=generic.get("required_conditions"),
            includes=values,
            excludes=generic.get("excludes"),
            realization_dependencies=generic.get("realization_dependencies"),
            rationale=generic.get("rationale", rationale),
        )
    )
    template = modal["per_value"]
    for value in values:
        replacements = {"{VALUE}": value, "{VALUE_UPPER}": value.upper()}

        def render(text: str) -> str:
            for pattern, replacement in replacements.items():
                text = text.replace(pattern, replacement)
            return text

        candidates.append(
            _candidate(
                render(template["kc_id_template"]),
                render(template["name_template"]),
                render(template["definition_template"]),
                {"cell": {"modal": value}},
                represents=[f"modal:{value}"],
                dimensions=["modal"],
                hypothesis_group=template.get("hypothesis_group"),
                taxonomy_parent_kc_ids=template.get("taxonomy_parent_kc_ids"),
                granularity_rank=int(template.get("granularity_rank", 0)),
                required_conditions=[f"modal={value}"],
                includes=[value],
                excludes=template.get("excludes"),
                realization_dependencies=template.get("realization_dependencies"),
                rationale=template.get("rationale", rationale),
            )
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

def load_obligation_policy(path: str | None = None) -> dict[str, Any]:
    from .io import read_json, repo_path

    policy = read_json(repo_path(path or DEFAULT_OBLIGATION_POLICY))
    if not isinstance(policy.get("fact_rules"), list):
        raise ValueError("obligation policy requires fact_rules")
    return policy


def salient_facts(
    cell: dict[str, str], policy: dict[str, Any] | None = None
) -> list[str]:
    """Compile facts from an explicit, replaceable obligation policy."""

    selected = policy or load_obligation_policy()
    opportunity = {"cell": cell, "realization_operations": []}
    facts = []
    for rule in selected["fact_rules"]:
        active, _evidence = evaluate_rule(rule["activation_rule"], opportunity)
        if not active:
            continue
        fact = rule.get("fact")
        if fact is None:
            fact = rule["fact_template"].format(**cell)
        facts.append(fact)
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
    opportunities = []
    for row in enumerate_valid_realisations(
        cell_row, frames, identity_namespace="kc-selection-grid"
    ):
        spec, frame = row["spec"], row["frame"]
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

    family = load_candidate_family(config.get("candidate_family"))
    obligation_policy = load_obligation_policy(config.get("obligation_policy"))
    candidates = add_interaction_candidates(canonical_candidates(family), family)
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
            row["canonical_cell_id"]: salient_facts(row["cell"], obligation_policy)
            for row in sorted(development_cells, key=lambda value: value["canonical_cell_id"])
        },
        "candidate_family_id": family["candidate_family_id"],
        "obligation_policy": obligation_policy,
    }
