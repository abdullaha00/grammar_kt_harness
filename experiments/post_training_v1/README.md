# Active-architecture post-training pilot

This directory asks whether the active five-module Grammar-KT pipeline can
yield useful supervision for selecting generated educational items. It does
not import or extend the archived deterministic realiser.

The experiment consumes active `GrammarCell` records, builds active
`MeasurementOpportunity` records, invokes the configured LLM generators, and
passes every schema-valid candidate through the active blind structural and
quality validators. Raw failures are retained but only educational structural
near misses can enter preference records.

The protocol was frozen before candidate generation in
[`protocols/preregistered.md`](protocols/preregistered.md).

Planned commands:

```bash
PYTHONPATH=src .venv/bin/python experiments/post_training_v1/scripts/run_pilot.py prepare
PYTHONPATH=src .venv/bin/python experiments/post_training_v1/scripts/run_pilot.py collect
PYTHONPATH=src .venv/bin/python experiments/post_training_v1/scripts/run_pilot.py revalidate
PYTHONPATH=src .venv/bin/python experiments/post_training_v1/scripts/run_pilot.py analyse
PYTHONPATH=src .venv/bin/python experiments/post_training_v1/scripts/run_pilot.py evaluate
```
