# EGP normalization v1.3-pilot frozen rulebook

This version changes only four localized v1.2 procedure boundaries: closed
nonmodal-simple and imperative defaults, generic-question Phase-2 eligibility,
phase-aware eligibility-note validation, and failure-safe audit behavior. The
six-field GrammarCell and EGPMapping schemas are byte-identical to v1-v1.2.

## In scope

Single-clause English verbal morphosyntax covering:

- present and past morphological tense;
- simple, progressive, perfect, and perfect-progressive aspect;
- active/non-passive and canonical BE-passive voice;
- positive and negative polarity;
- declaratives, polar questions, subject-WH questions,
  non-subject-WH questions, and imperatives;
- central modals: `can`, `could`, `may`, `might`, `must`, `shall`, `should`,
  `will`, and `would`.

## Out of scope or deferred

- question tags;
- linked conditionals;
- embedded or indirect questions;
- GET-passives;
- semi-modals and periphrastic modals such as `have to` and `be going to`;
- non-verbal grammar;
- multi-clause or relational constructions not representable as one cell.

## Evidence encoding: scalar, cells, list, null

Apply these rules in order for every dimension.

1. **Exact atomic source value -> scalar.** Use a scalar only when the
   descriptor establishes one exact value.
2. **Independently asserted alternatives -> separate OR cells.** If the source
   asserts each alternative, duplicate the remaining constraints and create
   one cell per supported alternative. For example, “affirmative and negative”
   gives positive and negative cells; “will and shall” gives one cell per modal.
3. **Bounded superclass or underspecified set -> list.** Use a list when the
   source constrains the value to a finite set without independently asserting
   every member. Generic “modal verbs” gives
   `[can,could,may,might,must,shall,should,will,would]`.
4. **No usable source constraint -> null.** Do not replace absent evidence with
   a convenient default unless an explicit rule below supplies that default.

A list is one conservative constraint. It never grants member-wise curriculum
support and is never automatically expanded into cells. Dimensions inside a
cell are AND constraints; cells are OR branches. Preserve source correlations.
Never infer a Cartesian product. If pairings are not established, remain
partial rather than inventing branches.

## Phase-1 normalization rules

Explicit descriptor evidence overrides defaults. Apply tense-modal
compatibility after identifying descriptor cues and before assigning result.

### Tense

- named morphological present -> `present`;
- named morphological past -> `past`;
- central-modal clause -> `NA`;
- imperative -> `NA`;
- there is no future-tense value: `will` is a modal;
- an explicit finite nonmodal FORM that names inflecting DO, main/auxiliary
  BE, auxiliary HAVE, or a subject-WH finite main verb but does not distinguish
  present from past -> `[present,past]`;
- no tense evidence -> `null`.

In modal + HAVE + participle, “modal perfect” or “present perfect ... with
modal verbs” establishes perfect aspect, not present morphological tense. A
central modal therefore requires `tense=NA`.

### Tense-modal compatibility invariant

This applies to every complete and partial cell.

- `tense=present` or `tense=past` -> `modal=none`;
- a tense list wholly contained in `{present,past}` -> `modal=none`;
- an exact central modal -> `tense=NA`;
- a list containing only central modals -> `tense=NA`.

Named/bounded morphological present/past is positive evidence for non-central-
modal status. Never use `modal=null` in such a cell. If explicit descriptor
evidence irreconcilably asserts both systems in one inseparable construction,
return `unresolved` rather than discarding a cue.

### Aspect: deterministic descriptor-cue table

Inspect only the descriptor in Phase 1. Apply the first matching row.

| Priority | Descriptor-level cue | Aspect |
|---:|---|---|
| 1 | explicit perfect-progressive or perfect-continuous target | `perfect_progressive` |
| 2 | explicit perfect target, including modal + HAVE + participle | `perfect` |
| 3 | explicit progressive/continuous target, including BE + `-ing` | `progressive` |
| 4 | explicit word “simple” | `none` |
| 5 | closed central-modal formula explicitly giving modal + base/main verb, including interrogative order or an explicitly closed modal + BE + participle passive formula | `none` |
| 6 | closed nonmodal formula: finite DO + base/main verb; simple main-BE; subject-WH finite main verb without an auxiliary; or another explicitly closed simple finite-main-verb form | `none` |
| 7 | ordinary imperative base form; emphatic-DO imperative; LET'S, LET'S NOT, or LET + pronoun + base verb | `none` |
| 8 | broad wording such as “with modal verbs”, “modal auxiliary verbs”, a generic modal question, or “passive with modal verbs”, without rows 1-5 | `null` |
| 9 | broad BE/HAVE wording whose construction does not establish simple, perfect, or progressive structure | `null` |
| 10 | no usable aspect cue | `null` |

Rows 1-3 always override simple/default cues. A formula is closed only when
the descriptor itself states a chain that excludes unmentioned perfect or
progressive structure. Merely naming a modal, a modal superclass, a generic
modal question/passive, or broad BE/HAVE does not close aspect. Examples never
supply a missing descriptor-level aspect cue.

### Voice

- explicit canonical BE-passive -> `passive`;
- ordinary unmarked verbal FORM -> `active` unless genuinely unresolved;
- otherwise no voice evidence -> `null`.

### Polarity

- AFFIRMATIVE -> `positive`;
- NEGATIVE or explicit `not`/`n't` -> `negative`;
- ordinary unnegated imperative, including LET/LET'S and emphatic-DO ->
  `positive`;
