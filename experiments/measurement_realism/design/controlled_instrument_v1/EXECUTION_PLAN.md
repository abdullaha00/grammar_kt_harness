# Controlled-instrument execution plan

Status: `PRE_RESPONSE_ESTIMATE_ONLY`

No learner responses were generated while preparing this plan. Runtime ranges
below are capacity estimates, not retained scientific outcomes.

## Frozen workload

- 6 worlds x 3 seeds under the Q-balanced schedule: 18 response runs and 18
  A-D analyses;
- 3 additional policies x 3 seeds in the combined-heterogeneous world: nine
  response/diagnostic runs;
- 27 response runs total;
- 500 learners per run;
- 188 acquisition events plus 152 terminal probes per learner;
- 170,000 events per run and 4,590,000 events over the full matrix;
- structured-error streams and error-history analyses only for the three
  combined-heterogeneous/Q-balanced runs;
- one final cross-world/seed aggregation.

The run matrix and event budget are recomputed and hashed into
`study_plan.json`; this note is not the executable authority.

## Current-host calibration and estimate

On the current host, dedicated schema/instrument validation took about 1.6
seconds. The focused world/scaffold test suite, including multiple 16-learner
in-memory simulations and bounded-logistic fits, took about 15 seconds. Those
small tests do not scale linearly enough to be a benchmark for the 500-learner
optimizer workload.

Conservative serial estimate after explicit approval:

- response-only generation: roughly 15-45 minutes for all 27 runs;
- 18 primary A-D analyses plus the three error-history analyses: roughly
  2-5 hours;
- aggregation and verification: under 10 minutes;
- total serial wall time: approximately 2.5-6 hours, with optimizer convergence
  and storage throughput as the main uncertainty.

Independent runs may be parallelized at the process level, subject to memory.
Do not parallelize by changing seeds, learner counts, event budgets, or model
settings. Exact elapsed time and peak memory must be recorded when authorized
runs occur; these estimates must not be reported as measured execution times.

## Approval gate

Before any response command is run, all focused tests must pass, the canonical
controlled study plan must validate byte-for-byte, and an explicit approval to
execute the non-release controlled scenario must be recorded outside the
frozen scientific config. The runner command must include
`--controlled-scenario`; omission fails closed.
