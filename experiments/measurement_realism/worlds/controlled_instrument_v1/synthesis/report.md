# Controlled-world evidence synthesis

Status: **non-release, content-free controlled structural evidence only**. Learner-facing measurement validity and platform plausibility were not assessed.

## Integrity

- Study plan SHA-256: `e3d50e10001b7dff8042b002aba04b595bb8d95e496bd66beebae08e4d678667`
- Aggregate results SHA-256: `06da0a0c2e297124234ad433caa0fd0d6f7924d5b13b707f4fed8ded9a81bfaf`
- Verified 27 response runs, 18 A–D analyses, and 3 error analyses.
- All declared hashes passed and the full and seen terminal-probe row identities align across the six q-balanced worlds within seed.

## Primary controlled contrasts

| Contrast | Three-seed mean [range] | Conditional per-seed learner intervals |
|---|---:|---|
| `explicit_format_remedy` | -0.005317 [-0.006034, -0.004652] | 20260829: -0.006034 [-0.007399, -0.004662]; 20260830: -0.005264 [-0.006765, -0.003800]; 20260831: -0.004652 [-0.006387, -0.003023] |
| `explicit_item_remedy_combined` | -0.012609 [-0.013506, -0.011947] | 20260829: -0.011947 [-0.015061, -0.008845]; 20260830: -0.013506 [-0.016722, -0.010503]; 20260831: -0.012374 [-0.015578, -0.009122] |
| `explicit_item_remedy_item_only` | -0.013099 [-0.013313, -0.012698] | 20260829: -0.013285 [-0.016743, -0.009887]; 20260830: -0.013313 [-0.016034, -0.010858]; 20260831: -0.012698 [-0.015979, -0.009464] |
| `format_confounding_difference_in_differences` | -0.031551 [-0.033431, -0.029013] | 20260829: -0.029013 [-0.033150, -0.024922]; 20260830: -0.033431 [-0.038192, -0.028720]; 20260831: -0.032211 [-0.036367, -0.027911] |

Corrected DiD sign: Negative means planted format nuisance increases false format-split model B's predictive advantage relative to shared-K* model A. It does not mean that an explicitly corrected model wins and does not validate B as a psychological ontology.

The frozen aggregate's generic sign string is retained for provenance but is wrong for the DiD and is not used here. The aggregate itself was not modified.

D is an oracle-aligned same-seen-item positive control: planted seen-item effects are constructed in D's own Q*/format-orthogonal span, and probe-only items are zero encoded.

Item-only B−A is mixed and near zero, with every conditional interval crossing zero: 20260829: +0.001195 [-0.001665, +0.004110]; 20260830: +0.000847 [-0.001477, +0.003183]; 20260831: -0.001328 [-0.003652, +0.001060]. This does not support a claim that false format-split KCs absorb item difficulty.

Under combined heterogeneity, C−B is mixed and every interval crosses zero, while D−C remains negative in all seeds. The explicit item positive control survives; explicit format superiority is not consistently demonstrated.

## A–D prediction and item-prerequisite state summaries

Values are three-seed means with `[minimum, maximum]` ranges on seen terminal probes.

