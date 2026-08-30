# Measurement-realism experiments: implementation preregistration draft

Status: design proposal; no responses have been generated under this design.

Date: 2026-08-30

Protected reference: `data/grammar_kt_full_v1/`

Companion configuration proposal: `scenario_config_proposal.yaml`

Upstream programme protocol:
[`../protocols/program_preregistered.md`](../protocols/program_preregistered.md)

Literature constraints:
[`../literature/synthesis.md`](../literature/synthesis.md) and
[`../literature/source_ledger.jsonl`](../literature/source_ledger.jsonl)

## 1. Scope and claim boundary

This is the smallest confirmatory implementation that can distinguish a clean
KC-representation question from measurement nuisance, learner heterogeneity,
selection policy, and structured response information. It is not a claim that
one simulator is human-like. Numerical effects are planted, interpretable
scenario magnitudes constrained only broadly by the literature review.

The protected full-v1 dataset remains the clean reference world. The proposed
study reads its fixed GrammarCells and K*/Q* declarations but writes no file
under `data/grammar_kt_full_v1/`.

The confirmatory questions are:

1. Can a format-specific false split gain predictive performance when format
   nuisance is planted, despite shared generator K*?
2. Can explicit format and item terms retain the shared K* representation while
   explaining that nuisance?
3. Does the conclusion survive a small, declared heterogeneous-learner world?
4. Does it change when the same bank is sequenced by laboratory, curriculum,
   mixed-practice, or observable-weakness policies?
5. Does a structured error category recover information that binary
   correctness discards?

The study does **not** test whether K* is human cognitive truth, estimate human
format effects, or validate generated error text.

## 2. Necessary correction to the 12-cell feasibility proposal

The literature synthesis proposed 12 cells by four formats by two variants.
That is a useful partial-rank usability pilot, but it cannot retain rank 18:
when all matched formats and variants preserve a cell's Q row, 12 cell-level
rows have rank at most 12.

The frozen Q* has cell-level rank 18 both over all 75 cells and over the 54 seen
cells. A deterministic lexicographic greedy pass supplies an 18-seen-cell rank
18 witness. Therefore:

- a study claiming recovery over all 18 generator KCs requires at least 18
  distinct cell-level activation rows;
- a 12-cell/96-item pilot must be labelled a partial-rank format/usability
  pilot and must not support all-K* identifiability or recovery claims;
- the smallest proposed confirmatory bank has 18 seen cells, four formats, and
  two semantic/lexical variants: `18 * 4 * 2 = 144` acquisition-eligible items;
- two optional held-out audit cells, one `unseen_combination` and one
  `unseen_value`, add four formats and one variant each, giving 152 total probe
  items. These eight rows are not used for acquisition or rank claims.

The final 18 cells must be selected before simulated outcomes. Rank, all-KC
coverage, and the declared grammar/rarity strata are hard constraints. Item
audit results may break ties because they precede learner simulation; KT or
learner outcomes may not.

The lexicographic witness is recorded in `q_basis_feasibility.json`. It proves
feasibility and is not the final pedagogical selection.

## 3. Matched-bank contract

Each seen cell has two shared semantic specifications. Each specification is
rendered in:

- `constrained_cloze`;
- `multiple_choice`;
- `sentence_transformation`;
- `dialogue_completion`.

For a matched `(cell, variant)` family, all four items must have the same
GrammarCell and generator-Q row. Lexical content, intended proposition, and
target grammatical realization must be as comparable as the response
mechanism allows. Format is not inferred from free text; it is frozen metadata.

Every family must pass linguistic validity, answer determinacy, learner
usability, and response-mechanism gates in all four formats. A failed format
rejects the family from the confirmatory bank. Pedagogical and platform
plausibility remain separately reported judgments and are never averaged into
Q rank.

The seen acquisition bank must satisfy:

```text
cells >= 18
generator KCs = 18
cell-level Q rank = 18
every selected cell crossed with every format
two independent semantic/lexical variants per selected cell
no format-specific Q row
```

## 4. Generator equations

### 4.1 Mastery and learning

For learner `l`, generator KC `k`, and event time `t`:

\[
M_{lk0} \sim \operatorname{Beta}(2,2).
\]

