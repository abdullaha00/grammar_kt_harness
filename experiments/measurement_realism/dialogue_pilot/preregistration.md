# Ecological-realism / measurement-precision continuum pilot

## Status and evidential boundary

This protocol was frozen on 2026-08-30 before any opportunity generation,
automated critique, human review, or learner response collection for this
pilot. The checked-in plan makes **zero live model calls**. It therefore
contains a design and deterministic inputs, not evidence that any proposed
format is natural, answerable, deployable, or valid.

The pilot asks whether a more contextual learner interaction can retain a
defensible grammatical opportunity boundary. It does not try to establish a
single realism ranking. Ecological plausibility and measurement precision are
different outcomes and will not be averaged into a score.

The protected benchmark `data/grammar_kt_full_v1/` is an input reference only.
This protocol must not write to it. Learner outcomes, private mastery
trajectories, response probabilities, and KT results are forbidden selection
inputs.

## Limitation motivating the pilot

The full-v1 bank provides controlled GrammarCells, declared generator KCs, and
a deterministic Q-matrix, but its response simulator ignores item wording once
Q is fixed. Conversely, adding dialogue merely because it appears natural can
destroy answer determinacy, introduce unmodelled grammar and vocabulary, or
make success impossible to attribute to the declared KCs.

The smallest useful test is therefore a matched continuum in which linguistic
and semantic content is held fixed while response constraint changes.

## Scientific questions

1. Can one shared GrammarCell/Q row and semantic proposition be expressed in
   five increasingly open learner interactions without silently changing the
   target?
2. Do contextual and interaction-naturalness judgments improve as scaffolding
   is removed?
3. Do answer ambiguity, incidental grammar, lexical nuisance, and weak KC
   attribution increase as scaffolding is removed?
4. Are these changes different for a one-KC anchor, a compositional row, a
   question, and a rare clause operation?
5. At what point, if any, does the one-turn opportunity cease to support a
   defensible measurement interpretation?

This is a four-family mechanism pilot. It is not powered to estimate rates for
the 75 GrammarCells, the 113-item bank, platforms in general, or human learners.

## Frozen cell selection

The source is
`experiments/measurement_realism/design/format_selection/selected_cells.json`,
specifically its outcome-free 18-cell `seen_cells` cohort. Selection is an
exact lookup by predeclared `selection_role`; it is not optimized against
learner outcomes or later judgments. If the source role, cell ID, or expected Q
width changes, `build_plan.py` fails rather than substituting another cell.

| Pilot stratum | Selection role | GrammarCell | Structure | Active generator KCs | Q width | Why included |
|---|---|---|---|---|---:|---|
| simple | `finite_present_anchor` | `gc_d15de8b5658bd6a5` | present, no aspect, active positive declarative | `gkc_finite_present` | 1 | Minimal common anchor and isolating Q row |
| multi-KC | `past_perfect_contrast` | `gc_2d6eb4f93cba4c6b` | past perfect active positive declarative | `gkc_aspect_perfect`, `gkc_finite_past` | 2 | Ordinary compositional measurement case |
| question | `present_perfect_polar_contrast` | `gc_08d90a35b669ed28` | present perfect active positive polar question | `gkc_aspect_perfect`, `gkc_finite_present`, `gkc_polar_question` | 3 | Tests a common clause-operation dependency |
| rare/complex | `non_subject_wh_rare_cell` | `gc_4634bf1b005f7724` | present active negative non-subject-WH question | `gkc_finite_present`, `gkc_negation`, `gkc_non_subject_wh_question` | 3 | Sole selected non-subject-WH cell and narrow-support stress case |

The rare stratum means rare in the frozen selected cohort, not rare in English
or among learners. The generator KCs are synthetic-world declarations, not
assertions of human cognitive atoms.

## Matched opportunity continuum

Each cell defines one family of five opportunities in this exact order:

1. `constrained_cloze`: one typed span inside a complete clause;
2. `sentence_transformation`: one typed sentence from a supplied proposition
   and communicative cue;
3. `contextual_production`: one short clause from context and a goal, without a
   full syntactic frame;
4. `dialogue_completion`: one named next-speaker turn after no more than three
   context turns;
5. `open_dialogue`: one free but bounded turn from a short history and a
   communicative goal.

The learner-visible representation separates instruction, context, stimulus,
dialogue history, response component, scoring interpretation, feedback target,
and opportunity boundary. This prevents an abstract annotation prompt from
being mistaken for an interface.

### Invariants within a family

The five opportunities must retain:

- the exact GrammarCell, active generator KC IDs, and 18-column Q row;
- one scenario and set of referents;
- one lexical head and target proposition;
- the same intended grammatical realization and canonical target example; and
- a non-target vocabulary policy.

