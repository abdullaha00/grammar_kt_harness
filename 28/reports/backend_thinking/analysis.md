# Backend thinking-effort audit

Experiment: `BACKEND-THINKING-001`  
Date: 2026-08-28  
Frozen randomisation/bootstrap seed: `20260828`

## Result

The strict predeclared rule is **inconclusive for all three model-backed
stages**: every effort failed at least one zero-tolerance safety, completeness,
or coverage gate. It would therefore be inaccurate to call any setting a
confirmatory winner.

For continued operation, the retained stage-specific fallbacks are:

| Stage | Model | Operational effort | Why this fallback was retained |
|---|---|---:|---|
| Normalisation | `gpt-5.6-sol` | **high** | High and xhigh tied on adjudicated quality (92.4%) and critical mappings (2); high was more repeatable, faster, and lower-token. Medium could not establish five-point non-inferiority to high. |
| Independent validation | `gpt-5.6-terra` | **medium** | Medium had the highest blind-reference agreement (69.4%), tied the fewest confirmed critical false accepts (2), rejected all authored safety controls, and used the least time and tokens. |
| Item generation | `gpt-5.6-sol` | **medium** | Medium had complete judge evidence, no blind-critical item accepted by the frozen validator, the fewest blind position-1 critical defects, and the lowest latency. High improved fixed-judge acceptance and coverage, but accepted two blind-critical items and did not establish a decisive paired gain. |

These are operational risk/quality/efficiency decisions, not superiority
claims. The machine-readable decisions are retained in
[`normalisation/selection.json`](artifacts/live_v1/normalisation/selection.json),
[`validation/selection.json`](artifacts/live_v1/validation/selection.json), and
[`generation/selection.json`](artifacts/live_v1/generation/selection.json).

## Question and design

The audit asked which Codex backend reasoning effort—`medium`, `high`, or
`xhigh`—should be used by each active language-model stage under otherwise
fixed scientific declarations and model aliases. It was a fresh, matched
experiment; historical medium outputs were not reused as the medium arm.

- **Normalisation:** 24 challenge-enriched Phase-1 descriptors and nine fixed
  Phase-2 transitions, with two calls per effort. Phase 1 and Phase 2 therefore
  contributed 48 and 18 calls per effort (66 per effort; 198 total).
- **Validation:** 36 fixed natural challenge items plus 12 supplementary
  authored negative safety controls, with two calls per effort (96 per effort;
  288 total). Primary quality uses only the 36 natural items (72 successful
  calls per effort); the 24 repeated authored-control calls form a separate
  safety gate.
- **Generation:** all 24 final GrammarCells, three candidate positions per
  cell, and one block per effort (72 calls per effort; 216 total). All generated
  candidates were then judged under one condition-blind, frozen
  `gpt-5.6-terra` medium validator (216 attempted judgments).

Effort calls were interleaved using seed `20260828`. The seed controls cohort
blinding, call ordering, and bootstrap resampling; the provider exposes no
sampling seed. Calls used Codex CLI `0.150.1`, four concurrent workers, frozen
prompt/rulebook/schema hashes recorded in
[`manifest.json`](artifacts/live_v1/manifest.json), and the active model aliases
rather than immutable model snapshots.

The predeclared objective was the lowest admissible effort non-inferior to the
best observed quality, with a five-percentage-point margin, a zero-confirmed-
critical-error gate, and—for generation—N=3 coverage no more than one cell
below the best condition. Paired differences use 10,000 percentile-bootstrap
resamples clustered by source descriptor, item, or GrammarCell as appropriate.

The complete audit made 918 stage evaluations: 198 normalisation evaluations,
288 validator evaluations, 216 generation evaluations, and 216 frozen-
validator generation judgments. Thirteen validation decisions ended at the
deterministic answer-span precheck, leaving 905 live model calls. One xhigh
generation judgment returned malformed JSON; 917/918 stage evaluations
therefore produced usable decisions. Codex CLI reported 3,351,258 total tokens: 1,133,198
for normalisation, 834,921 for the validation audit, 815,154 for generation,
and 567,985 for the fixed generation judge.

## Normalisation

Blind quality is adjudicated semantic acceptability among contract-valid
outputs. Repeat stability is exact structural agreement after ignoring note
wording and harmless cell/list order.

| Effort | Valid / calls | Blind quality | Confirmed critical mappings | Repeat structural agreement | Tokens | Median seconds | P90 seconds |
|---|---:|---:|---:|---:|---:|---:|---:|
| medium | 66 / 66 | 59 / 66 (89.4%) | 3 | 26 / 33 (78.8%) | 369,231 | 11.04 | 16.37 |
| high | 66 / 66 | 61 / 66 (92.4%) | 2 | 29 / 33 (87.9%) | 376,624 | 11.37 | 22.59 |
| xhigh | 66 / 66 | 61 / 66 (92.4%) | 2 | 27 / 33 (81.8%) | 387,343 | 12.40 | 37.26 |

