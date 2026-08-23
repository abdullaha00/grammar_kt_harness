# Realisation module

1. **Research question.** Which concrete forms are licensed by each canonical claim, and which distinctions are realisation-sensitive?
2. **Inputs.** Canonical cells/source edges and the declared predicate-frame lexicon.
3. **Outputs.** Intrinsic split-independent `RealizationSpec` rows and deterministic derivations.
4. **Assumptions.** Source-note imperative restrictions, frames, subjects, agreement sites, WH roles, and validity constraints.
5. **Researcher choice.** The lexicon and supported construction rules; a fold is deliberately not an input.
6. **Deterministic implementation.** Shared enumeration/validation, chain construction, inflection, inversion, and surface ordering.
7. **Without Python.** Select a lexicon in experiment settings; folds are edited separately in `modules/folds/`.
8. **Inspect.** `realisation/realisations.jsonl`; use the item opportunities for the larger nuisance grid.
9. **Example.** `python scripts/run_one.py realisation --fixture object_wh_lexical_do`.
10. **Paper dependencies.** RQ3, RQ5, RQ6 and RQ8.
