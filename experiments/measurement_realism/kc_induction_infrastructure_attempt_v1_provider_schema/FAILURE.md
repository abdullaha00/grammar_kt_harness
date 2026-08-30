# KC-induction infrastructure attempt v1

Status: rejected by the structured-output service before inference.

All three planned calls returned HTTP 400 with `invalid_json_schema`: the
provider does not permit `minProperties` in the response schema. Their call
metadata record zero reported model tokens, and no parsed proposal exists.
The exact prompts, schemas, settings, stdout, stderr, and call metadata remain
under `call_evidence/`.

Plan/input hashes:

- `study_plan.json`: `d9f6346b29adefc1bf5e96657ff1a004b7038f467817d31c6ee210cf8425a86e`
- `proposal_input.json`: `5cb46444763da87de19fcfc90f08ad0b519942d79fe5b6386f1dff5a13c7f733`
- `proposal_requests.jsonl`: `d579fd9c8ca3bf23e64b687f0612c958998a2ed4f55a3597770b51c95195bcff`

Correction: replace dynamic predicate keys plus `minProperties` with six fixed,
required GrammarCell dimension fields; an empty array denotes an unconstrained
dimension, while local validation requires at least one constrained dimension.
The corrected calls are replanned separately and this attempt is excluded from
scientific analysis.
