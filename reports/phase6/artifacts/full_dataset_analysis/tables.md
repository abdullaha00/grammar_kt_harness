# Medium-v1 paper-facing evidence tables

Generated deterministically from retained artifacts; no model calls or learner resimulation.

## Source and normalization

| descriptors | complete | partial | unresolved | out_of_scope | unique_cells | source_cell_edges |
| --- | --- | --- | --- | --- | --- | --- |
| 139 | 44 | 77 | 2 | 16 | 24 | 48 |

## Item construction by frozen cohort

| stage | generation_attempts | candidate_payloads | validator_accepted | validator_covered_cells | would_select_items |
| --- | --- | --- | --- | --- | --- |
| default_prefix_n1 | 24 | 24 | 16 | 16 | 16 |
| default_prefix_n2 | 48 | 48 | 33 | 19 | 33 |
| default_prefix_n3 | 72 | 71 | 51 | 22 | 41 |
| rescue_only | 4 | 4 | 1 | 1 | 1 |
| cumulative_through_rescue | 76 | 75 | 52 | 23 | 42 |
| intervention_only | 2 | 2 | 2 | 1 | 2 |
| final_cumulative | 78 | 77 | 54 | 24 | 44 |

## Grammar fold

| grammar_regime | cells | selected_items | unseen_development_feature_values | value_pairs_unseen_in_development |
| --- | --- | --- | --- | --- |
| development | 18 | 32 | 0 | 0 |
| compositional_holdout | 5 | 10 | 0 | 1 |
| novel_feature_holdout | 1 | 2 | 1 | 6 |

## KC candidate space

| family | raw_candidates | support_eligible | activation_duplicates | selection_eligible | median_item_support |
| --- | --- | --- | --- | --- | --- |
| feature_value | 9 | 9 | 0 | 9 | 6.000000 |
| operation | 10 | 7 | 6 | 3 | 4.500000 |
| interaction | 18 | 8 | 2 | 7 | 2.000000 |
| full_cell | 18 | 18 | 9 | 9 | 2.000000 |

## KC policy granularity

| policy | kcs | interaction_kcs | q_matrix_density | kcs_per_item | median_item_support |
| --- | --- | --- | --- | --- | --- |
| automated | 10 | 1 | 0.218182 | 2.181818 | 8.000000 |
| factorized | 9 | 0 | 0.232323 | 2.090909 | 8.000000 |
| oracle_all_cell | 24 | 0 | 0.041667 | 1.000000 | 2.000000 |
| supported_interactions | 16 | 7 | 0.180398 | 2.886364 | 6.000000 |

## Fixed-logistic primary comparison

| grammar_regime | candidate | delta_log_loss | delta_log_loss_interval_95 | delta_brier_score | delta_brier_interval_95 |
| --- | --- | --- | --- | --- | --- |
| all_test | supported_interactions | -0.000397 | [-0.000782064568956086, -2.600758015055349e-05] | -0.000180 | [-0.0003560395876483959, -7.761800370470384e-06] |
| all_test | automated | -0.000375 | [-0.0006308033158486051, -0.00010936756479462098] | -0.000166 | [-0.00028127975144913995, -4.609487487324536e-05] |
| all_test | oracle_all_cell | 0.013777 | [0.012287590045356038, 0.015234090290699274] | 0.006789 | [0.006070000177074931, 0.007491395781924884] |
| development | supported_interactions | -0.000176 | [-0.0006049541624651547, 0.00025168909623689165] | -0.000079 | [-0.0002760675488147581, 0.00011732586187789534] |
| development | automated | -0.000450 | [-0.0007575669528185719, -0.00014147222138164735] | -0.000203 | [-0.0003391300285979188, -6.494484365016224e-05] |
| development | oracle_all_cell | -0.000234 | [-0.0007528098499007738, 0.00027126632671559846] | -0.000115 | [-0.0003484519837684712, 0.00011169232738670996] |
| compositional_holdout | supported_interactions | -0.001168 | [-0.0020421508947284397, -0.0002456895597132668] | -0.000532 | [-0.0009353487702797716, -0.00010875221271984185] |
| compositional_holdout | automated | -0.000234 | [-0.0008355980065997456, 0.00037532574350429126] | -0.000091 | [-0.00037150925259948165, 0.00019219250924817552] |
| compositional_holdout | oracle_all_cell | 0.059615 | [0.053390119965936775, 0.0656751194672691] | 0.029375 | [0.026350531823183747, 0.03230508042550828] |
| novel_feature_holdout | supported_interactions | -0.000072 | [-0.000280836217971483, 0.0001282327146004338] | -0.000035 | [-0.00013484368936812597, 6.171706684131926e-05] |
| novel_feature_holdout | automated | 0.000119 | [-9.90661263082916e-05, 0.00035198469026455673] | 0.000057 | [-4.742060926588554e-05, 0.00016854267409930802] |
| novel_feature_holdout | oracle_all_cell | 0.008749 | [0.002038683974170472, 0.01511744459303597] | 0.004334 | [0.0010392498440938726, 0.0074639306830886695] |

Negative paired deltas favour the candidate representation. Confidence intervals resample whole learners.

## One versus up-to-two variants (structural only)

| item_bank | development_items | raw_total | selection_eligible | eligible_interactions | activation_duplicate_candidates |
| --- | --- | --- | --- | --- | --- |
| one_rank1_variant_per_cell | 18 | 55 | 23 | 2 | 17 |
| up_to_two_selected_variants_per_cell | 32 | 55 | 28 | 7 | 17 |

This sensitivity recomputes support/equivalence only; it does not read outcomes or rerun learner-evidence selection.
