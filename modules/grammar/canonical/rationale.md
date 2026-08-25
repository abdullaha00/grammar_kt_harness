# Canonical GrammarCell rationale

`GRAMMAR_CELL_v1` is the pilot's scientific compression hypothesis. An exact
cell is the ordered tuple `tense × aspect × voice × polarity × clause × modal`.
It represents structural contrasts needed by the current study; it is not a
claim that these six fields are cognitively atomic or sufficient for all of
English grammar.

The authoritative values, order, scope, and cross-field constraints are in
[`grammar_schema.yaml`](grammar_schema.yaml). Python validation derives its
domains from that file. The normalisation structured-output schema and prompt
declaration are checked against it in tests and by `scripts/validate.py`, so
they are derived mirrors rather than independent silent definitions.

Important exclusions are lexical aspect, argument structure as a canonical
dimension, agreement/person/number, WH role, imperative subtype, contractions,
semi-modals, embedded questions, and non-BE passives. Those may be downstream
conditions or explicit out-of-scope cases. Normalisation lists and `null`
express source uncertainty; only complete scalar mappings contribute exact
canonical cells.
