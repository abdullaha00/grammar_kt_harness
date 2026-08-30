# Measurement-realism literature synthesis

Status: primary/authoritative-source review completed 2026-08-30. The companion machine-readable ledger is [`source_ledger.jsonl`](source_ledger.jsonl). Bracketed identifiers below point to ledger records, which contain exact citations, DOI/URLs, supported claims, limits, and experiment implications.

## Scope and evidential boundary

This review asks what established work can constrain—not certify—the benchmark's measurement, learner, and platform scenarios. It covers nine KT/Q-matrix papers, ten educational-measurement and format sources, seven platform/scheduling sources, five learner-response/error sources, three learner-simulation sources, and three dialogue sources.

The evidence does **not** support calling any one simulator “human-like.” Most numerical values in the experiment design below are planted stress-test values. They are labelled as such. Published model fits and effect sizes are retained only as context showing that the corresponding mechanism is non-negligible in at least one setting.

## Findings that should change the methodology

### 1. Full Q-matrix rank is valuable, but it is not a general identifiability guarantee

Q-matrix misspecification can be absorbed by response parameters and can damage latent classification. In the DINA conditions studied by Rupp and Templin, removing required attributes inflated slip estimates, while adding attributes inflated guess estimates [KT03]. This is a useful warning for the proposed format experiment: a nuisance effect may be absorbed by a false skill split or by guess/slip, so predictive fit alone cannot identify the correct explanation.

Gu and Xu's formal result is sharper but model-specific. Under their DINA assumptions, strict joint identifiability requires a complete Q-matrix, distinct columns in the residual block, and at least three items per attribute; for broader restricted latent-class models, three items per attribute is necessary for generic joint identifiability [KT05]. A numerically full-rank `Q*` therefore answers only a linear-algebra question. It does not establish psychological uniqueness or identifiability for every response model.

Implications:

- Keep rank as one diagnostic, alongside KC support counts, duplicate activation columns, anchor/identity-like rows, and response-model-specific conditions.
- State explicitly whether each claim concerns structural Q distinguishability, statistical parameter identifiability, empirical recovery, or educational interpretability.
- Retain deletion, addition, merge, and split controls. Inspect whether their errors reappear as item, format, guess, or slip estimates.
- Do not describe the declared generator ontology as uniquely human-correct. Learning Factors Analysis itself treats cognitive-model refinement as a combination of statistical evidence, search, and expert interpretation [KT02].

### 2. Item and learner effects are credible alternative explanations for apparent KC structure

Item difficulty is central in IRT [ME01] and has improved KT prediction in some data. KT-IDEM raised mean ASSISTments AUC from 0.669 to 0.699 in one reported comparison, though results differed in another tutor and sparse item parameters can overfit [KT06]. KT/IRT hybrids and factorization approaches provide direct ways to represent skill, learner, and item effects [KT07, KT09]. Individualized BKT also improved prediction in the studied tutor data; individual learning speed contributed more than individualized prior knowledge in that particular comparison [KT08].

None of these results provides a population distribution for English learners. They do establish item difficulty and learner heterogeneity as serious rival explanations, rather than decorative realism variables.

Implications:

- Plant stable, centered item effects independently of Q and format.
- Plant learner ability and learning-speed variation independently, so that the simulator does not trivially reward a particular fitted model.
- Compare at least `K*`, `K* + item`, `K* + format`, `K* + item + format`, and false item/format-specific KC splits.
- Evaluate oracle mastery recovery and calibration as well as prediction. A more flexible nuisance model can predict better without recovering mastery better.

### 3. Format is part of the measurement instrument, not merely prompt styling

The format literature does not establish one universal ordering of exercise types. It does show that method effects are heterogeneous. A meta-analysis of multiple-choice and constructed-response measures found greater equivalence for matched stems and less equivalence when content also changed [ME05]. Language-assessment studies found format effects and proficiency/design moderation [ME06, ME07]. Even six variants within multiple-choice grammar tasks differed in difficulty and score variance [ME09]. Task sampling itself can contribute substantial measurement variation [ME10].

The strongest design consequence is therefore matching: “same GrammarCell and Q row, different format” is credible only when lexical content, context, target answer, and information shown are held as comparable as the response mechanism permits. Unmatched campaigns cannot separate format from content.

Implications:

- Construct matched families from a shared semantic/stem specification, then render cloze, transformation, multiple choice, and short contextual completion.
- Retain response-mechanism subtypes; “multiple choice” is not necessarily one homogeneous condition.
- Include a zero-format-effect negative control and planted moderate/large effects. Let effect direction vary by scenario rather than hard-coding multiple choice as always easier.
- Cross KCs with formats. Complete KC–format confounding makes a format-specific split observationally attractive by construction.

### 4. Measurement validity is an argument across layers, not a single realism score

Messick distinguishes threats from construct underrepresentation and construct-irrelevant influences [ME02]. Kane requires an explicit chain from observations to proposed interpretations and uses, with stronger claims requiring stronger evidence [ME03]. The testing standards distinguish evidence based on content, response processes, internal structure, external relations, and consequences, and treat accessibility and fairness as matters requiring evidence [ME04].

For this benchmark, the defensible chain is:

```text
visible task and response mechanism
→ interpretable learner response
→ evidence about declared K*
→ fitted KT state or recovered ontology
→ bounded implication for real data collection
```

Each arrow can fail independently. A linguistically correct target can be unanswerable; an answerable exercise can permit a shortcut; a clean Q row can be pedagogically implausible; a platform-like task can produce ambiguous evidence.

Implications:

- Preserve separate audit fields for linguistic validity, answer determinacy/response process, measurement purity, pedagogical plausibility, and platform deployability.
- Use hard gates for critical ambiguity and insufficiency rather than averaging all dimensions into a composite score.
- Treat model-as-learner critics as automated stress tests, not human response-process evidence.
- Plan expert and learner validation for claims that synthetic critics cannot establish.

### 5. Platform histories are selected by a policy

Public language-platform corpora make the selection problem visible. SLAM contains more than seven million produced word tokens from more than 6,000 learners and includes exercise type, time, lesson/practice context, repeated encounters, and token-level error labels [PL01]. Its cohort was selected by product participation and course-progress rules. EdNet contains more than 131 million interactions from more than 784,000 learners and mixes problem-solving with lecture, purchase, and within-question events [PL04]. These are service histories, not random item assignments.

Spacing and adaptation can also change learning. Production language-learning work models elapsed time and practice through trainable half-lives [PL02]. A semester-long language review experiment found better delayed outcomes for personalized scheduling than time-matched massed or generic spacing in that setting [PL05], while model-based spacing research likewise makes schedule a causal input [PL06]. Off-policy evaluation work formalizes why logs collected by one behavior policy cannot be read as though another policy generated them [PL07].

Implications:

- Keep the balanced laboratory schedule as the internal-validity reference.
- Compare it with a simple curriculum/review schedule under the same opportunity budget and, where scientifically useful, the same latent learner draws.
- Record `policy_id`, eligibility set or deterministic selection rule, time/order, session/phase, and selection propensity where a stochastic policy is used.
- Evaluate exposure imbalance and recovery conditional on policy. Do not interpret adaptive observations as random missingness.
- If forgetting is added, express it through elapsed time or half-life scenarios, not an unexplained per-row decrement.

### 6. Actual responses can carry information that correctness destroys, but they also expose ambiguity

Learner corpora show structured error variation. The Cambridge Learner Corpus used a multi-level 88-code error scheme across millions of error-coded words [ER01]. ERRANT provides reproducible edit alignment and error typing; experts rated at least 95% of its extracted edits Good or Acceptable in its validation, though such labels are not failed-KC truth [ER02]. The W&I+LOCNESS test set was corrected five times specifically to better represent alternative valid corrections [ER03].

In learner modelling, partial-credit and open-response work demonstrates that response information beyond a binary label can be modelled [ER04, ER05]. This is evidence for testing information loss, not evidence that generated English error text is realistic.

Implications:

- Begin with a small, operation-grounded structured error vocabulary: e.g. tense selection, auxiliary omission, negation, participle, progressive morphology, question order, modal complement, plus `non_target_or_unresolved`.
- Separate `failed_kc` (private simulator truth), `error_category` (possibly observable annotation), `surface_response`, and scoring decision.
- Compare oracle-linked error categories with a frequency-matched shuffled negative control.
- Validate open answers against multiple acceptable responses. Exact-string scoring is an avoidable measurement artifact.
- Generate surface error text only after structured errors demonstrably improve failed-KC localization or mastery recovery; validate the intended edit and absence of major unrelated edits.

### 7. Simulator validity is purpose-specific; complexity alone is not evidence

