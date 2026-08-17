# Experiment manifests

`current.yaml` names every immutable prompt, rule, schema, policy, and parameter file. Paths are repository-relative unless absolute. `extends` recursively deep-merges another YAML file, so a variant can contain only its new ID and changed component.

A verified unchanged run prefix can be reused explicitly:

```yaml
extends: current.yaml
experiment_id: logistic_variant
reuse:
  run: current
  through: simulation
kt:
  techniques: [logistic]
```

Reuse is by symlink to the named run after its manifests and hashes pass validation; the new resolved manifest records the dependency. Do not reuse through a stage whose configuration or upstream input changed.

