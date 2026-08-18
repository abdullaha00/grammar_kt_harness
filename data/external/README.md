# External EGP source

The parsed EGP source is consult-only and is not redistributed here. The current experiment expects:

- filename/path: `/home/abdullah/urop-aug/sources/parsed_final/egp_entries.jsonl` (overridable in experiment YAML);
- SHA-256: `e38c4f959f188150dae7b88f21e35d77828048772e222191818dc0c2488486cd`;
- records: 1,222 JSON objects.

Set `source.path` in `experiments/base.yaml`, then `python scripts/run.py base`
verifies the declared SHA-256 and constructs the fixed 139-descriptor subset
inside the run directory. The external dataset is the only normal run input
identified by SHA-256 because it is not stored in Git.
