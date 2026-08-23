# Source module

1. **Research question.** Which EGP evidence enters the study, and is that selection reproducible?
2. **Inputs.** A full EGP JSONL snapshot, mandatory SHA-256, frozen pilot IDs/metadata, annotation units, or a declared sampling design.
3. **Outputs.** Selected source rows, Phase-1 projections, sample metadata, and repeated annotation units.
4. **Assumptions.** Scope filters, strata, quotas, ordering, and any seed determine source coverage.
5. **Researcher choice.** Edit a sampling design under `modules/source/sampling_designs/`; do not edit Python.
6. **Deterministic implementation.** Hash verification, filtering, ordering, selection, and record projection.
7. **Without Python.** Point `GRAMMAR_KT_EGP_SOURCE` at the exact snapshot, or set `GRAMMAR_KT_DATA_ROOT`; create a later MAIN design without changing the frozen 139 IDs.
8. **Inspect.** `source/source_subset.jsonl` for a run, or `sampling_audit.json` from the sampler.
9. **Example.** `python scripts/run_one.py source --fixture` or `python scripts/sample_source.py --source SOURCE --sha256 HASH --design DESIGN --output OUT`.
10. **Paper dependencies.** RQ1, RQ2 and especially RQ8 source-sample robustness.
