# Five-module refactor map

## Old → new concepts

| Historical concept | Active concept |
|---|---|
| `item_opportunity_id` | `measurement_opportunity_id` |
| `RealizationSpec` | generator-invariant structural conditions plus generator-chosen lexical/surface content |
| `LexicalFrame` / `frame_type` | `predicate_class` for measurement; lexical frame machinery archived |
| realisation operations | `measurement.operations.derive_operations` |
| controlled transformation | no longer the main method; format is selected by generator config |
| `kc.py` | `knowledge/policy.py` |
| `kc_selection.py` | `knowledge/selection.py` |
| deterministic item validation | hard generator-independent checks plus blind reconstruction and separate quality diagnostics |
| item-keyed synthetic difficulty | opportunity-keyed synthetic difficulty and outcome projection |

## Before and after

Before, the active path exposed `source → normalisation → canonical → realisation → items → simulation → kc_selection → kc → qmatrix → kt`. It coupled candidate discovery, validation, and simulation to lexical frames and concrete realisations.

After, the active path is explained through five boxes while preserving individually runnable transformations inside each box:

```text
Grammar:     source → normalisation → canonical
Measurement: structural conditions → operations → opportunities
Generation:  constrained generator → blind validation → accepted items
Knowledge:   candidates → selection → frozen policy → application → Q-matrix
Evaluation:  structural simulation → KT / format transfer
```

Historical deterministic surface code and its fixtures/tests are archived and cannot be imported by active production code.

## Paper sections requiring revision

- Architecture/method diagram: replace the deterministic realisation stage with Measurement and swappable Dataset Generation.
- Dataset construction: make constrained LLM standalone the primary method and dialogue a format condition.
- Validation: distinguish blind grammatical reconstruction from quality diagnostics.
- KC method: state that selection uses development cells and structural opportunity space, never generated text.
- Simulation: describe opportunity-keyed latent difficulty/outcomes and ontology independence.
- Transfer experiments: frame standalone↔dialogue as paired surface formats over shared opportunities/KCs.
- Reproducibility and limitations: report unpinned model risk, evaluator dependence, CEFR diagnostic limitations, and the synthetic oracle claim boundary.
