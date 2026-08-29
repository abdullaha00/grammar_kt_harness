# Declared qualitative sample: research-agent review

**Reviewer status:** Codex research-agent inspection. This is not human
validation, expert annotation, or a gold standard. The six candidates were
selected mechanically by the audit script to prioritise judgment disagreement
while retaining condition/cell diversity; they were not selected after reading
their content.

## Item-level inspection

1. `candidate_controlled_lexicon_CELL_EE9DDB26E6C7D307_02` (negative
   imperative): the intended grammar in “Don't open the door” is clear, but
   “Please don't …” and vocative variants are also plausible. The original
   determinacy rejection follows a literal exhaustive-answer-set reading;
   both repeat judges used the looser target-form reading. This is an
   operational-definition disagreement, not an obvious random error.

2. `candidate_controlled_lexicon_CELL_B6AF2E896B998C79_05` (past passive):
   the cue order encourages “The rooms were cleaned,” but neither the
   instruction nor cue explicitly requires passive, and adjectival/got-passive
   alternatives are plausible. Both repeat judges rejected determinacy while
   the original accepted. The rejection is defensible under the declared
   accepted-answer-set criterion.

3. `candidate_readable_source_evidence_CELL_0ACC7E0377B19DC1_02` (`would`):
   the visible cue gives “she / like / a glass of water” but never supplies or
   requests `would`. Original Terra and repeat Terra rejected; Sol accepted.
   The two rejecting judgments better identify the observable undercueing, but
   this agent assessment is not human adjudication.

4. `candidate_model_selected_CELL_0A7F3FA2D498D97D_03` (negative present
   perfect): “still unwashed” strongly supports the intended meaning, while
   contractions and `still`/`yet` variants are omitted from accepted answers.
   Original Terra and Sol rejected, while repeat Terra accepted. Again the
   divide is exhaustive surface responses versus a fixed target form.

5. `candidate_model_selected_CELL_C20140C7DAD62DB2_02` (negative past): the
   blank appears after the already displayed subject “Lena,” but the target and
   accepted answer repeat “Lena.” This answer-span mismatch is a concrete item
   defect. Both Terra judgments rejected (with different determinacy notes),
   while Sol accepted. A deterministic structural check could catch this class
   before model validation.

6. `candidate_model_selected_CELL_0D017AFB2B3A3DB5_03` (past perfect
   progressive): the duration and past reference time favour “had been
   painting,” but a past-progressive response remains arguable. Repeat Terra
   rejected determinacy; original Terra and Sol accepted. This is a borderline
   pedagogical-cue judgment, not evidence that one model is categorically
   superior.

## Cross-item finding

All six disagreements concern determinacy or closely related pedagogical
suitability. None raises a target-fidelity or grammaticality dispute. The
sample supports clarifying two distinct questions in future validation:

1. Does the prompt determine the intended grammatical contrast?
2. Does the accepted-answer representation cover harmless surface variants and
   exactly match the visible response slot?

Conflating those questions makes repeat judgments sensitive to how strictly a
model interprets “accepted response set.” This review does not establish which
strictness level learners or human annotators would prefer.

