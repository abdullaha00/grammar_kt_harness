# Phase 4 — audit and repair of the experimental world

Date: 2026-08-27  
Status: complete

## Claim boundary and hypotheses

Phase 4 audits the same active pipeline built in Phases 2–3. It does not treat
the legacy 24-cell inventory, deterministic fixture, or offline model fixtures
as item-quality evidence.

- **H4.1 / RQ8:** a feature-tuple-based fold can create genuine
  compositional and novel-value regimes without reading learner outcomes or
  depending on ordinal cell IDs.
- **H4.2 / RQ5/RQ9:** development-only acquisition followed by non-updating
  probes provides a cleaner compositional-transfer estimand than mixed history.
- **H4.3 / RQ6:** representation rankings will depend on whether latent learner
  state is factorized, interaction-heavy, cell-specific, or mixed.
- **H4.4 / RQ7:** simulator-derived difficulty and KC-count features can change
  apparent representation performance and therefore should not enter primary
  logistic KT.
- **H4.5 / RQ10/RQ16:** common model-selected language will be at least as
  valid as a six-entry controlled lexicon, while readable source evidence may
  help only where it adds information beyond the fixed GrammarCell.
- **H4.6 / RQ11:** best-of-3 will recover most of the cell-coverage benefit of
  best-of-5 at lower cost than the latter.
- **H4.7 / RQ18:** some all-required validation criteria may be empirically
  redundant, but criteria will be retained unless blinded judgments support a
  safe simplification.
- **H4.8 / RQ12/RQ17:** explicit Phase-2 eligibility plus branch-preserving
  transition checks will sharply reduce unnecessary example calls and reject
  unsafe normalization transitions.

## Experiments and results

Results are appended only after the corresponding retained artifact and exact
command have been verified.

### Semantic fold (RQ8)

Exact command:

```bash
.venv/bin/python scripts/run_fold_analysis.py
```

The 24 schema-valid cells and 42 structural opportunity IDs were partitioned
without learner evidence. The active `0.20` fraction, two-development-cell
constituent support, and explicit `modal=would` novelty declaration yield 18
development cells (33 items), five compositional cells (eight items), and one
novel-value cell (one item). No compositional cell contains an unseen value;
the least-supported constituent occurs in three measured development cells.
The five compositional cells contain 37 distinct value pairs, 36 already seen
in development. Thus this is constituent-compositional rather than an
all-pairs-seen split.

At fraction `0.30`, the split becomes 16/7/1 cells and 29/12/1 items; the
minimum constituent support is two and 41/42 compositional value pairs occur in
development. Changing the configured minimum from one to two changes no
assignment at either fraction. Reversing inputs and replacing every ordinal
cell ID leaves feature-tuple assignments unchanged. Only 12/24 assignments
match the historical ID manifest, confirming that the new fold is a different
semantic intervention rather than an ID rewrite.

**Decision.** Use the active `0.20` fold for subsequent work because it retains
more development support while supplying five clean constituent-compositional
cells and one genuinely unseen value. Report pair coverage separately rather
than claiming all observed interactions have been recombined. Evidence:
`reports/phase4/artifacts/fold/`.

### Normalisation safety and Phase-2 routing (RQ12, RQ17)

Exact command:

```bash
.venv/bin/python scripts/run_normalisation_audit.py
```

This is an offline replay of retained `gpt-5.6-sol`/medium outputs, not a fresh
quality annotation. Among 139 primary descriptors, the final results are 44
complete, 77 partial, 16 out of scope, and two unresolved. The historical
runner made 80 Phase-2 calls but only two ended complete (2.5%); after explicit
eligibility is reconstructed, only 9/80 partial mappings have any dimension
that examples are allowed to resolve. The stronger routing would therefore
avoid 71 of those 80 example calls (88.75%) without changing the declared
evidence boundary.

All 80 retained Phase-2 transitions pass the stronger provenance, domain-
narrowing, exact-field, and branch-coverage contract. Eight repeated legacy
annotations agree exactly, but this small selected repeat set does not estimate
general annotation reliability. Six adversarial controls behave as expected:
valid narrowing passes, whereas an exact-field change, eligible-domain
broadening, cross-branch recombination, dropped branch, and eligibility on an
exact dimension fail.

**Decision.** Keep Phase 2 only for explicitly listed uncertain dimensions and
enforce branch-preserving narrowing in active code. Do not claim that Phase 2
has high yield: on the retained sample it is 2.5%, and 77/80 mappings remain
partial. Evidence: `reports/phase4/artifacts/normalisation/`.

