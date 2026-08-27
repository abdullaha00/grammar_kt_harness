# Research pipeline walkthrough reference

This directory is the compact, offline replay boundary for
[`notebooks/module_unit_examples.ipynb`](../../notebooks/module_unit_examples.ipynb).
It contains five source rows selected from the declared 139-descriptor EGP
research sample, retained model normalisation outputs, and six retained
LLM-generation/validation records. It does not contain synthetic fallback rows.

`LIVE_MODE = False` replays these outputs through the active Python contracts.
`LIVE_MODE = True` requires the verified external EGP snapshot and invokes the
currently configured model backends. The manifest records the provenance and
claim boundary of each retained evidence family.

The five descriptors were selected by a declared coverage rule: retain complete
real annotations while covering present/past, negation, progressive aspect,
questions, passive voice, and a central modal; include one repeated annotation
and one genuine canonical deduplication; then prefer records with accepted
active-architecture generation evidence. Source-sample order is the final
tie-breaker.
