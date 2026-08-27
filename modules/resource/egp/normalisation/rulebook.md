# EGP normalisation rulebook

This rulebook maps EGP evidence into the six-dimensional English pilot
GrammarCell. It intentionally ends the EGP-specific vocabulary at the
normalisation boundary.

## Scope

In scope: single-clause English verbal morphosyntax; morphological present and
past; simple, progressive, perfect and perfect-progressive aspect; active and
canonical BE-passive voice; positive and negative polarity; declaratives,
polar questions, subject-WH questions, non-subject-WH questions and
imperatives; and the central modals declared in the canonical schema.

Out of scope: tags, embedded questions, linked conditionals, GET-passives,
semi-modals, non-verbal targets, and multi-clause relations that cannot be
represented as one cell.

## Evidence encoding

1. Exact atomic evidence becomes a scalar.
2. Independently asserted alternatives become separate OR cells.
3. A bounded superclass without member-wise support becomes a list.
4. Missing usable evidence becomes null.

Dimensions within one cell are AND constraints. Cells are OR branches. Lists
do not independently support their members. Never infer a Cartesian product.

## English decisions

### Tense and modal

- Named morphological present/past gives that scalar and entails
  `modal: none`.
- A closed finite formula that establishes a nonmodal form but not present
  versus past may use `[present, past]`.
- An exact central modal gives `tense: NA`; a bounded set of central modals also
  gives `tense: NA`.
- `will` is a modal, not a future tense value.
- Irreconcilable morphological-tense and central-modal evidence in one
  inseparable construction is `unresolved`.

### Aspect cue priority

Apply the first supported row; examples do not supply a missing descriptor cue.

| Priority | Descriptor evidence | Aspect |
|---:|---|---|
| 1 | explicit perfect-progressive/perfect-continuous target | `perfect_progressive` |
| 2 | explicit perfect, including modal + HAVE + participle | `perfect` |
| 3 | explicit progressive/continuous or BE + -ing target | `progressive` |
| 4 | explicit “simple” | `none` |
| 5 | closed modal + base/main-verb formula | `none` |
| 6 | closed nonmodal DO/main-BE/finite-main-verb formula | `none` |
| 7 | ordinary, emphatic-DO, LET, or LET'S imperative | `none` |
| 8 | broad modal or BE/HAVE wording that does not close the chain | null |
| 9 | no usable aspect evidence | null |

Explicit perfect/progressive evidence overrides simple defaults. Merely naming
a modal superclass does not rule out perfect or progressive structure.

### Voice, polarity, and clause

- Explicit canonical BE-passive gives `passive`; an ordinary finite verbal
  form is `active` unless the descriptor leaves voice genuinely unresolved.
- Affirmative gives `positive`; negative/NOT gives `negative`. Bare generic
  questions do not establish polarity.
- Yes/no wording gives `polar_question`; explicit subject and non-subject WH
  wording use their respective values. Generic WH may remain
  `[subject_wh_question, non_subject_wh_question]` when the subtype is bounded
  but unresolved. Bare “questions” without a closed subtype set gives null.
- Ordinary unmarked tense/aspect forms are declarative.

### Imperatives

- Imperatives use `tense: NA`, `aspect: none`, `voice: active`, and
  `modal: none`. Unnegated imperatives are positive.
- Preserve special surface evidence such as emphatic DO, LET'S, LET'S NOT, or
  LET + pronoun in the mapping note only.
- LET'S NOT expresses negation without DO-support; ordinary negative
  imperatives such as “Don't open it” do use DO-support. This distinction is
  generation evidence, not a new GrammarCell field.

## Phase 2

Examples may be consulted only for a Phase-1 `partial` mapping whose note names
an eligible dimension. Bare generic “questions” do not by themselves license
example-based narrowing. Exact Phase-1 values cannot be silently broadened or
replaced. A direct contradiction produces `unresolved`.

Every Phase-1 partial note begins `phase2 eligible: ` followed by `none` or a
comma-separated subset of the six dimensions. A dimension is eligible only
when the descriptor establishes a closed broader alternative space, examples
could positively distinguish members, and refinement would not claim that the
examples exhaust an open class. Phase 2 may change only named dimensions;
unmentioned constraints and source correlations remain fixed.

`complete` means every field in every cell is one allowed scalar.
`partial` preserves at least one list or null. `out_of_scope` and `unresolved`
have no cells.