A systematic review found narrow learner mechanisms were common and nearly half of included studies supplied no simulator-validity evidence [SI01]. Simulation studies nevertheless show the scientific value of controlled truth across many parameter worlds, and that different models have different favorable regions [SI03]. This supports a family of transparent worlds rather than one opaque “realistic learner.”

Two short ASSISTments datasets yielded fitted BKT tuples `(prior, learn, guess, slip)` of `(.453, .068, .270, .156)` and `(.701, .044, .243, .165)` [SI02]. These values are useful only as a warning that the full-v1 constants are not inevitable. They are not language-learning constants, do not transfer across response models, and should not be used as a realism certificate.

Implications:

- Preserve full-v1 as the clean control.
- Add one mechanism per world where possible: item difficulty, format, learner heterogeneity, errors, or schedule.
- Use paired seeds/counterfactuals so observable changes can be attributed to the planted mechanism.
- Inspect both aggregate distributions and concrete trajectories. Similarity on marginals cannot prove causal realism.

### 8. Dialogue increases naturalness and weakens opportunity boundaries

TSCC v2 contains 260 one-to-one English lessons, about 41,400 turns, and 363,000 tokens; it distinguishes exercises, free practice, elicitation, scaffolding, repair, clarification, revision, grammar, lexis, and meaning [DL01]. This diversity illustrates why “one turn = one grammar opportunity” is not safe. Tutorial-dialogue work likewise finds that unrestricted language enables substantive responses while introducing interpretation failures and terminology/non-understanding problems [DL02]. A dialogue interaction includes task context, dialogue history, feedback, and recovery policy, not prompt text alone [DL03].

Implications:

- Pilot the continuum `cloze → transformation → contextual completion → dialogue completion → open dialogue`; do not jump directly to unrestricted dialogue.
- Record visible history, response function, feedback assumptions, and annotated opportunity boundary.
- Measure answer-set size/ambiguity, incidental KCs, unresolved responses, and inter-critic agreement at every step.
- Stop scaling when the intended KC attribution ceases to be defensible. That failure is itself evidence for the ecology–precision tradeoff.

## Scenario parameters: empirical anchors versus planted controls

The following table is a sensitivity design, not an estimate of human learners. Values marked **design** are deliberately interpretable stress levels. Values marked **anchor** come from a named source but remain setting/model-specific.

| Component | Negative/clean control | Smallest useful perturbations | Evidential status and interpretation |
|---|---:|---:|---|
| Opportunity learning increment | full-v1 `0.02` | `0.05`, `0.10` | **Design grid.** Two short ASSISTments BKT fits had learning `0.044` and `0.068` [SI02], only an order-of-magnitude anchor. Different update rules are not numerically comparable. |
| Guess/slip | full-v1 `0.10/0.10` | symmetric or crossed values in `{0.05, 0.10, 0.20, 0.30}` | **Design grid.** The two BKT fits reported guess `0.243/0.270` and slip `0.156/0.165` [SI02]. Do not call these grammar-platform estimates. |
| Stable item difficulty | logit SD `0` | centered logit SD `0.5`, `1.0` | **Design stress levels**, corresponding roughly to one-SD odds ratios `1.65` and `2.72`. Literature supports item variation, not these SDs [KT06, ME01]. Cross independently with Q and format. |
| Format effect | logit offset `0` | balanced offsets with magnitude `0.35`, `0.70` | **Design stress levels**, odds ratios about `1.42`, `2.01`. Literature supports heterogeneity and moderation, not a universal direction [ME05–ME09]. |
| Learner ability | logit SD `0` | `0.35`, `0.70` | **Design stress levels.** Center the distribution and pair learner draws across worlds. |
| Learning-speed heterogeneity | coefficient of variation `0` | log-normal CV `0.25`, `0.50` with fixed mean | **Design stress levels.** Individualized KT motivates the mechanism but does not supply population constants [KT08]. |
| Forgetting | none | half-life long versus short relative to the experiment's median inter-session gap | **Design scenarios.** Specify half-life in schedule units only after timestamps exist; production work motivates time sensitivity but supplies no universal grammar half-life [PL02]. |
| Error information | binary only | oracle-linked structured category; frequency-matched shuffled category | **Positive/negative information controls.** Surface strings remain a later validation stage [ER01–ER05]. |
| Selection policy | balanced assignment | fixed curriculum; deterministic weak-KC review; stochastic review with logged propensity | **Policy controls.** Equalize total opportunity budgets and, where possible, item eligibility sets [PL05–PL07]. |