| World | Model | Log loss | Brier | ECE | State RMSE |
|---|---:|---:|---:|---:|---:|
| `clean_zero` | A | 0.657219 [0.653367, 0.659362] | 0.232512 [0.230674, 0.233542] | 0.020034 [0.012927, 0.027211] | 0.115625 [0.114573, 0.117443] |
| `clean_zero` | B | 0.664138 [0.661144, 0.666435] | 0.235802 [0.234343, 0.236926] | 0.012487 [0.005037, 0.021407] | 0.135821 [0.134308, 0.137376] |
| `clean_zero` | C | 0.657231 [0.653383, 0.659334] | 0.232517 [0.230681, 0.233527] | 0.020041 [0.012943, 0.027219] | 0.115624 [0.114574, 0.117441] |
| `clean_zero` | D | 0.657843 [0.653595, 0.660012] | 0.232807 [0.230784, 0.233847] | 0.020121 [0.014267, 0.025901] | 0.115743 [0.114306, 0.117865] |
| `format_moderate` | A | 0.659499 [0.656554, 0.661501] | 0.233599 [0.232196, 0.234545] | 0.020558 [0.016326, 0.024856] | 0.117301 [0.116368, 0.117891] |
| `format_moderate` | B | 0.657328 [0.656612, 0.658729] | 0.232559 [0.232195, 0.233245] | 0.013345 [0.008026, 0.018365] | 0.154992 [0.153650, 0.155764] |
| `format_moderate` | C | 0.651279 [0.650159, 0.652198] | 0.229697 [0.229192, 0.230122] | 0.021077 [0.017963, 0.024590] | 0.116379 [0.115309, 0.117212] |
| `format_moderate` | D | 0.651795 [0.650360, 0.652912] | 0.229938 [0.229275, 0.230463] | 0.021019 [0.019667, 0.022737] | 0.116483 [0.114964, 0.117646] |
| `format_strong_control` | A | 0.663597 [0.661150, 0.665606] | 0.235550 [0.234392, 0.236508] | 0.021078 [0.018190, 0.025232] | 0.122492 [0.121564, 0.123137] |
| `format_strong_control` | B | 0.638965 [0.637732, 0.639914] | 0.223923 [0.223288, 0.224414] | 0.013055 [0.007711, 0.019150] | 0.201946 [0.201588, 0.202471] |
| `format_strong_control` | C | 0.633648 [0.633080, 0.633984] | 0.221460 [0.221140, 0.221634] | 0.021554 [0.017055, 0.024820] | 0.118506 [0.117080, 0.119439] |
| `format_strong_control` | D | 0.634070 [0.633459, 0.634533] | 0.221655 [0.221306, 0.221877] | 0.020667 [0.017389, 0.022921] | 0.118632 [0.116742, 0.119964] |
| `item_moderate` | A | 0.661378 [0.659237, 0.662749] | 0.234495 [0.233471, 0.235150] | 0.024363 [0.018747, 0.033657] | 0.120308 [0.120201, 0.120368] |
| `item_moderate` | B | 0.661616 [0.660432, 0.663597] | 0.234601 [0.234040, 0.235553] | 0.016681 [0.010110, 0.028464] | 0.154524 [0.153624, 0.155490] |
| `item_moderate` | C | 0.661489 [0.659338, 0.662951] | 0.234544 [0.233518, 0.235236] | 0.023303 [0.017508, 0.033671] | 0.120289 [0.120154, 0.120368] |
| `item_moderate` | D | 0.648390 [0.646053, 0.649638] | 0.228319 [0.227317, 0.228846] | 0.020839 [0.017083, 0.023948] | 0.117431 [0.115805, 0.119066] |
| `item_format_moderate` | A | 0.662507 [0.661100, 0.663234] | 0.235030 [0.234357, 0.235378] | 0.025766 [0.019552, 0.035950] | 0.121956 [0.120875, 0.123021] |
| `item_format_moderate` | B | 0.654498 [0.652775, 0.656678] | 0.231227 [0.230338, 0.232297] | 0.020360 [0.013670, 0.031278] | 0.171457 [0.170645, 0.172822] |
| `item_format_moderate` | C | 0.654465 [0.654332, 0.654601] | 0.231202 [0.231106, 0.231298] | 0.026638 [0.021008, 0.035894] | 0.120937 [0.120091, 0.121751] |
| `item_format_moderate` | D | 0.641856 [0.640955, 0.642655] | 0.225283 [0.224783, 0.225803] | 0.024201 [0.019892, 0.026590] | 0.117769 [0.116362, 0.118772] |
| `combined_heterogeneous` | A | 0.656133 [0.654837, 0.657535] | 0.232007 [0.231373, 0.232687] | 0.023787 [0.018632, 0.032709] | 0.131556 [0.128781, 0.135111] |
| `combined_heterogeneous` | B | 0.648718 [0.647398, 0.650285] | 0.228529 [0.227962, 0.229292] | 0.018264 [0.013791, 0.026636] | 0.177171 [0.174500, 0.179197] |
| `combined_heterogeneous` | C | 0.648390 [0.647567, 0.649545] | 0.228354 [0.227982, 0.228881] | 0.024833 [0.018895, 0.033672] | 0.131144 [0.128210, 0.135043] |
| `combined_heterogeneous` | D | 0.636359 [0.634562, 0.637321] | 0.222758 [0.221822, 0.223358] | 0.020229 [0.019512, 0.020637] | 0.129724 [0.126678, 0.135347] |

Item-prerequisite state is a model-specific nuisance-removed item-level diagnostic, not individual-KC mastery recovery.

## Structured-error controls

All error-history models hold condition D fixed. The failed-KC target is a post-outcome deficit-proportional oracle attribution, not a causal human-error label.

