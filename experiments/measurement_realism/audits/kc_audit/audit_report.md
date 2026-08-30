# Frozen full-v1 generator-KC methodology audit

Status: complete audit draft for the measurement-realism programme  
Audit target: `data/grammar_kt_full_v1/`  
Audit actor: Codex  
Mutation policy: the frozen dataset, declarations, shared reports, README, and ACL manuscript were not edited

## Evidence boundary

This report combines deterministic artifact calculations with explicitly
labelled **non-human Codex analysis**. The linguistic and pedagogical judgments
are hypotheses for expert/learner review, not human validation and not evidence
that any KC is a cognitive atom. No learner outcomes or private oracle
trajectories were read by the audit scripts.

The companion artifacts are:

- `structural_metrics.json`: hashes, K*/Q* geometry, support, nesting,
  campaign distributions, realisation contexts, and transparent prompt-regex
  diagnostics;
- `candidate_world_metrics.json`: deterministic projections for seven
  deliberately unselected structural worlds;
- `codex_judgment_ledger.jsonl`: one explicit, non-human review for each of the
  18 frozen KCs;
- `audit_kcs.py` and `audit_candidate_worlds.py`: reconstruction scripts.

Reconstruction:

```bash
python experiments/measurement_realism/audits/kc_audit/audit_kcs.py
python experiments/measurement_realism/audits/kc_audit/audit_candidate_worlds.py
```

## Bottom line

The 18-KC ontology remains a defensible **clean synthetic control world**. It
has unusually strong causal hygiene: it was declared before items and outcomes,
is projected mechanically, contains no outcome-selected interaction, and makes
its reference conditions and exclusions explicit. The full bank gives its Q
matrix 18/18 column rank and no equal activation columns. The perfect and
progressive decomposition is a sensible compositional hypothesis.

It is not yet a strong methodology for claiming plausible independently
learnable platform KCs. The construction evidence establishes that the columns
are reusable feature-linked factors and algebraically distinguishable. It does
not establish that each factor is a unitary competence, that practice transfers
over all cells sharing a column, or that the learner-facing items actually
diagnose that factor. The most accurate description is:

> **feature-linked latent factors with operation-motivated names**, declared as
> truth inside one synthetic world.

The extended programme should therefore preserve full-v1, retain this world as
R0, and compare conclusions across several plausible generator worlds rather
than silently promoting or replacing K*. A new dataset should use K* (or the
chosen world) during measurement-bank design so that educationally natural
anchor, crossing, and transfer items are designed intentionally.

## What the original methodology gets right

1. **Correct scientific ordering.** GrammarCells precede K*; K* precedes item
   calls and response generation. `construction.json` records that learner
   outcomes, items, discovered KCs, and KT results were not read.
2. **Executable definitions.** Every included KC has a fixed cell predicate;
   Q* is not retrospectively annotated from responses.
3. **Explicit synthetic status.** The rationale correctly disclaims human
   cognitive truth.
4. **Composition rather than a Cartesian KC copy.** Perfect-progressive
   activates shared perfect and progressive dependencies instead of being
   automatically treated as a wholly unrelated cell-specific skill.
5. **Reference conditions are not silently treated as learner states.** Active,
   positive, declarative, simple, modal-free, and tenseless values are declared
   background measurement conditions.
6. **No planted interaction by convenience.** The perfect-progressive-chain
   candidate was declared in advance and excluded on parsimony/nesting grounds,
   not because it harmed downstream prediction.
7. **Structural auditing is real and reproducible.** Support, row width,
   column equality, pair geometry, and rank are retained rather than merely
   asserted.

These strengths are worth preserving in every successor world.

## Quantitative structural audit

### Q geometry

The independent replay over the frozen files reproduces:

