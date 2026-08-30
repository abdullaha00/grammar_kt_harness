# Full-v1 learner/platform item audit rubric

## Scope and status

This is a non-human, post-freeze audit of all 113 learner-facing records in
`data/grammar_kt_full_v1/items/items.jsonl`. It does not alter or supersede the
frozen linguistic validator. Its narrower purpose is to ask whether the stored
opportunities could be understood, answered, scored, and deployed in a
mainstream language-learning interface.

The audit has two deliberately separated perspectives:

- **learner perspective:** can a learner understand the requested response,
  infer the intended construction from the visible information, and receive
  fair credit for an ordinary valid answer?
- **platform/product perspective:** is the task a plausible educational
  interaction, does its context support the target, and is success reasonably
  diagnostic of the declared Q-row rather than an unmodelled nuisance?

These are role-separated judgments by one Codex review pass, not independent
human judgments and not evidence about actual learners. `role_disagreement`
records cases where the two perspectives reach different overall judgments.
External teacher, learner, and product review remains necessary.

## Evidence read

For every item the reviewer inspected the exact stored prompt, target,
accepted-answer spans, GrammarCell, grammar regime, active generator KCs,
generation campaign, and response-slot position. The deterministic script
joins and freezes that evidence in `item_level_audit.jsonl`; it also verifies
that the manual ledger contains exactly the 113 current IDs once each.

The original validator's criteria and judgments were inspected to distinguish
this ecological audit from the already-completed linguistic audit. The
original acceptance decision should not be read as platform deployment
validation: it did not define a rendered UI, scoring normalizer, proficiency
level, or real-learner test.

## Categorical scale

Each dimension uses an ordinal category, never a composite numerical score:

- `pass`: no material problem visible from the stored artifact.
- `concern`: a plausible issue exists, but a small wording, context, UI, or
  scoring change could plausibly resolve it.
- `fail`: the stored opportunity has a material ambiguity, unfair response
  space, unnatural target-in-context, or measurement confound that calls for
  redesign or withholding.
- `uncertain`: the artifact lacks enough information to judge (for example,
  missing proficiency or scoring-policy evidence).

### Learner dimensions

- `task_comprehensibility`: the response action and instructions are clear
  without unnecessary specialist metalanguage.
- `answer_determinacy`: visible context and cues sufficiently select the
  intended response/construction.
- `response_space_fairness`: obvious licensed variants are not silently made
  wrong, taking the visible blank boundaries literally.
- `lexical_context_accessibility`: vocabulary, inference, and discourse do not
  plausibly dominate the grammatical operation.

### Platform/product dimensions

- `pedagogical_plausibility`: the opportunity is a sensible focused grammar
  exercise rather than merely a way to fill a Q-matrix row.
- `format_plausibility`: the stored prompt could reasonably be rendered as a
  learner interaction without annotation-like instructions or missing media.
- `measurement_purity`: a correct response is reasonably informative about the
  declared active KCs, with no obvious shortcut or substantial extra grammar.

## Primary deployment disposition

The mutually exclusive disposition is a qualitative synthesis, not a score:

- `usable_as_stored`: learner-facing content is plausibly usable under the
  declared response-slot contract and ordinary platform normalization.
- `minor_ui_or_context_change`: likely deployable after a local clarification,
  added accepted variant, context repair, or explicit UI treatment.
- `technically_valid_but_artificial`: linguistically answerable, but the
  metalanguage, register, or annotation-style constraints are unlikely to be
  used as stored in mainstream practice.
- `answer_space_problem`: multiple salient responses/constructions remain
  reasonable while only the target construction receives credit.
- `rewrite_or_withhold`: a substantive semantic, naturalness, or measurement
  issue makes a local scoring tweak insufficient.

## Interface-family coding

`format` is `controlled_production` for every frozen item, so the audit adds a
descriptive, non-oracle `interface_family` based only on the visible prompt:

- `inline_cloze`: the response field replaces material inside a printed clause.
- `whole_response`: the learner supplies a complete clause or question.
- `chunk_reorder_in_text`: prose instructs the learner to reorder fixed chunks.

This coding exposes surface heterogeneity hidden by the single format label;
it does not create experimentally crossed formats.

## Scoring assumption and global uncertainty

The item-bank schema supplies accepted strings but no executable policy for
case, whitespace, terminal punctuation, Unicode apostrophes, or typo handling.
Item-level fairness judgments take the printed response-slot boundaries
literally and assume ordinary trimming/terminal-punctuation normalization.
Without that assumption, even otherwise sound items are not deployable
`as-is`. The report therefore presents deterministic answer-packaging facts
separately from the categorical judgments.

## Confidence and disagreements

`confidence` concerns only consistency of this rubric application:

- `high`: the visible issue or absence of issue is direct.
- `medium`: the judgment depends on pedagogical/register interpretation.
- `low`: proficiency, UI, or contextual evidence is too incomplete.

`role_disagreement=true` when learner overall and platform overall differ. It
is not inter-rater disagreement. No actual learner solvability study, teacher
rating, product review, corpus comparison, or CEFR-stratified review occurred.

