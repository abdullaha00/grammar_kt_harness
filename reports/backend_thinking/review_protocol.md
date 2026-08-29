# Backend-thinking audit: blind review protocol

Experiment: `BACKEND-THINKING-001`  
Frozen seed: `20260828`

This protocol supports an effort-setting audit; it is not human or expert gold
annotation. Reviewers are research agents with no conversation history. The
blinding is procedural rather than cryptographic.

## Evidence boundary

Review only the packet named in the assignment plus the explicitly listed
public declaration files. Do not inspect:

- `private_mappings/`;
- `cohorts/`;
- live `results/` or `evidence/`;
- earlier validation-reliability or curation reports;
- `scripts/run_backend_thinking_audit.py`;
- retained dataset judgments or mappings;
- another reviewer's file.

Do not decode or reverse-engineer review IDs. Do not use repository search.
Judge semantic content, not prose style.

## Validation and generation-item review

Allowed declarations:

- `modules/items/validation/criteria.yaml`;
- `modules/items/generation/formats/controlled_production.yaml`;
- `modules/grammar/canonical/schema.yaml`.

For every packet row, emit exactly:

```json
{
  "review_id": "...",
  "decision": "accept|reject|uncertain",
  "failed_criteria": ["declared_criterion_name"],
  "critical_error": false,
  "confidence": "high|medium|low",
  "rationale": "one concise sentence"
}
```

`accept` means every required criterion passes. Use `uncertain` when the row
cannot be judged confidently; do not force a binary label. Mark
`critical_error=true` for an unmistakable target-feature error,
ungrammatical target, answer leakage, materially non-determinate answer set,
or another defect that makes the item unsafe to retain. Treat cells as the
declared target, not as a suggestion.

## Normalisation-output review

Allowed declarations:

- `modules/grammar/canonical/schema.yaml`;
- `modules/grammar/resource/egp/normalisation/rulebook.md`.

Phase 1 may use only the descriptor fields in its packet and never examples.
Phase 2 may additionally use the shown examples and fixed Phase-1 mapping.
For every packet row, emit exactly:

```json
{
  "review_id": "...",
  "decision": "acceptable|incorrect|uncertain",
  "critical_error": false,
  "error_types": ["unsupported_specificity|branch_loss|wrong_feature|wrong_scope|unsafe_refinement|other"],
  "confidence": "high|medium|low",
  "rationale": "one concise sentence"
}
```

Ignore `contract_success` and `contract_error`; these are merged later as an
objective, separate gate. Ignore harmless `note` wording and cell/list order.
Judge whether the mapping preserves all supported alternatives without
inventing specificity. For Phase 2, require every branch to be represented and
only eligible dimensions to be narrowed.

## Adjudication and analysis

The two independent files are frozen before condition identities are joined.
Disagreements remain visible and are adjudicated without changing either raw
review. Retained medium-lineage labels are drift diagnostics only. Selection
uses clear blind labels, successful-call denominators, critical-error gates,
paired unit-clustered uncertainty, and the frozen five-point non-inferiority
margin. Uncertain cases receive best/worst-case sensitivity rather than a
forced label.