For item `i`, let `K_i = {k: Q^*_{ik}=1}`. The clean prerequisite state is

\[
m_{lit}=\min_{k\in K_i}M_{lkt}.
\]

On an updating acquisition event, every active KC receives the full-v1
opportunity update, irrespective of correctness:

\[
M_{lk,t+1}=M_{lkt}+\rho_l(1-M_{lkt}),\quad k\in K_i.
\]

Inactive KCs are unchanged. Probe events never update. There is no forgetting
in the confirmatory study. This deliberately preserves one interpretable
learning mechanism while changing the measurement layer.

The homogeneous worlds use `rho_l = 0.02`. The heterogeneous world draws a
bounded learning rate with mean `mu=.02` and coefficient of variation `.25`:

\[
\rho_l\sim\operatorname{Beta}(\alpha_\rho,\beta_\rho),
\]

where

\[
T=\frac{1-\mu}{\mu\,CV^2}-1=783,\quad
\alpha_\rho=\mu T=15.66,\quad
\beta_\rho=(1-\mu)T=767.34.
\]

This Beta choice matches the declared mean/CV while respecting `[0,1]`; it is
a scenario distribution, not an estimate of learners.

### 4.2 Item effects orthogonal to Q and format

Let `z_i` be a keyed standard-normal draw for every item. Let `X` contain an
intercept, full-rank format contrasts, and the 18 Q* columns. Define

\[
r=(I-XX^+)z,\qquad
\widetilde r=r/\operatorname{sd}_{pop}(r),\qquad
b_i=\sigma_b\widetilde r_i.
\]

`X^+` is the Moore--Penrose inverse. Thus the realised finite-bank item effects
have mean zero, population SD `sigma_b`, and are orthogonal (within numerical
tolerance) to planted format and Q columns. Positive `b_i` means harder. The
projection is an experimental isolation device, not a population model of item
difficulty.

The main item scenarios use `sigma_b=0.50`; `1.00` is retained only as a
predeclared strong sensitivity. A one-SD latent-logit shift of `.50` has odds
ratio `exp(.50)=1.65`; this is a stress magnitude, not a human estimate.

### 4.3 Format effects

The four canonical format IDs are sorted and assigned the frozen contrast

\[
c_f\in\{-3,-1,1,3\}/\sqrt{5}.
\]

The contrast has exactly zero mean and population SD one. The planted format
offset is

\[
\delta_f=\sigma_f c_f.
\]

Its direction is an arbitrary preregistered stress-test direction and must not
be interpreted as a claim that one named format is easier. The main magnitudes
are `sigma_f=.35` (one-SD odds ratio `1.42`) and `.70` (one-SD odds ratio
`2.01`, positive control). The zero world uses `sigma_f=0`.

### 4.4 Learner response heterogeneity

The combined heterogeneous world adds a learner response intercept

\[
a_l=.35 z_l,\quad z_l\sim N(0,1),
\]

with the realised finite sample centred and population-standardised before
scaling. It also draws independent learner guess and slip bases:

\[
g_l=.05+.10G_l,\quad s_l=.05+.10S_l,\quad
G_l,S_l\sim\operatorname{Beta}(2,2).
\]

Both have expectation `.10` and range `[.05,.15]`. Homogeneous worlds retain
`g_l=s_l=.10`.

### 4.5 Response link

The primary generator retains the full-v1 bounded response semantics while
adding nuisance on the latent mastery logit:

\[
z_{lit}=\operatorname{logit}(\operatorname{clip}(m_{lit},\epsilon,1-\epsilon))
        +a_l+\delta_{f(i)}-b_i,
\]

\[
p_{lit}=g_l+(1-g_l-s_l)\operatorname{logistic}(z_{lit}),
\]

\[
Y_{lit}=\mathbb{1}[U^{response}_{lt}<p_{lit}],\quad \epsilon=10^{-12}.
\]

With all nuisance terms zero and `g=s=.10`, this is bitwise-equivalent up to
the clipping boundary to
`0.10 + 0.80 * min(active mastery)`. Tests must use interior mastery values to
verify exact numerical equivalence.

Item and format effects are additive only on the declared latent logit. The
probability-scale effect shrinks near the guess/slip bounds; saturation by
world, format, and item must be reported.