| Stream | Log loss | State RMSE | Localisation top-1 | Terminal-KC evidence RMSE |
|---|---:|---:|---:|---:|
| `binary_only` | 0.636359 [0.634562, 0.637321] | 0.129724 [0.126678, 0.135347] | 0.420781 [0.419372, 0.421840] | 0.228727 [0.225387, 0.230607] |
| `linked_positive_control` | 0.635493 [0.633665, 0.636827] | 0.125210 [0.122436, 0.128768] | 1.000000 [1.000000, 1.000000] | 0.144357 [0.141253, 0.146503] |
| `linked_80_percent` | 0.635833 [0.634093, 0.636986] | 0.127232 [0.124315, 0.131178] | 0.883728 [0.883395, 0.883992] | 0.158804 [0.155085, 0.160681] |
| `within_item_shuffled_negative_control` | 0.636987 [0.635169, 0.638011] | 0.131138 [0.128109, 0.135647] | 0.462525 [0.456719, 0.469783] | 0.165519 [0.160795, 0.168737] |

Prediction contrasts against binary history:

- `linked_80_percent_minus_binary_only` — 20260829: -0.000902 [-0.001716, -0.000123]; 20260830: -0.000469 [-0.001334, +0.000384]; 20260831: -0.000209 [-0.001041, +0.000545]
- `linked_positive_control_minus_binary_only` — 20260829: -0.001336 [-0.002358, -0.000304]; 20260830: -0.000897 [-0.001822, -0.000008]; 20260831: -0.000368 [-0.001247, +0.000544]
- `within_item_shuffled_negative_control_minus_binary_only` — 20260829: +0.000689 [-0.000105, +0.001503]; 20260830: +0.000608 [-0.000111, +0.001287]; 20260831: +0.000587 [-0.000310, +0.001438]

Linked prediction gains are small and do not exclude zero in every seed. The 80% control masks rather than misclassifies 20%; within-item shuffling preserves item-level category marginals. Shuffled categories also improve the secondary evidence-count RMSE over binary attribution, so that diagnostic cannot alone establish learner-specific error information.

Failed-KC localisation uses all learners' incorrect multi-KC probes (support by seed: 22,206; 22,131; 22,331), not only the held-out test learners. Its shuffled log loss is dominated by the 1e-12 incompatible-target floor and is not comparable with next-response log loss.

## Schedule diagnostics

These are descriptive history/exposure diagnostics, not efficacy estimates.

| Policy | Acquisition accuracy | Probe accuracy | Item exposure Gini | Median repetition gap |
|---|---:|---:|---:|---:|
| `q_balanced_lab` | 0.507493 [0.503319, 0.510191] | 0.586088 [0.584434, 0.587895] | 0.162530 [0.162530, 0.162530] | 93.67 [93.00, 94.00] |
| `curriculum` | 0.501199 [0.498723, 0.503074] | 0.586088 [0.584434, 0.587895] | 0.162530 [0.162530, 0.162530] | 31.00 [31.00, 31.00] |
| `mixed_practice` | 0.508000 [0.505968, 0.509106] | 0.586088 [0.584434, 0.587895] | 0.162530 [0.162530, 0.162530] | 92.00 [92.00, 92.00] |
| `adaptive_weakness` | 0.496830 [0.495638, 0.498926] | 0.593658 [0.590750, 0.597526] | 0.080298 [0.076043, 0.088029] | 26.67 [26.00, 27.00] |

q-balanced, curriculum, and mixed schedules have exactly the same within-seed terminal-probe accuracy because they use the same occurrence multiset under an order-independent unconditional learning update. Adaptive selection changes exposure. Overall accuracy is not used as an efficacy endpoint because it mixes selected acquisition rows with probes.

## Uncertainty and claim limits

- All bootstrap intervals are conditional test-learner intervals around frozen fits; they do not include refitting or hyperparameter-selection uncertainty.
- Three simulator seeds are summarized by mean and range only and do not support population random-effects inference.
- Learners are resampled but the 18 selected seen cells, 144 seen structural item slots, and content-free instrument are fixed.
- No multiplicity-adjusted family of tests is reported; interpretation is restricted to preregistered directional controls and descriptive secondary diagnostics.
- Item-prerequisite state recovery is not individual-KC mastery recovery, and the retained terminal-KC evidence diagnostic is not fitted A/B/C/D state recovery.
- Planted item-effect orthogonality is exact for the equally weighted 144-item seen bank/probe design, not for the 188-event acquisition multiset that duplicates 44 items.

The supported claims concern planted nuisance sensitivity in a content-free controlled instrument. They do not establish deployable items, platform realism, human task-format effects, human error realism, psychological KC truth, or policy learning efficacy.