For all planted logit effects, report the response function and saturation behavior. Effects near probability 0 or 1 will have a smaller probability-scale impact than the same logit shift near 0.5.

## Smallest controlled experiment programme justified by the review

### E1 — Matched-format measurement pilot

Select 12 representative GrammarCells before looking at response outcomes: common/rare, single/multi-KC, low/high KC support, and seen/held-out where appropriate. For each, author one shared semantic specification and render four plausible formats with two lexical/context variants (`12 × 4 × 2 = 96` items). This count is a feasibility proposal, not a power result.

Hard gates:

- target GrammarCell is instantiated;
- all information needed is visible;
- accepted-answer set covers independently proposed valid responses;
- no obvious non-target shortcut;
- vocabulary is controlled within a declared level;
- prompt and response mechanism could be represented in a minimal UI.

Retain each critic dimension and disagreement rather than only a mean. The matched family—not merely the cell ID—is the unit needed to identify a format contrast [ME05].

### E2 — Zero-effect falsification control

Simulate the matched bank with identical latent truth and **no** item or format effect. Use paired learner states, sequence, and random uniforms across hypotheses. A format-split KC representation should not gain oracle recovery advantage merely because format labels exist. Any gain diagnoses modeling flexibility, leakage, or finite-sample selection.

### E3 — Measurement-nuisance confounding

Plant independent stable item effects and known format offsets. Compare:

```text
A  shared K*, no nuisance covariates
B  false format-specific KC splits
C  shared K* + format covariate
D  shared K* + item + format effects
```

Primary evidence: held-out log loss, Brier score, calibration, oracle mastery RMSE, and whether false splits are selected. Include a planted-zero and shuffled-format control. If B beats A but C/D recover shared K*, the warranted conclusion is that measurement nuisance can masquerade as KC granularity in this controlled world—not that real format effects always do so.

### E4 — Learner heterogeneity robustness

Add centered ability and learning-speed variation separately, then jointly. Preserve marginal mean difficulty and use the same learner draws across model comparisons. Ask whether misspecification, discovery, and mastery-recovery rankings survive. Report learner-paired intervals and strata by planted ability/speed; aggregate prediction can hide systematic subgroup failure [KT08].

### E5 — Assignment-policy comparison

Run the same latent world and opportunity budget under (i) balanced laboratory assignment, (ii) fixed progressive curriculum plus spaced review, and (iii) a simple recent-error or estimated-weakness policy. Log the policy and exposure propensity. Compare KC/item exposure, Q geometry actually observed, learner/item accuracy, and recovery. A change is attributable to the generated measurement process, not automatically to human platform behavior [PL01, PL04, PL07].

### E6 — Structured-error information test

For incorrect multi-KC responses, compare weakest-KC sampling with probabilistic sampling proportional to a declared mastery deficit. Expose only a structured error category, not `failed_kc`. Fit binary and error-aware interpretable models. Positive control: oracle-linked category. Negative control: frequency-matched shuffle within item/format. Outcomes: failed-KC localization, mastery RMSE, next-response prediction, calibration, and information gain conditional on the same binary outcome.

Only if this stage succeeds should a small surface-text pilot generate responses from `(target answer, intended error, proficiency context)`. Independent validation should check that the intended error occurred, no major unrelated error was added, and the result remains contextually plausible [ER02, ER03].

### E7 — Dialogue boundary pilot

For a subset that passes E1, create contextual completion and dialogue-completion versions before open dialogue. Freeze visible history and expected response function. Measure the number of independently proposed valid answers, incidental grammar, unresolved cases, critic disagreement, and failed-KC attribution. Open dialogue is justified only if an opportunity boundary and scoring interpretation survive [DL01–DL03].

## Observable-distribution audit

External corpora justify inspecting these distributions; they do not supply target values that the synthetic data must match:

- learner accuracy and item accuracy, including tails;
- sequence length, session length, and truncation;
- item, format, and KC exposure counts;
- time gaps and repeated encounters;
- within-learner change conditional on opportunity count;
- lagged correctness/error autocorrelation;
- accepted-answer multiplicity and unresolved-response rate;
- error-category frequency by format and proficiency stratum;
- exposure/accuracy relationships induced by the policy.