Format-specific guess/slip is not included in the smallest A--D experiment: it
would make a single additive format intercept knowingly misspecified. It is a
separate nonlinear-link sensitivity only after the additive nuisance result is
established.

## 5. Common random numbers

Every potential latent stream is drawn in every world, even if its multiplier
is zero. SHA-256 keyed generators use independent namespaces:

```text
initial_mastery: seed, learner_id, kc_id
learner_ability_z: seed, learner_id
learner_learning_rate: seed, learner_id
learner_guess: seed, learner_id
learner_slip: seed, learner_id
item_difficulty_z: seed, item_id
acquisition_response: seed, learner_id, acquisition_step
probe_response: seed, learner_id, probe_repeat, item_id
failed_kc_draw: seed, learner_id, phase, sequence_index
policy_exploration: seed, learner_id, acquisition_step
policy_tie_rank: seed, policy_id, learner_id, acquisition_step, item_id
model_split: split_seed, learner_id
error_shuffle: seed, item_id, phase
```

Acquisition response uniforms are step-keyed so different assignment policies
receive a monotone paired draw at the same opportunity number. Probe uniforms
are item-keyed so the same learner/item probe is exactly paired across worlds
and policies. Policy exploration and tie-breaking never reuse response draws.

Moderate and strong effects multiply the same raw latent vector. Within a seed,
the implementation must hash and verify equality of raw initial, learner,
item, response, model-split, and failed-KC streams across applicable worlds.
Outcome hashes are expected to differ.

Seeds are `20260829`, `20260830`, and `20260831`. Each seed has 500 learners.
The three seeds are replication scenarios, not three independent real studies.

## 6. Small confirmatory response-world matrix

Run only these six balanced-policy worlds initially:

| World | Item SD | Format SD | Ability SD | Learning-rate CV | Learner g/s |
|---|---:|---:|---:|---:|---|
| `clean_zero` | 0 | 0 | 0 | 0 | `.10/.10` |
| `format_moderate` | 0 | .35 | 0 | 0 | `.10/.10` |
| `format_strong_control` | 0 | .70 | 0 | 0 | `.10/.10` |
| `item_moderate` | .50 | 0 | 0 | 0 | `.10/.10` |
| `item_format_moderate` | .50 | .35 | 0 | 0 | `.10/.10` |
| `combined_heterogeneous` | .50 | .35 | .35 | .25 | independent `[.05,.15]` |

The zero world is the negative control. `format_strong_control` is the planted
positive control. `item_format_moderate` versus `combined_heterogeneous` is the
small learner-heterogeneity robustness contrast. This avoids a large
factorial. Component-wise heterogeneity ablations and item SD `1.0` remain
secondary diagnostics only if the combined world changes the primary
conclusion or fails distributional gates.

## 7. Models A--D

### 7.1 Causal observable history features

Reuse the observable PFA-like history implementation. Before event `e`, for a
hypothesised representation `R`, compute:

1. Beta(1,1)-smoothed learner-wide prior correctness;
2. mean Beta(1,1)-smoothed correctness over active hypothesised KCs;
3. mean `log1p` prior opportunities over active hypothesised KCs;
4. active hypothesised-KC count;
5. one indicator for each active hypothesised KC.

Only prior acquisition responses update histories. Probe outcomes never enter
history. All features for the current row are constructed before its outcome is
read.

The false format split is fixed outcome-free as

\[
Q^B_{i,(k,f)}=Q^*_{ik}\mathbb{1}[f(i)=f].
\]

It has at most `18 * 4 = 72` columns. Empty split columns are prohibited, so the
matched bank must cross every retained KC and format.

### 7.2 Nuisance contrasts

Use three orthonormal, sum-zero format contrasts. For model D, use orthonormal
within-format item contrasts; their span contains vectors whose item effects
sum to zero separately within each format. This makes item residuals and
format intercepts identifiable. Raw item one-hot plus format one-hot is
rank-deficient and is not permitted.

The models are:

```text
A: shared K* history features
B: format-split K* history features
C: shared K* history features + format contrasts
D: shared K* history features + format contrasts + within-format item contrasts
```

The primary fitted response link should match the generator bounds:

\[
\widehat p_e=.10+.80\operatorname{logistic}(x_e^T\theta).
\]