| Quantity | Result | What it establishes | What it does not establish |
|---|---:|---|---|
| Items × KCs | 113 × 18 | fixed measurement geometry | human validity |
| Q edges | 269 | explicit sparse activation | causal attribution of an error |
| Rank | 18 | linear column independence | psychological independence |
| Raw condition number | 7.677 | no exact near-singular failure at raw scale | equal information/support |
| Column-normalised condition number | 4.578 | moderate scaled algebraic conditioning | finite-sample recovery for every KC |
| Distinct item-cell Q rows | 75 | every canonical cell has a distinct K* signature | every KC has an anchor |
| One-KC items | 16/113 (14.2%) | some anchors exist | broad isolation |
| Multi-KC items | 97/113 (85.8%) | composition is exercised | failed-KC localisation |
| KCs with a one-KC item | 12/18 | twelve columns have at least one Q-isolating row | content-valid isolation |
| Crossed KC pairs (A-only, B-only, A+B) | 46/153 (30.1%) | useful joint contrasts | complete pair coverage |
| Disjoint KC pairs | 105/153 (68.6%) | columns differ | evidence about joint mastery or transfer |
| Nested KC pairs | 2/153 (1.3%) | a specific source limitation is visible | independence of the nested KC |

All 36 pairs among the nine modal-lemma KCs are disjoint by schema: one cell
cannot contain two central modals. This contributes easy algebraic separation,
but it supplies no A+B evidence about a shared modal competence or transfer
between, for example, MAY and MIGHT. Full rank is therefore genuinely useful
but scientifically weaker than “18 independently measured competencies.”

### Per-KC support

“Isolate” below means a row containing only that Q column. It is not a claim
that lexical, semantic, or response-format nuisance has been removed. “Prompt
cue” is a transparent regex diagnostic. For modals it detects the literal
modal lemma; for question KCs it detects task language such as *ask* or
*question*. A hit is not automatically invalid—constrained practice often
provides a form—but it clarifies what type of knowledge is being measured.

| KC | Cells | Items | Q-isolating items | Explicit prompt cue |
|---|---:|---:|---:|---:|
| perfect | 30 | 42 | 0 | 2/42 |
| progressive | 17 | 29 | 0 | 7/29 |
| BE-passive | 13 | 22 | 0 | 0/22 |
| finite past | 13 | 20 | 2 | 3/20 |
| finite present | 17 | 30 | 2 | 1/30 |
| imperative | 2 | 4 | 2 | 4/4 |
| CAN | 4 | 7 | 1 | 2/7 |
| COULD | 5 | 5 | 1 | 5/5 |
| MAY | 5 | 8 | 1 | 5/8 |
| MIGHT | 3 | 5 | 2 | 5/5 |
| MUST | 5 | 7 | 1 | 6/7 |
| SHALL | 4 | 4 | 1 | 4/4 |
| SHOULD | 4 | 4 | 1 | 1/4 |
| WILL | 9 | 14 | 1 | 6/14 |
| WOULD | 4 | 5 | 1 | 0/5 |
| negation | 32 | 49 | 0 | 24/49 |
| non-subject-WH | 1 | 2 | 0 | 2/2 |
| polar question | 8 | 12 | 0 | 12/12 |

Support is highly unequal: 2–49 items and 1–32 cells per KC. Seven KCs have
fewer than six items. Repeated surface items do not repair cell scarcity: the
non-subject-WH state has two items but only one cell; imperative has four items
over two cells.

### The WH nesting is substantively important

The only non-subject-WH cell is:

```text
present + simple + active + negative + non-subject-WH + no modal
```

Its two Q rows are therefore strictly nested in both `gkc_finite_present` and
`gkc_negation`. Both prompts are present-negative DO-support questions. The
bank contains no positive non-subject-WH, past WH, modal WH, BE/HAVE WH, or
WH-function variation sufficient to test transfer. This KC is full-rank only
because the parent columns also occur elsewhere; it is not independently
isolated or broadly reused.

The subject-WH declaration was excluded because no canonical cell supports it.
That is correct for v1, but it means the clause inventory does not cover the
contrast that would be especially informative for separating WH fronting from
operator inversion.

### Format and campaign structure

All 113 records carry `format: controlled_production`, so no frozen KC is
formally a format-specific column. The surface tasks are not actually uniform.
The explicit heuristic finds:

| Surface interaction heuristic | Items |
|---|---:|
| completion/cloze-like | 85 |
| question formation | 13 |
| explicit-metalinguistic production | 11 |
| bounded chunk reordering | 4 |

All four imperative items come from the special bounded-cue campaign, and all
four use chunk reordering. The positive pair has the same target—“Close the
window”—and the negative pair only varies *hot pan* versus *wet paint*. Thus
the imperative latent state is completely confounded with a distinctive
campaign/interface style in v1, even though the coarse `format` field does not
show that. This is a measurement confound, not a reason to alter the frozen
world.

The nine explicit-construction intervention items also concentrate on
determination-sensitive complex forms, especially progressive/WILL chains.
Campaign/style and KC complexity can consequently be absorbed by KC state in
any model lacking item or format effects.

## The central methodology gap: cells generated the items, not KCs

The original pipeline deliberately required the K* artifact to exist before
item generation but then did not open or pass its contents. The code states:

```text
Generate the fixed N=3 candidates after, but without reading, K*.
```

This is excellent protection against outcome leakage and post-hoc ontology
tuning. It also means that generation optimized an exact GrammarCell, not a
measurement claim such as:

```text
this item isolates KC A;
this pair holds form fixed and contrasts A/B;
this item tests transfer of A across contexts;
this format measures A without supplying its answer form.
```

Q* is applied only after item curation. Accordingly, an item can be
linguistically faithful to its cell while being weak evidence for the named KC.
The successor methodology should retain the frozen ordering but pass the
already-frozen active KCs and a measurement objective into bank design. This is
not outcome leakage: it is instrument construction.

## Wording is not executable semantics

The Q matrix sees activation predicates, not KC names or rationales. Any two
descriptions attached to the same predicate are activation-equivalent. For
example, all of these would produce exactly the same MAY column:

- “select MAY for its intended meaning”;
- “produce the token *may*”;
- “construct MAY plus a base-form complement”;
- “master the item family whose GrammarCell says `modal=may`.”

The present bank cannot determine which interpretation generated a learner's
success. This matters because the current descriptions sometimes promise more
specific operations than their predicates encode.

### Definition/activation mismatches

1. `gkc_finite_present` names agreement conditions, but GrammarCell omits
   subject person/number. Its 17 cells span 7 perfect-HAVE, 6 BE, 3 DO-support,
   and 1 lexical-main-verb realisation context. The two isolating items are both
   regular third-person singular lexical *-s* forms.
2. `gkc_finite_past` spans 6 perfect-HAVE, 5 BE, 1 DO-support, and 1 lexical
   main-verb context. The two isolating items use regular lexical past. One
   latent value therefore claims transfer over *had*, *was/were*, *did*, and
   lexical regular/irregular morphology without measuring those subskills.
3. `gkc_negation` says “inserting DO when needed,” but its predicate is simply
   `polarity=negative`. Its 32 cells cover DO-support, BE, perfect HAVE, and
   each of the nine central modal operators. DO-support is only one subtype.
4. `gkc_polar_question` says finite-operator inversion; simple lexical-verb
   questions additionally require DO-support. Its eight cells cover DO,
   perfect HAVE, and six modal operators.
5. `gkc_non_subject_wh_question` combines WH fronting and inversion as one
   state. By contrast, `modules/grammar/canonical/english_operations.yaml`
   explicitly recognizes shared `operator_inversion` across polar and
   non-subject-WH questions plus a separate `wh_fronting` operation.
6. `gkc_be_passive` combines argument realisation, auxiliary BE, and lexical
   past-participle formation, but lexical transitivity and participle
   regularity are not in GrammarCell.

None of these choices is invalid in a synthetic world. The problem is calling
the column a narrow operation while simulating uniform transfer over a broader
bundle. Successor declarations should state whether a KC is a **construction
family**, **semantic choice**, **morphological operation**, or **item-family
factor**, and Q should only claim the scope its item metadata can support.

## KC-by-KC pedagogical and measurement audit

The following are non-human Codex judgments. Full rationales and requested
discriminating evidence are in `codex_judgment_ledger.jsonl`.

### Aspect and voice

