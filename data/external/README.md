# External EGP source

The parsed EGP source is consult-only and is not redistributed here. The current experiment expects:

- filename/path: `/home/abdullah/urop-aug/sources/parsed_final/egp_entries.jsonl` (overridable in YAML or with `--source-path`);
- SHA-256: `e38c4f959f188150dae7b88f21e35d77828048772e222191818dc0c2488486cd`;
- records: 1,222 JSON objects.

`python scripts/run_experiment.py experiments/current.yaml --to source --source-path /local/path/egp_entries.jsonl` verifies the source and constructs the fixed 139-descriptor subset inside the run directory.