Fit by penalised Bernoulli likelihood. The intercept is unpenalised. Continuous
history predictors are standardised using training learners only. All models
use the same regularisation grid `{0.1, 1.0, 10.0}` expressed as inverse L2
strength, chosen by dev-learner probe log loss. A standard-logistic fit using
the existing implementation is retained only as a compatibility sensitivity;
it must not silently replace the bounded primary link.

### 7.3 Learner split and evaluation

A keyed, world-invariant split assigns 60%/20%/20% of learners to
train/dev/test. Global parameters fit on acquisition rows from train learners.
Dev probe rows select regularisation. The selected model refits on train+dev
acquisition rows. Test learner acquisition outcomes may update that learner's
causal history but may not fit global parameters. Final metrics use test
terminal probes only.

All A--D models within a world must consume identical observable event keys.
The model split and event-row hashes must match across worlds for the balanced
policy.

### 7.4 Primary contrasts

The preregistered contrasts use event-level loss differences aggregated within
test learner and paired across models/worlds:

1. format confounding difference-in-differences:
   `(LL_B - LL_A)_format_strong - (LL_B - LL_A)_clean_zero`;
2. explicit format remedy: `LL_C - LL_B` in `format_strong_control`;
3. item remedy: `LL_D - LL_C` in `item_moderate` and
   `item_format_moderate`;
4. heterogeneity robustness: whether the signs of contrasts 1--3 survive in
   `combined_heterogeneous` where applicable.

Directional hypothesis: planted format nuisance makes contrast 1 negative;
C matches or improves on B while retaining shared K*; D improves on C when
stable item nuisance is present. A gain for B is predictive evidence only and
never makes B the generator ontology.

The clean-zero B-versus-A result is a falsification diagnostic. If B already
wins consistently there, investigate flexibility, pooling, or leakage before
attributing a later gain to format.

## 8. Mastery/state recovery

Prediction alone cannot establish ontology recovery. Before opening private
oracle files, freeze public-only predictions and nuisance-removed latent state
estimates.

For a probe event, remove fitted format and item terms from C/D and define

\[
\widehat m^{(R)}_{li}=\operatorname{logistic}(x^{state}_{li,R}\widehat\theta_R).
\]

For A/B there are no explicit nuisance terms to remove. Compare this with the
private oracle target `min_{k in K_i} M_lk` only after the public artifact is
frozen. Call the result **item prerequisite-state RMSE**, not individual-KC or
human-mastery recovery.

A secondary KC-level diagnostic constructs a counterfactual single-KC feature
row at each test learner's terminal history, with format/item contrasts zero.
For B, average the four format-child state estimates back to the parent K* KC.
Report terminal `(learner, K*)` RMSE, MAE, correlation, and calibration. This is
a model-state diagnostic over known synthetic truth, not evidence that a
single-KC item exists or that the state is psychologically valid.

## 9. Metrics and uncertainty

Primary predictive metric: event-weighted terminal-probe log loss.

Secondary metrics:

- Brier score;
- 10-bin fixed-width ECE with the full bin table;
- ROC AUC and threshold-.5 accuracy;
- item prerequisite-state RMSE/MAE/correlation/calibration;
- secondary KC-level terminal state RMSE;
- by-format, by-item, by-KC-support, single/multi-KC, and grammar-regime slices;
- realised probability saturation and learner/item/format accuracy
  distributions.

Use 2,000 paired learner bootstrap resamples per seed for model and world
contrasts. Report point estimates and percentile 95% intervals. Also report all
three seed-specific estimates, their mean, and range; do not treat three seeds
as enough for a population-level random-effects claim. No result may be
selected only because one seed is favourable.

## 10. Equal-budget platform policies

Build the balanced acquisition occurrence multiset using the existing
`exhaustive_then_q_balanced` rule: one pass over every seen matched item,
followed by top-up until every K* KC has at least 12 opportunities. Freeze its
length `B` before responses. For the 18-cell feasibility witness, 144 first
exposures plus 40 top-ups gives `B=184`; the final selected bank must recompute
and freeze its own B. Every policy uses exactly B acquisition events and the
same complete non-updating terminal probe.

### 10.1 `q_balanced_lab`