- generic QUESTIONS does not establish polarity -> `null`;
- otherwise no polarity evidence -> `null`.

### Clause

- ordinary unmarked tense/aspect FORM -> `declarative`;
- yes/no -> `polar_question`;
- explicit subject WH -> `subject_wh_question`;
- explicit object, adjunct, or non-subject WH ->
  `non_subject_wh_question`;
- generic WH -> `[subject_wh_question,non_subject_wh_question]`;
- explicit yes/no and generic WH -> one polar-question cell plus one cell with
  the generic-WH list;
- bare “question form”, “question forms”, or “questions” without an identified
  subtype or closed alternative set -> `null`;
- imperative -> `imperative`.

### Modal

- explicit central modal -> the exact modal scalar;
- generic “modal verbs” ->
  `[can,could,may,might,must,shall,should,will,would]`;
- an explicitly ordinary nonmodal lexical or BE/HAVE/DO auxiliary form ->
  `none`;
- a question construction establishing neither morphological present/past nor
  central-modal status -> `null`;
- ordinary imperative -> `none`;
- always apply tense-modal compatibility.

### Imperatives and source-specific realization

- `clause=imperative` -> `tense=NA`, `aspect=none`, and `modal=none`;
- ordinary/unnegated imperative -> `polarity=positive`;
- explicit negative or NOT -> `polarity=negative`;
- ordinary affirmative/negative, emphatic-DO, LET'S, LET'S NOT, and LET +
  pronoun may share a canonical cell whenever all six dimensions agree;
- preserve emphatic-DO, LET'S, LET'S NOT, or LET + pronoun in `note`, prefixed
  `source realization condition:`;
- routine negative-imperative DO realizes negative polarity and does not need
  a subtype field;
- agreement, predicate type, transitivity, operator choice, and imperative
  subtype remain downstream realization/KC concerns.

### Phase-2 eligibility declaration

Every Phase-1 `partial` mapping has a non-null note beginning exactly
`phase2 eligible: ` followed by `none` or a comma-space list of dimensions in
this fixed order: `tense, aspect, voice, polarity, clause, modal`. List each at
most once; `none` cannot be combined with a dimension.

An optional imperative realization condition may follow after exactly `; `,
for example:

```text
phase2 eligible: none; source realization condition: LET + third-person pronoun
```

A dimension is eligible only when all are true:

1. the descriptor explicitly targets uncertainty in that dimension rather
   than merely omitting it;
2. its alternatives form a closed space in the ontology;
3. Phase 1 cannot resolve the member or correlation and therefore uses a list
   or `null`; and
4. examples could positively resolve it without turning an illustrative
   subset into exhaustive source coverage.

Typical tense-eligible cases name an inflecting nonmodal DO, main/auxiliary BE,
auxiliary HAVE, or subject-WH finite main verb without distinguishing present
from past. Phase 1 uses `[present,past]`. Eligibility permits inspection; it
does not guarantee refinement.

Explicit exclusions:

- generic modal and generic-WH superclasses;
- broad modal aspect, including modal questions/passives;
- BE/HAVE incidental aspect;
- a bare “question form”, “question forms”, or “questions” clause subtype;
- any exact scalar;
- any null/list that is merely source underspecification rather than a closed,
  descriptor-targeted ambiguity.

A generic question-form descriptor has `clause=null` and never names `clause`
as eligible. Examples containing only polar and non-subject-WH questions do not
exclude subject-WH. Only a descriptor that itself identifies a closed
question-type space may make clause eligible.

If no dimension passes, write `phase2 eligible: none`. Complete mappings need
no eligibility prefix. A special imperative realization note may still occur
on a complete mapping. Zero-cell results use their required explanatory note.

### Scope results

- declared unsupported construction -> `out_of_scope`;
- clearly in-scope distinction impossible to represent -> `schema_failure`;
- source cannot be mapped reliably, including an inseparable mixed supported/
  unsupported construction -> `unresolved`.

Do not invent dimensions/values or infer Cartesian combinations.

## Phase-2 evidence and transformation policy

Read Phase 1's eligibility declaration before using examples. Phase 2 may
modify only named dimensions. All other values, branches, correlations, and
the note are fixed.

If eligibility is `none`, return Phase 1 unchanged unless relevant examples
directly contradict an exact scalar. If a named dimension cannot be validly
refined, leave the mapping unchanged.

Examples are illustrative, not exhaustive. Absence never shows exclusion. One
witnessed value, or repeated examples sharing one value, does not close a list
or `null`.

For a named eligible dimension, refine/split only when the descriptor licenses
the broader closed space and examples positively establish alternatives
sufficient to avoid false exhaustiveness. A `[present,past]` tense constraint
may split when both are positively exemplified. Never change an ineligible
dimension, expand a source superclass member-wise, add incidental grammar, or
infer a Cartesian product.

An exact Phase-1 scalar is immutable. If relevant examples directly contradict
one, return `result=unresolved`, `cells=[]`, and a note beginning
`phase2 contradiction: <dimension>=<value>; evidence: ` plus a brief reason.

Apart from contradiction, preserve the Phase-1 note byte-for-byte. A named
eligible dimension may become scalar in every resulting branch; its retained
eligibility declaration is provenance, not a claim that it remains uncertain.
Phase-2 validation uses the Phase-1 object plus the transition checker and does
not reapply the Phase-1 “eligible dimension is currently non-scalar” rule.