Every Phase-2 output was adjudicated acceptable (18/18 for each effort); the
observed quality and critical-error differences came from Phase 1. Relative to
high, medium's paired quality delta was -3.03 points with a 95% cluster-
bootstrap interval of [-9.68, +2.86] points. Its lower bound crosses the frozen
-5-point margin. High and xhigh tied in point quality; high-minus-xhigh was
0.00 points, 95% CI [-4.55, +4.55].

**Strict decision:** inconclusive. Medium, high, and xhigh had respectively
3, 2, and 2 adjudicated critical mappings, so none passed the zero-critical
gate.

**Operational decision:** high. Among the tied higher-quality conditions it
had the best repeat agreement, used 10,719 fewer tokens than xhigh, and avoided
xhigh's much longer P90 latency. This is a fallback in a challenge-enriched
sample, not evidence that high eliminates unsafe mappings.

## Independent validation

Primary quality is agreement with the adjudicated blind accept/reject reference
on the 36 natural challenge items. The denominator is 72 successful natural-
item calls per effort. The authored adversarial controls are excluded from
primary accuracy so that obvious negative controls cannot inflate it.

| Effort | Valid / all calls | Blind-reference quality | Confirmed critical false accepts | Authored safety false accepts | Repeat accept agreement | Tokens | Median seconds | P90 seconds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| medium | 96 / 96 | 50 / 72 (69.4%) | 2 | 0 / 24 | 26 / 36 (72.2%) | 271,454 | 10.36 | 13.15 |
| high | 96 / 96 | 42 / 72 (58.3%) | 3 | 0 / 24 | 22 / 36 (61.1%) | 279,687 | 11.29 | 13.84 |
| xhigh | 96 / 96 | 41 / 72 (56.9%) | 2 | 0 / 24 | 25 / 36 (69.4%) | 283,780 | 12.17 | 15.06 |

Medium-minus-high quality was +11.11 points, 95% CI [0.00, +22.22];
medium-minus-xhigh was +12.50 points, 95% CI [+1.39, +23.61]. Higher thinking
effort therefore did not improve this validator on the frozen cohort. All
efforts safely rejected every authored adversarial control, but all also false-
accepted at least one natural item adjudicated as critically defective.

**Strict decision:** inconclusive. The zero-critical-false-accept gate rejected
all three efforts.

**Operational decision:** medium. It had the best observed quality and lowest
cost/latency, tied xhigh for the smallest confirmed critical count, and was
frozen before it was used to judge generation candidates. Its two critical
false accepts remain a material validator limitation.

## Item generation

Primary quality is acceptance by the single frozen medium validator among
successfully generated and successfully judged candidates. Coverage is the
number of GrammarCells with at least one accepted candidate among N=3. A
separate blind research review evaluated candidate position 1 for every cell
and effort.

| Effort | Generated payloads | Successful fixed judgments | Fixed-judge acceptance | N=3 cell coverage | Blind position-1 quality | Blind critical defects | Critical defects accepted by judge | Span failures | Generation tokens | Median seconds | P90 seconds |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| medium | 72 / 72 | 72 / 72 | 51 / 72 (70.8%) | 21 / 24 | 21 / 24 (87.5%) | 2 | 0 | 1 | 268,832 | 7.37 | 12.24 |
| high | 72 / 72 | 72 / 72 | 56 / 72 (77.8%) | 23 / 24 | 21 / 24 (87.5%) | 3 | 2 | 0 | 278,611 | 7.77 | 12.62 |
| xhigh | 72 / 72 | 71 / 72 | 53 / 71 (74.6%) | 23 / 24 | 21 / 24 (87.5%) | 3 | 1 | 0 | 267,711 | 8.08 | 14.91 |

The one xhigh denominator loss was a malformed fixed-judge response, not a
generation-payload failure. The medium answer-span failure was a deterministic
first-pass packaging defect. Blind position-1 semantic quality tied at 87.5%,
so the fixed judge's higher high-effort acceptance did not receive independent
blind confirmation. Medium-minus-high fixed-judge acceptance was -6.94 points,
95% CI [-18.09, +4.17]; medium-minus-xhigh was -2.82 points, 95% CI
[-12.68, +8.33]. Neither comparison establishes a decisive gain.

**Strict decision:** inconclusive. Medium missed the coverage tolerance because
21 cells is two below the best coverage of 23; the fixed validator accepted two
high and one xhigh candidates adjudicated critically defective; xhigh also had
one unsuccessful judgment.

**Operational decision:** medium. It sacrifices two cells of observed N=3
coverage relative to high/xhigh, but it is the only condition with complete
judge evidence and zero fixed-judge acceptance of the blind-critical reviewed
items. High's acceptance/coverage advantage remains worth revisiting after the
validator and generator defects are repaired; it is not safe to promote from
this run.

## Blind review and adjudication

Two independent research agents reviewed condition-blinded packets under
[`review_protocol.md`](review_protocol.md). Only after both files were frozen
were review IDs joined to effort conditions. Raw disagreements remain in
[`reviewer_disagreements.jsonl`](artifacts/live_v1/analysis/reviewer_disagreements.jsonl),
and the joined evidence is in
[`merged_blind_reviews.jsonl`](artifacts/live_v1/analysis/merged_blind_reviews.jsonl).