Use the frozen occurrence multiset and the existing keyed occurrence-rank
ordering, respecting item exposure order. This is the clean laboratory
reference.

### 10.2 `curriculum`

Use exactly the same occurrence multiset. Each cell receives an outcome-free
`curriculum_stage` in `{1,2,3,4}` using declared source/complexity metadata
before simulation. Order occurrences lexicographically by curriculum stage,
then exposure number, then a keyed learner rank. No item may appear before its
stage. Earlier-stage repetitions remain eligible in later stages.

### 10.3 `mixed_practice`

Use exactly the same occurrence multiset. Subject to exposure `j` following
exposure `j-1` for the same item, greedily order the next occurrence by:

1. smallest Q-row Jaccard overlap with the previous item;
2. avoid repeating the previous format;
3. longest gap since the same cell;
4. longest gap since the same item;
5. keyed tie rank.

This manipulates interleaving while holding exposure counts fixed.

### 10.4 `adaptive_weakness`

Use a 72-event outcome-free burn-in: one keyed lexical variant for every
selected seen `(cell, format)` pair. This guarantees initial all-KC coverage and
rank. For the remaining `B-72` events, let

\[
\widehat r_{lk}(t)=\frac{1+C_{lk}(t)}{2+O_{lk}(t)}
\]

be Beta(1,1)-smoothed correctness from prior observable acquisition outcomes.
With probability `.20`, select uniformly from eligible items. Otherwise focus
the KC with lowest `r_hat`, then select among items activating it by smallest
item exposure, longest gap, and keyed tie rank. An eight-event same-item
cooldown applies unless it empties the eligible set.

The logged propensity is

\[
\pi(i\mid h_t)=.20/|E_t|+.80\mathbb{1}[i=i^*(h_t)],
\]

where `E_t` is the cooldown-adjusted eligible set and `i*` is the deterministic
exploit choice. The policy may read item metadata, Q*, and prior observable
responses. It may not read mastery, response probability, failed KC, future
outcomes, or probe outcomes.

Balanced, curriculum, and mixed policies have the same occurrence multiset.
With no forgetting and opportunity-only learning, their terminal oracle
masteries must therefore be identical learner-by-learner; this is a required
test invariant. They can still produce different observable paths and KT
recovery. Adaptive selection changes the multiset and may change terminal
truth; that is its intended policy effect.

Policy diagnostics include:

- KC/item/format exposure count, CV, Gini, minimum, and maximum;
- per-learner rank and unique-row count of the actually exposed Q submatrix;
- repetition gaps, same-cell gaps, adjacent Q Jaccard, and format runs;
- learner/item/format accuracy and within-session improvement;
- propensity distribution and dependence of selection on prior error;
- A--D prediction and state-recovery metrics under the same world;
- paired policy contrasts using shared learner latents and probe draws.

The policy study runs only the `combined_heterogeneous` world. The balanced
policy is reused from the response-world study; only three additional policy
worlds per seed are required.

## 11. Structured errors

### 11.1 Private failed-KC attribution

The binary response generator has no discrete causal failure. On an incorrect
event, introduce an explicit private synthetic attribution variable:

\[
P(F_{lit}=k\mid Y_{lit}=0)=
\frac{1-M_{lkt}}{\sum_{j\in K_i}(1-M_{ljt})},\quad k\in K_i.
\]

The draw is keyed independently of the response draw. The term `failed_kc`
therefore means a declared post-response synthetic attribution, not an
empirical diagnosis of a human error. A deterministic weakest-mastery choice
is a secondary sensitivity.

### 11.2 Observable categories

Map F through the frozen many-to-one operation taxonomy in
`scenario_config_proposal.yaml`. The linked positive-control label is
`C=map(F)`. A plausibility sensitivity emits the linked category with
probability `.80` and `non_target_or_unresolved` otherwise. Correct responses
have no error category.

The negative control permutes linked labels among incorrect events within
`(item_id, phase)` using a keyed permutation. This preserves every block's
category marginal and its item/format association while breaking its
learner/mastery alignment. Blocks of size one are reported and unchanged.

`failed_kc`, mastery, deficit weights, and the category-generation draw remain
private. Only `error_category` is potentially observable.

### 11.3 Binary versus error-aware histories

