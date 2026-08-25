# ACL manuscript evidence ledger

This ledger separates executable design facts from results. A statement may be
used as a result only when its status is `completed-run evidence` and the run is
clean, versioned, and retained.

| ID | Manuscript statement | Evidence | Status |
|---|---|---|---|
| E01 | The pipeline has nine explicit stages from source through KT. | `src/grammar_kt/runner.py`, `README.md` | implementation |
| E02 | The external parsed EGP snapshot is declared as 1,222 records and verified by SHA-256. | `experiments/base.yaml`, `data/external/README.md`, `src/grammar_kt/source.py` | configured input; source stage verifies on execution |
| E03 | The ordered subset contains 139 descriptors: 116 fresh and 23 regression controls. | `modules/source/sample_ids.txt`, `modules/source/sample_metadata.jsonl` | repository metadata |
| E04 | There are 147 annotation units: 139 primary and 8 repeats. | `modules/source/annotation_units.jsonl` | repository metadata |
| E05 | Phase 1 exposes five projected descriptor fields and withholds examples. | `src/grammar_kt/source.py`, `src/grammar_kt/normalisation.py` | implementation |
| E06 | GrammarCell has six closed dimensions; complete, partial, and zero-cell statuses have explicit invariants. | `src/grammar_kt/records.py`, `modules/normalisation/rules/grammar_dimensions.txt`, `src/grammar_kt/normalisation_validation.py` | implementation and scientific specification |
| E07 | Phase 2 is restricted to licensed refinement of partial Phase-1 mappings. | `src/grammar_kt/normalisation.py`, `src/grammar_kt/normalisation_validation.py`, `modules/normalisation/rules/rulebook.md` | implementation and scientific specification |
| E08 | Canonical cell IDs are content-derived and equal cells are deduplicated while source edges remain explicit. | `src/grammar_kt/canonical.py`, `src/grammar_kt/io.py` | implementation |
| E09 | Realization is deterministic over a ten-frame lexicon and records operations. | `src/grammar_kt/realisation.py`, `modules/realisation/lexicons/default.jsonl`, `modules/realisation/rules/default.md` | implementation |
| E10 | Three KC policy families are available: factorized, interaction-augmented, and full-cell. | `modules/kc/policies/*.json`, `src/grammar_kt/kc.py` | scientific specification and implementation |
| E11 | Item generation is deterministic; acceptance combines deterministic checks with an automated, non-human model diagnostic. | `src/grammar_kt/items.py`, `src/grammar_kt/item_validation.py`, `modules/items/validation/*` | implementation |
| E12 | The Q-matrix is derived from the frozen cell--KC projection; integrity errors are fatal and descriptive diagnostics are retained. | `src/grammar_kt/qmatrix.py` | implementation |
| E13 | The simulator uses three 60-learner profiles, two item passes, chronological 60/20/20 splits, and separate observable/oracle records. | `runs/base/simulation/audit.json`, `runs/*/metadata.json` | completed-run evidence |
| E14 | Empirical, BKT, and logistic baselines use pre-event observable features and report AUC, log loss, and accuracy. | `runs/*/kt/metrics.json`, `src/grammar_kt/kt.py` | completed-run evidence and implementation |
| E15 | Runs record resolved settings, Git state, seed, source digest, stage summaries, and explicit reuse. | `src/grammar_kt/runner.py`, `src/grammar_kt/backend.py` | implementation |
| E16 | Current model configs do not pin a model snapshot or all decoding parameters. | `modules/normalisation/configs/backend.yaml`, `modules/items/validation/backend.yaml` | current working configuration; freeze before final run |
| E17 | Existing reference counts and KT scores are technical regression checks, not human-learning or KC-validity evidence. | `reference/current/summary.json`, `reference/current/kt_sanity.json`, `README.md` | claim boundary |
| E18 | The legacy `runs/current` output is partial and contains only the source stage. | `runs/current/summary.json`, `runs/current/stage_status.json` | obsolete incomplete run; not used in the manuscript |
| E19 | Final normalization outcomes are 44 complete, 77 partial, 16 out of scope, 2 unresolved, and 0 schema failures; 48 source edges yield 24 cells. | `runs/base/metadata.json`, `runs/base/normalisation/summary.json`, `runs/base/canonical/` | completed-run evidence |
| E20 | All eight repeated normalization units match exactly; all five repeated item diagnostics match on decision flags. | `runs/base/source/annotation_units.jsonl`, `runs/base/normalisation/units/`, `runs/base/items/validation/diagnostics.jsonl` | completed-run evidence; small repeat samples |
| E21 | Factorized, interaction, and full-cell runs contain 9, 14, and 24 KCs and accept 45/45, 69/70, and 120/120 items. | `runs/base/metadata.json`, `runs/kc_interactions/metadata.json`, `runs/kc_full_cell/metadata.json` | completed-run evidence |
| E22 | The only item rejection is an automated ambiguity flag for a negative past perfect-progressive item. | `runs/kc_interactions/items/validation/rejected_items.jsonl` | completed-run automated diagnostic; not human validation |
| E23 | Q-matrix densities are .244, .208, and .042, with row widths 1--4, 1--5, and exactly 1. | `runs/{base,kc_interactions,kc_full_cell}/qmatrix/audit.json` | completed-run evidence |
| E24 | Five declared seeds per policy complete simulation and KT; logistic regression has the best mean test AUC and log loss within each policy-specific dataset. | `experiments/*_seed_*.yaml`, `runs/*/kt/metrics.json` | completed-run evidence; cross-policy scores not causally comparable |

## Deferred evidence

- Final confirmation of dataset licence wording and permitted quotations.
- Human evaluation of normalization mappings and generated items.
- Evaluation on a shared item pool and independent learner data.
