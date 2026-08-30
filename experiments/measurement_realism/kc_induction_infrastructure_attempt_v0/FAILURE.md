# KC-induction infrastructure attempt v0

Status: stopped before any model call.

The initial plan rendered the proposal input from insertion-ordered in-memory
JSON, while the run stage reloaded the same semantic input from a canonical
key-sorted file. The byte lengths were equal but the prompt hashes differed,
so the preregistered hash gate stopped the run before creating an evidence
directory or invoking `codex exec`.

Retained files and SHA-256 values:

- `study_plan.json`: `bb3c3fe515c38c4d3768b0832b496ec68e005d8ba30d536a4b68d3c7a2469ec5`
- `proposal_input.json`: `5cb46444763da87de19fcfc90f08ad0b519942d79fe5b6386f1dff5a13c7f733`
- `proposal_requests.jsonl`: `19df7c00450f5384e37457c86a19d00010b5d98951b3111529ec7792e7bc036c`

Correction: all JSON embedded in the rendered prompt is now serialized with
the same canonical JSON function used by the plan. The corrected study is a
new plan under `../kc_induction_v1/`; this directory is never treated as
scientific proposal evidence.
