# Automated ecological-precision dialogue pilot

## Evidence boundary

This four-family pilot contains automated generation and five independent
automated critic lenses. It is a structured stress test, not human learner,
teacher, expert, product, or response-process evidence. It does not establish
ecological validity, platform deployability, learner answerability, or justify
an extended dataset release on its own.

No scalar realism score or weighted ecology/precision composite was computed.

## Executed scale

- Generated families: 4
- Learner-facing opportunities: 20
- Independent family-by-role critic calls: 20
- Opportunity judgments: 100

## Generated viability by format

| Format | Candidate | Not viable |
|---|---:|---:|
| `constrained_cloze` | 4 | 0 |
| `sentence_transformation` | 4 | 0 |
| `contextual_production` | 4 | 0 |
| `dialogue_completion` | 4 | 0 |
| `open_dialogue` | 4 | 0 |

## Separate automated diagnostics by format

Counts below retain categories rather than converting them to a score.

| Format | Task comprehension | Interaction naturalness | Platform plausibility | Answer determinacy | KC attribution | Shortcut true/applicable |
|---|---|---|---|---|---|---:|
| `constrained_cloze` | pass:20 | minor_concern:3, pass:17 | pass:20 | bounded_multiple:3, determinate:17 | clear:17, partial:3 | 1/20 |
| `sentence_transformation` | minor_concern:1, pass:19 | minor_concern:7, pass:13 | minor_concern:2, pass:18 | bounded_multiple:16, determinate:4 | clear:10, partial:10 | 6/20 |
| `contextual_production` | minor_concern:1, pass:19 | minor_concern:10, pass:10 | minor_concern:3, pass:17 | bounded_multiple:19, determinate:1 | clear:5, partial:15 | 8/20 |
| `dialogue_completion` | pass:20 | minor_concern:4, pass:16 | minor_concern:4, pass:16 | bounded_multiple:19, materially_ambiguous:1 | clear:3, not_attributable:1, partial:15, weak:1 | 14/20 |
| `open_dialogue` | pass:20 | pass:20 | minor_concern:3, pass:17 | bounded_multiple:16, materially_ambiguous:3, not_applicable:1 | clear:4, partial:15, weak:1 | 13/20 |

## Role disagreement

Disagreement is retained at the exact opportunity level.

| Dimension | Opportunities with disagreement |
|---|---:|
| `task_comprehensibility` | 2 |
| `context_naturalness` | 9 |
| `interaction_naturalness` | 9 |
| `platform_plausibility` | 12 |
| `answer_determinacy` | 9 |
| `accepted_response_coverage` | 9 |
| `lexical_nuisance` | 2 |
| `kc_attribution` | 14 |

## Scale decision boundary

The generator marked 0 of four open-dialogue opportunities `not_viable`.
The measurement critic marked 0 open-dialogue opportunities `not_attributable`.
Regardless of these automated counts, the preregistered human/expert and
learner response-space gates remain outstanding. This pilot therefore remains
a bounded qualitative mechanism study and cannot authorize bank-scale dialogue
generation or a dataset release.

## Interpretation limits

- Four selected GrammarCells do not estimate bank- or platform-level rates.
- Model roles are prompts, not members of the named human populations.
- Category agreement does not validate the response process.
- A more natural interaction can still be a weaker measurement opportunity.
- Human review and actual learner responses are required before deployability
  or answerability claims.
