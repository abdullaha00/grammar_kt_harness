# FULL-LING-001 — full EGP linguistic census protocol

Status: frozen before primary model calls on 2026-08-29.

## Question

What proportion and which structures in the complete 1,222-descriptor EGP
snapshot can be represented exactly under the declared single-main-clause
English verbal-morphosyntax GrammarCell?

## Hypothesis

Processing the complete source will yield substantially more exact canonical
cells and broader clause/modal value coverage than the purposive 139-row pilot,
while most non-verbal and relation-level descriptors will be explicitly
partial or out of scope.

## Fixed methodology

- Source identity: SHA-256
  `e38c4f959f188150dae7b88f21e35d77828048772e222191818dc0c2488486cd`,
  exactly 1,222 rows.
- Population: all rows; no supercategory prefilter or manual cherry-picking.
- Schema/rulebook/prompts: current files under `modules/grammar/`.
- Phase 1: descriptor fields only, `gpt-5.6-sol`, high reasoning.
- Technical retry policy: at most two identical-prompt attempts only when a
  subprocess, JSON, or contract failure prevents a valid mapping. A valid
  mapping is never replaced by a preferred replicate.
- Phase 2: only the cohort frozen mechanically from partial Phase-1 mappings
  with explicit eligibility and available examples.
- Canonicalisation: only complete exact mappings; feature-derived stable IDs.
- Raw source and rendered prompts: restricted under ignored `runs/`.

## Manipulated and held-fixed variables

The manipulated variable relative to the historical pilot is source coverage
(all 1,222 rather than the 139-row purposive sample). Schema, prompt,
rulebook, backend, effort, and exact source snapshot are held fixed.

## Primary outcomes

- complete / partial / unresolved / out-of-scope counts and rates;
- Phase-2 eligibility and resolution;
- number of exact source branches and unique GrammarCells;
- value support for every canonical dimension;
- newly covered clause/modal values;
- technical failure count;
- systematic failure groups by source category.

## Interpretation rules

- Full execution is not semantic validation by itself.
- A high out-of-scope rate is acceptable if it follows the declared boundary.
- Schema expansion requires a coherent, frequent, pedagogically relevant
  failure family and a separate before/after pilot; coverage alone is not a
  reason to expand.
- No normalisation output may depend on items, KCs, learner responses, or KT.

## Commands

```bash
.venv/bin/python scripts/build_dataset.py --stage prepare-source \
  --source /home/abdullah/urop-aug/sources/parsed_final/egp_entries.jsonl

.venv/bin/python scripts/build_dataset.py --stage normalise-phase1 \
  --source /home/abdullah/urop-aug/sources/parsed_final/egp_entries.jsonl \
  --workers 8 --max-attempts 2

.venv/bin/python scripts/build_dataset.py --stage normalise-phase2 \
  --source /home/abdullah/urop-aug/sources/parsed_final/egp_entries.jsonl \
  --workers 8 --max-attempts 2

.venv/bin/python scripts/build_dataset.py --stage canonicalise
```