Both models retain an opportunity count for every active K* KC. On a correct
acquisition event, both add success evidence to every active KC. On an
incorrect event:

- binary history adds failure evidence to every active KC;
- error-aware history adds failure evidence only to active KCs whose taxonomy
  category matches the observed category;
- an unresolved category falls back to binary failure evidence.

For each KC, the smoothed evidence rate is

\[
R_{lk}(t)=\frac{1+S_{lk}(t)}{2+S_{lk}(t)+F_{lk}(t)}.
\]

Opportunity count remains a separate feature, so non-implicated active KCs are
not treated as unpractised. Fit the same bounded-link, shared-K*, item+format
nuisance model D with either binary or error-aware causal histories. A shuffled
error-aware history has identical dimensions and label marginals.

The current event's category is never used to predict its own correctness or
its pre-response state. It may update later acquisition history.

### 11.4 Error metrics

On incorrect multi-KC probes report:

- contemporaneous failed-KC top-1 accuracy, MRR, candidate-set size, and log
  loss for (a) uniform over active KCs, (b) uniform over category-compatible
  active KCs, and (c) state-deficit weighting within that set;
- next-response log loss, Brier, and calibration from binary, linked,
  80%-observed, and shuffled histories;
- terminal KC-state RMSE/MAE and item prerequisite-state RMSE;
- results by error family, format, and active-KC count.

The linked category is a positive information control and the within-item
shuffle is a negative control. Surface error text is out of scope unless the
linked/noisy structured labels improve at least one preregistered recovery
measure without degrading calibration materially, after which text requires a
separate validation protocol.

## 12. Observable and oracle schemas

Proposed observable event fields:

```text
learner_id
item_id
sequence_index
session_index
phase
correct
format
policy_id
selection_propensity
grammar_regime
error_category
```

`selection_propensity` is null for deterministic policies; `error_category` is
null for correct responses and for binary-only exports. `session_index` is a
relative grouping only; no arbitrary wall-clock timestamp or forgetting claim
is introduced.

Private oracle fields include:

```text
active_generator_kcs
mastery_before / mastery_after
aggregated_mastery_before
item_effect
format_effect
learner_ability
learner_learning_rate
learner_guess / learner_slip
response_probability / response_draw
failed_kc / failed_kc_draw
policy eligibility audit
```

Items expose format and response mechanism. Q* remains benchmark truth and is
supplied only to model conditions that explicitly declare it.

## 13. Leakage boundaries

1. Cell selection, matched generation, validation, Q projection, formats,
   taxonomy, worlds, policies, splits, metrics, and contrasts freeze before
   learner responses.
2. No item-generation or validation stage may read interactions, learner
   states, KT outputs, or the format experiment.
3. Adaptive scheduling reads only prior observable acquisition outcomes and
   its declared content map; never oracle state.
4. Model A--D receive only the observable rows, their declared projection, and
   allowed item/format metadata. They never receive planted effects,
   probabilities, draws, or mastery.
5. Test learner outcomes never fit global parameters. Test acquisition may
   update that learner's causal online history.
6. Probe outcomes never update histories.
7. Current error category is unavailable for current-response prediction.
8. Public-only predictions and state estimates are frozen and hashed before
   private oracle evaluation.
9. Qualitative examples are sampled by preregistered strata, not by favourable
   model results.
10. All files under `data/grammar_kt_full_v1/` are hash-checked before and after
    every executed stage.

## 14. Computational feasibility

With the proposed 152-item bank and the 18-cell witness schedule:

```text
acquisition events / learner: 184
terminal probes / learner:    152
rows / learner:               336
learners / seed:              500
rows / world:                 168,000
```

Six balanced response worlds over three seeds produce about 3.02 million rows.
Three additional policies (reusing balanced) over three seeds add about 1.51
million rows. Structured-error variants reuse the combined balanced events and
do not resimulate correctness. The confirmatory total is therefore about 4.54
million event rows.

Four models, three regularisation candidates, and three seeds require 216
candidate fits for the six response worlds, plus 108 for the three additional
policy worlds; final refits add 108 at most. Training uses only 60% (or after
selection 80%) of 92,000 acquisition rows per seed/world, and the largest D
design is under roughly 200 predictors for a 152-item bank. This is comfortably
below the scale of the existing full-v1 analyses.