### Item generation, best-of-N, and lexical/source interventions (RQ10, RQ11, RQ16)

Exact live command:

```bash
.venv/bin/python scripts/run_item_audit.py --pilot --select-second --workers 4 \
  --generation-model gpt-5.6-sol --validation-model gpt-5.6-terra \
  --reasoning-effort medium \
  --output-dir reports/phase4/artifacts/item_audit/live_pilot
```

Eight structurally diverse cells were fixed before new outcomes. Maximum-N
candidates were generated once, pooled and seed-shuffled, then judged from
neutral IDs by the independent validator; N=1/3/5 results are prefixes of those
same calls. Of 89 attempts, 86 returned structurally valid objects and 56 passed
all required criteria. The three structural failures had empty required notes,
not model-call failures.

| Condition | N | accepted / attempts | covered cells |
|---|---:|---:|---:|
| model-selected | 1 | 6/8 | 6/8 |
| model-selected | 3 | 18/24 | 8/8 |
| model-selected | 5 | 27/40 | 8/8 |
| controlled lexicon | 1 | 5/8 | 5/8 |
| controlled lexicon | 3 | 13/24 | 5/8 |
| controlled lexicon | 5 | 23/40 | 7/8 |
| readable source evidence | 1 | 2/3 | 2/3 |
| readable source evidence | 3 | 6/9 | 3/3 |

All eight model-selected cells have at least two accepted variants in the N=3
prefix. N=5 adds accepted candidates but no cell coverage and lowers end-to-end
acceptance from 0.750 to 0.675. The constrained six-entry lexicon never covers
the present-perfect-negative sentinel and reaches only 7/8 cells even at N=5.
It also produces lower lexical diversity at comparable N. These results support
common model-selected lexical/contextual material and best-of-3 for the next
scale-up.

Readable source evidence is available for only three sentinels. On those same
three cells at N=3, both the ordinary and source-evidence conditions yield six
accepted candidates from eight structurally valid outputs. The sample is too
small for a positive source-evidence claim, and opaque source IDs have no
linguistic content. Source-to-cell links should be retained in dataset
provenance but not passed as opaque generation input.

After restricting comparison to tags fixed by the GrammarCell, all 86 live
candidates' generator tags agree with the deterministic declaration. This is
evidence of reproducibility but also redundancy: the tags add no activation
information beyond the cell, while realisation-dependent tags remain outside
the validated candidate interface. They should be removed from active item
records rather than presented as an independent annotation source.

The 89 generation calls accumulated 1,841.3 seconds of concurrent call time
(median 11.49 seconds); 86 validation calls accumulated 922.1 seconds (median
10.53). These sums are not wall-clock time because four calls ran in parallel,
and provider monetary cost was unavailable.

Among the 86 valid judgments, target fidelity, grammaticality, non-target
language simplicity, no leakage, and no-world-knowledge pass every item.
Determinacy fails 29 of the 30 rejected candidates, sometimes alongside
naturalness, pedagogical suitability, or extraneous grammar. This is evidence
that validation materially filters the generator, not yet evidence that the
always-passing criteria can safely be removed. A repeat/model-sensitivity audit
is reported separately below.

**Decision.** Scale the active method as three model-selected candidates per
cell and retain up to two independently valid, lexically distinct variants.
Do not spend N=5 calls by default. Keep the controlled lexicon as a rejected
ablation and omit opaque source IDs from the generation prompt. Evidence:
`reports/phase4/artifacts/item_audit/live_pilot/`.

### Validation reliability and redundancy (RQ18)

Exact command:

```bash
.venv/bin/python scripts/run_validation_reliability.py \
  --input-dir reports/phase4/artifacts/item_audit/live_pilot \
  --output-dir reports/phase4/artifacts/validation_reliability \
  --sample-size 24 --seed 20260827 --workers 4 \
  --repeat-model gpt-5.6-terra --sensitivity-model gpt-5.6-sol \
  --reasoning-effort medium
```

The outcome/condition/failure/cell-stratified sample contains 12 originally
accepted and 12 rejected items across all eight cells and all observed failure
criteria. Original versus same-model repeat acceptance agrees on 19/23 valid
rejudgments (82.6%, Wilson 95% interval [62.9, 93.0], kappa .652); one repeat
is malformed and retained as invalid. Original Terra versus Sol agrees on
19/24 (79.2%, [59.5, 90.8], kappa .583). Terra repeat versus Sol agrees on
18/23 (78.3%, [58.1, 90.3], kappa .569). This is material model/judgment
uncertainty, not evidence for a deterministic gold validator.

