# Measurement-extension research-question ledger

Status: final. Every answer is conditional on the declared evidence source;
automated audits, content-free simulator worlds, and human/platform validation
are not interchangeable.

Release decision: **no new dataset release**. Results marked inconclusive remain
inconclusive rather than being promoted from point estimates.

## Final paper-level questions

| Research question | Status | Retained answer | Evidence boundary |
|---|---|---|---|
| **RQ1 — What must be declared and audited to construct a grammar-learning measurement environment with known latent structure, and where does a clean Q-driven benchmark fall short?** | **Auditable construction supported; platform-valid extension rejected** | Full-v1 provides immutable known GrammarCells, K*, Q*, mastery, and events. The new census separates linguistic validity, answerability, measurement purity, and deployability. Only 60/113 items were usable in both audit mappings; 53 were in the union requiring action and 18 in the critical answer-space/withhold union. A rigorously crossed four-format bank passed only 5/38 complete families, so no measurement dataset was frozen. | Audits are model-based stress tests, not learner/expert evidence. The 5/38 result is a valid negative under the frozen automated protocol, not proof that such a bank cannot be authored. |
| **RQ2 — How do KC/Q assumptions and item/format nuisance affect prediction and recovery of the planted state?** | **Supported for controlled planted mechanisms; external-format claim rejected** | Legacy full-v1 shows clean-world merge/split/Q sensitivity and one item-difficulty reversal. In the content-free extension, planted format nuisance shifts the false-split-vs-shared contrast by mean DiD -.031551; explicit format C beats false split B in every strong-format seed (mean -.005317). The aligned item positive-control D beats C in item-only and item+format worlds (means -.013099/-.012609). | Format labels are not validated tasks. D exactly spans planted seen-item nuisance and cannot establish a general item remedy or unseen-item recovery. In the combined heterogeneous world, C-vs-B intervals cross zero in every seed. Item-only B-vs-A is null/mixed. Intervals condition on fixed fits. |
| **RQ3 — Which measurement contrasts, assignment histories, and response information make latent structure or state distinguishable?** | **Equivalence limits supported; richer-response and policy effects bounded** | Existing A+B-only controls show that response volume cannot break identical Q activations; outcome-blind KC inductions are unstable, and observable discovery recovers an equivalence class rather than unique ontology. Linked structured errors raise failed-KC top-1 from .421 binary to 1.000 positive-control/.884 at 80% and reduce a secondary evidence RMSE, but next-response gains are small. Schedule policies create different histories/exposures and exploratory fit differences; open dialogue raises naturalness while sharply weakening determinacy and KC attribution. | Failed KC is post-outcome deficit attribution, not human causal truth; shuffled labels reveal estimator bias. Lab/curriculum/mixed terminal mastery is identical by construction. Policy fits are post-response exploratory. Dialogue evidence is automated and covers four families. |

## Claim ledger

| Claim | Decision | Exact support or reason |
|---|---|---|
| Synthetic perfect-information data enable tests unavailable in ordinary learner logs. | **Retain** | True GrammarCell, K*, Q*, learner state, response generator, controlled perturbations, and counterfactual streams are replayable. |
| Full-v1 is a realistic language-learning platform dataset. | **Reject** | Prompts do not cause responses; no executable scorer/UI; one broad item family; material audit concerns; laboratory schedule. Use “clean Q-driven control benchmark.” |
| The 18 generator KCs are uniquely correct human competencies. | **Reject** | They are declared feature-linked factors; repeated outcome-blind induction is non-unique; no human transfer/independent-mastery evidence. |
| Rank 18 establishes identifiability. | **Narrow** | It establishes linear column independence for this bank. Response-model identifiability requires additional model-specific conditions; pedagogical/psychological identity remains untested. |
| The 113 items are platform-deployable because they passed the original validator. | **Reject** | Original linguistic/model screening and broader response-space/platform audits address different claims and disagree materially. |
| A false format split can win because format nuisance is omitted. | **Retain for planted control** | Strong-format DiD mean -.031551; all conditional intervals exclude zero. The result is structural sensitivity, not a human format effect. |
| Explicit format adjustment always restores the shared ontology. | **Reject as universal** | C beats B under the strong-format control, but combined-heterogeneous C-B is mixed and all intervals cross zero. Prediction does not recover psychological semantics. |
| False format splits absorb item difficulty. | **Not supported here** | Item-only B-A is small/mixed and all intervals cross zero. Legacy split-2 reversal remains a motivating separate finding. |
| Item effects solve item-difficulty confounding. | **Narrow to positive control** | D recovers nuisance deliberately planted in D's seen-item residual span; held-out item effects are unestimable/zero encoded. |
| Error categories retain information lost by binary correctness. | **Supported for planted diagnostic signal** | Strong localisation and secondary state-evidence improvements; small predictive gains; shuffled control prevents interpreting any single metric alone. |
| Generated error categories are realistic learner errors. | **Reject** | Taxonomy is linguistically plausible and literature-informed, but no corpus/human validation and no surface response strings. |
| Platform-like policy changes can affect what KT observes. | **Supported descriptively/exploratorily** | Exposure Gini/repetition gaps and post-response D-fit/state diagnostics differ. This is not policy-value or real-platform evidence. |
| More open dialogue is always a better KT opportunity. | **Reject** | Open dialogue improves automated naturalness but produces 0/20 determinate judgments, only 4/20 clear KC attributions, and 13/20 shortcuts. |
| A new platform-plausible dataset should be released. | **Reject at current gate** | Only 5/38 matched families passed; rank/coverage/answerability gates fail. Controlled worlds remain `release_eligible=false`. |

## Stop-condition mapping

| Required area | Status | Evidence |
|---|---|---|
| full-v1 protection and replay | complete | `experiments/measurement_realism/baseline_anchor.json`; final verification |
| 113-item learner/platform critique | complete | `reports/platform_plausibility_audit.md`; item/live/cross-audit ledgers |
| KC methodology and induction | complete | `reports/kc_methodology_audit.md`; `kc_induction_v1/` |
| matched educational formats | investigated; release gate failed | selected rank-18 design; `matched_bank_v0_2_20260830/analysis/` |
| zero/planted format and item controls | complete as content-free sensitivity | controlled aggregate and synthesis |
| learner heterogeneity | complete as one transparent combined world | combined-world A-D results; no human parameter claim |
| laboratory versus platform-oriented schedules | complete descriptively plus exploratory recovery | aggregate schedule diagnostics; `policy_recovery_v1/` |
| structured errors versus binary | complete | three-seed error-history synthesis |
| error surface text | intentionally not scaled | prerequisite release/human validation not met |
| dialogue continuum | complete automated pilot | `dialogue_pilot_live_v1/`; human protocol retained |
| dataset-extension decision | complete: no release | matched-bank negative-result manifest and claim boundaries |
| human/expert planning | complete as future protocol, no fabricated evidence | dialogue/general expert and learner review protocol |

## Implication for the legacy four RQs

The legacy full-v1 answers remain reproducible: construction is supported in
its clean-control scope; KC misspecification harms the model in the planted
world; unique KC discovery is rejected in favour of activation-equivalence
recovery; and reusable histories support narrow grammatical recombination.
The measurement extension does not overwrite those findings. It changes their
external-validity interpretation: whether they matter for a real platform
depends on learner-facing instruments, nuisance variables, response retention,
and selection policy that full-v1 deliberately idealises.
