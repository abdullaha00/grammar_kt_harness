# External EGP source

The parsed EGP snapshot is consult-only and is not redistributed. The reference
experiment requires SHA-256
`e38c4f959f188150dae7b88f21e35d77828048772e222191818dc0c2488486cd`
and exactly 1,222 JSONL records; identity verification remains mandatory.

Choose its location without editing the experiment:

```bash
export GRAMMAR_KT_EGP_SOURCE=/path/to/egp_entries.jsonl
python scripts/run.py base
```

Alternatively set `GRAMMAR_KT_DATA_ROOT` to a directory containing
`egp_entries.jsonl`, or place it at `data/external/egp_entries.jsonl`. The
frozen 139-descriptor pilot IDs remain under `modules/source/`; the executable
sampling utility is `scripts/sample_source.py` and does not define MAIN quotas.
