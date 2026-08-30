# Future human and expert validation protocol

## Status

This is a feasible future protocol, not a report of completed human research.
No participant, teacher, linguist, measurement specialist, or platform-product
judgment has been collected for this pilot. Recruitment, ethics review or
exemption, informed consent, fair compensation, and an approved data-management
plan are prerequisites.

The protocol validates distinct claims separately. Agreement on deployability
cannot substitute for GrammarCell accuracy; learner completion cannot establish
KC plausibility; and expert opinion cannot substitute for observed learner
answerability.

## Materials entering review

Review starts only after the four five-format families have passed schema and
identity checks. Review packets contain exactly what a learner would see plus a
separate oracle sheet where needed. They do not contain simulator outcomes, KT
results, automated-critic conclusions, or the other reviewers' ratings.

All 20 opportunities are randomized within reviewer-specific packets. Format
labels are hidden from learner participants. Experts may see a neutral
description of the response mechanism but not a claim that later formats are
more realistic.

## Panel A: linguistic, pedagogical, and measurement review

Recruit three qualified reviewers who each inspect all 20 opportunities:

- at least two with substantial English-language teaching or assessment-item
  development experience; and
- at least one with graduate-level expertise in English grammar, applied
  linguistics, educational measurement, or cognitive diagnosis.

Overlapping qualifications are acceptable, but all three reviews are completed
independently before adjudication. Three reviews per opportunity are enough to
surface systematic disagreement in a bounded pilot while keeping an all-item
review feasible; they are not a normative expert sample.

For each opportunity, reviewers separately record:

1. **GrammarCell accuracy**: whether the canonical target and every response
   treated as positive evidence instantiate the declared cell; identify the
   conflicting feature when they do not.
2. **KC plausibility**: whether each declared generator KC has a coherent
   pedagogical/transfer interpretation for this opportunity; whether two KCs
   appear inseparable, format-specific, lexical, or missing. This assesses
   plausibility, not psychological truth.
3. **Answerability**: whether the visible information supports a reasonable
   response; list at least one overlooked valid response or state that none was
   found; flag hidden assumptions and inaccessible vocabulary.
4. **Measurement interpretation**: whether target success supports the
   declared KCs, whether a target-avoiding shortcut exists, and which additional
   grammar operations are needed.
5. **Pedagogical appropriateness**: whether feedback on the proposed target
   would be understandable and useful at the proposed proficiency band.

Any GrammarCell mismatch, indefensible opportunity boundary, or
`not_attributable` measurement decision is a hard gate pending adjudication and
revision. Revised items receive a new ID/version and are re-reviewed; original
ratings remain retained.

## Panel B: deployability and format review

Recruit two reviewers with language-learning exercise design, tutoring-system,
or educational-platform product experience. Each reviews all 20 opportunities
independently in a minimal UI specification showing instruction, context,
stimulus/history, response field, and proposed feedback.

They separately assess:

- whether the interaction could plausibly appear in lesson, practice, review,
  or diagnostic use;
- instruction length and action clarity;
- fit between the response component and the scoring/feedback policy;
- whether the exercise requires interface capabilities not represented in the
  specification;
- whether contextual or dialogue text is natural enough for the task; and
- format plausibility independent of whether the grammatical target is correct.

Two reviewers identify product-perspective disagreement but do not establish
industry consensus. A format is not called broadly platform-valid on this
sample.

## Learner answerability and response-space study

### Participants

Recruit 60 adult learners of English, split evenly across two adjacent
proficiency bands by an independent short placement measure (30 per band).
The exact bands are set only after Panel A identifies the intended range; they
must not be inferred from EGP labels alone. Record first-language background
for description and balancing, not for post-hoc exclusion.

The sample yields 12 independent learner responses per opportunity while
avoiding repeat exposure to the same family. This is sufficient to expose
common instruction and answer-space failures in a 20-item pilot, but not to
estimate population accuracy or subgroup effects precisely.

### Assignment

Use five precomputed Latin-rotation blocks, stratified by proficiency. Each
participant sees exactly four opportunities: one format from each GrammarCell
family and no repeated scenario. Across 60 participants, every one of the 20
cell-by-format opportunities receives six responses from each proficiency band
(12 total). Item and format order are counterbalanced.

No correctness feedback is shown until the participant has submitted the
response and the immediate usability questions. This prevents feedback from
changing the response-space evidence. The study is diagnostic and
non-updating; responses do not alter a learner model.

