# Simulation module

1. **Research question.** How do ontology conclusions behave under a fixed, explicit synthetic data-generating world?
2. **Inputs.** Accepted intrinsic items plus runtime fold views, canonical cells, oracle config, response parameters, and seed.
3. **Outputs.** Oracle projection/evidence, learners, one fixed observable stream, and frozen-probe streams.
4. **Assumptions.** Structural feature rules, latent profiles, response equation, learning gains, difficulty range, and protocol settings.
5. **Researcher choice.** `structural_oracle_v0.json` and seed; candidate KC policies are never inputs.
6. **Deterministic implementation.** Rule evaluation, keyed draws, mastery update, chronology, and audit hashes.
7. **Without Python.** Change declared feature rules using `cell`, `operation`, `agreement_site`, `frame_type`, `all`, or `any`.
8. **Inspect.** `simulation/audit.json`, oracle projection, private oracle evidence, and compositional audit.
9. **Example.** `python scripts/run_one.py simulation --learner L0001`.
10. **Paper dependencies.** RQ6, RQ7 and RQ8; results remain synthetic-world evidence, not human-KC claims.
