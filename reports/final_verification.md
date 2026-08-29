# Final verification

Date: 2026-08-28  
Scope: final curated dataset, active pipeline, backend-effort audit, experiment
evidence, executable notebooks, and ACL manuscript.

## Outcome

All active scientific-contract tests pass; the fixture pipeline and notebook
execute without live model calls; the final dataset counts reconcile; the ACL
paper builds and passes its regression suite; the 12-page PDF has embedded
fonts and passed complete rendered-page inspection. No required active
execution remains failed.

## Commands and results

### Scientific-contract tests

```bash
.venv/bin/python -m pytest -q
```

Final result after the backend-effort integration and notebook additions:
**112 passed in 5.22 s**.

This includes outcome-independent candidate construction, holdout mutation
invariance, development-only selection, fixed-event representation comparison,
semantic folds, frozen probes, no-oracle logistic KT, support/equivalence,
penalty behavior, final-dataset preparation/finalization/analysis, stability,
and the alternate `mood`/`person` candidate→selection→freeze→projection
contract.

### Paper-facing fixture runner

```bash
fixture_parent_dir=$(mktemp -d tmp/final-fixture-parent.XXXXXX)
.venv/bin/python scripts/run.py --fixture --output "$fixture_parent_dir/run"
```

Result: completed with 6 selected items and 624 events. The temporary output
was removed after inspection. Fixture evidence is software verification, not a
scientific result.

### Executable walkthrough

```bash
.venv/bin/jupyter nbconvert --to notebook --execute --inplace \
  --ExecutePreprocessor.timeout=600 notebooks/pipeline_walkthrough.ipynb
```

Result: completed in offline `LIVE_MODE = False`. Every code cell has an
execution count and no error output. The walkthrough uses the active
normalisation, canonicalisation, generation, validation, semantic fold,
schema-validated latent-world materialisation, frozen-probe simulation,
candidate generation, learner-evidence selection, projection, KT, and
evaluation functions. Its reduced demonstration contains 6 cells/items, 8
learners, 208 events, 27 structural candidates, 6 selection-eligible
candidates, and a 4-KC selected policy.

The walkthrough now reads the same per-stage backend declaration as
`scripts/run.py`: Sol/high for normalisation, Sol/medium for generation, and
Terra/medium for validation. Its offline fixture overrides all three stages
with deterministic responses, so notebook execution makes no model calls.

### Final-dataset results notebook

```bash
.venv/bin/jupyter nbconvert --to notebook --execute --inplace \
  --ExecutePreprocessor.timeout=600 notebooks/final_dataset_results.ipynb
```

Result: completed with no error output against
`data/grammar_kt_medium_v1`. The first code cell exposes `DATA_FOLDER` (or
the `GRAMMAR_KT_DATA_FOLDER` environment variable); every subsequent stage
resolves artifacts relative to that folder. Pandas tables cover
manifest/provenance, source and normalisation, canonical cells and fold,
generation and validation, fixed item bank, learner events, KC
candidates/equivalence, selected policy and Q-matrices, KT metrics, paired
comparisons, stability, and retained RQ results.

### Curated finalization and analysis

Final retained executions:

```bash
.venv/bin/python scripts/curate_item_packaging.py \
  --dataset-dir data/grammar_kt_medium_v1 --workers 4 \
  --validation-model gpt-5.6-terra --reasoning-effort medium

.venv/bin/python scripts/finalize_full_dataset.py \
  --dataset-dir data/grammar_kt_medium_v1 \
  --learners 1000 --seed 20260827 --bootstrap-repeats 5000

.venv/bin/python scripts/run_phase6_selection_stability.py

.venv/bin/python scripts/analyze_full_dataset.py \
  --dataset-dir data/grammar_kt_medium_v1 \
  --output-dir reports/phase6/artifacts/full_dataset_analysis
```

Reconciled retained counts:

- 139 source rows and 139 mappings;
- 24 cells and 24 fold assignments;
- 44 selected items and four 44-row projections/Q-matrices;
- 204,000 events;
- 612,000 prediction rows per policy (204,000 events × 3 KT techniques);
- zero holdout or reserved-test events supplied to any stability selection;
- four evaluated policies, 48 policy×KT×regime metric rows, and 12 paired
  logistic representation comparisons.

The finalization manifest fixes 1,000 learners, seed 20260827, 55 raw/38
activation-class/28 selection-eligible candidates, and λ=.0005. The compact
stability artifact fixes seeds 20260827--20260831 and five identical full-
support inventories.

After the Phase-7 simulator cleanup, the exact finalizer was deliberately run
again and reproduced every count, selected KC, log-loss value, and interval.
All five stability streams and all nine selections were then forced through
`scripts/run_phase6_selection_stability.py --recompute`; the resulting
inventories/frequencies were unchanged. A final no-flag replay restored the
paper-recorded resumable command in the artifact manifest.

### Backend thinking-effort audit

```bash
.venv/bin/python scripts/run_backend_thinking_audit.py \
  --stage prepare \
  --output-dir reports/backend_thinking/artifacts/live_v1
.venv/bin/python scripts/run_backend_thinking_audit.py \
  --stage normalisation \
  --output-dir reports/backend_thinking/artifacts/live_v1 --workers 4
.venv/bin/python scripts/run_backend_thinking_audit.py \
  --stage validation \
  --output-dir reports/backend_thinking/artifacts/live_v1 --workers 4
.venv/bin/python scripts/run_backend_thinking_audit.py \
  --stage generation \
  --output-dir reports/backend_thinking/artifacts/live_v1 --workers 4
.venv/bin/python scripts/run_backend_thinking_audit.py \
  --stage generation \
  --output-dir reports/backend_thinking/artifacts/live_v1 \
  --workers 4 --judge-effort medium
.venv/bin/python scripts/analyze_backend_thinking_reviews.py \
  --output-dir reports/backend_thinking/artifacts/live_v1 \
  --bootstrap-replicates 10000
```

