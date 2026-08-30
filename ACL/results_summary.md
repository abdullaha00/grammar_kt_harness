# Retained ACL results summary — known truth and measurement realism

Full-v1 values below remain the immutable known-truth reference. The later
measurement programme is reported separately and never changes its rows.
Historical medium-v1 values are not paper-facing results.

## Dataset construction

| Quantity | Full-v1 result |
|---|---:|
| Source records processed | 1,222 |
| Complete / partial / unresolved / out of scope | 211 / 327 / 9 / 675 |
| Source-cell relations / canonical cells | 228 / 75 |
| Generator KCs | 18 |
| Validator-accepted candidates / selected items | 126 / 113 |
| Seen / unseen-combination / unseen-value cells | 54 / 15 / 6 |
| Seen / unseen-combination / unseen-value items | 84 / 20 / 9 |
| Q* dimensions / edges / rank | 113×18 / 269 / 18 |
| Learners / acquisition / probes / all events | 1,000 / 170,000 / 113,000 / 283,000 |

The default N=3 campaign accepted 102/225 candidates and covered 57/75
cells. Unchanged rescue accepted 10/36 and added nine cells; explicit
construction accepted 9/18 and added six; a frozen answer-package correction
added one. Open full-sentence imperative production remained indeterminate, so
a separately declared cue-bounded N=2 campaign accepted 4/4 and added the final
two cells. Item quality is model-judged, not human-validated.

Prompt and accepted-answer fields document the intended measurement surface.
The baseline simulator does not render those strings or score a textual
response; it samples binary correctness from item identity, Q*, active mastery,
and keyed randomness.

The final Q* has density .1323, 75 distinct cell-activation rows, no identical
columns, no Jaccard-at-least-.90 pairs, and 2–49 items per KC. Seven KCs have
fewer than six items.

## RQ2 — misspecification

| Representation | KCs | Delta log loss vs K* [95% learner CI] | Item prerequisite-state RMSE |
|---|---:|---:|---:|
| All merged | 1 | +.010225 [.009380,.011029] | — |
| Linguistic families | 6 | +.008132 [.007450,.008779] | .146300 |
| K* | 18 | .670627 absolute | .123738 |
| Structural split-2 | 35 | +.003165 [.002744,.003581] | .132752 |
| Structural split-4 | 66 | +.005868 [.005281,.006473] | .140428 |
| Exact cell | 75 | +.015039 [.014108,.015990] | .163828 |

All nine 10% Q-noise instances are harmful. Mean costs are .001685 false
positive, .002644 false negative, and .002294 mixed; three structural seeds do
not support a universal ordering. Coarse prerequisite-state recovery reverses
on the six unseen-value cells by -.003663
[-.005740,-.001507].

## RQ3 — discovery

The observable-only selector evaluates 181 candidates and retains its 18
atomic features. Atomic and compositional policies have the same seen-Q
signature. After selection freezes:

| Hypothesis | Exact K* KCs | Activation Jaccard | Aligned edge F1 | Probe loss vs compositional |
|---|---:|---:|---:|---:|
| Compositional ceiling | 18/18 | 1.000000 | 1.000000 | .669606 absolute |
| Selected atomic class | 16/18 | .970854 | .965385 | +.000374 [.000228,.000517] |
| RQ3 operation groups | 5/18 | .371913 | .750929 | +.005864 |
| RQ3 seen-cell fine | 1/18 | .084184 | .186969 | +.006657 |
| Hash negative control | 0/18 | .202342 | .359259 | +.013238 |

The ceiling proves reachability, not blind recovery. Unique predictive recovery
is rejected because seen evidence cannot distinguish exact-Q-equivalent rules.

## RQ4 — linguistic generalisation

| Representation | Seen | Pairwise-seen/full-tuple-unseen | Unseen value |
|---|---:|---:|---:|
| K* absolute log loss | .669161 | .672036 | .681181 |
| Exact-cell delta | +.008209 | +.037609 | +.028627 |
| Family-union delta | +.008940 | +.009185 | -.001751, inconclusive |
| Split-2 delta | +.002234 | +.008806 | -.000684, inconclusive |
| K* plus intersections | +.001415 | +.001196 | +.006954 |

The six unseen-value cells all involve perfect-progressive aspect. Their K*
per-cell loss ranges .666512–.691208. A 30-cell exact-item negative control
preserves K* opportunity counts and yields 30,000 outcomes exactly equal to
paired baseline probes; this follows from the no-item-memory baseline.

## Robustness and state semantics

The compact study runs 13 conditions × three seeds × 500 learners. K* ranks
first in 38/39 primary worlds and beats both family-coarse and split-2 in every
seed for 12/13 conditions. Unmodelled item difficulty is the exception:
split-2 mean cost remains +.004138 but ranges -.000413 to +.009955.

Fixed BKT is secondary because its mean/full-credit mechanics mismatch the
minimum/opportunity generator. Its unique learner-KC state RMSE is .300804 and
correlation .434973, illustrating that KT state semantics can diverge from
generator mastery.

## Collection design

