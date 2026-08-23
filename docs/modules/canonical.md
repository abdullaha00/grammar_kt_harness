# Canonical module

1. **Research question.** What does the six-dimensional GrammarCell preserve and exclude?
2. **Inputs.** Complete normalisation mappings and `modules/canonical/grammar_schema.yaml`.
3. **Outputs.** Unique cells, source-cell edges, and a paper-ready attrition audit.
4. **Assumptions.** Dimensions, values, cross-field constraints, interpretation, and scope are declared in the schema.
5. **Researcher choice.** The schema is the scientific representation; this task does not expand it.
6. **Deterministic implementation.** Exact validation, stable IDs, complete-only contribution, and deduplication.
7. **Without Python.** Clarify the declaration/rationale; substantive schema changes require an explicit migration and consistency tests.
8. **Inspect.** `canonical/canonical_cells.jsonl`, `source_cell_edges.jsonl`, and `audit.json`.
9. **Example.** `python scripts/run_one.py canonical --fixture`.
10. **Paper dependencies.** RQ2 directly and all KC/transfer questions downstream.
