# Design boundaries

Each stage reads only paths declared by the orchestrator and immutable resources named in the experiment manifest. Generated files live only under `runs/<experiment_id>/`; module directories contain code and fixed configuration, never run output.

An EGP descriptor is source evidence, not a KC. A `GrammarCell` is canonical grammar identity, not automatically a KC. Realization conditions are separate from that identity. Only complete scalar mappings produce atomic canonical opportunities; partial mappings are retained but never expanded for yield. The KC policy is a declared input and cannot inspect items, simulations, or KT metrics. Item validation may reject an item but cannot revise upstream grammar or KCs. Q rows are mechanically rederived from the activation policy rather than manually labeled.

Observable and oracle simulation records are separate. KT receives observable records only. Synthetic mastery, profiles, transition parameters, and responses are simulator truth, not evidence about people or acquisition. KT scores are interface sanity checks, never ontology-selection objectives. Automated item diagnostics are not human validation, and no KC-count result is a claim about latent dimensionality.