| Module | Rows | Exact decision agreement | Decision disagreements | Critical-flag disagreements | Adjudicated rows |
|---|---:|---:|---:|---:|---:|
| Normalisation | 198 | 180 (90.9%) | 18 | 4 | 18 |
| Validation | 48 | 46 (95.8%) | 2 | 3 | 3 |
| Generation | 72 | 67 (93.1%) | 5 | 4 | 5 |
| **Total** | **318** | **293 (92.1%)** | **25** | **11** | **26** |

An independent research-agent adjudicator resolved the 26 rows requiring a
decision or critical-flag resolution. No unresolved score intervals remained.
Adjudication did not overwrite either raw review. These labels are structured
research checks, not human, teacher, or expert gold annotations.

## Interpretation

Increasing thinking effort was not monotonically beneficial:

- Normalisation improved from medium to high on semantic quality and repeat
  stability, but xhigh added cost without improving quality and was less
  repeatable than high.
- Validation quality decreased as effort increased on this cohort. All three
  settings nevertheless retained natural-item safety failures that the authored
  controls did not expose.
- Generation high increased frozen-judge acceptance and coverage, but blind
  position-1 quality tied across efforts and the judge accepted two high
  candidates with adjudicated critical defects.

The evidence therefore supports stage-specific settings rather than one global
thinking effort. It also shows that increasing inference effort is not a
substitute for repairing prompts, validation criteria, or independent safety
checks.

## Limitations

- The strict zero-critical gate made every stage inconclusive. The operational
  settings are transparent fallbacks, not post-hoc redefinitions of that rule.
- Calls used mutable model aliases and no provider sampling seed. Two repeats
  estimate ordinary variability for normalisation and validation but cannot
  isolate future model drift.
- Normalisation calls were launched from the repository root before the audit
  runner isolated later stage calls in a declaration-only working directory.
  A retained transcript scan found no file or tool access, but this boundary
  was procedural rather than sandbox-enforced for that stage.
- Reviewers and adjudicator were research agents, not human learners, teachers,
  or grammar experts. Their agreement does not establish human validity.
- The normalisation sample was challenge-enriched. Its Phase-2 calls started
  from fixed Phase-1 mappings, so they do not compare complete effort-specific
  Phase-1→Phase-2 chains.
- Validation used 36 natural challenge items and 12 authored controls. The
  authored controls all passed, yet natural critical false accepts remained;
  the control set is therefore not exhaustive.
- Generation has one fresh N=3 block rather than repeated blocks. Blind review
  covers position 1 only, while all three positions use one frozen medium
  model-validator condition.
- Latency was measured during four-worker live execution and is sensitive to
  service load. CLI token totals are an efficiency measure, not a billing-cost
  estimate.
- The experiment covers the current English grammar declarations and these two
  model families only. It does not establish a universal effort choice.
- The retained manifest records both the 918 stage evaluations and the 905
  live-model calls; deterministic prechecks must not be mistaken for model
  judgments when interpreting cost or model reliability.

## Reproduction

Run from the repository root. The following are the exact live-call commands
retained in the manifest (absolute interpreter paths are shortened to the
equivalent repository-local `.venv/bin/python`):

```bash
.venv/bin/python scripts/run_backend_thinking_audit.py --stage prepare --output-dir reports/backend_thinking/artifacts/live_v1
.venv/bin/python scripts/run_backend_thinking_audit.py --stage normalisation --output-dir reports/backend_thinking/artifacts/live_v1 --workers 4
.venv/bin/python scripts/run_backend_thinking_audit.py --stage validation --output-dir reports/backend_thinking/artifacts/live_v1 --workers 4
.venv/bin/python scripts/run_backend_thinking_audit.py --stage generation --output-dir reports/backend_thinking/artifacts/live_v1 --workers 4
.venv/bin/python scripts/run_backend_thinking_audit.py --stage generation --output-dir reports/backend_thinking/artifacts/live_v1 --workers 4 --judge-effort medium
.venv/bin/python scripts/run_backend_thinking_audit.py --stage analyze --output-dir reports/backend_thinking/artifacts/live_v1
```

The second generation command reuses the frozen generation payloads and adds
the condition-blind fixed-validator judgments. Before that command,
`validation/selection.json` must be frozen with `operational_setting=medium`,
as enforced by the runner.

The blind review/adjudication procedure is a research annotation step rather
than a model-execution CLI: give each reviewer only the packets and declarations
allowed by `review_protocol.md`, freeze both reviewer files, adjudicate only
flagged rows without altering the raw reviews, and then merge identities and
compute the 10,000-resample analysis with:

```bash
.venv/bin/python scripts/analyze_backend_thinking_reviews.py --output-dir reports/backend_thinking/artifacts/live_v1 --bootstrap-replicates 10000
```

Key retained evidence is
[`automated_summary.json`](artifacts/live_v1/automated_summary.json),
[`review_analysis.json`](artifacts/live_v1/analysis/review_analysis.json), the
three `selection.json` files linked above, and the declaration/cohort hashes in
the manifest. Existing per-call input, prompt, raw output, stderr, parsed JSON,
token, and latency artifacts make each condition inspectable without rerunning
the models.
