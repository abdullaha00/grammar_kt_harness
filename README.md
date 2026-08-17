# Modular grammar-to-KT harness

This repository is the minimal executable form of the current EGP grammar-to-KT experiment. It keeps normalization, canonical grammar, realization, KC policy, item construction, Q-matrix derivation, simulation, and KT techniques independently configurable through one experiment manifest; it intentionally omits the methodology-development history.

```text
external EGP source -> source subset -> normalization -> canonical cells
  -> realization -> KC projection -> item generation -> item validation
  -> Q-matrix -> simulation -> KT -> provenance
```

| module | declared input | output |
|---|---|---|
| source | hash-pinned EGP JSONL + fixed IDs | subset, metadata, units |
| normalization | subset + frozen v1.3 contract | Phase 1/2 and final mappings |
| canonical | final mappings | cells and source-to-cell edges |
| realization | cells, source edges, frozen rules/lexicon | executable RealizationSpecs |
| KC | cells, realizations, policy | KC inventory and cell projection |
| items | cells, realizations, KC projection | candidates, diagnostics, accepted/rejected items |
| Q-matrix | accepted items + KC policy | matrix and derived item-to-KC edges |
| simulation | item bank + Q-matrix | separate observable and oracle interactions |
| KT | observable interactions | predictions and technical metrics |
| provenance | all stage interfaces | typed lineage graph and audit |

## Prerequisites

Use Python 3.11+ and install the pinned packages with `python -m pip install -e .`. The current normalization and item diagnostic use Codex CLI 0.147.0 semantics and require working Codex authentication. The restricted EGP source is not redistributed; see `data/external/README.md`. The reference run launches 147 Phase-1 annotations, mechanically routed Phase 2 annotations (88 in the accepted run), and 50 independent item diagnostics.

## Reproduce and validate

```bash
python scripts/run_experiment.py experiments/current.yaml
python scripts/validate_experiment.py runs/current
```

Override only the local source location with `--source-path /path/to/egp_entries.jsonl`. Existing completed runs are never overwritten; `--force` first moves the old run to a timestamped backup.

## Controlled variants

Experiment files may `extends: current.yaml`; nested keys are deep-merged. Give every variant a new `experiment_id`. To reuse a verified unchanged prefix, declare `reuse.run` and `reuse.through`.

```bash
cp experiments/current.yaml experiments/new_prompt.yaml
# change experiment_id and normalization.phase1_prompt only
python scripts/run_experiment.py experiments/new_prompt.yaml

cp experiments/current.yaml experiments/dkt.yaml
# change experiment_id and kt.techniques; optionally reuse through simulation
python scripts/run_experiment.py experiments/dkt.yaml

cp experiments/current.yaml experiments/full_cell.yaml
# change experiment_id and kc.policy to full_cell
python scripts/run_experiment.py experiments/full_cell.yaml
```

Trace an accepted item with:

```bash
python scripts/trace_item.py ITEM_ID --run current
```

See `DESIGN.md` for the scientific boundaries and `experiments/README.md` for manifest inheritance and prefix reuse.

