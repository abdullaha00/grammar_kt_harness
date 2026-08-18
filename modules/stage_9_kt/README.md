# KT

Purpose: run technical prediction baselines on one frozen observable chronological dataset.

Input type: observable `Interaction[]` only. Oracle state is not in the function or manifest inputs. See `contract.yaml` and `schemas/`.

Scientific/configuration inputs: selected techniques and parameters in `configs/`.

Output types: `KTPrediction[]` and technical metrics.

Inspect one prediction: `python -m modules.stage_9_kt.inspect EVENT_ID --experiment current`

Batch on frozen upstream data: `python scripts/run_experiment.py kt_bkt_only --only kt`

Adjustable research variables: empirical, BKT-style, and logistic baselines plus their declared parameters.

Example question: How do BKT and logistic compare on exactly the same observable data? Metrics are technical sanity checks, not KC validity evidence.
