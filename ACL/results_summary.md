# Retained ACL results summary — full-v1

All values below are final full-v1 evidence. Historical medium-v1 values are
not paper-facing results.

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
| Coarse | 5/18 | .371913 | .750929 | +.005864 |
| Fine exact-cell | 1/18 | .084184 | .186969 | +.006657 |
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
