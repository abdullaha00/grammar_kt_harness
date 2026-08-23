# Items module

1. **Research question.** Which controlled measurements operationalise the grammar evidence independently of a KC ontology?
2. **Inputs.** Canonical cells, shared admissible realisation rules, lexicon, item-family prompt, bank config, and validation policy.
3. **Outputs.** Opportunities, a fixed intrinsic bank, deterministic checks, model diagnostics, accepted bank, and reliability report.
4. **Assumptions.** Measurement subset, agreement representatives, lexical/operator contrasts, and diagnostic acceptance flags.
5. **Researcher choice.** Bank config, family prompt, lexicon, diagnostic backend, and acceptance vector.
6. **Deterministic implementation.** Construction, identities, answers, validation, and the split-independent fingerprint.
7. **Without Python.** Edit module configs; no fold or KC labels belong in item content.
8. **Inspect.** Generation/validation bank reports, `accepted_items.jsonl`, and `validation/reliability.json`.
9. **Example.** `python scripts/run_one.py items --fixture valid_deterministic_item`.
10. **Paper dependencies.** RQ3–RQ8 because the bank determines observable contrasts.
