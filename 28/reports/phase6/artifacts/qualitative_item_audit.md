# Phase-6 all-item qualitative audit

Date: 2026-08-27  
Scope: all 45 selected items and all 22 rejected, structurally valid candidates  
Status: independent agent review; **not** human, teacher, learner, or expert
validation

The reviewer inspected the visible prompt, complete target reference, slot-only
accepted answers, intended GrammarCell, and retained criterion judgments. The
audit asked about clause/slot reconstruction, target fidelity, determinacy,
naturalness, lexical/contextual simplicity, template repetition, and
consistency between acceptance and rejection decisions. It made no model calls
and did not change any artifact.

## Selected-bank classification

- **No material item-level concern (31):**
  `candidate_cell_001_01`, `candidate_cell_001_02`,
  `candidate_cell_002_03`, `candidate_cell_003_03`,
  `candidate_cell_004_01`, `candidate_cell_004_02`,
  `candidate_cell_005_03`, `candidate_cell_006_01`,
  `candidate_cell_007_01`, `candidate_cell_007_02`,
  `candidate_cell_008_01`, `candidate_cell_008_02`,
  `candidate_cell_009_01`, `candidate_cell_009_02`,
  `candidate_cell_010_01`, `candidate_cell_010_03`,
  `candidate_cell_013_02`, `candidate_cell_014_01`,
  `candidate_cell_014_03`, `candidate_cell_015_03`,
  `candidate_cell_016_01`, `candidate_cell_016_02`,
  `candidate_cell_017_07`, `candidate_cell_020_01`,
  `candidate_cell_020_03`, `candidate_cell_021_01`,
  `candidate_cell_021_03`, `candidate_cell_023_02`,
  `candidate_cell_023_03`, `candidate_cell_024_02`, and
  `candidate_cell_024_03`.
- **Usable but judgment-sensitive (9):** `candidate_cell_002_01` has a weak
  connection between its visit context and lexical cue;
  `candidate_cell_006_03` permits shorter negative imperatives;
  `candidate_cell_011_01` and `_011_03` do not uniquely force past
  progressive; `candidate_cell_012_01`, `_012_02`, and `_013_01` sit near the
  present-perfect/simple-past boundary; `candidate_cell_019_02` excludes
  optional time/agent variants; and `candidate_cell_022_05` remains near the
  past-perfect/simple-past-passive boundary.
- **Deterministic packaging/reference correction required (5):**
  `candidate_cell_003_01`, `_005_01`, `_018_01`, `_018_03`, and `_019_03`.
  Four accepted-answer sets repeat terminal punctuation already printed after
  the response slot; two complete-target references omit visible clause
  material. No learner-facing prompt or intended grammatical/semantic target
  needs to change.

No selected target was judged clearly ungrammatical or assigned to the wrong
GrammarCell. Representative strong items are `candidate_cell_001_01`,
`_013_02`, `_016_01`, `_020_03`, `_021_03`, and `_024_03`.

## Rejected candidates

Fifteen of 22 rejections were supported by contradiction, genuine ambiguity,
pronoun/slot mismatch, or weak elicitation. Seven decisions are plausibly
inconsistent or repairable: `candidate_cell_012_03`, `_013_03`, `_017_06`,
`_018_02`, `_019_01`, `_022_03`, and `_023_01`. The clearest judge error is
`candidate_cell_017_06`: its accepted answers contain only slot text, but the
judge appears to have inserted the complete `target_answer` into the slot and
inferred a spurious doubled subject. It remains rejected unless the separately
declared correction and independent revalidation change that result.

The one structurally invalid candidate, `candidate_cell_001_03`, failed because
of a missing legacy output field rather than its learner-facing language.

## Diversity and realism boundary

The final pre-correction bank has 45 distinct prompt strings and 235 prompt word
types over 816 tokens (TTR .288), but surface uniqueness overstates contextual
diversity. Twenty-seven prompts use “Complete the sentence,” 34 use some
“Complete…” formulation, and 20 explicitly mention a cue. “Mia” occurs in 13
prompts, “Maya” in eight, “paint” in seven, and “wash” in six. The two
`cell_018` variants repeat Maya, fence painting, the 8:00-to-noon interval, and
four hours. The material resembles focused worksheets more than naturally
varied communicative practice.

## Methodological implication

The five selected packaging defects motivate deterministic suffix-punctuation
checking, an explicit correction overlay that preserves raw model artifacts,
and independent revalidation of corrected records. Marked tense/aspect cells
also expose a realism/determinacy trade-off: naming the construction improves
answer uniqueness but produces a more metalinguistic exercise. These are
qualitative agent observations and cannot establish human acceptability,
pedagogical efficacy, or expert correctness.
