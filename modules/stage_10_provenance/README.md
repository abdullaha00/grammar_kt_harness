# Provenance

Purpose: connect record lineage to the exact stage configuration and implementation hashes that produced it.

Input types: declared stage-interface identifiers and stage manifests. See `contract.yaml` and `schemas/`.

Scientific/configuration inputs: provenance version only; referenced methodology is never duplicated.

Output types: typed `ProvenanceEdge[]`, audit, and `methodology.json` hash/path references.

Single item trace: `python scripts/trace_item.py ITEM_ID --run current`

Batch: `python scripts/run_experiment.py current --only provenance`

Adjustable research variables: enable/disable and provenance format version.

Example question: Which prompt, rulebook, KC policy, item method, Q edge, and simulator configuration led from a source descriptor to one observable interaction?
