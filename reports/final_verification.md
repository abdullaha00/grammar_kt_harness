# Final full-v1 verification

Date: 2026-08-30

Scope: the frozen `grammar_kt_full_v1` baseline, its construction boundary,
headline RQ2--RQ4 experiments, mastery and sensitivity evidence, executable
notebooks, final reports, and ACL manuscript.

## Outcome

The declared synthetic programme is reproducible and complete. The deterministic
Q* projection and all 283,000 public/private simulator rows replay exactly; the
scientific-contract suite passes; the headline RQ2, RQ3, and RQ4 results replay
from the frozen baseline; all three tracked notebooks execute without live model
calls; and the ACL manuscript builds, passes its author-list/BibTeX regression,
embeds all fonts, and passes complete rendered-page inspection.

The verified boundary remains:

```text
GrammarCell != generator K* != discovered K_hat
```

No verification step uses downstream outcomes to construct K* or Q*. The
LLM-backed source-normalisation and item-construction calls are not needlessly
reissued: their prompts, outputs, settings, intervention records, and hashes are
frozen in the dataset provenance. Deterministic construction after those calls
is replayed independently.

## Frozen baseline

The release manifest reports `FROZEN_BASELINE_COMPLETE` and an 88-file recursive
inventory. Its scale reconciles to 75 GrammarCells, 18 generator KCs, 113 items,
269 Q* edges, 1,000 learners, and 283,000 interactions: 170,000 seen acquisition
events followed by 113,000 non-updating probes.

Core SHA-256 values are:

| Artifact | SHA-256 |
|---|---|
| `manifest.json` | `322128843f8e7e6547a99efcecc6836fcd581f314fb49557a28d58fe79c69f4c` |
| `interactions.jsonl.gz` | `9272ca86a647e3b13c9ce52b5381dde215f7ef448e4a19a41a22495fa99ef97f` |
| `oracle/learner_truth.jsonl.gz` | `956ed53f370d5494d379072954c0821d4098f11e51e2629b33d8ee0b8b844601` |
| Recursive inventory semantic digest | `78008283ae56bad84199145495ad76c9c4897031f4e9bc0861fbb964b2338387` |

### Q* replay

```bash
.venv/bin/python scripts/build_true_q_matrix.py \
  --cells data/grammar_kt_full_v1/grammar/cells.jsonl \
  --items data/grammar_kt_full_v1/items/items.jsonl \
  --kcs data/grammar_kt_full_v1/kcs.jsonl \
  --design modules/kcs/generator/design.yaml \
  --regimes data/grammar_kt_full_v1/grammar/regime_assignments.jsonl \
  --dense-q-matrix data/grammar_kt_full_v1/q_matrix.csv \
  --sparse-q-matrix data/grammar_kt_full_v1/oracle/q_matrix_sparse.jsonl \
  --audit data/grammar_kt_full_v1/provenance/measurement/audit.json \
  --manifest data/grammar_kt_full_v1/provenance/measurement/manifest.json \
  --verify-only
```

Result: `verified frozen Q* artifacts`. The 113-by-18 matrix retains rank 18,
269 edges, 75 distinct cell rows, and no equal or Jaccard-at-least-.90 columns.

### Event and oracle replay

```bash
.venv/bin/python scripts/freeze_baseline_dataset.py \
  --dataset-dir data/grammar_kt_full_v1 \
  --pilot reports/baseline/artifacts/full_simulator_v1/pilot_seed_20260829.json \
  --verify-only
```

Result: `FROZEN_BASELINE_COMPLETE`, 113 items, 1,000 learners, and 283,000
events. Verification regenerates keyed draws and state trajectories and checks
public/private event alignment, probabilities, updates, non-updating probes,
gzip determinism, and every manifest digest. Public rows expose no mastery,
response probability, active-KC, update, or random-draw fields.

## Scientific-contract suite

```bash
.venv/bin/python -m pytest -q
```

Final result: **271 passed**. Contracts cover, among other boundaries:

- incomplete mappings cannot silently become exact GrammarCells;
- generator-KC declarations and Q* precede learner outcomes;
- item generation and baseline construction cannot read learner responses;
- the simulator consumes K*/Q* rather than discovered KCs;
- pure representation comparisons reuse identical events;
- selection skips probe outcomes before reading `correct`;
- private oracle fields cannot enter ordinary KT or discovery;
- probes do not update state;
- a `mood`/`person` alternate schema executes cells to K* to Q* to events
  without English-specific branches; and
- the collection result's typed pre-serialization and stored-byte hashes are
  both independently validated.

## Headline experiment replay

### RQ2 misspecification

An independent output directory was planned and run from the frozen baseline:

```bash
.venv/bin/python scripts/experiments/rq2_kc_misspecification.py \
  --stage plan --dataset-dir data/grammar_kt_full_v1 \
  --output-dir /tmp/grammar_kt_rq2_replay_final
.venv/bin/python scripts/experiments/rq2_kc_misspecification.py \
  --stage run --dataset-dir data/grammar_kt_full_v1 \
  --output-dir /tmp/grammar_kt_rq2_replay_final
```