Same-model criterion agreement is 82.6% for determinacy and 91.3% for
pedagogical suitability; the alternate-model rates are 79.2% and 79.2%, with
naturalness at 87.5%. Naturalness and pedagogical suitability have failure
Jaccard .875 on the full 86-item bank but are not identical and diverge across
models. Five criteria have no negative cases; their perfect agreement is a
ceiling effect rather than evidence of redundancy. A declared six-item agent
review (not human validation) confirms a subject/blank answer-span mismatch and
several undercued grammatical forms.

**Decision.** Retain the explicit per-criterion, single independent validator;
an ensemble has no human-gold evidence to tell which disagreement is correct.
Keep all criteria, clarify determinacy as target-form plus accepted-surface-form
adequacy, and add a conservative deterministic answer-span consistency check.
Quantitative item-quality claims must identify the bank as model-validated and
report this reliability limitation. Evidence:
`reports/phase4/artifacts/validation_reliability/`.

### Frozen transfer, latent worlds, and KT audit (RQ5, RQ6, RQ7, RQ9, RQ20)

Exact command:

```bash
.venv/bin/python scripts/run_phase4_world_audit.py
```

The fixed structural bank has 24 cells/42 item identifiers and the semantic
18/5/1 fold. For each of four declared worlds and seeds 20260827--20260829,
240 learners receive either five passes of development-only acquisition plus a
single frozen all-bank probe, or the six-pass mixed-history control. The same
events are reused across factorized, all-supported-interaction, automated, and
labelled oracle-all-cell representations. The 12 frozen streams each contain
49,680 events, including 10,080 probes; no legacy outcomes or KCs are used.

The 18-development-cell bank generates 55 raw candidates: 9 features, 10
operations, 18 interactions, and 18 exact cells. There are 38 activation
classes, 17 duplicate candidates, 41 support-eligible candidates, and 27
selection-eligible representatives. Two planted interaction-heavy dependencies
meet the 2-cell/3-item guard; present×passive has two cells but only two items
and is correctly marked below threshold.

#### Automated recovery and stability

| Latent world | selected KC counts (3 seeds) | mean Jaccard | selected planted interactions |
|---|---:|---:|---:|
| factorized | 9, 9, 9 | 1.000 | 0/3 |
| interaction-heavy | 11, 12, 11 | .944 | both eligible interactions, 3/3 each |
| cell-specific | 9, 9, 9 | 1.000 | 0/3 |
| mixed | 9, 9, 10 | .933 | perfect×negative, 1/3 |

Thus the selector now passes both a stronger null control and a repeated
interaction-recovery control. It remains conservative in the mixed world and
cannot choose exact-cell candidates because active additions deliberately
exclude them.

Primary no-oracle logistic frozen-probe mean all-test log loss is:

| World | factorized | automated | automated minus factorized |
|---|---:|---:|---:|
| factorized | .578311 | .578311 | .000000 |
| interaction-heavy | .609353 | .607097 | -.002256 |
| cell-specific | .686715 | .686715 | .000000 |
| mixed | .641559 | .641575 | +.000016 |

On the reference interaction-heavy seed, automated minus factorized log loss
is -.002666 with learner-bootstrap 95% interval [-.004244, -.001103] over all
probes. The compositional-only delta is -.001438 [-.005268, .002646], so the
evidence supports predictive interaction recovery but not a decisive
compositional-transfer benefit. The oracle exact-all-cell baseline wins only in
the matching cell-specific world (mean all-probe .679439 versus .686715;
compositional .681244 versus .704406). It is substantially worse on
compositional probes in the other worlds. This demonstrates the intended
granularity tradeoff and also the active selector's cell-world limitation.

#### Protocol and KT controls

Frozen compositional and novel probes have exactly zero prior same-cell
exposures. Under mixed history, compositional probes have mean 8.843 prior
same-cell exposures (range 4--11) and novel probes 4.836 (4--5). In the
cell-specific world the private oracle mean compositional response probability
rises from .417 frozen to .567 mixed. Mixed-history performance is therefore
contaminated by direct acquisition and is rejected as the primary transfer
protocol.