The instruction, syntactic scaffolding, response component, minimal dialogue
history, and format-appropriate scoring policy may change. A format may not
introduce a format-specific KC, change the lexical head to make production
easier, require specialist linguistic terminology, or present one example as
an exhaustive answer set for open dialogue.

Exactly one candidate family per cell is planned. Creating alternatives,
changing cells, or changing the matching contract requires a dated amendment
before any corresponding call.

## Generation and critique procedure if later authorized

Generation is one isolated call per cell family using
`prompts/generate_continuum_family.txt` and
`schemas/generated_family.schema.json`. Exact input, rendered prompt, model,
settings, raw output, parsed output, and hashes must be retained. Schema
validity does not imply scientific validity.

Each viable family is then judged independently through five lenses:

- learner;
- language teacher;
- platform product;
- measurement;
- linguistic validity.

Roles do not see one another's outputs. Each role produces one judgment per
opportunity using `prompts/critic_continuum.txt` and
`schemas/critic_judgment.schema.json`. Disagreement is retained at the exact
opportunity level. These model-based judgments are automated stress tests, not
human, expert, platform, or response-process evidence.

## Outcomes retained separately

### Ecological / usability dimensions

- task comprehensibility;
- context naturalness;
- interaction naturalness; and
- platform plausibility.

### Measurement-precision dimensions

- answer determinacy;
- conservative lower bound on plausible response families;
- accepted-response coverage;
- incidental grammatical operations;
- lexical nuisance;
- KC attribution; and
- availability of a target-avoiding shortcut.

Ordinal categories are reported as category distributions. The plausible
response count is explicitly a conservative lower bound, not an exhaustive
enumeration. Incidental grammatical operations remain a multi-label set. No
dimension is normalized and averaged with another.

## Predeclared expectations

These are stress-test expectations, not guaranteed monotonic laws:

- interaction-naturalness and platform-plausibility concern may fall with
  contextualization;
- determinacy risk, plausible-response count, incidental grammar, lexical
  nuisance, and KC-attribution risk may rise with openness;
- sentence transformation or dialogue completion may provide a useful middle
  ground, so strict monotonicity need not hold; and
- the question and rare/complex families may expose attribution and
  incidental-grammar failures sooner than the one-KC anchor.

A result that constrained formats are more deployable than open dialogue is
allowed. A result that no proposed open-dialogue item has a defensible
opportunity boundary is also allowed.

## Primary analysis

`analyze_dialogue_pilot.py` will require the exact 20 planned opportunities
and, by default, all 100 opportunity-by-role judgments. It will report:

1. every dimension by format, cell stratum, critic role, and opportunity;
2. exact opportunity IDs with cross-role disagreement;
3. within-family, within-role deltas from `constrained_cloze` for each
   dimension separately;
4. descriptive direction checks across the five-format order for each
   dimension separately; and
5. incidental-operation labels and shortcut frequencies without collapsing
   them into a score.

The four cells are the unit of format matching. The five critic roles are not
independent human replications and will not be treated as such. With four
families, no population-level significance claim is planned.

## Hard gates and scale decision

An opportunity is withheld or redesigned if any retained evidence establishes
one of the following:

- the visible task does not instantiate the frozen GrammarCell or changes the
  declared Q row;
- the learner action or one-turn boundary is not explicit;
- the task is materially ambiguous but uses exact or purportedly exhaustive
  scoring;
- ordinary plausible responses would have a major accepted-response gap;
- success can clearly bypass the intended operation;
- KC attribution is `not_attributable`;
- an essential incidental grammar operation is neither controlled nor declared;
- vocabulary or context is necessary but inaccessible for the intended band;
  or
- a plausible learner interaction cannot be represented without deceptive
  scoring.

`open_dialogue` may be retained as `not_viable`; a forced viable item is not a
success. It is eligible for a larger study only if all four families retain a
defensible opportunity boundary, no linguistic critic identifies a target-cell
mismatch, no measurement critic identifies `not_attributable` evidence, and
the human protocol confirms that its interpretive rubric does not reject
ordinary relevant turns. Failure means the continuum result remains a bounded
negative or qualitative pilot, not that the target must be weakened.

No extended dataset release can be justified from this four-cell pilot alone.

## Human evidence still required

The future protocol is specified in
`human_expert_validation_protocol.md`. Until it is executed, the project may
say only that the design is auditable and that automated critics raised or did
not raise specified concerns. It may not claim learner answerability,
deployability, format validity, error realism, or ecological validity.

## Reproducibility and amendments

`build_plan.py` freezes the selected cells, 20 opportunity slots, generation
requests, and hashes. It refuses to overwrite changed outputs. Any amendment
after generation or critique begins must preserve the original artifacts,
state the reason, identify affected hypotheses/analyses, and use a new pilot
version. Silent repair is prohibited.