- **Perfect:** a credible reusable practice target, and the compositional link
  to perfect-progressive is a strength. A single state nevertheless combines
  aspectual choice, HAVE, participial dependencies, lexical participles, and
  chain ordering. It has broad support but zero one-KC items.
- **Progressive:** similarly credible as a reusable family. The current state
  combines progressive meaning, BE, *-ing*, and longer-chain ordering over
  modal/nonmodal/passive contexts. It has zero one-KC items.
- **BE-passive:** a conventional pedagogical target, but not a single obvious
  cognitive operation. Argument mapping, auxiliary choice, passivisability,
  and participle production can dissociate. All 22 items require at least one
  other KC.

### Finite form

- **Finite past:** independently improvable in a broad sense, but the one-state
  transfer assumption over lexical inflection, HAVE, BE, and DO is strong. The
  only anchors are regular lexical past completions.
- **Finite present:** likewise plausible at family level but bundles tense,
  agreement, lexical/auxiliary allomorphy, and DO-support. Person/number is
  absent, and its anchors only exercise third-person singular lexical *-s*.

### Clause and polarity

- **Imperative:** an educationally meaningful target whose v1 measurement is
  weak. It has two cells, four campaign-specific reorder prompts, and extremely
  narrow lexical/target diversity. “Learns from any imperative opportunity” is
  plausible only as a synthetic stipulation.
- **Negation:** highly reusable, but its one-state model is strongly composite.
  No row isolates it; it crosses twelve coarse operator contexts, and roughly
  half the prompts explicitly supply negative/not information.
- **Polar question:** plausible as a construction family, with good operator
  variety, but no one-KC item. It has no shared inversion state with WH
  questions, so the world forbids a natural transfer route by construction.
- **Non-subject-WH:** linguistically plausible but structurally and
  pedagogically under-supported. The one cell/two prompts cannot justify
  general transfer across WH types or operators.

### Modal lemmas

Treating each central modal lemma as a separate state is a useful flat control:
learners can plausibly differ in familiarity with CAN, MAY, SHALL, etc. The
method goes further, however: it gives each lemma independent Beta mastery and
independent learning while providing no shared modal-complement competence and
no semantic-function labels. That assumption is not supported by the bank.

- **CAN:** mixes ability and negative retrospective inference/perfect uses;
  its simple ability anchor does not establish transfer across them.
- **COULD:** pools ability, impossibility, permission, and perfect/counterfactual
  uses. Every prompt literally supplies COULD; three of five items are
  rescue/intervention items.
- **MAY:** pools permission and epistemic possibility across simple, perfect,
  passive, and negative contexts; five of eight prompts supply MAY.
- **MIGHT:** the sampled items are relatively coherent around epistemic
  possibility, but all five supply MIGHT and the two anchors are parallel rain
  completions.
- **MUST:** pools obligation, prohibition, and epistemic deduction; six of
  seven prompts supply MUST.
- **SHALL:** one item each represents an offer, a formal rule, a polar offer,
  and progressive futurity. All four supply SHALL; register/function
  heterogeneity makes unitary mastery especially uncertain.
- **SHOULD:** pools advice, retrospective regret, negated regret, and a
  progressive expectation/obligation context, with one item per cell.
- **WILL:** has the strongest modal support but still only one anchor. It spans
  simple, question, progressive, perfect, and perfect-progressive uses; four
  items required explicit-construction intervention.
- **WOULD:** pools polite willingness/request, counterfactual perfect, and
  reported speech. Those uses can plausibly dissociate even though they share
  the lemma.

The likely alternative is not “merge all modals.” A pedagogically stronger
hypothesis would separate shared modal form mechanics from function-specific
knowledge (ability, permission, epistemic possibility, obligation/advice,
counterfactuality, futurity/volition) and then permit lemma-specific residuals
where justified. Current GrammarCell cannot project that world because it
stores modal identity, not modal function.

## Reference-condition assumptions

