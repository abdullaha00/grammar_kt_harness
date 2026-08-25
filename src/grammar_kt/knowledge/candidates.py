"""Discover KC candidates from development cells and measurement structure only."""

from __future__ import annotations

import json
from collections import defaultdict
from typing import Any

from ..io import read_json, repo_path, stable_id
from ..measurement.operations import evaluate_structural_rule, structural_evidence
from ..records import DIMENSIONS, measurement_opportunity


DEFAULT_CANDIDATE_FAMILY = "modules/knowledge/selection/candidate_families/structural_v0.json"
DEFAULT_OBLIGATION_POLICY = "modules/knowledge/selection/obligations/marked_operational_v0.json"
FORBIDDEN_DISCOVERY_KEYS = {"content", "prompt", "target_answer", "accepted_answers", "generator_id", "item_id"}


def load_candidate_family(path: str | None = None) -> dict[str, Any]:
    family = read_json(repo_path(path or DEFAULT_CANDIDATE_FAMILY))
    if not isinstance(family.get("candidates"), list):
        raise ValueError("candidate family requires candidates")
    return family


def load_obligation_policy(path: str | None = None) -> dict[str, Any]:
    policy = read_json(repo_path(path or DEFAULT_OBLIGATION_POLICY))
    if not isinstance(policy.get("fact_rules"), list):
        raise ValueError("obligation policy requires fact_rules")
    return policy


def _candidate(record: dict[str, Any], *, default_rationale: str) -> dict[str, Any]:
    required = {"kc_id", "name", "definition", "activation_rule", "represents", "canonical_dimensions"}
    if missing := required - set(record):
        raise ValueError(f"candidate {record.get('kc_id')} missing {sorted(missing)}")
    interaction_order = int(record.get("interaction_order", 1))
    return {
        "candidate_id": stable_id(
            "CAND", record["kc_id"], record["activation_rule"], record["represents"], record["canonical_dimensions"]
        ),
        "kc_id": record["kc_id"],
        "name": record["name"],
        "definition": record["definition"],
        "activation_rule": record["activation_rule"],
        "represents": sorted(record["represents"]),
        "canonical_dimensions": sorted(record["canonical_dimensions"]),
        "origin": record.get("origin", "canonical"),
        "hypothesis_group": record.get("hypothesis_group"),
        "taxonomy_parent_kc_ids": list(record.get("taxonomy_parent_kc_ids", [])),
        "requires_selected_kc_ids": list(record.get("requires_selected_kc_ids", [])),
        "interaction_order": interaction_order,
        "rule_complexity": int(record.get("rule_complexity", 1)),
        "granularity_rank": int(record.get("granularity_rank", 0)),
        "required_conditions": list(record.get("required_conditions", [])),
        "includes": list(record.get("includes", [])),
        "excludes": list(record.get("excludes", [])),
        "measurement_dependencies": list(
            record.get("measurement_dependencies", record.get("realization_dependencies", []))
        ),
        "near_neighbours": list(record.get("near_neighbours", [])),
        "rationale": record.get("rationale", default_rationale),
    }


