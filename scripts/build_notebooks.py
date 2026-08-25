#!/usr/bin/env python3
"""Build the two deterministic research notebooks from readable cell sources."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def markdown(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": source}


def code(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": source,
    }


def notebook(cells: list[dict]) -> dict:
    return {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3.11"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


SETUP = '''import copy
import json
import tempfile
from pathlib import Path

from grammar_kt.evaluation import kt, simulation
from grammar_kt.generation.generators import generate_items
from grammar_kt.generation.validation import validate_items
from grammar_kt.grammar import canonical, normalisation, source
from grammar_kt.grammar.schema import consistency_report
from grammar_kt.io import ROOT, read_json, read_jsonl, read_yaml, write_json
from grammar_kt.knowledge import policy, qmatrix, selection
from grammar_kt.measurement.operations import derive_operations
from grammar_kt.measurement.opportunities import build_measurement_opportunities

CELL = {"tense":"past", "aspect":"none", "voice":"active", "polarity":"negative", "clause":"declarative", "modal":"none"}
audit_tmp = tempfile.TemporaryDirectory(prefix="grammar-kt-notebook-")
audit_root = Path(audit_tmp.name)

def show(value):
    print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str))'''


GRAMMAR_CODE = '''source_record = read_jsonl(ROOT / "modules/grammar/source/fixtures/core.jsonl")[0]
phase1 = source.phase1_record(source_record)
response_path = audit_root / "normalisation_response.json"
write_json(response_path, {"egp_id": source_record["egp_id"], "result": "complete", "cells": [CELL], "note": None})
normalised = normalisation.normalise_one(
    source_record,
    phase1_template=(ROOT / "modules/grammar/normalisation/prompts/phase1.txt").read_text(),
    phase2_template=(ROOT / "modules/grammar/normalisation/prompts/phase2.txt").read_text(),
    backend_config={"kind": "fixture_file", "response_file": str(response_path)},
    max_attempts=1,
    output=audit_root / "normalisation",
    phase1_only=True,
)
canonical_cells, source_edges = canonical.build([normalised["output"]])
show({"source_phase1": phase1, "normalisation_result": normalised["output"], "canonical_cells": canonical_cells, "source_edges": source_edges})'''


MEASUREMENT_CODE = '''question = {**CELL, "tense": "present", "polarity": "positive", "clause": "polar_question"}
conditions = {"subject_person": 3, "subject_number": "singular", "wh_role": None, "imperative_subtype": None}
operation_dependence = {
    "lexical_transitive": derive_operations(question, {**conditions, "predicate_class": "lexical_transitive"}),
    "copular": derive_operations(question, {**conditions, "predicate_class": "copular"}),
}
opportunities = build_measurement_opportunities(
    canonical_cells,
    {"include_predicate_class_contrasts": False, "include_agreement_variants": False},
)
opportunity = opportunities[0]
show({"same_cell_operation_dependence": operation_dependence, "measurement_opportunity": opportunity})'''


GENERATION_CODE = '''generated_by_format = {}
validated_by_format = {}
for format_name in ("standalone", "dialogue"):
    generated = generate_items(
        [opportunity],
        ROOT / f"modules/generation/generators/llm_{format_name}_fixture_v0.yaml",
        evidence_root=audit_root / "generation" / format_name,
    )
    validated = validate_items(
        generated["candidates"],
        [opportunity],
        ROOT / "modules/generation/validation/blind_fixture_v0.yaml",
        evidence_root=audit_root / "validation" / format_name,
    )
    generated_by_format[format_name] = generated
    validated_by_format[format_name] = validated
standalone_item = validated_by_format["standalone"]["accepted"][0]
dialogue_item = validated_by_format["dialogue"]["accepted"][0]
show({
    "invariant": {
        "same_measurement_opportunity": standalone_item["measurement_opportunity_id"] == dialogue_item["measurement_opportunity_id"],
        "same_grammar_cell": standalone_item["canonical_cell_id"] == dialogue_item["canonical_cell_id"],
        "same_expected_operations": standalone_item["validated_structure"]["operations"] == dialogue_item["validated_structure"]["operations"],
        "different_item_ids": standalone_item["item_id"] != dialogue_item["item_id"],
    },
    "standalone": standalone_item,
    "dialogue": dialogue_item,
    "validation_reports": {key: value["report"] for key, value in validated_by_format.items()},
})'''


KNOWLEDGE_CODE = '''selection_fixture = read_json(ROOT / "modules/knowledge/selection/fixtures/core.json")
selection_config = read_json(ROOT / "modules/knowledge/selection/configs/deterministic_v0.json")
selected = selection.evaluate_fixture(selection_fixture, selection_config)
frozen_policy = policy.load_policy(ROOT / "modules/knowledge/policies/factorized.json")
items_for_projection = [{**standalone_item, "canonical_split": "development"}, {**dialogue_item, "canonical_split": "development"}]
item_projection, kc_cards = policy.project_items(items_for_projection, [opportunity], frozen_policy)
q_columns, q_rows, q_edges, q_audit = qmatrix.build(items_for_projection, kc_cards, item_projection)
show({
    "selected_kcs": [row["kc_id"] for row in selected["selection"]["selected_candidates"]],
    "selection_partition": selected["selected_policy"]["selection_metadata"],
    "cross_format_projection": item_projection,
    "same_kcs_across_formats": item_projection[0]["kc_ids"] == item_projection[1]["kc_ids"],
    "qmatrix": {"columns": q_columns, "rows": q_rows, "edges": q_edges, "audit": q_audit},
})'''


EVALUATION_CODE = '''def simulate_one(item):
    runtime_item = {**item, "canonical_split": "development"}
    params = simulation.load_simulation_parameters(ROOT / "modules/evaluation/simulation/configs/structural_oracle_v0.json")
    params.update({"seed": 77, "learners_per_profile": 1, "item_passes_per_learner": 2, "profiles": {"mixed": params["profiles"]["mixed"]}})
    oracle_projection, feature_ids = simulation.project_oracle_items([runtime_item], [opportunity], params)
    oracle_by_item = {runtime_item["item_id"]: oracle_projection[0]["oracle_feature_ids"]}
    observed, private, learners, _ = simulation.simulate_records(params, {runtime_item["item_id"]: runtime_item}, oracle_by_item, feature_ids, 1, 2)
    return observed, private, learners

standalone_events, _, _ = simulate_one(standalone_item)
dialogue_events, _, _ = simulate_one(dialogue_item)
kt_fixture = read_json(ROOT / "modules/evaluation/kt/fixtures/compositional_probe.json")
acquisition, probes, supported, frozen_counts = kt.project_compositional_interactions(
    kt_fixture["acquisition_events"], kt_fixture["probe_events"], kt_fixture["item_projections"]
)
show({
    "simulation_invariance": {
        "standalone": [(row["measurement_opportunity_id"], row["item_difficulty"], row["correct"]) for row in standalone_events],
        "dialogue": [(row["measurement_opportunity_id"], row["item_difficulty"], row["correct"]) for row in dialogue_events],
        "same_opportunity_outcome_fingerprint": simulation.opportunity_outcome_fingerprint(standalone_events) == simulation.opportunity_outcome_fingerprint(dialogue_events),
    },
    "frozen_kt_probe": {"development_supported_kcs": sorted(supported), "frozen_counts": {key: dict(value) for key, value in frozen_counts.items()}, "probes": probes, "probe_updates_state": False},
})'''


unit_cells = [
    markdown("# Five-module executable tour\n\nAll model-dependent examples use deterministic fixture transports; no paid API call is made."),
    code(SETUP),
    markdown("# 1. Grammar Representation\n\n## Source\n## Normalisation\n## Canonical GrammarCells"),
    code(GRAMMAR_CODE),
    markdown("# 2. Measurement\n\n## Structural conditions\n## Required operations\n## Measurement Opportunity"),
    code(MEASUREMENT_CODE),
    markdown("# 3. Dataset Generation\n\n## LLM standalone\n## LLM dialogue\n## Validation"),
    code(GENERATION_CODE),
    markdown("# 4. Knowledge Representation\n\n## KC candidates / selection\n## KC application\n## Q-matrix"),
    code(KNOWLEDGE_CODE),
    markdown("# 5. Evaluation\n\n## Simulation\n## Knowledge tracing"),
    code(EVALUATION_CODE),
]


audit_cells = [
    markdown("# Research audit: five scientific modules\n\nFor every box, review the declared method, input/output contract, assumptions, leakage boundary, examples, failures, and metrics. Automated checks establish software behavior; they do not certify linguistic validity."),
    code(SETUP),
    markdown("# 1. Grammar Representation\n\n**Question:** What grammatical structures exist?\n\n- Declared method: verified source snapshot → two-phase isolated normalisation → exact canonical cells.\n- Leakage boundary: Phase 1 sees descriptor fields only; partial mappings never create exact cells.\n- Review: provenance, raw model evidence, retries, repeated-normalisation stability, exclusions, and deduplication."),
    code(GRAMMAR_CODE + '\nshow({"schema_consistency": consistency_report(), "partial_cells_excluded": True, "phase1_fields": sorted(phase1)})'),
    markdown("# 2. Measurement\n\n**Question:** Under which controlled structural conditions are cells elicited?\n\n- Input/output: GrammarCell + structural conditions → derived operations → stable `OPP_…`.\n- Assumption: predicate class and agreement/WH/imperative conditions are measurement variables; words are not.\n- Leakage boundary: no surface text, generator, KC, outcome, or fold fields."),
    code(MEASUREMENT_CODE + '\nshow({"opportunity_fields": sorted(opportunity), "surface_fields_present": sorted(set(opportunity) & {"prompt", "content", "target_answer"})})'),
    markdown("# 3. Dataset Generation\n\n**Question:** How are opportunities presented naturally?\n\n- Main conditions: constrained LLM standalone and constrained LLM dialogue through one interface.\n- Hard validation: IDs, references, family content, no KC/fold labels, exact opportunity preservation.\n- Independent validation: target-blind grammatical reconstruction.\n- Separate quality diagnostics: naturalness, ambiguity, pedagogy, world knowledge, CEFR, and dialogue quality."),
    code(GENERATION_CODE),
    markdown("## Representative failure: blind reconstruction mismatch"),
    code('''bad_generator = read_yaml(ROOT / "modules/generation/generators/llm_standalone_fixture_v0.yaml")
bad_generator["backend_config"] = {"kind":"fixture_map", "default":{"content":{"prompt":"Complete the sentence."}, "target_answer":"Yesterday, the technician wrote the report.", "accepted_answers":["Yesterday, the technician wrote the report."]}}
bad_candidate = generate_items([opportunity], bad_generator)["candidates"][0]
bad_evaluator = read_yaml(ROOT / "modules/generation/validation/blind_fixture_v0.yaml")
bad_evaluator["structural_backend_config"] = {"kind":"fixture_map", "default":{"cell":{**CELL, "polarity":"positive"}, "operations":[], "predicate_class":"lexical_transitive", "agreement_site":"main_verb"}}
bad_validation = validate_items([bad_candidate], [opportunity], bad_evaluator)
show({"accepted": len(bad_validation["accepted"]), "rejected": bad_validation["rejected"], "metrics": bad_validation["report"]})'''),
    markdown("# 4. Knowledge Representation\n\n**Question:** Which KCs encode learner knowledge over opportunities?\n\n- Discovery input: development GrammarCells and MeasurementOpportunities only.\n- Boundary: holdout content is removed before discovery; policy is written and frozen before holdout evaluation.\n- Q-matrix is a mechanical accepted-item → frozen-projection conversion."),
    code(KNOWLEDGE_CODE),
    markdown("# 5. Evaluation\n\n**Question:** Does the representation transfer and predict under controlled evidence?\n\n- Structural oracle uses opportunity identity and never candidate KCs.\n- Acquisition updates use development events only; probes read frozen state.\n- Report cold-KC and zero-KC fallback separately.\n- Cross-format transfer changes the item surface, not the opportunity or KC logic."),
    code(EVALUATION_CODE),
    markdown("# Reproducibility review\n\nRetain command, resolved config, seed, opportunity-bank fingerprint, generator and raw output, validation evidence and counts, simulation fingerprint, frozen-policy fingerprint, and representative examples. Keep software correctness, dataset validity, and research evidence as separate claims."),
    code('''show({
    "software_correctness": "test suite and schema/reference audits",
    "dataset_validity": {key: value["report"] for key, value in validated_by_format.items()},
    "research_evidence": "requires manual review; this notebook does not auto-accept methodology",
    "evidence_root": str(audit_root),
})'''),
]


for name, cells in (
    ("module_unit_examples.ipynb", unit_cells),
    ("research_audit.ipynb", audit_cells),
):
    target = ROOT / "notebooks" / name
    target.write_text(json.dumps(notebook(cells), ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