Flipping every probe outcome and reversing probe order changes empirical, BKT,
and logistic predictions by exactly zero in all worlds. Primary factorized
logistic versus labelled oracle-difficulty or KC-count controls differs by less
than .00020 reference-seed log loss, so removing them is methodologically
clean with negligible observed performance cost here. Logistic C=.1/1/10 does
not change representation ordering. Exact activation-column duplication leaves
BKT predictions identical but shifts logistic probabilities by up to .00071--
.00199 because L2 regularisation is dimension-dependent. Multi-KC BKT assigns
the full response update to a mean 2.15 active factorized KCs/event and 2.94
all-supported KCs/event, versus one exact-cell KC; this is a real shared-credit
confound. BKT/logistic selector Jaccard ranges .600--.846, and BKT overselects
three to six additions in null/cell/mixed controls. Keep BKT as sensitivity,
not the selector.

Factorized projection covers every compositional item but zero percent of the
novel `would` item: `would` is absent from development and its other values are
declared backgrounds. This is an honest limitation rather than a reason to
invent a holdout KC.

**Decision.** Make development acquisition plus frozen probes primary; retain
mixed history only as a contamination/ontology-generalisation control. Keep
observable standardized logistic without oracle difficulty or KC count as the
fixed selector and primary KT comparison, with BKT/empirical sensitivities.
Retain the automated predictive/parsimony selector: it recovers supported
interactions when they are strong, defaults stably to marginals in two null
worlds, and exposes rather than solves the cell-specific alternative. Evidence:
`reports/phase4/artifacts/world_kt/study_v1/`.

### Active integration and research-configuration audit

The Phase-4 findings now alter the single active path rather than remaining
experimental side scripts. `scripts/run.py` performs best-of-three generation,
independent validation, deterministic selection of at most two variants,
semantic folding, frozen probes, automated selection, projection, KT, and
evaluation in that order. It writes both the complete validator-accepted pool
and the smaller selected bank; only the latter enters fold construction,
simulation, KC support, and KT. The fixture has an explicit one-candidate
override solely to keep offline verification small.

The active researcher-facing declarations correspond to interventions:

- normalisation prompts/rulebook and the canonical schema control the
  source-specific evidence boundary and canonical values;
- item design controls calls per cell and bank size/diversity; validation YAML
  controls required criteria and the enforced all-required rule;
- semantic fold YAML controls novelty, compositional fraction, and minimum
  constituent/item support;
- protocol/world YAMLs control acquisition/probes and latent learner
  assumptions;
- KC candidate/selection YAMLs control candidate families, references,
  support, scorer, and parsimony;
- KT YAML controls the small model family and observable logistic features.

Pseudo-controls were removed: unused evaluation metric lists, KT history/split
prose, and active-world `learning_update` labels. Their behavior is a fixed
methodological invariant visible in code, not an adjustable switch. The
validation `acceptance_rule` is now checked by active code. Opaque source IDs,
generator notes, and operation tags are absent from active item generation.
The controlled lexicon and contextual/source prompt remain clearly scoped
audit inputs; manual policies and the ordinal reference fold remain historical
baselines and will receive final active/archive separation in Phase 7.

### Phase checkpoint verification

Exact commands:

```bash
.venv/bin/python -m pytest -q
.venv/bin/python scripts/run.py --fixture \
  --output runs/phase4_checkpoint_fixture
.venv/bin/jupyter nbconvert --to notebook --execute --inplace \
  notebooks/pipeline_walkthrough.ipynb --ExecutePreprocessor.timeout=180
git diff --check -- . ':(exclude)pipeline.txt'
```

The suite reports 82 passing tests. The fixture selects six items and produces
624 fixed events. The walkthrough executes without cell errors and calls the
same active functions. The scoped whitespace check is clean; the whole-tree
check still reports only the pre-existing user-owned trailing whitespace in
`pipeline.txt`.

## Phase-4 answers and remaining uncertainty

- RQ8/RQ9 are answered for the current schema and synthetic protocol: semantic
  tuple folds plus frozen probes give the required acquisition boundary.
- RQ6/RQ7 are answered within four declared synthetic worlds: rankings depend
  on latent structure, no policy universally wins, and observable logistic is
  a cleaner selector than the audited mean-credit BKT.
- RQ10/RQ11 support model-selected text and N=3 at eight-cell pilot scale;
  human realism and 24-cell coverage remain Phase-6 questions.
- RQ12/RQ17 support explicit eligibility and stronger transition checks, while
  also establishing low historical Phase-2 yield.
- RQ18 remains partial because model agreement is not human validity.
- RQ5 remains partial: the estimand is now correct, but automated interactions
  do not yet show a decisive compositional-probe benefit.

Phase 5 therefore reuses the fixed medium-scale streams to investigate learner
support, parsimony sensitivity, and inventory stability before the live
24-cell bank is generated.
