#!/usr/bin/env python3
"""Build the primary deterministic research walkthrough from readable cells.

The separate compact ``research_audit.ipynb`` is intentionally left untouched.
"""

from __future__ import annotations

import hashlib
import json
import textwrap
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def clean(source: str) -> str:
    return textwrap.dedent(source).strip() + "\n"


def markdown(source: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": clean(source)}


def code(source: str) -> dict:
    return {
        "cell_type": "code",
        "execution_count": None,
        "metadata": {},
        "outputs": [],
        "source": clean(source),
    }


def notebook(cells: list[dict]) -> dict:
    identified = []
    for index, cell in enumerate(cells):
        digest = hashlib.sha256(f"{index}\0{cell['source']}".encode("utf-8")).hexdigest()[:12]
        identified.append({**cell, "id": f"cell-{digest}"})
    return {
        "cells": identified,
        "metadata": {
            "kernelspec": {
                "display_name": "Python 3",
                "language": "python",
                "name": "python3",
            },
            "language_info": {"name": "python", "version": "3.11"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }


unit_cells = [
    markdown(
        r'''
        # 0. Overview — Grammar-KT research pipeline

        ## Research goal

        Grammar resources provide grammatical descriptions, but they do not directly provide
        learner-facing items, KC annotations, Q-matrices, or learner histories. Grammar-KT
        constructs those artifacts while keeping source interpretation, measurement design,
        surface generation, knowledge representation, and evaluation as separate scientific
        decisions.

        ```text
        EGP descriptors
              │
              ▼
        ┌──────────────┐
        │   Grammar    │
        │ source       │
        │ normalise    │
        │ canonicalise │
        └──────┬───────┘
               │ GrammarCells
               ▼
        ┌──────────────┐
        │ Measurement  │
        │ conditions   │
        │ operations   │
        │ opportunities│
        └──────┬───────┘
               │ MeasurementOpportunities
               ▼
        ┌──────────────┐
        │  Generation  │
        │ LLM generator│
        │ blind validate│
        └──────┬───────┘
               │ accepted items
               ▼
        ┌──────────────┐
        │  Knowledge   │
        │ candidates   │
        │ select/freeze│
        │ project / Q  │
        └──────┬───────┘
               │ item–KC mapping
               ▼
        ┌──────────────┐
        │  Evaluation  │
        │ simulation   │
        │ KT           │
        └──────────────┘
        ```

        The five boxes are scientific groupings; each contains one or more separately
        executable transformations. The literal executor order in
        [`runner.py`](../src/grammar_kt/runner.py) is:

        ```text
        source → normalisation → canonical → measurement → generation
        → knowledge_selection → knowledge → qmatrix → simulation → kt
        ```

        This notebook follows one coherent mini-run: five authentic descriptors from the
        declared EGP sample become five canonical cells, 17 MeasurementOpportunities, six
        retained-model items, a frozen structural KC projection, a Q-matrix, and small
        ordinary/compositional KT benchmarks. It never imports the archived deterministic
        realiser.
        '''
    ),
    markdown(
        r'''
        ## Research modularity: which files are intended to change?

        In this notebook, **research-modular** means an explicitly named, versioned input that
        can be exchanged to define a new experimental condition—another language, source sample,
        measurement policy, generator, KC hypothesis family, oracle, or KT configuration.
        Swapping one is a scientific intervention and should produce a new manifest/fingerprint.

        Python modules implement the contracts and transformations. They are normally held
        stable across comparisons. Where a language change requires different derivation logic
        rather than different declarations, the table says so explicitly: that is a versioned
        code-level intervention, not a hidden configuration tweak.

        | Executable stage | Intended research-modular files/artifacts | What can be changed without rewriting the stage contract? |
        | --- | --- | --- |
        | `source` | [`base.yaml`](../experiments/base.yaml), external snapshot selected through `GRAMMAR_KT_EGP_SOURCE`, [`sample_ids.txt`](../modules/grammar/source/sample_ids.txt), [`sample_metadata.jsonl`](../modules/grammar/source/sample_metadata.jsonl), [`annotation_units.jsonl`](../modules/grammar/source/annotation_units.jsonl) | Source language/resource, verified snapshot, sampling frame, strata, and reliability design. `source.py` remains the verification/projection mechanism. |
        | `normalisation` | [`phase1.txt`](../modules/grammar/normalisation/prompts/phase1.txt), [`phase2.txt`](../modules/grammar/normalisation/prompts/phase2.txt), [`wrapper.txt`](../modules/grammar/normalisation/prompts/wrapper.txt), [`rulebook.md`](../modules/grammar/normalisation/rules/rulebook.md), [`model_instructions.md`](../modules/grammar/normalisation/rules/model_instructions.md), [`mapping_schema.json`](../modules/grammar/normalisation/configs/mapping_schema.json), [`backend.yaml`](../modules/grammar/normalisation/configs/backend.yaml) | The annotation protocol, linguistic guidance, model/backend, and response contract. Phase prompt paths and backend are configured by the experiment today; wrapper/rulebook/instructions/schema are versionable research files currently resolved from their standard module paths. A new language should version the whole bundle coherently. |
        | `canonical` | [`grammar_schema.yaml`](../modules/grammar/canonical/grammar_schema.yaml) | Canonical dimensions, values, and cross-field constraints. `schema.py` and `canonical.py` are stable validation/deduplication mechanics; a language with different categories needs a new versioned schema and compatible mapping contract. |
        | `measurement` | [`default.json`](../modules/measurement/opportunities/default.json) | Which declared opportunity expansions are active. The English operation and agreement rules currently live in `operations.py`/`opportunities.py`; a language requiring different derivations needs a named code-level implementation plus tests, because those rules are not yet a data-only plug-in. |
        | `generation` | [`llm_standalone_v0.yaml`](../modules/generation/generators/llm_standalone_v0.yaml), [`llm_dialogue_v0.yaml`](../modules/generation/generators/llm_dialogue_v0.yaml), generation prompts/instructions/output schemas, [`blind_v0.yaml`](../modules/generation/validation/blind_v0.yaml), validation prompts/schemas, and backend YAML files | Surface language, exercise format, lexical/register constraints, generator/evaluator models, and validation protocol—while retaining the fixed MeasurementOpportunity interface and blind-target boundary. |
        | `knowledge_selection` | [`deterministic_v0.json`](../modules/knowledge/selection/configs/deterministic_v0.json), [`structural_v0.json`](../modules/knowledge/selection/candidate_families/structural_v0.json), [`marked_operational_v0.json`](../modules/knowledge/selection/obligations/marked_operational_v0.json), and the fold manifest | Candidate KC hypotheses, eligibility/support thresholds, obligation vocabulary, selector inputs, and development/holdout design. `selection.py` remains the deterministic selection/freeze algorithm. |
        | `knowledge` | The frozen selected-policy artifact or a declared predefined policy such as [`factorized.json`](../modules/knowledge/policies/factorized.json), plus the fold manifest | Which already-frozen ontology is projected. `policy.py` is intentionally a generic structural rule evaluator; generated text is not a modular input here. |
        | `qmatrix` | Accepted item bank and frozen item→KC projection artifacts | No independent research configuration is intended. `qmatrix.py` is deliberately mechanical: changing the matrix requires changing the upstream bank or frozen policy, not adding an unrecorded Q-matrix rule. |
        | `simulation` | [`structural_oracle_v0.json`](../modules/evaluation/simulation/configs/structural_oracle_v0.json), seed/scale in experiment config, and fold manifest | Oracle feature declaration, learner profiles, learning/noise parameters, scale, and protocol. A different response/update equation is a named code-level simulator version, not merely a seed change. |
        | `kt` | [`default.json`](../modules/evaluation/kt/configs/default.json), technique list and fold manifest in experiment config | Smoothing, BKT/logistic parameters, enabled baselines, calibration/bootstrap settings, and evaluation partition. `kt.py` keeps observable pre-event projection/fitting mechanics fixed. |

        The five conceptual boxes therefore expose different kinds of modularity. Some modules
        are declaration-driven; some deliberately have no local knob because they must remain
        mechanical; and some current English assumptions are explicit code-level research
        definitions that require a new implementation version for cross-linguistic work.
        '''
    ),
    markdown(
        r'''
        ## Evidence mode and reproducibility

        The safe default is **replay mode**. It passes retained real model outputs back through
        the active parsers, validators, and transformations, so rerunning the notebook makes no
        paid calls. It is not a claim of fresh inference.

        To run live, deliberately change `LIVE_MODE` to `True` below, provide the verified
        external EGP snapshot through `GRAMMAR_KT_EGP_SOURCE` (or the configured data root), and
        confirm the configured model backends. The normalisation and generation/validation
        execution cells are the only cells that invoke models in live mode.

        The compact reference boundary is documented in
        [`reference/pipeline_walkthrough`](../reference/pipeline_walkthrough/README.md). The
        retained EGP rows are real; there is no fabricated fallback source.
        '''
    ),
    code(
        r'''
        import hashlib
        import html
        import json
        import os
        import platform
        import subprocess
        import sys
        import tempfile
        from collections import Counter, defaultdict
        from pathlib import Path

        from IPython.display import HTML, Markdown, display

        # Jupyter starts kernels in the notebook directory; direct scripts/tests start at the
        # repository root. Resolve either case before importing the local package.
        WORKSPACE = Path.cwd().resolve()
        if not (WORKSPACE / "src/grammar_kt").is_dir() and (WORKSPACE.parent / "src/grammar_kt").is_dir():
            WORKSPACE = WORKSPACE.parent
        if not (WORKSPACE / "src/grammar_kt").is_dir():
            raise RuntimeError("Open this notebook from the grammar_kt_harness repository.")
        sys.path.insert(0, str(WORKSPACE / "src"))

        from grammar_kt.evaluation import kt, simulation
        from grammar_kt.folds import annotate_items, assignment_for_cells, fold_rows, load_fold
        from grammar_kt.generation.generators import generate_items
        from grammar_kt.generation.items import FORBIDDEN_GENERATION_KEYS, nested_keys
        from grammar_kt.generation.validation import validate_items
        from grammar_kt.grammar import canonical, normalisation, source
        from grammar_kt.grammar.normalisation_reliability import analyse_repeated_normalisations
        from grammar_kt.grammar.schema import consistency_report
        from grammar_kt.io import (
            ROOT, read_json, read_jsonl, read_yaml, write_jsonl,
        )
        from grammar_kt.knowledge import candidates as kc_candidates
        from grammar_kt.knowledge import policy, qmatrix, selection
        from grammar_kt.measurement.operations import (
            derive_agreement_site, derive_operations, structural_evidence,
        )
        from grammar_kt.measurement.opportunities import build_measurement_opportunities
        from grammar_kt.records import grammar_cell, measurement_opportunity
        from grammar_kt.runner import STAGE_NAMES

        LIVE_MODE = False  # Safe default. Changing this can invoke configured model backends.
        if os.environ.get("AUDIT_SMOKE_TEST") == "1":
            LIVE_MODE = False

        REFERENCE = ROOT / "reference/pipeline_walkthrough"
        reference_manifest = read_json(REFERENCE / "manifest.json")
        walkthrough_tmp = tempfile.TemporaryDirectory(prefix="grammar-kt-walkthrough-")
        walkthrough_root = Path(walkthrough_tmp.name)
        invariant_results = {}

        def compact(value):
            if isinstance(value, (dict, list)):
                try:
                    return json.dumps(value, ensure_ascii=False, sort_keys=True)
                except TypeError:
                    return str(value)
            return "—" if value is None else str(value)

        def table(rows, columns=None, max_rows=24, title=None):
            rows = list(rows)
            if title:
                display(Markdown(f"**{title}**"))
            if not rows:
                display(Markdown("_No rows._"))
                return
            shown = rows[:max_rows]
            columns = columns or list(shown[0])
            head = "".join(f"<th>{html.escape(str(column))}</th>" for column in columns)
            body = "".join(
                "<tr>" + "".join(
                    f"<td><code>{html.escape(compact(row.get(column)))}</code></td>"
                    for column in columns
                ) + "</tr>" for row in shown
            )
            suffix = (f"<p><em>Showing {len(shown)} of {len(rows)} rows.</em></p>"
                      if len(rows) > len(shown) else "")
            display(HTML("<div style='overflow-x:auto'><table><thead><tr>" + head
                         + "</tr></thead><tbody>" + body + "</tbody></table></div>" + suffix))

        def show_json(value, title=None):
            if title:
                display(Markdown(f"**{title}**"))
            print(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True, default=str))

        def show_text(path, max_lines=40, start_line=1):
            selected = Path(path)
            if not selected.is_absolute():
                selected = ROOT / selected
            lines = selected.read_text(encoding="utf-8").splitlines()
            excerpt = lines[start_line - 1:start_line - 1 + max_lines]
            language = {".json": "json", ".yaml": "yaml", ".yml": "yaml"}.get(selected.suffix, "text")
            label = selected.relative_to(ROOT) if selected.is_relative_to(ROOT) else selected
            display(Markdown(
                f"`{label}` (lines {start_line}–{start_line + len(excerpt) - 1} of {len(lines)})\n\n"
                f"```{language}\n" + "\n".join(excerpt) + "\n```"
            ))

        def check_group(name, checks):
            rows = [{"invariant": label, "status": "PASS" if passed else "FAIL"}
                    for label, passed in checks.items()]
            invariant_results[name] = rows
            table(rows, title=f"{name} invariant summary")
            assert all(checks.values()), f"{name} invariant failure"
        '''
    ),
    code(
        r'''
        git_commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip()
        git_dirty = bool(subprocess.check_output(
            ["git", "status", "--porcelain"], cwd=ROOT, text=True
        ))
        generator_backend = read_yaml(ROOT / "modules/generation/generators/backend.yaml")
        validator_backend = read_yaml(ROOT / "modules/generation/validation/backend.yaml")
        normalisation_backend_decl = read_yaml(
            ROOT / "modules/grammar/normalisation/configs/backend.yaml"
        )
        table([
            {"field": "Git commit", "value": git_commit},
            {"field": "Working tree dirty?", "value": git_dirty},
            {"field": "Python", "value": platform.python_version()},
            {"field": "Evidence mode", "value": "LIVE" if LIVE_MODE else "REPLAY (retained real evidence)"},
            {"field": "Reference ID", "value": reference_manifest["reference_id"]},
            {"field": "Source snapshot SHA-256", "value": reference_manifest["source"]["snapshot_sha256"]},
            {"field": "Normalisation model", "value": normalisation_backend_decl.get("model")},
            {"field": "Live generator model", "value": generator_backend.get("model")},
            {"field": "Live validator model", "value": validator_backend.get("model")},
            {"field": "Replay normalisation model", "value": reference_manifest["normalisation"]["model"]},
            {"field": "Replay generation models", "value": [
                reference_manifest["generation"]["retained_pilot"]["generation_model"],
                reference_manifest["generation"]["walkthrough_pair"]["generation_model"],
            ]},
            {"field": "Replay validator model", "value": reference_manifest["generation"]["retained_pilot"]["validator_model"]},
            {"field": "Replay paid calls", "value": reference_manifest["paid_calls_during_replay"]},
        ], title="Execution identity")
        print("Literal runner order:", " → ".join(STAGE_NAMES))
        '''
    ),
    code(
        r'''
        artifact_fingerprints = []
        for relative_path, expected_sha in reference_manifest["artifact_sha256"].items():
            actual_sha = hashlib.sha256((REFERENCE / relative_path).read_bytes()).hexdigest()
            artifact_fingerprints.append({
                "artifact": relative_path,
                "expected SHA-256": expected_sha,
                "actual SHA-256": actual_sha,
                "status": "PASS" if actual_sha == expected_sha else "FAIL",
            })
        table(artifact_fingerprints, max_rows=20, title="Retained-reference fingerprint verification")
        assert all(row["status"] == "PASS" for row in artifact_fingerprints)
        '''
    ),
    markdown(
        r'''
        # 1. Grammar

        Scientific question: **What grammatical structure does each source descriptor license?**

        The Grammar module consumes selected EGP descriptors and produces exact, deduplicated
        six-dimensional `GrammarCell` records plus source-to-cell provenance. Phase 1 cannot see
        examples; Phase 2 can see them only after a partial Phase-1 result. Partial,
        out-of-scope, unresolved, and schema-failure results do not create canonical cells.

        Forbidden here: generator choices, item text, KCs, folds, learner outcomes, simulation
        state, and KT results.

        ### Files used by this stage

        - [`source.py`](../src/grammar_kt/grammar/source.py): verifies the external snapshot and selects declared IDs; `phase1_record` enforces field isolation.
        - [`base.yaml`](../experiments/base.yaml): active experiment declaration, including external source path/environment variable, snapshot hash, row count, and the 139-record sample inputs.
        - [`sample_ids.txt`](../modules/grammar/source/sample_ids.txt), [`sample_metadata.jsonl`](../modules/grammar/source/sample_metadata.jsonl), and [`annotation_units.jsonl`](../modules/grammar/source/annotation_units.jsonl): full declared research sample, sampling strata, and primary/repeated annotation design.
        - [`sample_ids.txt`](../reference/pipeline_walkthrough/sample_ids.txt): deterministic five-ID walkthrough selection.
        - [`sample_metadata.jsonl`](../reference/pipeline_walkthrough/sample_metadata.jsonl): retained sampling stratum and rule for each selected descriptor.
        - [`annotation_units.jsonl`](../reference/pipeline_walkthrough/annotation_units.jsonl): five primary units plus one declared repeated annotation.
        - [`normalisation.py`](../src/grammar_kt/grammar/normalisation.py): two-phase fresh-context execution and evidence retention.
        - [`phase1.txt`](../modules/grammar/normalisation/prompts/phase1.txt): descriptor-only annotation task.
        - [`phase2.txt`](../modules/grammar/normalisation/prompts/phase2.txt): example-assisted refinement after a partial result.
        - [`wrapper.txt`](../modules/grammar/normalisation/prompts/wrapper.txt): shared schema/rule context around each phase.
        - [`rulebook.md`](../modules/grammar/normalisation/rules/rulebook.md): linguistic decision rules.
        - [`model_instructions.md`](../modules/grammar/normalisation/rules/model_instructions.md): model execution constraints.
        - [`mapping_schema.json`](../modules/grammar/normalisation/configs/mapping_schema.json): structured-output contract for normalisation.
        - [`backend.yaml`](../modules/grammar/normalisation/configs/backend.yaml): configured live normalisation model/backend; replay overrides transport only.
        - [`grammar_schema.yaml`](../modules/grammar/canonical/grammar_schema.yaml): authoritative six dimensions, values, and cross-field constraints.
        - [`schema.py`](../src/grammar_kt/grammar/schema.py): loads and cross-checks the declarative schema.
        - [`canonical.py`](../src/grammar_kt/grammar/canonical.py): retains complete mappings, deduplicates cells, and writes source edges.

        ### Intended research-modular inputs

        - **Source/sample module:** external snapshot, sample IDs, sampling metadata, and
          annotation units may be exchanged to study another resource, language, population of
          descriptors, or reliability design.
        - **Normalisation protocol module:** Phase-1/Phase-2 prompts, wrapper, rulebook, model
          instructions, output schema, and backend are a coherent versioned bundle. For a new
          language, these are the primary adaptation surface: the rulebook defines the linguistic
          analysis and the prompts operationalise it. The Phase prompt paths and backend are
          experiment-configurable today. The wrapper, rulebook, instructions, and mapping schema
          are currently loaded from standard paths in `normalisation.py`; they are intended to be
          versioned research resources, but parallel language bundles would require exposing
          those paths in configuration rather than silently overwriting the English files.
        - **Canonical ontology module:** `grammar_schema.yaml` is the authoritative research
          declaration. A cross-linguistic study may replace it, but must update the mapping
          schema/prompts coherently and create a new experiment fingerprint.
        - **Stable mechanics:** `source.py`, `normalisation.py`, `schema.py`, and `canonical.py`
          enforce isolation, validation, provenance, and exact deduplication. They are not
          intended to be edited merely to select a new language or prompt.
        '''
    ),
    markdown(
        r'''
        ## 1.1 Source

        EGP records are corpus-backed curriculum descriptors: a description such as “Can form
        interrogative clauses...” plus examples and metadata. A descriptor is evidence about a
        grammatical construction, not a KC and not an item. Sampling chooses descriptors;
        normalisation interprets them.

        Primary annotation units cover every selected descriptor. Repeated units independently
        re-annotate a declared subset for stability analysis; they do not double-count source
        descriptors in the canonical inventory.

        Implementation: [`source.select_records` and `source.phase1_record`](../src/grammar_kt/grammar/source.py).
        '''
    ),
    code(
        r'''
        source_settings = read_yaml(ROOT / "experiments/base.yaml")["source"]
        selected_ids = [line for line in (REFERENCE / "sample_ids.txt").read_text(
            encoding="utf-8").splitlines() if line]
        if LIVE_MODE:
            source_path = source.resolve_source_path(source_settings)
            if not source_path.is_file():
                raise FileNotFoundError(
                    "LIVE_MODE requires the verified 1,222-row EGP snapshot. Set "
                    "GRAMMAR_KT_EGP_SOURCE=/path/to/egp_entries.jsonl. No fake fallback is used."
                )
            source_records, sample_metadata, annotation_units = source.select_records(
                source_path,
                expected_sha256=source_settings["sha256"],
                expected_record_count=int(source_settings["records"]),
                sample_ids_path=REFERENCE / "sample_ids.txt",
                expected_descriptor_count=5,
                sample_metadata_path=REFERENCE / "sample_metadata.jsonl",
                annotation_units_path=REFERENCE / "annotation_units.jsonl",
            )
            source_evidence_mode = "fresh verified external source selection"
        else:
            source_records = read_jsonl(REFERENCE / "source_records.jsonl")
            sample_metadata = read_jsonl(REFERENCE / "sample_metadata.jsonl")
            annotation_units = read_jsonl(REFERENCE / "annotation_units.jsonl")
            assert [row["egp_id"] for row in source_records] == selected_ids
            assert [row["egp_id"] for row in sample_metadata] == selected_ids
            source_evidence_mode = "retained authentic source evidence"

        declared_research_ids = {
            line for line in (ROOT / "modules/grammar/source/sample_ids.txt").read_text(
                encoding="utf-8"
            ).splitlines() if line
        }
        assert set(selected_ids) <= declared_research_ids

        table([{key: row.get(key) for key in (
            "egp_id", "supercategory", "subcategory", "guideword", "can_do"
        )} for row in source_records], title=f"Five selected EGP records — {source_evidence_mode}")
        table(sample_metadata, max_rows=10, title="Committed selection strata and tie-breaking provenance")
        '''
    ),
    code(
        r'''
        table([{"egp_id": row["egp_id"], "examples": row.get("examples", [])}
               for row in source_records],
              title="Examples (kept separate because Phase 1 cannot see them)")
        phase1_records = [source.phase1_record(row) for row in source_records]
        table(phase1_records, title="Exact Phase-1 projections for all five records")
        assert all(set(row) == set(source.PHASE1_FIELDS) for row in phase1_records)
        '''
    ),
    markdown(
        r'''
        Why these five? The committed rule maximizes methodological coverage among descriptors
        with complete real annotations and accepted active-generator evidence: present/past,
        negation, progressive aspect, polar questions, passive voice, and central modality. It
        also deliberately includes one repeated annotation and two passive descriptors that
        genuinely deduplicate. Declared sample order breaks ties; IDs were not chosen for
        convenience.

        ## 1.2 Phase-1 normalisation

        Phase 1 sees only the five projected descriptor fields above. It must decide whether an
        exact mapping is already defensible without example sentences.

        ## 1.3 Phase-2 normalisation and result classes

        - `complete`: every cell has one exact value per dimension; contributes downstream.
        - `partial`: bounded alternatives or unknowns remain; may route to Phase 2, but never contributes an exact cell.
        - `out_of_scope`: the descriptor is outside the declared grammar representation.
        - `unresolved`: evidence cannot support a mapping.
        - `schema_failure`: model output exhausted validation/retry handling.

        Phase 2 may refine only dimensions explicitly declared eligible in a partial Phase-1
        note. It cannot silently revise already-exact fields.
        '''
    ),
    code(
        r'''
        show_text("modules/grammar/canonical/grammar_schema.yaml", max_lines=70)
        show_text("modules/grammar/normalisation/configs/mapping_schema.json", max_lines=55)
        show_text("modules/grammar/normalisation/prompts/phase1.txt", max_lines=35)
        show_text("modules/grammar/normalisation/prompts/phase2.txt", max_lines=45)
        '''
    ),
    markdown(
        r'''
        Implementation: [`normalisation.normalise_one`](../src/grammar_kt/grammar/normalisation.py).

        **Live-call boundary:** the next cell invokes the configured normalisation backend only
        when `LIVE_MODE is True`. Replay uses retained outputs from
        [`normalisation_replay.json`](../reference/pipeline_walkthrough/normalisation_replay.json)
        through the same parser, schema checks, Phase-2 transition checks, and evidence writer.
        '''
    ),
    code(
        r'''
        normalisation_config = read_yaml(
            ROOT / "modules/grammar/normalisation/configs/backend.yaml"
        ) if LIVE_MODE else {
            "kind": "fixture_map",
            "response_file": str(REFERENCE / "normalisation_replay.json"),
        }
        record_by_id = {row["egp_id"]: row for row in source_records}
        normalisation_by_unit = {}
        for unit in annotation_units:
            normalisation_by_unit[unit["unit_id"]] = normalisation.normalise_one(
                record_by_id[unit["egp_id"]],
                phase1_template=(ROOT / "modules/grammar/normalisation/prompts/phase1.txt").read_text(encoding="utf-8"),
                phase2_template=(ROOT / "modules/grammar/normalisation/prompts/phase2.txt").read_text(encoding="utf-8"),
                backend_config=normalisation_config,
                max_attempts=2 if LIVE_MODE else 1,
                output=walkthrough_root / "normalisation",
                unit_id=unit["unit_id"],
            )

        primary_units = [row for row in annotation_units if row["duplicate_of"] is None]
        normalisation_results = [normalisation_by_unit[row["unit_id"]] for row in primary_units]
        table([{
            "egp_id": row["egp_id"],
            "phase1_result": result["phase1"]["result"],
            "phase2_routed": result["phase2"] is not None,
            "final_result": result["output"]["result"],
            "number_of_cells": len(result["output"].get("cells", [])),
            "note": result["output"].get("note"),
        } for row, result in zip(primary_units, normalisation_results)],
        title="Five primary normalisation results")
        '''
    ),
    markdown(
        r'''
        ### One complete evidence trail

        The question descriptor is useful because Phase 1 identifies a bounded tense
        alternative and Phase 2 uses examples to split it into exact present and past cells.
        Notice that the Phase-1 input contains no `examples` field, while Phase 2 does.
        '''
    ),
    code(
        r'''
        representative = normalisation_by_unit["u001"]
        representative_root = Path(representative["evidence_directory"])
        show_json(read_json(representative_root / "phase1/attempt-01/input.json"), "Phase-1 input")
        show_text(representative_root / "phase1/attempt-01/rendered_prompt.txt", max_lines=42)
        show_text(representative_root / "phase1/attempt-01/raw_output.txt", max_lines=30)
        show_json(read_json(representative_root / "phase1/attempt-01/validation.json"), "Phase-1 validation")
        show_json(read_json(representative_root / "phase2/attempt-01/input.json"), "Phase-2 input")
        show_json(representative["output"], "Final mapping")
        '''
    ),
    markdown(
        r'''
        ## 1.4 Repeated annotations / reliability

        Repetition asks whether a fresh annotation of the same source record changes result
        class, exact cells, dimensions, Phase-2 routing, or downstream canonical contribution.
        It is automated-model stability, not human inter-rater reliability.

        Implementation:
        [`analyse_repeated_normalisations`](../src/grammar_kt/grammar/normalisation_reliability.py).
        '''
    ),
    code(
        r'''
        reliability_summary, reliability_comparisons = analyse_repeated_normalisations(
            annotation_units, normalisation_by_unit
        )
        show_json(reliability_summary, "Repeated-annotation summary")
        table(reliability_comparisons, max_rows=10, title="Pair-level comparison")
        '''
    ),
    markdown(
        r'''
        ## 1.5 Canonical GrammarCells

        Implementation: [`canonical.build`](../src/grammar_kt/grammar/canonical.py).

        ```text
        multiple descriptor mappings
        → identical exact six-dimensional cell
        → one canonical GrammarCell
        ```

        Canonical identity depends only on the six exact dimensions. Provenance remains in an
        explicit edge table, so deduplication never erases descriptor support.
        '''
    ),
    code(
        r'''
        final_mappings = [row["output"] for row in normalisation_results]
        canonical_cells, source_cell_edges = canonical.build(final_mappings)
        table([{"canonical_cell_id": row["canonical_cell_id"], **row["cell"],
                "source_descriptor_count": row["source_descriptor_count"]}
               for row in canonical_cells], title="Canonical cell table")
        table([{key: row[key] for key in ("egp_id", "source_cell_index", "canonical_cell_id")}
               for row in source_cell_edges], title="Source → cell edges")
        deduplicated = [row for row in canonical_cells if row["source_descriptor_count"] > 1]
        table(deduplicated, title="Actual deduplication in this mini-run")
        print(f"5 descriptors → {len(final_mappings)} final mappings → "
              f"{len(source_cell_edges)} exact source-cell edges → {len(canonical_cells)} canonical cells")
        '''
    ),
    markdown(
        r'''
        ## 1.6 Source → cell provenance

        The edge table above is the non-lossy counterpart to canonical deduplication. Each edge
        retains the descriptor and its source-local cell index even when multiple edges point
        to one canonical identity.
        '''
    ),
    code(
        r'''
        contributing_ids = {row["egp_id"] for row in final_mappings
                            if row["result"] == "complete" and row["cells"]}
        check_group("Grammar", {
            "canonical cells obey the declared schema": all(
                grammar_cell(row["cell"]) is row["cell"] for row in canonical_cells),
            "canonical schema and output schema agree": consistency_report()["status"] == "PASS",
            "source→cell provenance is retained": all(
                row["egp_id"] in contributing_ids for row in source_cell_edges),
            "only complete mappings contribute": all(
                row["result"] == "complete" for row in final_mappings
                if row["egp_id"] in contributing_ids),
            "the two passive descriptors genuinely deduplicate": (
                len(deduplicated) == 1 and deduplicated[0]["source_descriptor_count"] == 2),
        })
        '''
    ),
    markdown(
        r'''
        > **What should I inspect after Grammar?**
        >
        > - Were mappings complete or partial for linguistically sensible reasons?
        > - Did Phase 2 refine only declared eligible dimensions?
        > - Do the repeated units preserve the same downstream inventory?
        > - Why did the passive descriptors collapse while the question descriptor expanded?
        > - Are the six dimensions sufficient for these source phenomena?
        '''
    ),
    markdown(
        r'''
        # 2. Measurement

        Scientific question: **Under which generator-independent structural conditions is a
        GrammarCell elicited?**

        A `GrammarCell` says what grammatical structure is represented. A
        `MeasurementOpportunity` says how that structure is measured: predicate class,
        subject agreement conditions, WH role, and imperative subtype. One cell may therefore
        expand into several opportunities before any wording is generated.

        Forbidden here: prompts, item text, generator IDs, KC labels or policy, structural
        folds, temporal splits, learner state, and model outcomes.

        ### Files used by this stage

        - [`operations.py`](../src/grammar_kt/measurement/operations.py): deterministically derives operations and the agreement site from a cell plus structural conditions.
        - [`opportunities.py`](../src/grammar_kt/measurement/opportunities.py): expands cells into stable, deduplicated MeasurementOpportunities.
        - [`default.json`](../modules/measurement/opportunities/default.json): turns predicate-class contrasts and agreement variants on or off.

        Implementations:
        [`build_measurement_opportunities`](../src/grammar_kt/measurement/opportunities.py),
        [`derive_operations`](../src/grammar_kt/measurement/operations.py), and
        [`derive_agreement_site`](../src/grammar_kt/measurement/operations.py).

        ### Intended research-modular inputs

        - `default.json` is the current data-level measurement-policy module: it selects
          predicate-class contrasts and agreement variants.
        - The canonical schema inherited from Grammar defines which structural categories can
          reach Measurement.
        - English operation, agreement, WH, and imperative derivations currently reside in
          `operations.py` and `opportunities.py`. They are scientifically modular in the sense
          that another language can supply a versioned implementation, but they are **not**
          currently runtime-swappable JSON. Such a port should add tests and an explicit
          implementation/version identifier rather than conditionals hidden in the notebook.
        - Opportunity IDs and record validation are stable mechanics; generator prompts are
          deliberately not measurement inputs.
        '''
    ),
    markdown(
        r'''
        ## 2.1 Structural conditions

        Conditions fix predicate class, subject agreement, WH role, and imperative subtype.

        ## 2.2 Derived operations

        Operations follow deterministically from the cell and conditions.

        ## 2.3 Agreement site

        Operations are consequences of the fixed target and conditions, not labels supplied by
        a generator. For example, the actual present lexical polar question below requires
        `do_support` and `operator_inversion`; the copular contrast has inversion without
        DO-support. The progressive negative has `progressive` and `negation`, the passive has
        `be_passive`, and the modal has `central_modal`.
        '''
    ),
    code(
        r'''
        measurement_config = read_json(ROOT / "modules/measurement/opportunities/default.json")
        show_json(measurement_config, "Active opportunity-expansion configuration")
        opportunities = build_measurement_opportunities(canonical_cells, measurement_config)
        opportunity_by_id = {row["measurement_opportunity_id"]: row for row in opportunities}

        representative_ids = [
            "OPP_DA35D6B379FF278E",  # lexical present polar question
            "OPP_44E2F55FC429A74E",  # copular contrast for that question
            "OPP_7E1E0B371E1A07AD",  # progressive negative
            "OPP_772FF9B236FFEC3C",  # passive
            "OPP_DF15F4EA275D224B",  # modal would
        ]
        representative_opportunities = [opportunity_by_id[value] for value in representative_ids]
        table([{
            "opportunity": row["measurement_opportunity_id"],
            "cell": row["cell"],
            "structural conditions": row["structural_conditions"],
            "derived operations": derive_operations(row["cell"], row["structural_conditions"]),
            "agreement site": derive_agreement_site(row["cell"], row["structural_conditions"]),
        } for row in representative_opportunities], max_rows=10,
        title="Actual structural contrasts in the mini-run")
        '''
    ),
    markdown(
        r'''
        ## 2.4 MeasurementOpportunity construction

        ```text
        GrammarCell
            → baseline opportunity
            → predicate-class contrasts, where licensed
            → agreement variants, where agreement is measurable
            → WH/imperative subtypes, where present
        ```

        This is still a latent measurement bank: no sentence, dialogue, answer, KC, or fold has
        entered the record. Expansion is exhaustive under the active config; only the display
        is sampled.

        ## 2.5 Opportunity expansions and groupings

        Expansion is one-to-many by structural contrast; identical condition sets deduplicate
        by stable opportunity identity.

        ## 2.6 Opportunity-bank audit
        '''
    ),
    code(
        r'''
        def counts_for(path):
            return dict(sorted(Counter(path(row) for row in opportunities).items(), key=lambda pair: str(pair[0])))

        table([
            {"summary": "canonical cells", "value": len(canonical_cells)},
            {"summary": "measurement opportunities", "value": len(opportunities)},
            {"summary": "opportunities per cell", "value": counts_for(lambda row: row["canonical_cell_id"])},
            {"summary": "coverage reasons", "value": dict(sorted(Counter(
                reason for row in opportunities for reason in row["coverage_reasons"]).items()))},
            {"summary": "predicate classes", "value": counts_for(lambda row: row["structural_conditions"]["predicate_class"])},
            {"summary": "agreement conditions", "value": counts_for(lambda row: (
                row["structural_conditions"]["subject_person"], row["structural_conditions"]["subject_number"]))},
            {"summary": "WH roles", "value": counts_for(lambda row: row["structural_conditions"]["wh_role"])},
            {"summary": "imperative subtypes", "value": counts_for(lambda row: row["structural_conditions"]["imperative_subtype"])},
        ], title="Complete mini-bank audit")

        table([{
            "opportunity_id": row["measurement_opportunity_id"],
            "cell_id": row["canonical_cell_id"],
            "predicate": row["structural_conditions"]["predicate_class"],
            "subject": f'{row["structural_conditions"]["subject_person"]}/{row["structural_conditions"]["subject_number"]}',
            "WH role": row["structural_conditions"]["wh_role"],
            "operations": row["expected_operations"],
            "coverage reason": row["coverage_reasons"],
        } for row in opportunities], max_rows=17, title="All 17 opportunities (compact view)")
        '''
    ),
    code(
        r'''
        measurement_keys = set().union(*(nested_keys(row) for row in opportunities))
        check_group("Measurement", {
            "all canonical cells are represented": (
                {row["canonical_cell_id"] for row in opportunities}
                == {row["canonical_cell_id"] for row in canonical_cells}),
            "no generator fields": not ({"generator_id", "item_family", "content", "target_answer"} & measurement_keys),
            "no KC fields": not ({"kc_id", "kc_ids", "policy_id"} & measurement_keys),
            "no fold fields": not ({"fold", "fold_id", "canonical_split", "dataset_split"} & measurement_keys),
            "operations reconstruct deterministically": all(
                row["expected_operations"] == derive_operations(row["cell"], row["structural_conditions"])
                for row in opportunities),
            "every opportunity obeys its schema": all(
                measurement_opportunity(row) is row for row in opportunities),
        })
        '''
    ),
    markdown(
        r'''
        > **What should I inspect after Measurement?**
        >
        > - Why did one cell create several opportunities?
        > - Which operations change with lexical versus copular predicates?
        > - Where does subject agreement live for each auxiliary configuration?
        > - Are any useful WH or imperative subtypes absent simply because this five-record
        >   sample does not contain them?
        '''
    ),
    markdown(
        r'''
        # 3. Dataset Generation

        Scientific question: **Can a model surface a fixed MeasurementOpportunity as a usable
        learner exercise, and can an independent blind evaluator recover the intended
        structure?**

        The generator receives the exact `GrammarCell`, structural conditions, expected
        operations, and format constraints. It never receives KC IDs, a KC policy, structural
        fold, temporal split, simulation state, or KT results.

        ### Files used by this stage

        - [`generators.py`](../src/grammar_kt/generation/generators.py): renders the fixed interface and invokes standalone/dialogue backends.
        - [`items.py`](../src/grammar_kt/generation/items.py): defines generator-independent candidate identity and item-bank records.
        - [`validation.py`](../src/grammar_kt/generation/validation.py): hard checks, blind reconstruction, and separate quality diagnostics.
        - [`llm_standalone_v0.yaml`](../modules/generation/generators/llm_standalone_v0.yaml): standalone mode, constraints, prompt/schema/backend references.
        - [`llm_dialogue_v0.yaml`](../modules/generation/generators/llm_dialogue_v0.yaml): dialogue mode and its constraints.
        - [`llm_standalone_v0.txt`](../modules/generation/prompts/llm_standalone_v0.txt): standalone generation prompt.
        - [`llm_dialogue_v0.txt`](../modules/generation/prompts/llm_dialogue_v0.txt): dialogue generation prompt.
        - [`generator_instructions.md`](../modules/generation/prompts/generator_instructions.md): shared generator instructions.
        - [`standalone_output_schema.json`](../modules/generation/generators/standalone_output_schema.json) and [`dialogue_output_schema.json`](../modules/generation/generators/dialogue_output_schema.json): mode-specific structured-output contracts.
        - [`blind_v0.yaml`](../modules/generation/validation/blind_v0.yaml): evaluator configuration and retry/repetition policy.
        - [`structural_prompt.txt`](../modules/generation/validation/structural_prompt.txt) and [`structural_schema.json`](../modules/generation/validation/structural_schema.json): blind structural reconstruction.
        - [`quality_prompt.txt`](../modules/generation/validation/quality_prompt.txt) and [`quality_schema.json`](../modules/generation/validation/quality_schema.json): non-acceptance quality diagnostics.
        - [`evaluator_instructions.md`](../modules/generation/validation/evaluator_instructions.md): evaluator constraints.

        ### Intended research-modular inputs

        - **Generator condition:** each generator YAML chooses a mode, prompt, instructions,
          output schema, constraints, and backend. New languages or exercise formats should be
          introduced as new named configurations while preserving the opportunity interface.
        - **Validation condition:** evaluator config, blind structural prompt/schema, quality
          prompt/schema, and evaluator instructions are separately replaceable. A language port
          must keep the structural evaluator's ontology aligned with the Grammar/Measurement
          declarations without exposing the intended target.
        - **Stable mechanics:** `generators.py`, `items.py`, and `validation.py` enforce the fixed
          target, candidate identity, hard checks, blind boundary, and acceptance comparison.
          KC policy, folds, and simulation state are never legitimate generator modules.
        '''
    ),
    markdown(
        r'''
        ## 3.1 Fixed input, prompts, and output schemas

        Implementations:
        [`render_generation_prompt` and `generate_items`](../src/grammar_kt/generation/generators.py).
        The excerpts make the model boundary auditable without dumping every file.
        '''
    ),
    code(
        r'''
        show_text("modules/generation/prompts/llm_standalone_v0.txt", max_lines=45)
        show_text("modules/generation/prompts/llm_dialogue_v0.txt", max_lines=45)
        show_text("modules/generation/generators/standalone_output_schema.json", max_lines=45)
        show_text("modules/generation/generators/dialogue_output_schema.json", max_lines=55)
        '''
    ),
    markdown(
        r'''
        ## 3.2 Standalone generation

        Standalone prompts request one self-contained completion exercise.

        ## 3.3 Dialogue generation

        Six retained accepted examples are replayed: four standalone and two dialogue. The
        first standalone/dialogue pair shares one opportunity, making format invariance visible.

        **Live-call boundary:** when `LIVE_MODE is True`, this cell calls the configured
        generator backends. In replay it uses authentic retained outputs from
        [`generation_replay.json`](../reference/pipeline_walkthrough/generation_replay.json).
        A failed live candidate remains rejected; the notebook never fabricates an item to hit
        a quota.
        '''
    ),
    code(
        r'''
        generation_replay = read_json(REFERENCE / "generation_replay.json")
        retained_model_records = read_json(REFERENCE / "validation_replay.json")["records"]
        retained_origin_by_key = {
            (row["measurement_opportunity_id"], row["generator_id"]): row
            for row in retained_model_records
        }
        generation_plan = {
            "standalone": ["OPP_DA35D6B379FF278E", "OPP_7E1E0B371E1A07AD",
                           "OPP_DF15F4EA275D224B", "OPP_F1BFD8A774DAED74"],
            "dialogue": ["OPP_DA35D6B379FF278E", "OPP_772FF9B236FFEC3C"],
        }

        generated_runs = []
        for mode, opportunity_ids in generation_plan.items():
            config_path = ROOT / f"modules/generation/generators/llm_{mode}_v0.yaml"
            config = read_yaml(config_path)
            if not LIVE_MODE:
                config["backend_config"] = {
                    "kind": "fixture_map",
                    "responses": generation_replay[mode],
                }
                config["max_attempts"] = 1
            generated_runs.append(generate_items(
                [opportunity_by_id[value] for value in opportunity_ids], config,
                evidence_root=walkthrough_root / "generation" / mode,
            ))

        candidate_items = sorted(
            [item for run in generated_runs for item in run["candidates"]],
            key=lambda row: row["item_id"],
        )
        generation_rejections = [row for run in generated_runs for row in run["rejections"]]

        def surface(item):
            if item["item_family"] == "dialogue_completion":
                turns = " / ".join(f'{turn["speaker"]}: {turn["text"]}' for turn in item["content"]["turns"])
                return f'{turns} / {item["content"]["learner_prompt"]} → {item["target_answer"]}'
            return f'{item["content"]["prompt"]} → {item["target_answer"]}'

        table([{
            "item_id": item["item_id"],
            "retained origin item": retained_origin_by_key[
                (item["measurement_opportunity_id"], item["generator_id"])
            ]["origin_item_id"] if not LIVE_MODE else "fresh live candidate",
            "opportunity_id": item["measurement_opportunity_id"],
            "family": item["item_family"],
            "generation model": retained_origin_by_key[
                (item["measurement_opportunity_id"], item["generator_id"])
            ]["provenance"]["generation_model"] if not LIVE_MODE else item["generation_metadata"]["backend"].get("model"),
            "exercise → answer": surface(item),
        } for item in candidate_items], max_rows=10,
        title=f"Generated candidates ({'live' if LIVE_MODE else 'retained real model evidence'})")
        print("Generation rejections:", len(generation_rejections))
        '''
    ),
    code(
        r'''
        target_keys = {"canonical_cell_id", "cell", "structural_conditions", "expected_operations"}
        generator_forbidden = {
            "kc", "kc_id", "kc_ids", "kc_policy", "policy_id", "fold", "fold_id",
            "canonical_split", "dataset_split", "kt", "simulation_state",
        }
        for item in candidate_items:
            exact_input = item["generation_metadata"]["input_opportunity"]
            rendered = item["generation_metadata"]["rendered_prompt"]
            assert target_keys <= set(exact_input)
            assert not (nested_keys(exact_input) & generator_forbidden)
            assert not any(label in rendered for label in ("KC_", "canonical_split", "dataset_split"))
        print("PASS — fixed structural target is present and KC/fold/KT fields are absent.")
        '''
    ),
    markdown(
        r'''
        ## 3.4 Candidate item schema

        Candidate identity includes the concrete surface form and its fixed opportunity
        reference.

        ## 3.5 Hard validation

        Hard validation checks stable identity, schema, exact opportunity provenance, known
        generator, content shape, and leakage. Structural acceptance then compares the intended
        opportunity against an independently reconstructed structure. Naturalness, ambiguity,
        and pedagogical suitability are reported separately; they do not redefine grammar.

        Implementations: [`candidate_item`](../src/grammar_kt/generation/items.py) and
        [`validate_items`](../src/grammar_kt/generation/validation.py).

        ## 3.6 Blind structural reconstruction

        The evaluator sees visible exercise content, the proposed learner response, and allowed
        surface variants—but not the intended cell, operations, conditions, or IDs.

        ## 3.7 Quality diagnostics

        Quality scores naturalness and pedagogical properties in a separate record. A quality
        observation cannot turn a structural mismatch into an accepted item.
        '''
    ),
    code(
        r'''
        show_text("modules/generation/validation/structural_prompt.txt", max_lines=45)
        show_text("modules/generation/validation/structural_schema.json", max_lines=60)
        show_text("modules/generation/validation/quality_prompt.txt", max_lines=35)
        show_text("modules/generation/validation/quality_schema.json", max_lines=70)
        '''
    ),
    markdown(
        r'''
        **Live-call boundary:** the next cell calls structural and quality evaluator backends
        only in live mode. Replay indexes retained real evaluator outputs by the newly computed
        item IDs and runs them through the active parsers and comparison logic.
        '''
    ),
    code(
        r'''
        retained_validation = read_json(REFERENCE / "validation_replay.json")["records"]
        validation_by_key = {
            (row["measurement_opportunity_id"], row["generator_id"]): row
            for row in retained_validation
        }
        if LIVE_MODE:
            validation_config = read_yaml(ROOT / "modules/generation/validation/blind_v0.yaml")
            validation_config["repeat_first_n"] = 0
        else:
            structure_responses = {}
            quality_responses = {}
            for item in candidate_items:
                retained = validation_by_key[(item["measurement_opportunity_id"], item["generator_id"])]
                structure_responses[item["item_id"]] = retained["structural"]
                quality_responses[item["item_id"]] = retained["quality"]
            validation_config = {
                "evaluator_id": "blind_reconstruction_v0_retained_real_replay",
                "structural_backend_config": {"kind": "fixture_map", "responses": structure_responses},
                "quality_backend_config": {"kind": "fixture_map", "responses": quality_responses},
                "known_generators": ["llm_standalone_v0", "llm_dialogue_v0"],
                "max_attempts": 1,
                "repeat_first_n": 0,
            }

        validated = validate_items(
            candidate_items, opportunities, validation_config,
            evidence_root=walkthrough_root / "validation",
        )
        accepted_items = validated["accepted"]
        table([{
            "item_id": item["item_id"],
            "opportunity_id": item["measurement_opportunity_id"],
            "family": item["item_family"],
            "hard checks": item["validation_metadata"]["hard_checks"]["status"],
            "cell match": item["validated_structure"]["cell"] == opportunity_by_id[item["measurement_opportunity_id"]]["cell"],
            "operations match": set(item["validated_structure"]["operations"]) == set(opportunity_by_id[item["measurement_opportunity_id"]]["expected_operations"]),
            "predicate match": item["validated_structure"]["predicate_class"] == opportunity_by_id[item["measurement_opportunity_id"]]["structural_conditions"]["predicate_class"],
            "agreement match": item["validated_structure"]["agreement_site"] == derive_agreement_site(opportunity_by_id[item["measurement_opportunity_id"]]["cell"], opportunity_by_id[item["measurement_opportunity_id"]]["structural_conditions"]),
            "naturalness": item["quality_diagnostics"]["naturalness"],
            "ambiguity": item["quality_diagnostics"]["answer_ambiguity"],
            "pedagogical suitability": item["quality_diagnostics"]["pedagogical_suitability"],
            "final acceptance": True,
        } for item in accepted_items], max_rows=10, title="Validation summary")
        print("Rejected candidates:", len(validated["rejected"]))
        '''
    ),
    markdown(
        r'''
        ## 3.8 Accepted and rejected items

        ### What the blind evaluator actually sees

        The intended cell, opportunity ID, expected operations, KC labels, and folds are hidden.
        Below, one surface exercise and learner response are compared with the target only
        *after* reconstruction.
        '''
    ),
    code(
        r'''
        representative_item = next(
            item for item in accepted_items if item["generator_id"] == "llm_dialogue_v0"
            and item["measurement_opportunity_id"] == "OPP_DA35D6B379FF278E"
        )
        blind_input_path = (
            walkthrough_root / "validation" / representative_item["item_id"]
            / "structural" / "repetition-01" / "blind_input.json"
        )
        show_json(read_json(blind_input_path), "Evaluator input — intended target hidden")
        intended_opportunity = opportunity_by_id[representative_item["measurement_opportunity_id"]]
        table([{
            "view": "intended structure",
            "cell": intended_opportunity["cell"],
            "operations": intended_opportunity["expected_operations"],
            "predicate": intended_opportunity["structural_conditions"]["predicate_class"],
            "agreement": derive_agreement_site(intended_opportunity["cell"], intended_opportunity["structural_conditions"]),
        }, {
            "view": "blind reconstruction",
            "cell": representative_item["validated_structure"]["cell"],
            "operations": representative_item["validated_structure"]["operations"],
            "predicate": representative_item["validated_structure"]["predicate_class"],
            "agreement": representative_item["validated_structure"]["agreement_site"],
        }], title="Intended versus blindly reconstructed")
        '''
    ),
    markdown(
        r'''
        ## 3.9 Cross-format invariance

        Surface identity is format-specific, but the latent target is not. The pair below has
        the same opportunity, canonical cell, and structural target; it has different item IDs
        and surface content.
        '''
    ),
    code(
        r'''
        paired = [item for item in accepted_items
                  if item["measurement_opportunity_id"] == "OPP_DA35D6B379FF278E"]
        table([{
            "item_id": item["item_id"],
            "format": item["item_family"],
            "measurement_opportunity_id": item["measurement_opportunity_id"],
            "canonical_cell_id": item["canonical_cell_id"],
            "structural target": item["validated_structure"],
            "surface": surface(item),
        } for item in paired], title="One latent target, two formats")
        '''
    ),
    code(
        r'''
        accepted_by_id = {row["item_id"]: row for row in accepted_items}
        check_group("Generation", {
            "generator target fixed before generation": all(
                item["generation_metadata"]["input_opportunity"]
                == opportunity_by_id[item["measurement_opportunity_id"]]
                for item in candidate_items),
            "no KC/fold leakage": all(
                not (nested_keys(item["generation_metadata"]) & FORBIDDEN_GENERATION_KEYS)
                for item in candidate_items),
            "blind target hidden": all(
                item["validation_metadata"]["intended_target_hidden_from_evaluator"]
                for item in accepted_items),
            "accepted structure matches opportunity": all(
                item["validated_structure"]["cell"]
                == opportunity_by_id[item["measurement_opportunity_id"]]["cell"]
                and set(item["validated_structure"]["operations"])
                == set(opportunity_by_id[item["measurement_opportunity_id"]]["expected_operations"])
                for item in accepted_items),
            "format pair preserves one latent target": (
                len(paired) == 2
                and len({item["item_id"] for item in paired}) == 2
                and len({item["canonical_cell_id"] for item in paired}) == 1),
        })
        '''
    ),
    markdown(
        r'''
        > **What should I inspect after Generation?**
        >
        > - Does each surface exercise genuinely elicit the intended construction?
        > - Did blind reconstruction agree on cell, operations, predicate class, and agreement?
        > - Is each item natural, unambiguous, and pedagogically suitable?
        > - Does the standalone/dialogue pair preserve the target while varying only surface form?
        '''
    ),
    markdown(
        r'''
        # 4. Knowledge Representation

        Scientific question: **Which structural hypotheses form an identifiable, supported KC
        inventory on development data, and how does that frozen inventory project to items?**

        Candidate KCs are hypotheses, not assumed cognitive truth. Discovery and selection read
        canonical structure and MeasurementOpportunities from development only. They do not
        read generated text, learner outcomes, the simulator oracle, or KT results.

        ### Files used by this stage

        - [`candidates.py`](../src/grammar_kt/knowledge/candidates.py): declares, activates, and diagnoses KC hypotheses on development structure.
        - [`selection.py`](../src/grammar_kt/knowledge/selection.py): partitions structure, constructs obligations, solves deterministic greedy set cover, freezes, and evaluates.
        - [`policy.py`](../src/grammar_kt/knowledge/policy.py): applies a frozen structural policy and projects items via opportunities.
        - [`qmatrix.py`](../src/grammar_kt/knowledge/qmatrix.py): materializes item–KC matrices, edges, and support diagnostics.
        - [`structural_v0.json`](../modules/knowledge/selection/candidate_families/structural_v0.json): candidate-family declaration.
        - [`marked_operational_v0.json`](../modules/knowledge/selection/obligations/marked_operational_v0.json): defines salient facts that selection must cover.
        - [`deterministic_v0.json`](../modules/knowledge/selection/configs/deterministic_v0.json): support thresholds and selection inputs.
        - [`core.json`](../modules/knowledge/selection/fixtures/core.json): controlled 12-cell development/holdout selection demonstration.
        - [`factorized.json`](../modules/knowledge/policies/factorized.json), [`factorized_plus_interactions.json`](../modules/knowledge/policies/factorized_plus_interactions.json), and [`full_cell.json`](../modules/knowledge/policies/full_cell.json): predefined comparison policies; they are linked controls, not silently substituted below.
        - [`fold_manifest.json`](../reference/pipeline_walkthrough/fold_manifest.json): exact structural split for this five-cell mini-run.

        ### Intended research-modular inputs

        - **Selection hypotheses:** candidate-family JSON, obligation-policy JSON, selector config,
          and structural fold are the intended discovery/selection interventions. They can vary
          across ontology experiments while `selection.py` holds the algorithm fixed.
        - **Frozen ontology:** `knowledge_selection` produces a selected-policy artifact. The
          `knowledge` stage may instead receive a named predefined control policy, but it must
          never switch policies implicitly or refit on holdouts.
        - **Projection:** `policy.py` is stable rule-application machinery. The accepted item bank
          enters only through MeasurementOpportunity references; generated wording is not a
          configurable KC-discovery input.
        - **Q-matrix:** there is intentionally no independent Q-matrix policy file. `qmatrix.py`
          mechanically materializes the frozen projection, so any research change must be
          attributed upstream to the item bank or ontology.
        '''
    ),
    markdown(
        r'''
        ## 4.1 Structural folds

        - **Development** is available for KC discovery and selection.
        - **Compositional holdout** combines salient components already observed in development.
        - **Novel-feature holdout** contains a genuinely unseen salient component.

        A fold is attached after intrinsic cells/items exist; it is not part of a
        GrammarCell or MeasurementOpportunity. The mini-run intentionally places the past
        question in compositional holdout and `would` in novel-feature holdout.
        '''
    ),
    code(
        r'''
        mini_fold = load_fold(REFERENCE / "fold_manifest.json")
        mini_assignment = assignment_for_cells(canonical_cells, mini_fold)
        mini_fold_rows = fold_rows(canonical_cells, mini_fold)
        table([{
            "cell": row["canonical_cell_id"],
            "split": row["split"],
            "reason": (
                "selection evidence" if row["split"] == "development"
                else "unseen combination of observed components" if row["split"] == "compositional_holdout"
                else "modal=would is unseen in development"
            ),
        } for row in mini_fold_rows], title="Five-cell structural split")
        table([{
            "split": split,
            "cells": sum(row["split"] == split for row in mini_fold_rows),
            "example": next(row["canonical_cell_id"] for row in mini_fold_rows if row["split"] == split),
        } for split in ("development", "compositional_holdout", "novel_feature_holdout")],
        title="Structural-fold counts and examples")
        '''
    ),
    markdown(
        r'''
        ## 4.2 Candidate KC hypotheses — an explicit dataset boundary

        > **Controlled methodology demonstration (not derived from the five EGP records).**
        > The five-cell walkthrough is too small to identify and select a useful general KC
        > inventory. The following committed 12-cell development/holdout fixture demonstrates
        > the actual selection algorithm. After the policy is frozen, subsection 4.9 applies
        > that exact selected policy to the real five-record mini-run. No predefined policy is
        > loaded between these steps.

        The controlled fixture contains primitive and compositional contrasts (including
        perfect-progressive, perfect-passive, and negative imperative) needed to make candidate
        activation, support, obligations, and holdout semantics meaningful.
        '''
    ),
    code(
        r'''
        selection_fixture = read_json(ROOT / "modules/knowledge/selection/fixtures/core.json")
        selection_config = read_json(ROOT / "modules/knowledge/selection/configs/deterministic_v0.json")
        selection_cells = selection_fixture["canonical_cells"]
        selection_opportunities = build_measurement_opportunities(
            selection_cells, selection_fixture["measurement_config"]
        )
        selection_partition = selection.partition_inputs(
            selection_cells, selection_opportunities, selection_fixture["cell_splits"]
        )
        table(selection_fixture["cell_splits"], max_rows=20,
              title="Controlled selection fixture: cell-level folds")
        table([{
            "split": split,
            "cells": sum(row["split"] == split for row in selection_fixture["cell_splits"]),
            "opportunities": sum(
                selection_partition["split_by_id"][row["canonical_cell_id"]] == split
                for row in selection_opportunities),
        } for split in ("development", "compositional_holdout", "novel_feature_holdout")],
        title="Controlled selection fixture counts")
        '''
    ),
    markdown(
        r'''
        ## 4.3 Candidate activation

        Each candidate states an activation rule, the obligations it represents, which
        canonical dimensions it concerns, interaction order, and whether support makes it
        eligible. Activation vectors are evaluated over development MeasurementOpportunities.

        Implementation: [`discover_candidates`](../src/grammar_kt/knowledge/candidates.py).

        ## 4.4 Support diagnostics
        '''
    ),
    code(
        r'''
        show_text("modules/knowledge/selection/candidate_families/structural_v0.json", max_lines=55)
        show_text("modules/knowledge/selection/obligations/marked_operational_v0.json", max_lines=45)
        show_text("modules/knowledge/policies/factorized.json", max_lines=35)
        discovery = kc_candidates.discover_candidates(
            selection_partition["development_cells"],
            selection_partition["development_opportunities"],
            selection_config,
        )
        diagnostic_by_candidate = {row["candidate_id"]: row for row in discovery["diagnostics"]}
        table([{
            "kc_id": row["kc_id"],
            "name": row["name"],
            "activation_rule": row["activation_rule"],
            "represents": row["represents"],
            "canonical_dimensions": row["canonical_dimensions"],
            "interaction_order": row["interaction_order"],
            "selection_eligible": diagnostic_by_candidate[row["candidate_id"]]["base_eligible"],
        } for row in discovery["candidates"]], max_rows=18,
        title="Representative candidate definitions")
        '''
    ),
    code(
        r'''
        development_opp_ids = sorted(
            row["measurement_opportunity_id"]
            for row in selection_partition["development_opportunities"]
        )[:12]
        candidate_rows = [row for row in discovery["candidates"]
                          if diagnostic_by_candidate[row["candidate_id"]]["base_eligible"]][:12]
        activation_lookup = {
            (row["candidate_id"], row["measurement_opportunity_id"]): row["activated"]
            for row in discovery["activations"]
        }
        activation_matrix = []
        for candidate in candidate_rows:
            activation_matrix.append({
                "candidate KC": candidate["kc_id"],
                **{opp_id.removeprefix("OPP_")[:6]: "✓"
                   if activation_lookup[(candidate["candidate_id"], opp_id)] else ""
                   for opp_id in development_opp_ids},
            })
        table(activation_matrix, max_rows=15,
              title="Candidate KC × development opportunity (representative window)")
        table([{
            "kc_id": row["kc_id"],
            "opportunity support": row["development_opportunity_support"],
            "cell support": row["development_cell_support"],
            "descriptor support": row["development_source_descriptor_support"],
            "eligible": row["base_eligible"],
            "rejection reasons": row["rejection_reasons"],
        } for row in discovery["diagnostics"]], max_rows=25,
        title="Development-only support diagnostics")
        '''
    ),
    markdown(
        r'''
        ## 4.5 Equivalence classes

        Two candidates are unidentifiable from development only when development evidence
        cannot distinguish both their activation behaviour **and** the obligations they
        represent. Equal activation alone is deliberately insufficient: two facts may co-occur
        in a small sample while remaining different hypotheses.
        '''
    ),
    code(
        r'''
        non_singleton_equivalence = [
            row for row in discovery["equivalence_classes"]
            if row["unidentifiable_from_development"]
        ]
        if non_singleton_equivalence:
            table(non_singleton_equivalence, max_rows=20,
                  title="Actual non-singleton equivalence classes")
        else:
            display(Markdown(
                "> **No non-singleton equivalence classes occurred in this run.**\n\n"
                "> Every declared candidate had a distinct combination of development activation "
                "and represented obligations."
            ))
        '''
    ),
    markdown(
        r'''
        ## 4.6 Development obligations

        ```text
        development cell → salient facts → obligation IDs
        ```

        Selection is a deterministic set-cover problem. Each eligible candidate covers the
        obligations whose cells it activates on and whose facts it explicitly represents. At
        each step the selector maximizes new coverage, then resolves ties by declared
        complexity/granularity/KC ID. A reverse pass removes redundant selected candidates
        without losing exact coverage.

        ## 4.7 Selection trace and greedy coverage

        Implementations: [`build_obligations` and `select_inventory`](../src/grammar_kt/knowledge/selection.py).
        '''
    ),
    code(
        r'''
        obligation_rows = selection.build_obligations(discovery)
        table([{
            "development cell": cell_id,
            "salient facts": facts,
            "obligation IDs": [row["obligation_id"] for row in obligation_rows
                               if row["canonical_cell_id"] == cell_id],
        } for cell_id, facts in sorted(discovery["development_cell_facts"].items())],
        max_rows=15, title="Facts become explicit coverage obligations")

        selected_inventory = selection.select_inventory(discovery, selection_config)
        cumulative = 0
        trace_rows = []
        for step in selected_inventory["selection_trace"]:
            new_count = len(step.get("new_obligation_ids", []))
            if step["action"] == "greedy_add":
                cumulative += new_count
            trace_rows.append({
                "step": step["step"],
                "action": step["action"],
                "KC added/pruned": step["kc_id"],
                "new obligations covered": new_count if step["action"] == "greedy_add" else "—",
                "total greedy coverage": cumulative,
            })
        table(trace_rows, max_rows=30, title="Deterministic selection trace")
        show_json(selected_inventory["objective"], "Set-cover objective")
        '''
    ),
    markdown(
        r'''
        ## 4.8 Frozen policy

        The selected rules are serialized conceptually at the freeze boundary before any
        holdout evaluation. Metadata records the evidence that selection did *not* read.

        Implementation: [`compile_policy` and `evaluate_after_freeze`](../src/grammar_kt/knowledge/selection.py).

        ## 4.9 Holdout evaluation
        '''
    ),
    code(
        r'''
        selected_policy = selection.compile_policy(
            selected_inventory, selection_partition["development_cell_ids"]
        )
        selection_evaluation = selection.evaluate_after_freeze(
            selected_policy,
            selection_opportunities,
            selection_partition["split_by_id"],
            selection_partition["development_cell_ids"],
            discovery["obligation_policy"],
        )
        table([{
            "kc_id": rule["kc_id"],
            "name": rule["name"],
            "activation_rule": rule["activation_rule"],
        } for rule in selected_policy["rules"]], max_rows=30,
        title="Final selected and frozen policy")
        show_json(selected_policy["selection_metadata"], "Freeze metadata")
        table([{"split": split, **values}
               for split, values in selection_evaluation["split_results"].items()],
              title="Frozen-policy holdout evaluation")
        table(selection_evaluation["split_audit"]["cells"], max_rows=15,
              title="Compositional versus novel-feature semantic audit")
        '''
    ),
    markdown(
        r'''
        ## 4.10 Mini-run item → KC projection

        We now return to the authentic five-record mini-run. This is the exact policy selected
        above—not [`factorized.json`](../modules/knowledge/policies/factorized.json) or another
        fixture. Projection follows:

        ```text
        surface item → MeasurementOpportunity → frozen structural policy → KC set
        ```

        The LLM does not read item text and guess KCs. A standalone/dialogue pair sharing one
        opportunity therefore receives identical KCs by construction.

        Implementations: [`policy.project_items`](../src/grammar_kt/knowledge/policy.py) and
        [`qmatrix.build`](../src/grammar_kt/knowledge/qmatrix.py).
        '''
    ),
    code(
        r'''
        accepted_items = annotate_items(accepted_items, mini_assignment)
        item_projections, projected_kc_cards = policy.project_items(
            accepted_items, opportunities, selected_policy
        )
        projection_by_item = {row["item_id"]: row for row in item_projections}
        table([{
            "item": row["item_id"],
            "measurement opportunity": row["measurement_opportunity_id"],
            "canonical cell": row["canonical_cell_id"],
            "format": accepted_by_id[row["item_id"]]["item_family"],
            "KCs": row["kc_ids"],
        } for row in item_projections], max_rows=10, title="Mechanical item → KC projection")
        paired_kc_sets = {
            tuple(projection_by_item[item["item_id"]]["kc_ids"]) for item in paired
        }
        print("Standalone/dialogue pair has identical KCs:", len(paired_kc_sets) == 1)
        '''
    ),
    markdown(
        r'''
        ## 4.11 Q-matrix and diagnostics

        The human-readable binary matrix and explicit edges are two views of the same
        projection. Density, row width, KC support, low-support KCs, identical columns, and
        uncovered items are diagnostics—not grounds to change the already-frozen policy.
        '''
    ),
    code(
        r'''
        q_kc_ids, q_rows, q_edges, q_audit = qmatrix.build(
            accepted_items, projected_kc_cards, item_projections
        )
        q_human = [{"item": item_id, **dict(zip(q_kc_ids, values))}
                   for item_id, values in q_rows]
        table(q_human, max_rows=10, title="Human-readable Q-matrix")
        table(q_edges, columns=["item_id", "kc_id", "activation_scope"],
              max_rows=40, title="Explicit item–KC edges")
        show_json(q_audit["scientific_diagnostics"], "Q-matrix diagnostics")
        '''
    ),
    code(
        r'''
        metadata = selected_policy["selection_metadata"]
        check_group("Knowledge", {
            "selection uses development only": metadata["data_partition"] == "development",
            "generated text was not read": metadata["generated_text_read"] is False,
            "simulation or KT evidence was not read": metadata["simulation_or_kt_evidence_read"] is False,
            "policy was frozen before holdout evaluation": selection_evaluation["selected_policy_written_before_holdout_evaluation"],
            "items project via opportunity": all(
                row["measurement_opportunity_id"] in opportunity_by_id for row in item_projections),
            "format pair has identical KC projection": len(paired_kc_sets) == 1,
            "Q-matrix exactly covers accepted bank": (
                q_audit["status"] == "PASS" and q_audit["items"] == len(accepted_items)),
        })
        '''
    ),
    markdown(
        r'''
        > **What should I inspect after Knowledge?**
        >
        > - Which candidate KCs lacked development support or were rejected?
        > - Did any candidates become unidentifiable, and under what exact criterion?
        > - Which obligation caused each final KC to be retained?
        > - Does the frozen inventory reuse development-supported components on holdouts?
        > - Are uncovered items or identical Q-matrix columns scientifically consequential?
        '''
    ),
    markdown(
        r'''
        # 5. Evaluation

        Scientific question: **Given a fixed item bank, event stream, and frozen item–KC
        mapping, what predictive coverage and temporal signal does the representation support?**

        The simulator is ontology-independent: its private structural oracle generates
        outcomes without consulting candidate KCs. KT receives only observable events and the
        frozen item–KC projection; it never reads oracle mastery, active oracle features, random
        draws, or response probabilities.

        ### Files used by this stage

        - [`simulation.py`](../src/grammar_kt/evaluation/simulation.py): projects oracle features, samples learner profiles, generates ordinary events, and runs frozen probes.
        - [`structural_oracle_v0.json`](../modules/evaluation/simulation/configs/structural_oracle_v0.json): declares evaluation-only structural data-generating features and equations/configuration.
        - [`simulation_config.json`](../reference/pipeline_walkthrough/simulation_config.json): notebook scale override—one learner per profile and two item passes.
        - [`kt.py`](../src/grammar_kt/evaluation/kt.py): projects observable interactions and fits empirical, BKT, and logistic baselines.
        - [`default.json`](../modules/evaluation/kt/configs/default.json): KT smoothing, BKT, logistic, calibration, and bootstrap parameters.
        - [`fold_manifest.json`](../reference/pipeline_walkthrough/fold_manifest.json): canonical structural split reused unchanged.
        - [`compare.py`](../scripts/compare.py): learner-level comparison/uncertainty workflow for full experiments.
        - [`run_scientific_checks.py`](../scripts/run_scientific_checks.py): repository-level scientific audit entry point.

        ### Intended research-modular inputs

        - **Simulation condition:** oracle declaration, learner profiles, response/learning
          parameters, protocol scale, seed, and structural fold are named research inputs. A new
          language normally changes oracle activation rules to match its structural evidence;
          changing the response equation itself requires a versioned simulator implementation.
        - **KT condition:** KT parameter JSON, enabled technique list, calibration/bootstrap
          settings, and fold are replaceable comparison inputs.
        - **Stable boundaries:** `simulation.py` must remain independent of candidate KCs, and
          `kt.py` must consume only observable pre-event data plus frozen item→KC projection.
          Private oracle state is never a valid KT configuration.
        '''
    ),
    markdown(
        r'''
        ## 5.1 Why simulation is ontology-independent

        ```text
        simulation oracle features ≠ candidate KCs
        ```

        Oracle primitives are controlled data-generating dimensions, not claims about human
        cognition and not evidence for choosing a KC inventory. A response probability combines
        pre-event mastery over active oracle features, stable opportunity-level difficulty, and
        a complexity penalty; correctness updates only the private active-feature mastery.

        Implementations:
        [`project_oracle_items`](../src/grammar_kt/evaluation/simulation.py),
        [`response_probability`](../src/grammar_kt/evaluation/simulation.py), and
        [`simulate_records`](../src/grammar_kt/evaluation/simulation.py).

        ## 5.2 Structural oracle
        '''
    ),
    code(
        r'''
        show_text("modules/evaluation/simulation/configs/structural_oracle_v0.json", max_lines=115)
        simulation_params = simulation.load_simulation_parameters(
            REFERENCE / "simulation_config.json"
        )
        oracle_item_projection, oracle_feature_ids = simulation.project_oracle_items(
            accepted_items, opportunities, simulation_params
        )
        table([{
            "item": row["item_id"],
            "opportunity": row["measurement_opportunity_id"],
            "oracle structural features": row["oracle_feature_ids"],
            "difficulty": round(simulation.difficulty(
                row["measurement_opportunity_id"],
                simulation_params["difficulty_min"], simulation_params["difficulty_max"]), 4),
        } for row in oracle_item_projection], max_rows=10,
        title="Evaluation-only oracle projection for accepted items")
        '''
    ),
    markdown(
        r'''
        ## 5.3 Synthetic learner profiles

        The low, mixed, and high profiles differ only in the Beta distribution used for initial
        oracle mastery and in learning rate.

        ## 5.4 Response probability and learning updates

        The notebook calls the real response and update implementation; it does not restate the
        equations as executable notebook logic.

        ### Small real mini-bank simulation

        The notebook uses all six accepted items, three synthetic learners (one low, one mixed,
        one high profile), and two complete item passes: 36 ordinary events. The equations are
        unchanged; only scale is reduced. Numbers below are illustrative execution results, not
        paper evidence.
        '''
    ),
    code(
        r'''
        # Stage artifacts are written only to a temporary directory; core logic stays in source.
        for stage in ("canonical", "measurement", "generation", "knowledge"):
            (walkthrough_root / stage).mkdir(parents=True, exist_ok=True)
        write_jsonl(walkthrough_root / "canonical/canonical_cells.jsonl", canonical_cells, sort_keys=False)
        write_jsonl(walkthrough_root / "measurement/measurement_opportunities.jsonl", opportunities, sort_keys=False)
        write_jsonl(walkthrough_root / "generation/accepted_items.jsonl", accepted_items, sort_keys=False)
        write_jsonl(walkthrough_root / "knowledge/item_kc_projection.jsonl", item_projections, sort_keys=False)

        simulation_summary = simulation.run(walkthrough_root, {
            "parameters": str(REFERENCE / "simulation_config.json"),
            "seed": 20260827,
            "fold_manifest": str(REFERENCE / "fold_manifest.json"),
        })
        observed_events = read_jsonl(walkthrough_root / "simulation/observable_interactions.jsonl")
        oracle_events = read_jsonl(walkthrough_root / "simulation/oracle_interactions.jsonl")
        learners = read_jsonl(walkthrough_root / "simulation/learners.jsonl")
        table(observed_events[:20], columns=[
            "learner_id", "sequence_index", "item_id", "measurement_opportunity_id",
            "correct", "item_difficulty", "dataset_split", "canonical_split",
        ], max_rows=20, title="First 20 observable interactions")
        show_json(simulation_summary, "Simulation summary")
        '''
    ),
    markdown(
        r'''
        ## 5.5 Observable versus private oracle data

        The observable record exposes event order, item/opportunity/cell IDs, correctness,
        stable difficulty, temporal split, and structural split. The separately stored private
        row contains the active oracle features, pre/post mastery, response probability, and
        random draw.

        > **Evaluation-only private simulation state; never available to KT.**
        '''
    ),
    code(
        r'''
        first_event = observed_events[0]
        first_oracle = next(row for row in oracle_events if row["event_id"] == first_event["event_id"])
        table([{
            "record": "observable (KT may read)",
            "fields": sorted(first_event),
            "values": first_event,
        }, {
            "record": "private oracle (KT forbidden)",
            "fields": sorted(first_oracle),
            "values": first_oracle,
        }], title="Aligned public/private evidence for one learner event")
        '''
    ),
    markdown(
        r'''
        ## 5.6 Ordinary temporal KT benchmark and two split systems

        | System | Labels | Unit | Purpose | May affect |
        | --- | --- | --- | --- | --- |
        | Canonical structural split | `development`, `compositional_holdout`, `novel_feature_holdout` | GrammarCell/item | Representation discovery and structural generalisation | KC selection and compositional protocol |
        | Temporal event split | `train`, `validation`, `test` | Ordered learner event | Chronological fitting and scoring | KT fitting and ordinary benchmark metrics |

        These solve different problems. In the ordinary technical benchmark, all item types may
        appear in temporal training. The stricter compositional protocol below uses development
        items for acquisition and reserves canonical holdouts as probes.
        '''
    ),
    code(
        r'''
        table([{
            "canonical split": canonical_split,
            "temporal split": temporal_split,
            "events": count,
        } for (canonical_split, temporal_split), count in sorted(Counter(
            (row["canonical_split"], row["dataset_split"]) for row in observed_events
        ).items())], title="Both labels coexist on ordinary events")
        '''
    ),
    markdown(
        r'''
        ## 5.7 Development acquisition

        ```text
        development acquisition → freeze learner state
                                → compositional probes
                                → novel-feature probes
        ```

        Every held-out probe prediction reads the same post-development state. Probe outcomes
        do not update the state used by later probes, so probe ordering cannot leak learning.

        ## 5.8 Frozen probes

        Implementation: [`simulate_compositional_records`](../src/grammar_kt/evaluation/simulation.py).
        '''
    ),
    code(
        r'''
        comp_root = walkthrough_root / "simulation/compositional"
        acquisition_events = read_jsonl(comp_root / "acquisition_events.jsonl")
        compositional_probes = read_jsonl(comp_root / "compositional_probe_events.jsonl")
        novel_probes = read_jsonl(comp_root / "novel_feature_probe_events.jsonl")
        oracle_probe_evidence = read_jsonl(comp_root / "oracle_probe_evidence.jsonl")
        frozen_oracle_states = read_jsonl(comp_root / "learner_frozen_oracle_state.jsonl")
        learner_id = learners[0]["learner_id"]
        learner_acquisition = [row for row in acquisition_events if row["learner_id"] == learner_id]
        learner_probes = [row for row in oracle_probe_evidence if row["learner_id"] == learner_id]
        table([{
            "phase": "last acquisition",
            "event": learner_acquisition[-1]["event_id"],
            "sequence": learner_acquisition[-1]["sequence_index"],
            "opportunity": learner_acquisition[-1]["measurement_opportunity_id"],
            "updates state": True,
        }, *[{
            "phase": "held-out probe",
            "event": row["event_id"],
            "sequence": next(event["sequence_index"] for event in compositional_probes + novel_probes
                             if event["event_id"] == row["event_id"]),
            "opportunity": row["measurement_opportunity_id"],
            "updates state": row["oracle_update_applied"],
        } for row in learner_probes]], max_rows=10,
        title="Development exposure followed by non-updating probes")
        print("probe_updates_state ==", any(row["oracle_update_applied"] for row in oracle_probe_evidence))
        show_json(next(row for row in frozen_oracle_states if row["learner_id"] == learner_id),
                  "Frozen post-development oracle state for one learner")
        '''
    ),
    markdown(
        r'''
        ## 5.9 KT projection

        Observable events are joined mechanically to the frozen item–KC projection, creating
        pre-event KC opportunity indices.

        ## 5.10 KT baselines

        - **Empirical** is a smoothed historical-success baseline.
        - **BKT** is a classic latent-mastery baseline with fixed learn/guess/slip parameters.
        - **Logistic** is a simple discriminative baseline using observable pre-event features
          and KC indicators.

        All three use the same observable events and item–KC projection. The logistic model is
        fit on temporal training rows only; reported validation/test predictions are pre-event.
        Zero-KC rows receive the shared ontology-independent fallback.

        Implementations: [`project_interactions`, `pre_event_features`, and `run`](../src/grammar_kt/evaluation/kt.py).
        '''
    ),
    code(
        r'''
        show_text("modules/evaluation/kt/configs/default.json", max_lines=60)
        kt_summary = kt.run(walkthrough_root, {
            "parameters": "modules/evaluation/kt/configs/default.json",
            "techniques": ["empirical", "bkt", "logistic"],
            "fold_manifest": str(REFERENCE / "fold_manifest.json"),
        })
        kt_interactions = read_jsonl(walkthrough_root / "kt/projected_interactions.jsonl")
        kt_predictions = read_jsonl(walkthrough_root / "kt/predictions.jsonl")
        kt_metrics = read_json(walkthrough_root / "kt/metrics.json")
        table(kt_interactions[:12], columns=[
            "learner_id", "sequence_index", "item_id", "dataset_split",
            "canonical_split", "correct", "kc_ids", "opportunity_indices",
        ], max_rows=12, title="Observable event stream projected into KT interactions")
        table(kt_predictions[:12], max_rows=12, title="Pre-event predictions")
        '''
    ),
    markdown(
        r'''
        ## 5.11 Metrics and representation support

        Log loss measures probabilistic error; AUC ranks positive above negative outcomes;
        Brier is mean squared probability error; ECE summarizes calibration gaps; accuracy uses
        a 0.5 threshold; coverage records whether the frozen ontology supplies any KCs.

        Tiny notebook metrics are **illustrative execution results, not paper evidence**.
        Representation support must be inspected before interpreting probe predictions:
        development-supported coverage says whether activated probe KCs were learned from
        development, and cold-KC rate reports the complement.
        '''
    ),
    code(
        r'''
        ordinary_metric_rows = []
        for technique, splits in kt_metrics["techniques"].items():
            for split, views in splits.items():
                ordinary_metric_rows.append({
                    "technique": technique,
                    "split": split,
                    "view": "all events / fixed fallback",
                    **views["all_events_fixed_fallback"],
                })
        table(ordinary_metric_rows, max_rows=20,
              title="Ordinary validation/test metrics (illustrative)")
        show_json(kt_metrics["coverage"], "Ordinary ontology coverage")

        compositional_metrics = read_json(walkthrough_root / "kt/compositional/metrics.json")
        representation_support = read_json(
            walkthrough_root / "kt/compositional/representation_support.json"
        )
        comp_metric_rows = []
        for technique, splits in compositional_metrics["holdout_evaluation"].items():
            for probe_split, values in splits.items():
                comp_metric_rows.append({
                    "probe split": probe_split,
                    "technique": technique,
                    "coverage": values["coverage"],
                    "development-supported coverage": values["development_supported_coverage"],
                    "cold KC rate": values["cold_kc_rate"],
                    **values["all_probes_fixed_fallback"],
                })
        table(comp_metric_rows, max_rows=20,
              title="Frozen-probe prediction metrics (illustrative)")
        show_json(representation_support, "Probe representation support")
        '''
    ),
    code(
        r'''
        simulation_audit = read_json(walkthrough_root / "simulation/audit.json")
        compositional_audit = read_json(comp_root / "audit.json")
        kt_model_details = read_json(walkthrough_root / "kt/compositional/model_details.json")
        oracle_private_fields = {
            "oracle_feature_ids", "pre_mastery", "post_mastery", "response_probability",
            "random_draw", "oracle_complexity_penalty", "profile",
        }
        pair_difficulties = {
            simulation.difficulty(item["measurement_opportunity_id"],
                                  simulation_params["difficulty_min"], simulation_params["difficulty_max"])
            for item in paired
        }
        check_group("Evaluation", {
            "simulation does not read candidate KCs": not simulation_audit["evaluated_ontology_inputs_read"],
            "observable events contain no oracle fields": all(
                not (set(row) & oracle_private_fields) for row in observed_events),
            "same opportunity has same latent difficulty across formats": len(pair_difficulties) == 1,
            "probe events do not update frozen state": (
                compositional_audit["probe_oracle_updates"] is False
                and not any(row["oracle_update_applied"] for row in oracle_probe_evidence)),
            "held-out items never enter development acquisition": compositional_audit["holdout_in_acquisition"] is False,
            "KT does not read oracle state": (
                kt_metrics["oracle_used"] is False and kt_model_details["oracle_fields_read"] is False),
            "all three KT baselines executed": set(kt_metrics["techniques"]) == {"empirical", "bkt", "logistic"},
        })
        '''
    ),
    markdown(
        r'''
        > **What should I inspect after Evaluation?**
        >
        > - Can the frozen ontology cover held-out compositions?
        > - Were probe KCs supported from development, or are they cold?
        > - Do the observable rows contain anything that reveals private oracle mastery?
        > - Do probe predictions remain fixed-state rather than learning from prior probes?
        > - Does KT recover useful predictive structure in a suitably powered experiment?
        '''
    ),
    markdown(
        r'''
        # 6. One complete provenance trace

        One accepted dialogue item is traced backward to its authentic EGP descriptor and
        forward to one simulated interaction and its KT prediction. Every arrow is an explicit
        ID-bearing record; no text-based KC guessing is inserted.
        '''
    ),
    code(
        r'''
        traced_item = representative_item
        traced_opp = opportunity_by_id[traced_item["measurement_opportunity_id"]]
        traced_edge = next(row for row in source_cell_edges
                           if row["canonical_cell_id"] == traced_item["canonical_cell_id"])
        traced_source = record_by_id[traced_edge["egp_id"]]
        traced_mapping = next(row["output"] for row in normalisation_results
                              if row["output"]["egp_id"] == traced_edge["egp_id"])
        traced_projection = projection_by_item[traced_item["item_id"]]
        traced_q = next({"item_id": item_id, **dict(zip(q_kc_ids, values))}
                        for item_id, values in q_rows if item_id == traced_item["item_id"])
        traced_event = next(row for row in observed_events if row["item_id"] == traced_item["item_id"])
        traced_kt = next(row for row in kt_interactions if row["event_id"] == traced_event["event_id"])
        traced_prediction = next(row for row in kt_predictions if row["event_id"] == traced_event["event_id"])
        provenance_trace = [
            {"stage": "EGP descriptor", "id": traced_source["egp_id"], "evidence": traced_source["can_do"]},
            {"stage": "normalisation mapping", "id": traced_mapping["egp_id"], "evidence": traced_mapping["cells"]},
            {"stage": "canonical GrammarCell", "id": traced_item["canonical_cell_id"], "evidence": traced_opp["cell"]},
            {"stage": "MeasurementOpportunity", "id": traced_opp["measurement_opportunity_id"], "evidence": traced_opp["structural_conditions"]},
            {"stage": "generated candidate", "id": traced_item["item_id"], "evidence": surface(traced_item)},
            {"stage": "blind validation", "id": traced_item["validation_metadata"]["evaluator_id"], "evidence": traced_item["validated_structure"]},
            {"stage": "accepted item", "id": traced_item["item_id"], "evidence": "accepted"},
            {"stage": "KC projection", "id": selected_policy["policy_id"], "evidence": traced_projection["kc_ids"]},
            {"stage": "Q-matrix row", "id": traced_item["item_id"], "evidence": traced_q},
            {"stage": "learner interaction", "id": traced_event["event_id"], "evidence": {"correct": traced_event["correct"], "split": traced_event["dataset_split"]}},
            {"stage": "KT interaction", "id": traced_kt["event_id"], "evidence": {"kc_ids": traced_kt["kc_ids"], "indices": traced_kt["opportunity_indices"]}},
            {"stage": "prediction", "id": traced_prediction["event_id"], "evidence": {key: traced_prediction[key] for key in ("empirical", "bkt", "logistic")}},
        ]
        table(provenance_trace, max_rows=20, title="End-to-end actual-ID provenance")
        '''
    ),
    markdown(
        r'''
        # 7. Scientific invariant summary

        A passing cell means the current execution satisfied the explicitly stated boundary. It
        does not validate the linguistic ontology or establish external validity; those remain
        research judgments.
        '''
    ),
    code(
        r'''
        final_invariants = [
            {"module": module, **row}
            for module, rows in invariant_results.items()
            for row in rows
        ]
        table(final_invariants, max_rows=50, title="All module invariants")
        assert all(row["status"] == "PASS" for row in final_invariants)
        print("PASS — all scientific boundary assertions in this walkthrough hold.")
        '''
    ),
    markdown(
        r'''
        # 8. Where to investigate next

        - Audit alternative five-record mappings by running live normalisation with the verified
          source snapshot; preserve new evidence rather than overwriting this reference.
        - Inspect opportunities with WH roles or imperative subtypes in a larger declared sample.
        - Compare the development-selected policy with the linked predefined controls on one
          fixed accepted item bank and event stream.
        - Increase learners/items/replications before interpreting KT metrics; use
          [`compare.py`](../scripts/compare.py) for learner-level uncertainty.
        - Treat quality diagnostics, mapping reliability, KC identifiability, representation
          coverage, and predictive performance as distinct evidence streams.

        This notebook is the methodological tour. The machine-oriented
        [`research_audit.ipynb`](research_audit.ipynb) remains a compact contract smoke test.
        '''
    ),
]


def main() -> None:
    target = ROOT / "notebooks/module_unit_examples.ipynb"
    target.write_text(
        json.dumps(notebook(unit_cells), ensure_ascii=False, indent=1) + "\n",
        encoding="utf-8",
    )
    print(f"wrote {target.relative_to(ROOT)} ({len(unit_cells)} cells)")


if __name__ == "__main__":
    main()
