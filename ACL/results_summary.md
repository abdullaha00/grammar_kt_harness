# Retained ACL results summary

All numbers below are generated from retained Phase-6 artifacts under
`reports/phase6/artifacts/full_dataset_analysis/` and
`data/grammar_kt_medium_v1/`.  Phase-5 robustness numbers come from
`reports/phase5/artifacts/integrated_validation_v1/`.

## Dataset

| Stage | Result |
|---|---:|
| Source descriptors | 139 |
| Complete / partial / unresolved / out of scope | 44 / 77 / 2 / 16 |
| Source-cell edges / unique cells | 48 / 24 |
| Generation attempts / candidate payloads | 78 / 77 |
| Model-validator accepts / selected items | 54 / 44 |
| Cells covered | 24 / 24 |
| Development / compositional / novel cells | 18 / 5 / 1 |
| Development / compositional / novel items | 32 / 10 / 2 |
| Synthetic learners / events | 1,000 / 204,000 |

Before curation, default prefix coverage at N=1/2/3 was 18/21/22 cells.  After
the frozen six-item correction and independent rejudgment, the prefixes contain
16/33/51 accepts and cover 16/19/22 cells.  An unchanged-prompt rescue accepts
1/4; the separately declared explicit-cue intervention accepts 2/2 for its one
cell.  Item quality is model-judged and agent-audited, not human-validated.

## KC space and frozen policies

| Quantity | Result |
|---|---:|
| Raw candidates (feature / operation / pair / development cell) | 55 (9 / 10 / 18 / 18) |
| Activation classes / duplicate excess | 38 / 17 |
| Support-eligible / selection-eligible | 42 / 28 |
| Factorized / all-supported / automated / oracle KCs | 9 / 16 / 10 / 24 |
| Automated addition | aspect=perfect × polarity=negative |

## Final fixed-logistic comparison

| Representation | KCs | All-probe log loss | Delta vs factorized [95% learner CI] | Compositional delta [95% CI] |
|---|---:|---:|---:|---:|
| Factorized | 9 | .643731 | reference | reference |
| Automated | 10 | .643356 | −.000375 [−.000631,−.000109] | −.000234 [−.000836,.000375] |
| All supported | 16 | .643334 | −.000397 [−.000782,−.000026] | −.001168 [−.002042,−.000246] |
| Oracle all-cell | 24 | .657507 | +.013777 [.012288,.015234] | +.059615 [.053390,.065675] |

The final automated policy has a small all-probe improvement in the retained
mixed-world stream, but its compositional interval includes zero; its novel-
value delta is +.000119 [−.000099,.000352].  The all-supported policy improves
in this stream but is a sensitivity, not the penalized selector's output.

## Robustness conclusion

At 240 learners and lambda=.0005, the selector has zero additions in all three
factorized and cell-specific null seeds, while recovering both eligible strong
planted interactions in all three interaction-heavy seeds.  Automated minus
factorized mean log loss across factorized / interaction-heavy / cell-specific /
mixed worlds is 0 / −.002256 / 0 / +.000016.  Exact cells win only in the
cell-specific world.  No representation is universally best, and the current
compositional benefit of automation is unresolved.

On the final curated bank, five out of five 1,000-learner mixed-world seeds
select the identical ten-KC inventory.  Nested 60/240/500/1,000-learner samples
match it; the 120-learner sample selects a different interaction (inventory
Jaccard .818).  This is synthetic selection stability, not human replication.