Flag mechanical signatures such as identical exposure for all learners, near-zero item variance, identical improvement slopes, perfectly balanced format histories, or errors that name the weakest KC without noise. Conversely, matching a real corpus on these marginals does not prove response-process or causal validity [SI01].

## External comparison and human validation plan

External evidence can constrain failure modes without fitting the simulator to one dataset. A future validation study should distinguish expert judgments from learner behavior:

1. **Expert review:** sample the full 96-item pilot, with at least three independent judgments per item distributed across language-teacher, language-assessment, and platform-product expertise. Use the separate audit dimensions and require written failure rationales. Double-code at least 20% across all roles and adjudicate hard-gate failures. These counts are a feasible design proposal, not a power calculation.
2. **Learner cognitive/response pilot:** recruit learners in the declared proficiency range; ask a stratified item subset, collect answers plus brief comprehension/strategy probes, and estimate ambiguity, completion, and alternative-valid-answer rates. Do not reveal KCs in the instructions.
3. **Error review:** for every generated error family, include common/rare KCs and both intended and adversarial near-misses. Ask annotators to identify the error without being shown the intended label, then check unintended errors separately.
4. **Dialogue review:** have experts mark opportunity boundaries and incidental targets independently. Low agreement is evidence against treating the segment as a precise KT item.

No human judgment should be fabricated or replaced by agreement among language models. Model critics are useful for finding likely defects before this study.

## Paper-level implications

The literature supports framing the dataset as an **experimental instrument**, not the main scientific claim:

> Real platform logs provide learner behavior but not uniquely trustworthy grammatical opportunity boundaries, KCs, Q, mastery, or counterfactual states. A controlled simulator supplies those hidden quantities. Its relevance then depends on an explicit validity argument for the observable measurement and platform process.

The defensible contribution is therefore conditional:

- known truth enables tests that opaque real logs cannot support;
- matched instruments reveal when item/format nuisance is mistaken for skill structure;
- multiple transparent worlds test robustness without claiming a synthetic human clone;
- richer response experiments quantify information discarded by correctness;
- policy comparisons show that recoverability depends on what a platform chooses to present;
- concrete collection recommendations follow only where results persist across plausible scenarios.

This shifts the paper from “a realistic synthetic dataset” toward “a controlled analysis of when language-learning KT representations are informative or misleading.” Any word such as *realistic* should be qualified as platform-plausible, scenario-based, and not human-validated unless the proposed external study is actually run.

## Priority primary sources

The complete bibliography and exact claims are in the ledger. The shortest evidence spine for the paper is:

- Q misspecification: [Rupp & Templin 2008](https://doi.org/10.1177/0013164407301545) [KT03].
- Q identifiability: [Gu & Xu 2021](https://www3.stat.sinica.edu.tw/statistica/oldpdf/A31n118.pdf) [KT05].
- Item difficulty in KT: [Pardos & Heffernan 2011](https://people.csail.mit.edu/zp/papers/UMAP2011_IDEM.pdf) [KT06].
- Individualized KT: [Yudelson et al. 2013](https://www.cs.cmu.edu/~ggordon/yudelson-koedinger-gordon-individualized-bayesian-knowledge-tracing.pdf) [KT08].
- Validity arguments: [Messick 1994](https://www.ets.org/research/policy_research_reports/publications/report/1994/hxpp.html), [Kane 2013](https://doi.org/10.1111/jedm.12000), and the [2014 Testing Standards](https://www.testingstandards.net/uploads/7/6/6/4/76643089/standards_2014edition.pdf) [ME02–ME04].
- Format effects: [Rodriguez 2003](https://doi.org/10.1111/j.1745-3984.2003.tb01102.x) and [In'nami & Koizumi 2009](https://doi.org/10.1177/0265532208101006) [ME05, ME07].
- Platform language logs: [SLAM](https://aclanthology.org/W18-0506/) and [half-life regression](https://aclanthology.org/P16-1174/) [PL01, PL02].
- Learner errors: [ERRANT](https://aclanthology.org/P17-1074/) and [W&I+LOCNESS](https://aclanthology.org/W19-4406/) [ER02, ER03].
- Simulator validity: [Kaser & Alexandron 2024](https://doi.org/10.1007/s40593-023-00337-2) [SI01].
- L2 dialogue: [TSCC v2](https://aclanthology.org/2022.nlp4call-1.3/) [DL01].

