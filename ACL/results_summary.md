# Retained ACL results summary

This file is a compact index of the evidence reported in `paper.tex`.  The
primary run directories are `runs/base`, `runs/kc_interactions`, and
`runs/kc_full_cell`; the four corresponding `*_seed_20260818` through
`*_seed_20260821` directories complete each five-seed set (20260817--20260821).
All fifteen run metadata records report a clean Git worktree.  The clean source
history is retained in `runs/evidence_snapshot.bundle`.

## Primary artifact counts

| Policy | KCs | Candidate items | Accepted | Q edges | Q density | Row width | Events per seed |
|---|---:|---:|---:|---:|---:|---:|---:|
| Factorized | 9 | 45 | 45 | 99 | 0.244444 | 1--4 (mean 2.20) | 16,200 |
| Factorized + interactions | 14 | 70 | 69 | 201 | 0.208075 | 1--5 (mean 2.91) | 24,840 |
| Whole cell | 24 | 120 | 120 | 120 | 0.041667 | 1 (mean 1.00) | 43,200 |

The single rejection is an automated answer-ambiguity flag in the interaction
run, not a human judgement.  The factorized primary run finishes with 44
complete, 77 partial, 16 out-of-scope, two unresolved, and zero schema-failure
mappings.  Its 48 source-cell edges deduplicate to 24 canonical cells.

## Synthetic KT metrics

Values are mean +/- 95% Student-t interval over five seeds, using
`t(0.975, 4) = 2.776`.  They are descriptive technical checks within each
policy-specific simulated dataset.  Because each policy changes its item pool
and response-generating state, differences between policy blocks are not
controlled policy effects.

| Policy-specific data | Model | Test AUC | Test log loss | Test accuracy |
|---|---|---:|---:|---:|
| Factorized | Empirical | .613378 +/- .010051 | .661139 +/- .010266 | .604938 +/- .009469 |
|  | BKT | .602894 +/- .007024 | .722813 +/- .016300 | .623519 +/- .012858 |
|  | Logistic | .658120 +/- .012889 | .618262 +/- .010027 | .659198 +/- .012685 |
| + interactions | Empirical | .607866 +/- .008169 | .648601 +/- .005891 | .619206 +/- .010104 |
|  | BKT | .603049 +/- .014127 | .690356 +/- .007330 | .662778 +/- .004069 |
|  | Logistic | .645609 +/- .011534 | .603184 +/- .004627 | .680079 +/- .003100 |
| Whole cell | Empirical | .659089 +/- .004875 | .661352 +/- .004510 | .631250 +/- .006947 |
|  | BKT | .650066 +/- .004588 | .728832 +/- .005952 | .621250 +/- .003939 |
|  | Logistic | .690779 +/- .008897 | .625542 +/- .005837 | .652593 +/- .004431 |
