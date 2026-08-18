# Simulation

Purpose: execute the declared synthetic learner process while separating observable and oracle records.

Input types: accepted items and their frozen Q-matrix. KC identifiers come only from the Q columns. See `contract.yaml` and `schemas/`.

Scientific/configuration inputs: parameters in `configs/`, seed, learner count, and sequence length.

Output types: observable `Interaction[]`, parallel oracle interactions, and learner records.

Try one learner with a one-item fixture (`before` → `after`): `python -m modules.stage_8_simulation.run_one`

Single learner: `python -m modules.stage_8_simulation.run_one LEARNER_ID --experiment current`

Batch: `python scripts/run_experiment.py current --only simulation`

Adjustable research variables: declared simulator parameters and seed. These are generation inputs, not findings.

Example question: How do declared simulator settings change observable response statistics? This does not establish human learning.