Excluding active, positive, declarative, simple, modal-free, and tenseless
conditions is parsimonious and avoids a full dummy-coded ontology. It also
means that all difficulty associated with ordinary word order, lexical access,
argument structure, or the response mechanism is treated as mastered
background or generic noise. A simple present declarative item has only the
present KC, for example, even though a real learner must understand the
instruction, retrieve the verb, preserve arguments, spell it, and produce a
well-formed clause.

This asymmetry is acceptable in R0 if stated as a marked-operation world. It
should not be interpreted as evidence that reference values require no
knowledge. A plausible measurement extension needs item/format/lexical nuisance
variables rather than turning every reference condition into another KC.

## Interaction audit

No formal interaction KC is included in v1. This is a strength for a simple
control, but the interaction search was narrow: only the
perfect-progressive-chain was explicitly optional. Other plausible
realisation interactions include:

- simple lexical clause × negation → DO-support;
- simple lexical clause × polar/non-subject-WH → DO-support;
- polar/non-subject-WH → shared operator inversion;
- perfect × progressive → fixed HAVE–BE chain;
- aspect × passive → longer auxiliary/participle chain;
- modal × aspect → modal plus nonfinite auxiliary chain.

These should not all become KCs. They are candidates for controlled worlds,
especially where structured learner errors can distinguish which operation
failed. The current full-rank result does not prove their absence.

## Alternative plausible generator worlds

The deterministic alternative script illustrates that multiple coherent
worlds fit the same 75 cells and 113 items:

| World | KCs | Rank | Distinct rows | Purpose |
|---|---:|---:|---:|---|
| frozen v1 | 18 | 18 | 75 | clean flat reference |
| clause-compositional | 18 | 18 | 75 | shared inversion + separate WH fronting |
| v1 + perfect-progressive chain | 19 | 19 | 75 | interaction-rich sensitivity |
| v1 + DO-support | 19 | 19 | 75 | realisation-operation sensitivity |
| shared central-modal only | 10 | 10 | 43 | coarse modal transfer control |
| shared modal parent + nine lemma children | 19 | 18 | 75 | hierarchical transfer hypothesis |
| non-reference feature values | 19 | 19 | 75 | atomic feature control |

These structural calculations do not select a world. They demonstrate four
important points.

1. **Full rank does not select linguistic factorisation.** Both the frozen and
   clause-compositional worlds are 18/18 rank with 75 distinct rows.
2. **An interaction can be nested yet linearly estimable.** The chain and
   DO-support augmented worlds are 19/19 rank because their parent operations
   also occur without them. Inclusion remains a substantive, not algebraic,
   choice.
3. **Merging modal lemmas changes what cells are distinguishable.** The shared
   modal-only world reduces distinct rows to 43, deliberately treating lemma
   identity as measurement content rather than learner state.
4. **A meaningful hierarchy can fail the flat full-rank gate by design.** A
   shared modal parent is the sum/union of mutually exclusive lemma children,
   so the parent-plus-children world has rank 18 for 19 columns. Requiring every
   ontology to be a flat full-rank Q therefore rules out some pedagogically
   plausible hierarchical/prerequisite representations rather than proving
   them false.

Three especially relevant worlds cannot honestly be projected from the current
GrammarCell:

- **modal function + shared form**, because ability/permission/epistemic/etc.
  are not retained;
- **lexical morphology/argument structure**, because lemma, regularity,
  transitivity, and person/number are absent;
- **prerequisite/transfer hierarchy**, because flat binary Q does not encode
  transfer strengths.

Those worlds require enriched item/measurement metadata, not unsupported
Cartesian filling of GrammarCells.

## Recommended successor methodology

### 1. Keep two ledgers

For every proposed KC, separately record:

- **activation semantics:** exactly which cells/items activate it;
- **competence semantics:** what learner capability is asserted to transfer;
- **measurement manifestation:** what observable success/error would provide
  evidence for it;
- **learning interpretation:** why practice on one active item should improve
  another;
- **nuisance boundary:** lexical, semantic, format, and item burdens excluded
  from the KC.

A name or rationale should never be treated as evidence that activation has
measured the competence semantics.

### 2. Use explicit hard gates, not one ontology score

Candidate KCs should be audited for:

- linguistic coherence;
- plausible independent mastery;
- pedagogical relevance;
- reuse and proposed transfer domain;
- item/cell support;
- Q distinguishability under the intended flat model;
- availability of diagnostic errors or matched contrasts;
- susceptibility to format, campaign, lexical, and item-difficulty confounds;
- parsimony.

Full rank should remain a hard gate only for a **flat independent-state world**.
Hierarchical worlds need a different identifiability statement.

### 3. Generate candidates independently, then canonicalise structurally

If model-assisted induction is used, freeze multiple independent proposals,
prompts, inputs, raw outputs, and settings. Canonicalise both wording and
activation. Two differently named proposals with the same cell/item activation
must be logged as activation-equivalent, not counted as independently recovered
KCs. Subjective pedagogical judgments need explicit rubrics and independent
critics or expert review.

### 4. Let the frozen KC world inform measurement design

After a candidate world is frozen, use it to request:

- Q-isolating anchors where linguistically natural;
- A-only/B-only/A+B contrasts;
- matched items crossing the same KC over formats;
- matched items crossing different KCs within one format;
- semantic-choice items that do not literally provide the target modal/form;
- form-production items that deliberately provide meaning/content;
- error-diagnostic items for DO-support, auxiliary order, agreement, negation,
  participles, and inversion.

This is instrument design, not response-selected ontology tuning.

### 5. Retain multiple generator worlds

At minimum, future robustness work should compare:

- R0 frozen operation hybrid;
- a feature-value world;
- a clause/mechanics-factorised world;
- a modal-function/shared-form world after metadata are available;
- one modest interaction-rich or hierarchical world.

The scientifically useful claim is then whether misspecification,
identifiability, format-confounding, and error-aware conclusions persist across
plausible latent structures—not that one world is human truth.

### 6. Validate transfer claims externally

An expert review sample should ask, for matched item pairs:

> Would improvement on item A plausibly transfer to item B for the reason named
> by this KC, after controlling format and vocabulary?

Learner pilot evidence could later test within-KC transfer, between-KC
dissociation, and error consistency. Until then, use “declared generator KC”
and “plausible synthetic scenario,” never “validated learner competence.”

## Risks to paper interpretation

1. A result where K* wins in its own generated world demonstrates sensitivity
   to declared misspecification, not that the 18 KCs are pedagogically correct.
2. Predictive recovery of a Q column cannot recover the intended meaning of its
   label when multiple competence stories share that activation.
3. Modal lemma splits can absorb item/campaign/semantic difficulty just as
   later split-KC experiments absorb item difficulty.
4. The current bank's all-`controlled_production` metadata should not be used
   to claim a controlled format effect; surface interactions differ.
5. The absence of format, lexical, and item effects makes equal transfer within
   a KC true by construction.
6. Full rank is a property of the item-cell projection, not a validity argument
   for human KCs.

A minor documentation issue should also be corrected when shared reports are
next revised: `reports/full_dataset_investigation.md` says K* contains “four
clause operations,” while the frozen inventory contains three included clause
KCs (imperative, polar question, non-subject-WH); subject-WH was excluded for
zero cell support. The ACL methods section lists the three correctly.

## Decision for the measurement-realism programme

Do not modify full-v1. Treat its K* as an intentionally flat, marked-operation
R0 generator world. It is suitable for preserving all completed controlled
experiments.

Before freezing any measurement-realism dataset:

1. adopt explicit competence/activation/measurement ledgers;
2. compare at least the clause-compositional and modal-function alternatives;
3. enrich item metadata only where a plausible world requires information that
   GrammarCell intentionally omits;
4. construct matched anchor/crossing items with K* visible to the measurement
   designer;
5. plant and model item/format nuisance separately from KC mastery;
6. test conclusions across worlds rather than selecting human truth from
   synthetic responses;
7. obtain expert/learner validation before any deployability or human-transfer
   claim.

This preserves v1's internal validity while directly addressing the revised
programme's central question: whether the observable opportunities provide
plausible evidence about a competence a learner could actually improve through
practice.