Process one world at a time. Retain compressed observable/error streams only
when required for audit; retain public predictions, aggregate results, exact
configs, hashes, and reconstruction commands. Never retain duplicated event
copies for A--D because those models consume the same rows.

## 15. Required tests before a confirmatory run

### Frozen reference and bank

- full-v1 manifest, Q replay, interaction replay, and protected-directory hash;
- all matched family schemas and hard validation gates;
- exact GrammarCell and Q equality within every matched family;
- at least 18 distinct seen cell rows, rank 18, all 18 KCs supported;
- every selected KC crossed with all four formats;
- a 12-cell fixture is rejected from any rank-18 claim.

### Generator and random numbers

- zero-nuisance response equals the full-v1 equation on interior fixtures;
- probabilities and mastery stay finite and in `[0,1]`;
- item effects have declared realised SD and are orthogonal to intercept,
  format contrasts, and Q within tolerance;
- moderate/strong worlds reuse identical raw item/learner draws;
- all declared common-random hashes match across worlds within seed;
- acquisition/probe response key semantics differ exactly as declared;
- repeated runs are byte-deterministic.

### Models

- A--D design matrices have declared columns and full numerical rank after
  contrast construction;
- B has only outcome-free `(K*, format)` children and no empty child;
- D item contrasts sum to zero within format and are not raw rank-deficient
  item+format dummies;
- histories are causal and probe outcomes do not update them;
- learner splits are disjoint, deterministic, and invariant across worlds;
- scaling uses training learners only, dev selects regularisation, test labels
  are never touched during fitting;
- all models consume the same evaluation-row hash;
- toy metrics and paired learner bootstrap reproduce analytic answers;
- public state estimates exist and hash before the oracle reader can open.

### Policies

- all policies have the same acquisition budget B and terminal probes;
- lab, curriculum, and mixed schedules have exactly the same occurrence
  multiset;
- those three policies have identical terminal mastery for every learner/KC;
- curriculum never presents a cell before its frozen stage;
- mixed ordering respects exposure precedence and declared tie order;
- adaptive burn-in covers all KCs and has rank 18;
- adaptive choices are reproducible from prior observable history alone;
- every logged stochastic propensity is in `(0,1]`, sums to one over the
  eligible set, and matches the realised exploration/exploit branch;
- oracle access during adaptive selection raises immediately.

### Structured errors

- correct rows have no error; every private failed KC is active on an incorrect
  row; deficit probabilities sum to one;
- every K* KC has exactly one declared taxonomy mapping;
- observable rows contain category but never failed KC or deficit weights;
- within-item shuffling preserves category marginals exactly;
- linked and shuffled streams share correctness and every non-error field;
- current labels cannot enter current-row predictors;
- unresolved labels execute the declared binary fallback;
- localisation metrics handle ties and non-identifiable same-category active
  KCs explicitly.

### Audit and reproducibility

- every world emits realised distribution and saturation diagnostics;
- qualitative trace sampler covers each format, policy, error family,
  easy/hard learner, rare/common KC, and unusual trajectory stratum;
- configs, scripts, inputs, outputs, package versions, seeds, commands, and
  semantic hashes enter a run manifest;
- `git diff --check`, focused tests, notebook execution, and paper build pass;
- the protected full-v1 directory hash is unchanged after the programme.

## 16. Stop/scale rules

Do not add dialogue, surface error text, forgetting, response times, dropout,
or format-specific guessing to this confirmatory matrix.

- If the 12-cell usability pilot is retained, stop at partial-rank qualitative
  and format-effect evidence.
- Scale to the 18-cell confirmatory bank only after all matched families pass
  hard gates.
- If B wins in the zero-format world, treat that as a design/model failure to
  diagnose before interpreting the positive control.
- If the linked error label does not improve failed-KC localisation or state
  recovery relative to both binary and shuffled controls, do not generate
  surface error text.
- If matched dialogue completion fails determinacy or measurement-purity gates,
  report the ecology--precision tradeoff and do not silently replace its
  response space.
- A new dataset release is considered only after all experiments, trace audits,
  observable/oracle separation, and reconstruction succeed. Until then these
  remain derived experiments over protected full-v1 truth.
