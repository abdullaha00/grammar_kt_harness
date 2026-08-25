# Deterministic English realiser v0 — archived

This directory preserves the former lexical-frame / `RealizationSpec` / auxiliary-chain / deterministic surface-generation subsystem, its method resources, and its realiser-specific fixtures.

`reference/current/` contains the former 58-item deterministic-bank counts and KT sanity reference. Its filenames are preserved so historical reports can still be interpreted, but it is not an active reference baseline.

It was archived because concrete lexical frames and a fixed English realiser obscured the scientific distinction between:

- the structural conditions under which a GrammarCell is measured; and
- the surface format used to present that opportunity to a learner.

The code is retained for reproducibility of historical runs and reports. It is not required to satisfy active APIs, lint, or tests. Active production code must never import from `archived_code/`; the active test suite checks this boundary.

Structural logic that remains scientifically relevant was re-expressed in `src/grammar_kt/measurement/operations.py` and `opportunities.py`. No active code imports the archived realiser.
