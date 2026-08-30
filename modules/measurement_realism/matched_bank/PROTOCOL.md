# Matched-format bank protocol

This protocol constructs a confirmatory, fully crossed measurement bank from
the frozen `grammar_kt_full_v1` GrammarCells and Q rows. It does not alter v1,
read learner outcomes, infer KCs, or permit generated wording to change Q*.

The design contains 38 semantic families: two variants for each of 18 seen
cells and one variant for each of two non-updating held-out cells. Every family
is generated as a whole across constrained cloze, dialogue completion,
multiple choice, and sentence transformation. A family is the curation unit;
formats may never be cherry-picked across generation rounds.

For candidate round 1, then 2 and 3 only where needed, the workflow is:

1. make one audited generation call per unresolved family;
2. run two fresh-context, oracle-blind solver replicates, batched by format so
   a call never contains two items from one family;
3. run separate linguistic, measurement, and platform-product critic calls in
   batches of at most five families, without sharing role outputs;
4. apply schema, interface, crossing, reconstruction, solver, and critic hard
   gates deterministically; and
5. select the earliest whole-family candidate that passes every gate.

All requests, prompts, settings, provider schemas, raw outputs, parsed outputs,
technical failures, and hashes are append-only evidence. Scientific rejection
does not send feedback to the generator. If any family has no passing candidate
after round 3, the 152-item bank cannot freeze. Passing automated critics is
stress-test evidence, not human validation or proof of real-platform adoption.

The executable entry point is
`scripts/experiments/measurement_realism_bank.py`; the standalone verifier is
`scripts/experiments/verify_measurement_realism_bank.py`. Run `--help` for the
stage commands. `config.yaml` is the complete preregistration and remains the
normative source where this summary omits detail.