def declared_candidates(family: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    selected = family or load_candidate_family()
    rationale = selected.get("default_rationale", "Declared structural hypothesis.")
    rows = [_candidate(record, default_rationale=rationale) for record in selected["candidates"]]
    modal = selected.get("modal_alternatives")
    if modal:
        values = list(modal["values"])
        generic = modal["generic"]
        rows.append(
            _candidate(
                {
                    **generic,
                    "activation_rule": {"cell": {"modal": values}},
                    "represents": [f"modal:{value}" for value in values],
                    "canonical_dimensions": ["modal"],
                },
                default_rationale=rationale,
            )
        )
        for value in values:
            template = modal["per_value"]
            rows.append(
                _candidate(
                    {
                        **template,
                        "kc_id": template["kc_id_template"].format(VALUE_UPPER=value.upper()),
                        "name": template["name_template"].format(VALUE_UPPER=value.upper()),
                        "definition": template["definition_template"].format(VALUE_UPPER=value.upper()),
                        "activation_rule": {"cell": {"modal": value}},
                        "represents": [f"modal:{value}"],
                        "canonical_dimensions": ["modal"],
                        "required_conditions": [f"modal={value}"],
                        "includes": [value],
                    },
                    default_rationale=rationale,
                )
            )
    by_kc = {row["kc_id"]: row for row in rows}
    for interaction in selected.get("interaction_candidates", []):
        parents = list(interaction["parents"])
        if len(parents) != 2 or any(parent not in by_kc for parent in parents):
            raise ValueError(f"invalid interaction parents: {parents}")
        parent_rows = [by_kc[parent] for parent in parents]
        row = _candidate(
            {
                "kc_id": interaction["kc_id"],
                "name": interaction["name"],
                "definition": interaction["definition"],
                "activation_rule": {"all": [parent["activation_rule"] for parent in parent_rows]},
                "represents": [],
                "canonical_dimensions": sorted({value for parent in parent_rows for value in parent["canonical_dimensions"]}),
                "origin": "interaction",
                "hypothesis_group": interaction.get("hypothesis_group", "interaction_structure"),
                "requires_selected_kc_ids": parents,
                "interaction_order": 2,
                "rule_complexity": 1 + sum(parent["rule_complexity"] for parent in parent_rows),
                "granularity_rank": 3,
                "measurement_dependencies": interaction.get("residual_fact_patterns", []),
                "required_conditions": [f"parents={','.join(parents)}"],
                "includes": ["supported parent conjunction"],
                "excludes": ["unsupported conjunctions"],
            },
            default_rationale="Declared interaction over development measurement structure.",
        )
        rows.append(row)
        by_kc[row["kc_id"]] = row
    ids = [row["candidate_id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("candidate IDs are duplicated")
    return rows


def salient_facts(cell: dict[str, str], policy: dict[str, Any] | None = None) -> list[str]:
    selected = policy or load_obligation_policy()
    evidence = {
        "cell": cell,
        "operations": [],
        "predicate_class": "lexical_transitive",
        "agreement_site": "main_verb",
    }
    facts = []
    for rule in selected["fact_rules"]:
        active, _ = evaluate_structural_rule(rule["activation_rule"], evidence)
        if active:
            facts.append(rule.get("fact") or rule["fact_template"].format(**cell))
    return sorted(facts)


def minimal_contrasts(cells: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    ordered = sorted(cells, key=lambda row: row["canonical_cell_id"])
    for index, left in enumerate(ordered):
        for right in ordered[index + 1 :]:
            changed = [field for field in DIMENSIONS if left["cell"][field] != right["cell"][field]]
            if len(changed) == 1:
                field = changed[0]
                rows.append(
                    {
                        "contrast_id": stable_id("CONTRAST", left["canonical_cell_id"], right["canonical_cell_id"], field),
                        "left_cell_id": left["canonical_cell_id"],
                        "right_cell_id": right["canonical_cell_id"],
                        "changed_dimension": field,
                    }
                )
    return rows


def discover_candidates(
    development_cells: list[dict[str, Any]],
    development_opportunities: list[dict[str, Any]],
    config: dict[str, Any],
) -> dict[str, Any]:
    """Discover and diagnose candidates without generated text or holdout content."""

    development_ids = {row["canonical_cell_id"] for row in development_cells}
    for opportunity in development_opportunities:
        measurement_opportunity(opportunity)
        if opportunity["canonical_cell_id"] not in development_ids:
            raise ValueError("holdout opportunity supplied to development-only discovery")
        if FORBIDDEN_DISCOVERY_KEYS & set(opportunity):
            raise ValueError("generated item content supplied to candidate discovery")
    family = load_candidate_family(config.get("candidate_family"))
    obligations = load_obligation_policy(config.get("obligation_policy"))
    candidates = declared_candidates(family)
    opportunity_ids = [row["measurement_opportunity_id"] for row in sorted(development_opportunities, key=lambda row: row["measurement_opportunity_id"])]
    evidence_by_id = {
        row["measurement_opportunity_id"]: structural_evidence(row["cell"], row["structural_conditions"])
        for row in development_opportunities
    }
    opportunity_by_id = {row["measurement_opportunity_id"]: row for row in development_opportunities}
    activations = []
    diagnostics = []
    vectors: dict[str, str] = {}
    minimum_opportunity_support = int(config.get("minimum_candidate_opportunity_support", config.get("minimum_candidate_cell_support", 1)))
    minimum_descriptor_support = int(config.get("minimum_candidate_descriptor_support", 1))
    for candidate in candidates:
        active_ids = []
        for opportunity_id in opportunity_ids:
            active, evidence = evaluate_structural_rule(candidate["activation_rule"], evidence_by_id[opportunity_id])
            activations.append(
                {
                    "candidate_id": candidate["candidate_id"],
                    "kc_id": candidate["kc_id"],
                    "measurement_opportunity_id": opportunity_id,
                    "data_partition": "development",
                    "activated": active,
                    "evidence": evidence,
                }
            )
            if active:
                active_ids.append(opportunity_id)
        vector = "".join("1" if opportunity_id in set(active_ids) else "0" for opportunity_id in opportunity_ids)
        vectors[candidate["candidate_id"]] = vector
        cell_ids = sorted({opportunity_by_id[value]["canonical_cell_id"] for value in active_ids})
        descriptor_ids = sorted({source_id for value in active_ids for source_id in opportunity_by_id[value]["source_descriptor_ids"]})
        reasons = []
        if len(active_ids) < minimum_opportunity_support:
            reasons.append("insufficient development MeasurementOpportunity support")
        if len(descriptor_ids) < minimum_descriptor_support:
            reasons.append("insufficient development source-descriptor support")
        if candidate["interaction_order"] > 1 and len(cell_ids) < int(config.get("minimum_interaction_cell_support", 2)):
            reasons.append("insufficient interaction development-cell support")
        diagnostics.append(
            {
                "candidate_id": candidate["candidate_id"],
                "kc_id": candidate["kc_id"],
                "data_partition": "development",
                "development_opportunity_support": len(active_ids),
                "development_cell_support": len(cell_ids),
                "development_source_descriptor_support": len(descriptor_ids),
                "activation_vector": vector,
                "activation_vector_hash": stable_id("ACT", vector),
                "base_eligible": not reasons,
                "rejection_reasons": reasons,
            }
        )
    diagnostics_by_id = {row["candidate_id"]: row for row in diagnostics}
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for candidate in candidates:
        # Collapse candidates only when development cannot distinguish either
        # their activation domain or the explicit obligations they represent.
        # Equal activation alone is not enough: with a small development set,
        # tense and polarity can co-occur while remaining distinct obligations.
        equivalence_key = json.dumps(
            {
                "activation": vectors[candidate["candidate_id"]],
                "represents": candidate["represents"],
            },
            sort_keys=True,
        )
        groups[equivalence_key].append(candidate)
    equivalence_classes = []
    for equivalence_key, members in sorted(groups.items()):
        vector = vectors[members[0]["candidate_id"]]
        representative = sorted(
            members,
            key=lambda row: (
                not diagnostics_by_id[row["candidate_id"]]["base_eligible"],
                row["interaction_order"],
                row["granularity_rank"],
                row["rule_complexity"],
                row["kc_id"],
            ),
        )[0]
        class_id = stable_id("EQ", vector, sorted(row["candidate_id"] for row in members))
        member_kcs = sorted(row["kc_id"] for row in members)
        equivalence_classes.append(
            {
                "equivalence_class_id": class_id,
                "member_candidate_ids": sorted(row["candidate_id"] for row in members),
                "member_kc_ids": member_kcs,
                "representative_candidate_id": representative["candidate_id"],
                "unidentifiable_from_development": len(members) > 1,
                "reason": "identical development activation and obligation coverage" if len(members) > 1 else None,
            }
        )
        for member in members:
            diagnostic = diagnostics_by_id[member["candidate_id"]]
            diagnostic["equivalence_class_id"] = class_id
            diagnostic["equivalence_members"] = member_kcs
            diagnostic["equivalence_representative"] = member is representative
            diagnostic["selection_eligible"] = diagnostic["base_eligible"] and member is representative
            member["equivalence_class_id"] = class_id
            member["selection_eligible"] = diagnostic["selection_eligible"]
    return {
        "candidate_family_id": family["candidate_family_id"],
        "obligation_policy": obligations,
        "candidates": sorted(candidates, key=lambda row: row["candidate_id"]),
        "activations": sorted(activations, key=lambda row: (row["candidate_id"], row["measurement_opportunity_id"])),
        "diagnostics": sorted(diagnostics, key=lambda row: row["candidate_id"]),
        "equivalence_classes": equivalence_classes,
        "minimal_contrasts": minimal_contrasts(development_cells),
        "development_cell_facts": {
            row["canonical_cell_id"]: salient_facts(row["cell"], obligations)
            for row in sorted(development_cells, key=lambda row: row["canonical_cell_id"])
        },
        "opportunity_to_cell": {
            row["measurement_opportunity_id"]: row["canonical_cell_id"]
            for row in sorted(
                development_opportunities,
                key=lambda row: row["measurement_opportunity_id"],
            )
        },
        "development_opportunity_ids": opportunity_ids,
        "generated_text_read": False,
        "holdout_content_read": False,
    }