The frozen audit records 918 stage evaluations: 905 live model calls and 13
deterministic precheck decisions. It used 3,351,258 Codex CLI tokens, returned
no nonzero CLI status, and produced one malformed fixed-judge response. Two
condition-blind research-agent reviewers each assessed 318 rows; an independent
adjudicator resolved 26 flagged rows. All seven result hashes in the final
manifest match the retained files.

The strict zero-critical rule was inconclusive for every stage. The operational
decision is normalisation **high**, generation **medium**, and validation
**medium**. This changes future active configuration only: the retained dataset
and all paper dataset results preserve their original all-medium provenance.

### ACL paper

```bash
cd ACL
latexmk -pdf -interaction=nonstopmode -halt-on-error paper.tex
cd ..
.venv/bin/python ACL/tests/regression/run_tests.py
```

Result: build succeeded; author-list/content regression **71/71 passed**.
`paper.pdf` is 12 A4 pages (249,078 bytes, PDF 1.7). `pdffonts` reports every
font embedded. The log contains no overfull box, undefined reference/citation,
or LaTeX error. All 12 rendered pages were inspected for clipping, overlap,
broken glyphs, table/figure legibility, headers/footers, page numbers, and
section transitions; the final render has no observed layout defect.

### Whitespace check

```bash
git diff --cached --check -- . \
  ':(exclude)pipeline.txt' \
  ':(exclude)reports/**' \
  ':(exclude)28/**' \
  ':(exclude)data/grammar_kt_medium_v1/**'
```

Result: pass with no output across active source, declarations, tests,
fixtures, notebooks, and manuscript artifacts. The full staged check also
reports retained textual formatting: CommonMark two-space hard breaks in
reports and their `28/` copies, plus terminal blank lines in immutable
rendered model prompts. These frozen evidence files were not rewritten merely
to satisfy a whitespace linter.

The unfiltered working-tree command separately reports three trailing-space
lines in pre-existing user-owned `pipeline.txt` (lines 18, 20, and 30).
That unrelated file was intentionally preserved; it is not read by the
pipeline, tests, experiments, dataset, or paper.

## Models and seeds

| Purpose | Model / setting | Seed |
|---|---|---|
| Retained normalisation snapshot | `gpt-5.6-sol`, medium, 2026-08-20 | provider sampling seed unavailable |
| Item generation | `gpt-5.6-sol`, medium, four workers | provider sampling seed unavailable; deterministic candidate positions |
| Independent validation | `gpt-5.6-terra`, medium, four workers | provider sampling seed unavailable |
| Backend-effort audit | same aliases, medium/high/xhigh, four workers | 20260828 controls order/blinding/bootstrap; provider sampling seed unavailable |
| Future active normalisation | `gpt-5.6-sol`, high | operational fallback; strict audit rule inconclusive |
| Future active generation/validation | `gpt-5.6-sol`/`gpt-5.6-terra`, medium | operational fallbacks; strict audit rule inconclusive |
| Frozen correction revalidation | `gpt-5.6-terra`, medium, six records | frozen plan SHA-256; provider seed unavailable |
| Final mixed simulation / selection / bootstrap | declared synthetic world / observable logistic | 20260827; 5,000 learner resamples |
| Final policy stability | declared mixed world / same selector | 20260827--20260831 |
| Phase-5 world robustness | four declared worlds | 20260827--20260829 |
| Selector logistic | regularisation C=.1, max 300 iterations | 20260827 |

No language model is called by finalization, stability replay when retained
streams are valid, KT evaluation, paper-table analysis, fixture tests, or the
default notebook.

## Final artifact locations

- Dataset: `data/grammar_kt_medium_v1/`
- Final dataset report: `reports/full_dataset_investigation.md`
- Final methodology: `reports/final_methodology.md`
- RQ ledger: `reports/final_rq_ledger.md`
- Backend effort analysis: `reports/backend_thinking/analysis.md`
- Backend effort raw/derived evidence:
  `reports/backend_thinking/artifacts/live_v1/`
- Experiment ledger/state: `reports/experiment_log.md`,
  `reports/research_state.md`
- Final-dataset results notebook: `notebooks/final_dataset_results.ipynb`
- Paper-facing tables: `reports/phase6/artifacts/full_dataset_analysis/`
- Full-support stability: `reports/phase6/artifacts/selection_stability_v1/`
- Manuscript/PDF: `ACL/paper.tex`, `ACL/paper.pdf`

## Remaining execution and evidence failures

There are no unresolved active-code, test, notebook, finalization, analysis, or
paper-build failures. The remaining limitations are evidential rather than
execution failures: no human/expert item validation, no real learner outcomes,
English-only empirical data, incomplete normalisation/model-run stability,
five compositional cells, one novel-value cell, and synthetic latent-world
assumptions. Backend choices additionally use mutable aliases, unseeded
provider sampling, condition-blind research agents rather than human experts,
and operational fallbacks because every strict critical-error gate was
inconclusive. The programme narrows its claims accordingly rather than treating
these as established results.