Raw predictive validation selects K* in all 21 nested cohorts from N=60 to
1,000, whereas the fixed `.0005 × KC count` objective selects family union in
18/21. Opportunity targets 6/12/24 give K* probe losses
.681757/.672104/.636837 and increasingly separate it from the alternatives.
Moving from max-one to max-two raises items from 75 to 113 and minimum KC
support from one to two, but adds no distinct Q row or rank.

In the two-KC control, A+B-only designs make all compared representations tie
exactly through N=1,000. Anchors restore full rank and expose union merging, but
omitting a planted interaction costs only +.000506 with balanced anchors at
N=1,000; the spurious-interaction negative control is approximately null.
These are conditional synthetic failure boundaries, not human recruitment
thresholds.

## Measurement audit and KC methodology

The strict audit rates 70/113 prompts usable as stored, 15 minor repair, 15
technically valid but artificial, 10 answer-space failure, and three
rewrite/withhold. Across the strict and four-role audits, 60 items are usable in
both, 53 occur in the union requiring action, and 18 occur in the critical
answer-space/withhold union. Four live roles disagree on 56 items.

Only 16/113 Q rows isolate one KC and six KCs lack an isolate. Three independent
outcome-blind induction worlds produce 17/18/18 activation signatures at rank
17/18/17; their intersection is nine, union 30, pairwise Jaccard
.400/.440/.458, and exact K* matches 5/4/7.

## Matched-format bank negative result

The v0.2 run has no technical call failures: 178 calls, 106 generated
candidates, 712 solver attempts, and 90 role outputs. Its three funnels are
38→31→12→3, 35→32→12→2, and 33→26→6→0. Only 5/38 whole families and 20/152
slots pass, covering 4/20 cells, 6/18 KCs, and seen-Q rank 3/18. Measurement
critics accept 9/30 critic-reached candidates, compared with 29/30 linguistic
and 24/30 product decisions; 23/30 are mixed. The release gate fails.

## Controlled measurement nuisance

This is a content-free controlled scenario with 27 × 500-learner response
runs, not a learner-facing bank.

| Contrast (candidate minus reference) | Three-seed mean | Range |
|---|---:|---:|
| Format DiD `(B−A)strong − (B−A)zero` | -.03155149 | [-.03343064,-.02901315] |
| Strong format `C−B` | -.00531682 | [-.00603405,-.00465212] |
| Item-only `D−C` | -.01309876 | [-.01331319,-.01269811] |
| Item+format `D−C` | -.01260890 | [-.01350604,-.01194687] |

Negative format DiD means planted nuisance increases false split B's relative
advantage over shared A. D exactly spans the planted same-seen-item residual
basis and is only a positive control. Item-only B−A is
+.00119473/+.00084733/−.00132758 and every interval crosses zero. Combined
heterogeneity C−B is −.00222577/+.00016911/+.00107418 and every interval
crosses zero.

## Structured response information

| History | Log loss | Failed-KC top-1 | Terminal evidence RMSE |
|---|---:|---:|---:|
| Binary | .636359 | .420781 | .228727 |
| Linked positive control | .635493 | 1.000000 | .144357 |
| 80% linked, otherwise unresolved | .635833 | .883728 | .158804 |
| Within-item shuffled | .636987 | .462525 | .165519 |

Linked-minus-binary log loss averages −.00086664 but one seed interval crosses
zero. The failed KC is post-outcome, deficit-proportional oracle attribution.
The shuffled improvement in the evidence-count diagnostic shows that it is not
sufficient evidence for learner-specific state recovery.

## Assignment-policy recovery diagnostics

| Policy | Item Gini | Median repetition gap | D loss | D item-state RMSE |
|---|---:|---:|---:|---:|
| Q-balanced lab | .162530 | 93.67 | .636359 | .129724 |
| Curriculum | .162530 | 31.00 | .639779 | .139472 |
| Mixed | .162530 | 92.00 | .636341 | .130748 |
| Adaptive | .080298 | 26.67 | .639477 | .141659 |

Relative to lab, mean D-loss deltas are +.003420 curriculum, −.000018 mixed,
and +.003118 adaptive. These are exploratory model-recovery diagnostics, not
policy efficacy. Lab/curriculum/mixed share an occurrence multiset and terminal
oracle mastery by construction; adaptive also changes exposure and state.

## Dialogue continuum

Cloze receives 17/20 naturalness, 17/20 determinacy, 17/20 clear-KC, one
shortcut, and mean response-family lower bound 1.30. Open dialogue receives
20/20 naturalness, 0/20 determinate, 4/20 clear-KC, 13 shortcuts, and response
bound 4.55. Open-minus-cloze risk deltas are +1.00 determinacy, +.70 KC
attribution, +1.50 incidental grammar, +.60 shortcuts, and +3.25 response
families. The pilot contains four generated families and automated critics
only.

## Release decision

There is **no new dataset release**. Full-v1 remains the controlled reference;
the matched learner-facing bank failed its gates, while the structural world is
explicitly non-release and lacks prompts, answers, and scorers. Human/expert
review and a learner answerability pilot remain prerequisites for release
validity.
