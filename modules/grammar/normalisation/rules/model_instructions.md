# Experiment instructions

This is one isolated EGP normalisation unit.

- Treat the supplied prompt, rules, schema, and task input as fixed for this
  invocation. Preserve defects as outcomes; do not repair inputs during the run.
- An annotation process may use only the schema, rulebook, phase prompt, and
  single task input supplied in its prompt.
- Do not inspect the filesystem, invoke tools, browse, consult other records,
  or read prior outputs during an annotation unit.
- Return exactly one JSON `EGPMapping` and no commentary.
- Apply scalar/cells/list/null priority, tense-modal compatibility, and both
  descriptor-level aspect cue tables literally.
- Ordinary imperative base forms have `aspect=none`; unnegated imperatives
  have `polarity=positive`, while explicit negative/NOT has `negative`.
- A generic `question form`, `question forms`, or `questions` descriptor does
  not make `clause` Phase-2 eligible.
- Every partial Phase-1 mapping must use the frozen `phase2 eligible:` note
  convention. Phase 2 may change only named dimensions and must preserve this
  note as provenance even after a named dimension becomes scalar.
- Examples are illustrative, not exhaustive. Do not narrow from frequency or
  absence, expand a superclass, or infer Cartesian combinations.
- Do not use KC, item-generation, or KT considerations to choose a mapping.
- Model annotations are not human judgements.
