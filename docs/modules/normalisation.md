# Normalisation module

1. **Research question.** How reliably do heterogeneous descriptors map to structured grammatical claims?
2. **Inputs.** Isolated source fields, Phase-1/Phase-2 prompts, canonical declaration, backend settings, and repeated units.
3. **Outputs.** Retained model evidence, final mappings, `reliability.json`, and repeated comparisons.
4. **Assumptions.** Prompt/rulebook wording, allowed uncertainty, and Phase-2 routing policy.
5. **Researcher choice.** Prompts, instructions, backend, attempts, and annotation-repeat design.
6. **Deterministic implementation.** Schema checking, routing, transition validation, and explicit agreement summaries.
7. **Without Python.** Change files under `modules/normalisation/` or the canonical schema declaration.
8. **Inspect.** A unit’s rendered prompts/outputs plus `normalisation/reliability.json`.
9. **Example.** `python scripts/run_one.py normalisation --fixture --phase1-only --output /tmp/norm-one`.
10. **Paper dependencies.** RQ1 directly; RQ2, RQ3 and RQ8 through mapping uncertainty.