All 15 conditions reran. The projection bundle is byte-identical to the frozen
bundle (`4b793fc6a44a14b975db41f272abfcc0d9df7c3f8effa6b1109f0711c3885661`).
After excluding only expected output-path plan metadata and the later repository
revision field, canonical replay and frozen result both hash to
`e0572337c64eb491ff941e75abc5a5cf969e5a53598f4fae465392b8d0e181c5`.
Every metric, interval, and ordering is identical.

### RQ3 observable-only discovery evaluation

```bash
.venv/bin/python scripts/experiments/rq3_kc_discovery.py evaluate \
  --plan experiments/full_v1/rq3_kc_discovery_v1/plan.json \
  --selection experiments/full_v1/rq3_kc_discovery_v1/final_selection.json \
  --cohort final --output /tmp/rq3_final_evaluation.json
```

The replay is byte-identical to the frozen evaluation at SHA-256
`52e4ff8cba3932010d54fa3af653d64553d3e042d901ab5ac5f9d308bf12f0cd`.
Truth and probes enter only after the immutable selection is supplied.

### RQ4 linguistic generalisation

RQ4 records repository-relative artifact paths, so its independent output is
placed in the ignored `runs/` verification area rather than `/tmp`:

```bash
.venv/bin/python scripts/experiments/rq4_grammar_generalisation.py \
  --stage plan --dataset data/grammar_kt_full_v1 \
  --output runs/final_verification_rq4_replay
.venv/bin/python scripts/experiments/rq4_grammar_generalisation.py \
  --stage run --dataset data/grammar_kt_full_v1 \
  --output runs/final_verification_rq4_replay
```

The plan reproduces SHA-256
`0f7a2d423f3761f196ddb4c16dd76aa18a3a0eac2ad114c14aa27342f0813515`;
the full N=1,000 result reproduces
`a25f43833e620f40294c350259673dadfaaf3f38356339cd6b4cef42be4ec144`.

### Mastery, robustness, and collection-design integrity

Mastery recovery preserves the observable-before-oracle boundary. Its frozen
observable estimates, primary result, learner-paired bootstrap, and secondary
BKT result hash respectively to:

```text
9fba28d564f31c1b9ee552f15bf2e23a8c65b3c12817cd30f3e6f6f6fc33df93
3055096d70232dd53b37010f5eb22d59d47c763b7df950b33ecbb0093a2824c6
684bda7d9ae25758f9ad5b56c4328fe9ac5bd5258ddcf1cb59dd4d546277d651
b6099901212302c47cbb353848fffbe099ffe2b780918c80bca01155bd96f07e
```

The 39-world robustness plan/result hashes are
`66403c074fe7dbdfa3bd859225d7998a34524e8a2332e1286adecdc6a77636dc`
and `f9a01e718588e6fbb69994d111f62bee2384333d94526bdaa456f8806d052d6a`.
All 117 primary fits converged, common keyed draws match, and the baseline seed
reproduces the first 500 frozen learners exactly.

The collection plan/result hashes are
`5049a7f4cd61579ee68034e33e2cec1b6588eb09efe83490607e464ffb10242d`
and `5ef059f18025ec6f5fc88bfeaccfebb536be29fab8ff32767059ebd40f931533`;
all 282 fits converged and before/after baseline manifests match. The immutable
result contains a pre-serialization semantic digest over eight integer-keyed
`q_row_multiplicity` maps. JSON necessarily serializes those keys as strings.
Rather than overwrite the result, `integrity_verification.json` records the
stored-byte digest, plain JSON-roundtrip digest, typed-key restoration rule,
and restored digest. A test validates all four claims. This is a metadata
representation caveat, not numeric nondeterminism.

## Executable notebooks

```bash
.venv/bin/jupyter nbconvert --to notebook --execute \
  --output /tmp/pipeline_walkthrough.executed.ipynb \
  --ExecutePreprocessor.timeout=600 notebooks/pipeline_walkthrough.ipynb

GRAMMAR_KT_DATA_FOLDER=data/grammar_kt_full_v1 \
  .venv/bin/jupyter nbconvert --to notebook --execute \
  --output /tmp/final_dataset.executed.ipynb \
  --ExecutePreprocessor.timeout=600 notebooks/final_dataset.ipynb

GRAMMAR_KT_DATA_FOLDER=data/grammar_kt_full_v1 \
  .venv/bin/jupyter nbconvert --to notebook --execute \
  --output /tmp/final_dataset_results.executed.ipynb \
  --ExecutePreprocessor.timeout=600 notebooks/final_dataset_results.ipynb
```

All three complete without error or live model calls. The walkthrough executes
all nine code cells. The dataset viewer executes 9/9 code cells; its two setup
cells are intentionally quiet and its seven display cells have outputs. Its
tracked SHA-256 is
`f339ef58e579ea837e2981fcc5c71658c0f8df6fd90b1c697397f10a933e3369`.
The full-v1 results notebook executes 20/20 code cells, all with outputs; its
tracked SHA-256 is
`89671397bd05c18d23e682cbd7de68aca53131f7df5f2abc1a6e8988af5aeaa9`.
Static and runtime contracts prohibit direct access to private learner
trajectories. The dataset viewer opens only the public baseline artifacts; the
results notebook additionally opens publishable summaries and already-derived
oracle-evaluation aggregates.

