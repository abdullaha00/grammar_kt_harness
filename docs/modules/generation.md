# Dataset Generation

Question: **How is a MeasurementOpportunity presented naturally?**

Standalone and dialogue are configurations of one generator interface. The prompt declares the fixed cell, structural conditions, expected operations, and lexical/item-family constraints. The model chooses surface wording, not target grammar.

Validation first checks schema/reference/leakage invariants, then asks an independent evaluator to reconstruct grammar blindly. Quality diagnostics are reported separately and do not silently redefine grammatical correctness.
