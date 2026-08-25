# Focused literature synthesis

Search and verification date: 2026-08-25. Claims below were checked against
the linked paper or official release, not inferred from titles or secondary
summaries. “Supervision” means the signal actually used to train the reported
system, which is often narrower than the paper's educational motivation.

## FEAT: exact scope and transfer boundary

[FEAT](https://aclanthology.org/2025.acl-short.45/) addresses **ranking short
teacher feedback for an incorrect multiple-choice answer to an MCTest reading
comprehension question**. It is not a grammar dataset, a language-production
tutor, a KT model, or evidence about learner gains.

- DIRECT-Manual (DM) contains feedback candidates written by humans, two
  GPT-2-based tutor models, GPT-3.5, and GPT-4. Humans rank only Correctness and
  Revealingness; the paper derives pairwise preferences from those ranks. The
  reported split has 5,025 training and 475 test pairs.
- DIRECT-Generated (DG) asks GPT-4o, Claude 3.5 Sonnet, and Llama-3.1-70B for
  feedback both with the five criteria—Correct, Revealing, Guidance,
  Diagnostic, Encouragement—and without them. The with-criteria response is
  automatically designated chosen and the without-criteria response rejected;
  there is no independent human or model comparison of each generated pair.
  The reported split has 3,996 training and 444 test records.
- DIRECT-Augmented (DA) mixes DG with 5–100% of DM. The experiments train
  pairwise classifiers, scalar reward models, DPO-style rankers, RankNet, and
  an ensemble with LoRA-adapted small Llama/Qwen backbones. The outcome is
  rank-order agreement, measured by rank-biased overlap against held-out human
  DM rankings over five seeds—not tutor-response generation or learning gain.
- The headline result is that adding 5–10% DM to DG ranks DM candidates better
  than training on 100% DM alone. It supports economical **ranker data
  augmentation**, not a general claim that preference optimization is superior
  to SFT for tutoring.

Transferable ideas are the decomposed feedback rubric, purpose-built negative
contrast, economical synthetic-plus-small-human validation, and ranker-based
evaluation. Non-transferable assumptions are MCTest multiple-choice context,
feedback already written by external generators, no canonical grammar/KCs,
no learner state or sequence, and a chosen label whose DG validity follows
prompt condition rather than an independent check.

The official [FEAT release](https://github.com/hyenee/FEAT) was also audited at
commit `c598a7b6f52e5b3b22fa31fd5c40024d93f37e3f`. In the DIRECT-G base
five-criteria files, 3,996 train records reduce to 1,478 unique
`(data_id, reply_id)` contexts and 444 test records to 399; 397/399 test
contexts and all 268 test `data_id`s occur in train. This does **not** invalidate
DG-to-DM evaluation because FEAT evaluates on the independently human-ranked
DM test set. It does make DG's released internal split unsuitable for a claim
of held-out context generalization. The pinned inputs, hashes, exact command,
and result are retained in [feat_release_audit.json](feat_release_audit.json).

## Evidence table

| Work | Training signal | Data source | Objective | Educational task | Evaluation | Relevance to Grammar-KT |
| --- | --- | --- | --- | --- | --- | --- |
| [FEAT](https://aclanthology.org/2025.acl-short.45/) | Human pairwise ranks in DM; synthetic prompt-condition preference in DG; mixtures in DA | MCTest wrong-answer contexts; human and several LM feedback writers | Pair classifier, RM, DPO ranker, RankNet, ensemble | Rank corrective tutor feedback | RBO against held-out human DM rankings, five seeds | Strong rubric/data-efficiency precedent; no grammar, KT state, generation, or learner outcome |
| [More Insightful Feedback for Tutoring](https://aclanthology.org/2024.emnlp-main.605/) | Gold feedback plus NLI-derived candidate preference | Existing tutoring feedback with enriched inputs; generated candidates | SFT with KL regularization, then preference optimization | Answer-adaptive elaborated feedback without revealing the answer | Text metrics, NLI-based faithfulness/informativeness proxies, human subset | Supports separating correctness, targeting, and revealingness; warns that a proxy can favor less useful feedback |
| [Improving Socratic Question Generation](https://aclanthology.org/2024.bea-1.10/) | Ground-truth question preferred to GPT-4-generated, targeted invalid question | Programming-tutor dialogues plus synthetic invalid categories and consistency filtering | DPO | Generate non-revealing Socratic questions | Automatic validity and generation metrics | Closest precedent for meaningful negative types; Grammar-KT can replace some model labels with structural checks |
| [LearnLM-Tutor](https://arxiv.org/abs/2407.12687) | Human tutoring dialogues, golden dialogues, and synthetic learner-state conversations | Math tutoring data and human pedagogical rubrics | SFT/evaluation-driven model development | Conversational tutoring | Human education-expert and learner-facing evaluation | Shows synthetic dialogues alone are insufficient and pedagogy needs explicit human-grounded rubrics |
| [MathDial](https://arxiv.org/abs/2305.14536) | Next tutor utterance | Human teacher/GPT-3.5 student math dialogues with tutoring strategies | SFT | Multi-turn tutoring | Automatic and human dialogue evaluation | Useful dialogue schema and strategy labels; simulated students limit causal learner claims |
| [EXPECT](https://aclanthology.org/2023.acl-long.413/) | Correction, evidence span, and error-type labels | Human-annotated grammatical error correction data | Supervised explainable GEC | Diagnose/correct/explain learner grammar errors | Task metrics and human usefulness study | Direct evidence for decomposing diagnosis before explanation; current Grammar-KT lacks authentic learner errors/evidence spans |
| [GEE!](https://aclanthology.org/2024.findings-naacl.49/) | Atomic edit extraction followed by explanation generation | GEC corrections transformed into edit/explanation instances | Prompting/few-shot staged generation | Grammar-error explanation | Automatic and human evaluation | Supports a two-stage deterministic diagnosis → soft explanation design |
| [Adaptive and Personalized Exercise Generation](https://arxiv.org/abs/2306.02457) | Learner interaction likelihood plus controlled generation conditions | Real Duolingo English interactions, lexical skills, instructor constraints | Joint KT and conditional generation with consistency loss/constrained decoding | Learner-state-conditioned exercise generation | Generation metrics and simulations | Most direct KT→generation precedent; Grammar-KT offers structural grammar KCs and exact provenance rather than mainly lexical controls |
| [Dialogue-KT](https://arxiv.org/abs/2409.16490) | KC/correctness sequence prediction | Tutor–student dialogue with annotated concepts and correctness | Supervised autoregressive KT | Infer knowledge from dialogue | Correctness/KC prediction | Shows dialogue can feed KT; does not provide gold tutor actions or prove state-conditioned generation helps learning |
| [KT4EQG](https://arxiv.org/abs/2605.23933) (2026 preprint) | KT-guided concept selection plus concept-grounded question generation | XES3G5M and MOOCRadar interactions/concepts | Select a concept for predicted mastery improvement; train an LLM question generator for concept faithfulness | Personalized exercise-question generation | Generation/effectiveness measures on two educational datasets | Direct recent precedent for KT→structured action→generation; Grammar-KT must distinguish real outcomes from predicted gain under the same KT model |
| [LongTutor](https://aclanthology.org/2026.acl-long.1371/) | Benchmark annotations, not primarily post-training | Expert-annotated real learning logs plus generator–verifier expansion | Evaluate evidence retrieval, state diagnosis, adaptive action | Long-term personalized tutoring | Three staged tasks | Supports evaluating state use rather than merely including state in prompts; reports action adaptation remains hard |
| [SHAPE](https://aclanthology.org/2026.acl-long.529/) | Benchmark/graph guidance rather than a single post-training recipe | 9,087 student-question pairs and a knowledge-mastery graph | Infer prerequisite/mastery gaps and gate tutoring versus answer provision | Pedagogically safe tutoring under answer-inducing prompts | Safety/helpfulness/pedagogy dimensions | Supports structured action gating and anti-answer-leak evaluation as alternatives/complements to end-to-end RL |
| [Teaching Problem-Solving via RL](https://aclanthology.org/2025.emnlp-main.15/) | Reward over generated tutoring episodes | Synthetic students and math tasks | GRPO-style RL | Teach problem solving | Simulated and rubric-based tutoring measures | Demonstrates an RL formulation, but also embodies the simulator-dependence Grammar-KT must avoid |
| [Simulated Students: Substance or Illusion?](https://aclanthology.org/2026.acl-long.1960/) | SFT/preference signals for student simulation; benchmark metrics | Real math tutoring dialogue as reference | Compare prompted/SFT/preference student simulators | Simulate learner turns | Linguistic, behavioral, cognitive, automatic and human measures | Strong warning: fluent prompted students can be behaviorally/cognitively unfaithful; synthetic self-evaluation is circular |
| [DPO](https://arxiv.org/abs/2305.18290) | Pairwise chosen/rejected responses | Human or synthetic preferences | Closed-form preference classification relative to a reference policy | General alignment | Reward-model and human preference benchmarks | Simple preference baseline after SFT, but requires trustworthy, nontrivial pairs and does not create pedagogical validity |
| [IPO / ΨPO](https://proceedings.mlr.press/v238/gheshlaghi-azar24a.html) | Pairwise preferences | Same data regime as DPO | Regularized preference optimization derived without Bradley–Terry reward assumption | General alignment | General preference benchmarks | A defensible small ablation for deterministic preferences; empirical tutoring advantage is unestablished |
| [ReST](https://arxiv.org/abs/2308.08998) and [RAFT](https://arxiv.org/abs/2304.06767) | Filtered/ranked self-generated candidates | Policy generations scored by a reward/checker | Iterative supervised fine-tuning on accepted samples | General alignment | Task/reward benchmarks | Natural fit for exact realization checks; simpler than preference learning and retains only verified positives |
| [Training Verifiers](https://arxiv.org/abs/2110.14168) and [Process Supervision](https://arxiv.org/abs/2305.20050) | Outcome or intermediate correctness labels | Automatically/human checked solutions | Learned verifier/reward model | Mathematical reasoning | Best-of-N/verification accuracy | Supports reranking candidates and factorized labels; current grammar checks are outcome-level, not a truthful process trace |
| [Constitutional AI](https://arxiv.org/abs/2212.08073) / [RLAIF](https://arxiv.org/abs/2309.00267) | AI critiques, revisions, and AI preferences under a rubric | Model-generated candidates plus principles/judges | SFT then preference/RL alignment | General assistant behavior | Human and automated preference | Relevant only for soft pedagogical dimensions after deterministic grammar constraints; inherits judge bias and circularity |

## Methodological synthesis

The literature supports a staged evidence hierarchy:

1. **Structured SFT** on exact positive targets has the fewest assumptions.
2. **Verifier-filtered generation / rejection sampling** exploits deterministic
   grammar checks without needing arbitrary rejected text.
3. **Preference optimization** is justified only when plausible near misses
   remain difficult after SFT and filtered-SFT baselines. Targeted negatives,
   not generic “bad feedback,” are the useful unit.
4. **A learned reward model or LLM judge** belongs only on soft dimensions such
   as hint usefulness, answer revealingness, tone, and level fit, with a
   human-validated subset.
5. **RL** needs a credible action-dependent transition and delayed learning
   outcome. A sequence of simulated events alone does not meet that bar.

Grammar-KT should therefore retain independent verifier dimensions and use a
lexicographic decision rule: hard grammatical validity first; KC/solvability
second; learner-state fit third; human-validated pedagogical quality last.
Collapsing these into an arbitrary weighted reward would obscure which signal
actually improved.

## What Grammar-KT may add

The focused search found adjacent systems with KT-conditioned exercise
generation, grammar-error explanations, synthetic targeted preferences, and
long-term tutor-action evaluation. It did not identify a work that derives,
from one provenance chain, canonical morphosyntax, realizations, factorized
KCs/Q-matrix edges, exact answer checks, structural near misses, and observable
learner histories for both KT and post-training views. This is a **candidate
integration contribution**, not a blanket novelty claim; a fuller systematic
review would be needed before a paper's final novelty statement.

The scientifically useful distinction from FEAT is not “more RL.” FEAT begins
with alternative feedback strings and learns to rank them. Grammar-KT can begin
with an explicit grammatical opportunity and derive exact positives,
single-feature counterfactuals, KC projections, and leakage groups before any
model writes pedagogical text. Human/LLM judgment is still required once the
claim moves from structural validity to educational usefulness.
