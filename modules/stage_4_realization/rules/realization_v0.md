# Deterministic realization rules v0

## Cue precedence and chain

Build the underlying verb chain in this order:

`[MODAL] [perfect HAVE] [progressive BE] [passive BE] MAIN`

The first chain member is finite unless preceded by a modal. A modal is finite
but uninflected and forces the next member to its base form. Perfect HAVE takes
a past participle; progressive BE takes an `-ing` form; passive BE takes the
main past participle. Thus perfect passive uses `HAVE + been + participle`, and
progressive passive uses `BE + being + participle`.

With no modal, finite present/past morphology is realized on the first
auxiliary, or on the main verb when the chain has no auxiliary. Agreement is
third-person-singular present versus all other present subjects. Past BE also
distinguishes singular first/third person from other subjects.

## Operators and polarity

The first auxiliary or modal is the operator. Simple active lexical predicates
have no inherent operator. For their negative declaratives and polar/non-subject
WH questions, insert finite DO and leave the main verb in base form. Main
copular BE is its own operator and never takes DO.

Place uncontracted `not` immediately after the operator. A positive declarative
has no added operator. Contractions are outside v0.

## Clause order

- declarative: SUBJECT + CHAIN;
- polar question: OPERATOR + SUBJECT + REST;
- subject WH: WH-PHRASE + CHAIN, without inversion or DO solely for clause type;
- non-subject WH: WH-PHRASE + polar-question order;
- imperative: no ordinary subject and no tense morphology.

For object WH, omit the lexical object. For adjunct WH, retain ordinary
arguments. WH inputs are conditional requirements even though the frozen exact
mini-inventory contains no source-backed exact WH cells.

## Imperatives

- ordinary: base-form chain;
- emphatic DO: `do` + base-form chain;
- LET'S: `let's` + base-form chain;
- LET'S NOT: `let's not` + base-form chain;
- LET + pronoun: `let` + pronoun + base-form chain.

An ordinary negative imperative is `do not` + base-form chain. The subtype is
selected from source-edge realization provenance; it is never inferred as a
new GrammarCell distinction.

## Compatibility

Passive realization requires `passive_compatible=true` and an overt object in
the lexical frame. Copular frames cannot be passive. A subject-WH spec requires
WH role `subject`; a non-subject-WH spec requires `object` or `adjunct`.