### Per-opportunity observations

Collect:

- the raw response, including punctuation and spelling;
- completion/skip and response time as process metadata only, not as a realism
  variable;
- a concise task-understanding choice plus optional paraphrase;
- whether the learner believed more than one answer was possible;
- confidence that the response met the instruction; and
- an optional report of confusing words or missing context.

Two Panel-A reviewers, blinded to condition summaries, independently adjudicate
whether each raw response is contextually reasonable, instantiates the target,
and would be accepted by the frozen scoring policy. Disagreements are retained
and then adjudicated by the third reviewer.

Primary learner-facing diagnostics are reported separately by opportunity and
format:

- task-comprehension failure/uncertainty;
- skip rate;
- rate of contextually reasonable responses;
- target-realization rate;
- rate of reasonable responses rejected by the scoring policy;
- count and examples of unanticipated valid response families; and
- lexical/context confusion reports.

Response time is used only to investigate obvious interface or instruction
failures. No arbitrary human-like response-time distribution is fitted to the
simulator.

## Error-realism validation, conditional on an error stage

Do not run this phase until a structured failed-KC/error-category generator is
frozen and the correct matched opportunities have passed the earlier panels.
Sample 40 plausible synthetic error responses: two independently generated
responses per opportunity, stratified across intended failed-KC categories.
Add 20 blinded diagnostic controls (well-formed target responses and
deliberately category-mismatched or context-incompatible responses), for 60
responses total. Controls test whether reviewers are merely endorsing all
learner-like strings; they are not a substitute for learner-corpus evidence.

Three Panel-A reviewers inspect every response in its learner-visible context,
without seeing the intended category or generation condition, and record:

- whether the intended grammatical error is actually present;
- all major unrelated grammatical errors;
- whether the response is a plausible L2-English production;
- whether it fulfills the interaction context;
- whether its apparent proficiency is compatible with the intended band; and
- whether the binary correct/incorrect label loses diagnostically useful
  information in this instance.

Report intended-category precision, unrelated-error rate, context-fit
distribution, exact disagreements, and category-specific examples. If the
learner study produces errors in comparable contexts, compare error categories
and failure modes descriptively. Do not claim human realism from rater approval
alone, and do not claim corpus validation unless licensed corpus comparisons
are actually performed.

## Agreement, adjudication, and reporting

Retain every pre-adjudication rating. For categorical/ordinal judgments report
raw agreement, item-level disagreement, and a suitable chance-corrected
coefficient with uncertainty where sample size permits. Treat coefficients as
descriptive with 20 opportunities. Never erase disagreement by publishing only
an adjudicated label.

Adjudication notes must name the affected opportunity, disputed dimension,
evidence, resolution, and whether the item was revised, withheld, or retained
with a limitation. Reviewer identities may be pseudonymous in released data,
but qualifications and conflicts of interest are described in aggregate.

## Claim gates

The following wording remains unavailable until its evidence condition is met:

| Proposed claim | Minimum evidence |
|---|---|
| GrammarCell-valid | Independent Panel-A review, disagreement resolved without changing the frozen target |
| pedagogically plausible KC interpretation | Panel-A ratings and rationale; still not human cognitive truth |
| learner-answerable | Learner response-space study plus adjudicated overlooked-valid-response analysis |
| deployable interaction | Panel-B review of the minimal UI; still limited to the reviewed use case |
| format-plausible | Panel-B review plus learner action-comprehension evidence |
| plausible synthetic learner error | Blinded error phase passes intended-error and context-fit gates |
| ecologically valid or representative of platform logs | Not established by this bounded protocol alone |

An extended dataset should not be released on automated criticism alone. At a
minimum, every released opportunity must pass GrammarCell accuracy,
answerability, scoring fairness, opportunity-boundary, and deployability gates;
all revisions and withheld opportunities must be reconstructable.

## Feasibility and scope

The proposed burden is deliberately bounded:

- Panel A: 3 reviewers × 20 opportunities = 60 reviews;
- Panel B: 2 reviewers × 20 opportunities = 40 reviews;
- learners: 60 participants × 4 opportunities = 240 responses, 12 per
  opportunity; and
- optional error phase: 3 reviewers × 60 responses = 180 ratings.

This scale is intended to catch consequential measurement failures before bank
expansion. If it succeeds, a separately preregistered larger, stratified sample
is needed before making bank-level prevalence or broad platform claims.