## Standalone dataset visualization

`reports/final_dataset_visualization.html` presents the same ten public full-v1
events in two switchable views: binary outcomes joined to their 18-column Q*
rows, and the stored prompts with accepted response text. It explicitly labels
the learner as simulated, distinguishes sampled `y` from Q*, and states that
the prompt/answer strings were neither rendered nor scored by the simulator.
The only script performs local tab switching; there are no external resources,
downstream results, or private oracle values. Event IDs, outcomes, prompts,
accepted responses, Q* rows, KC labels, and scale claims were checked against
the frozen artifacts. Both views were visually inspected at 1,024, 736, and 360
pixels in light and dark themes. Its SHA-256 is
`85bf379f03ea4473cbb64d4ff759e1f3f478f2bea5f965ab9bedc700346d5218`.

## ACL manuscript

```bash
cd ACL
TZ=UTC SOURCE_DATE_EPOCH=1788069406 FORCE_SOURCE_DATE=1 \
  latexmk -g -pdf -interaction=nonstopmode -halt-on-error paper.tex
python tests/regression/run_tests.py
pdfinfo paper.pdf
pdffonts paper.pdf
```

The build succeeds and the author-list/BibTeX regression passes **71/71**; it is
not treated as a paper-content correctness test. The final PDF
is 13 A4 pages, PDF 1.7, with SHA-256
`aef66e282bcec04d19ce6fc9f3216dce6ee3f9bda526ac28207fcc693e20d61b`.
The fixed epoch makes the tracked PDF byte-reproducible; two independent audit
builds and the final in-tree build produce this digest.
Every font is embedded. The log contains no overfull box, undefined citation or
reference, multiply defined label, or LaTeX error. All 13 pages were rendered
with Poppler and inspected for clipping, overlap, broken glyphs, table and
figure legibility, headers, footers, numbering, and float placement; no visual
defect remains. Underfull-box messages are benign line-breaking diagnostics.
All 13 page rasters from the fixed-epoch build are byte-identical to the
visually inspected render.

Text extraction contains no stale medium-v1 headline counts (`139`, `44`,
`204,000`, or `18/5/1`) and no unresolved insertion marker. The evidence ledger
maps each central manuscript claim to a full-v1 artifact and an explicit claim
boundary.

## Repository and report consistency

The active `README.md`, methodology, investigation, RQ ledger, experiment log,
experiment bank, results notebook, and manuscript all use the full-v1 causal
order and counts. Earlier final reports are preserved under
`reports/historical/medium_v1/` rather than overwritten without provenance.
The experiment bank has no remaining high-priority synthetic execution item;
deferred ideas require a new research purpose or real-data parameter range.

`reports/final_release_manifest.json` is the machine-readable root anchor for
every scoped release artifact. It records repository-relative path, byte size,
SHA-256, and scope group; its deterministic selector detects changed, missing,
and newly added scoped files. The manifest deliberately excludes itself to
avoid a circular self-hash and is anchored by the final Git tree. Verify it
with:

```bash
.venv/bin/python scripts/final_release_manifest.py --verify
```

Task-scoped `git diff --check` passes. The unfiltered command continues to
report only the pre-existing trailing whitespace in user-owned `pipeline.txt`,
which is not read by the pipeline or paper and was deliberately preserved.
The unrelated untracked user files listed in `reports/research_state.md` also
remain untouched.

## Remaining limitations, not execution failures

- Automatic normalisation and item validation have no expert or learner gold.
- K*, simulator parameters, synthetic sample counts, and structural thresholds
  are controlled-world declarations, not human estimates.
- The unseen-value cohort consists of six perfect-progressive cells and cannot
  establish unrestricted out-of-inventory generalisation.
- Learner bootstrap does not represent uncertainty over source annotations,
  item prompts, simulator families, or human populations.
- The compact robustness design uses three seeds and one-factor severities;
  unmodelled item difficulty produces a genuine representation reversal.
- Q full rank is not sufficient for practically unique recovery: the planted
  interaction remains weak even after anchors restore rank.
- The alternate-language schema proves software abstraction only; empirical
  cross-lingual validity remains untested.
- The pre-item generator-alternative pilot records a transient
  `/tmp/grammar_kt_full_v1_structural_items.jsonl` path. It is classified as
  development evidence, not a release reconstruction input; the frozen K*,
  item bank, Q*, measurement audit, and paper results use retained repository
  artifacts.
- Python and TeX dependency versions are recorded where available but the
  environment is not supplied as a fully locked container. Licensed EGP source
  content, provider snapshots, and provider sampling seeds cannot be
  redistributed or reconstructed from this release.

These limitations narrow the claims. They do not leave a declared synthetic
experiment, reconstruction check, notebook, report, or paper build incomplete.
