# Simulation

**Purpose:** Generate chronological synthetic learner interactions from the accepted bank and Q-matrix.

**Inputs:** Accepted items, Q-matrix, KC inventory, simulator parameter file, and seed.

**Procedure:** Sample declared latent profiles, shuffle complete item passes, generate Bernoulli outcomes, and update active synthetic states after each event.

**Outputs:** `observable_interactions.jsonl`, `oracle_interactions.jsonl`, learner files, `audit.json`, and `manifest.json`.

**Command:** `python scripts/run_experiment.py experiments/current.yaml --only simulation`

**Configurable components:** Seed, population/profile parameters, event count, probability process, and learning gains.

