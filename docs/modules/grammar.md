# Grammar Representation

Question: **What grammatical structures exist?**

The source stage verifies the declared snapshot and selected descriptors. Normalisation runs Phase 1 on restricted descriptor evidence and Phase 2 only for eligible partial mappings, in fresh contexts with retry and raw-evidence retention. Canonicalisation then validates exact GrammarCells, derives stable IDs, deduplicates them, and records source edges. Partial mappings never contribute exact cells.

Inputs and outputs remain stage-specific; grouping these transformations does not merge them.
