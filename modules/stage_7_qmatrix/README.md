# Q-matrix

Purpose: copy frozen item-opportunity activation into deterministic item–KC edges and a binary matrix.

Input types: accepted `ItemSpec`s, `KCActivation`s, and `KCSpec`s. See `contract.yaml` and `schemas/`.

Scientific/configuration inputs: Q-matrix version and maximum reported row width; there are no manual labels.

Output types: binary Q-matrix, `ItemKCEdge[]`, and audit.

Single row/explanation: `python -m modules.stage_7_qmatrix.explain ITEM_ID --experiment current`

Batch: `python scripts/run_experiment.py current --only qmatrix`

Adjustable research variables: row-width guard only; KC assignments change upstream through the KC policy.

Example question: Which exact frozen activation rule accounts for every edge in one row?
