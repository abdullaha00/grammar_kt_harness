# ACL manuscript

`paper.tex` is the paper-facing account of the active grammar-KT dataset and KC
selection pipeline.  Quantitative claims are indexed in `evidence.md` and
`results_summary.md`; detailed experiment commands and artifacts remain in the
repository-level reports.  Its named ACL-style preprint shell, modular section
order, and artifact-map convention follow `report_versions/UROP/`.  The
archived UROP pilot claims are historical and are not copied into this full-v1
manuscript.

## Build

Run from this directory so that section, table, figure, and bibliography paths
resolve correctly:

```bash
cd ACL
latexmk -pdf -interaction=nonstopmode -halt-on-error paper.tex
```

Equivalent invocation from the repository root:

```bash
latexmk -cd -pdf -interaction=nonstopmode -halt-on-error ACL/paper.tex
```

To run the ACL bibliography-style regression suite:

```bash
cd ACL
python tests/regression/run_tests.py
```

The named preprint uses the unmodified ACL style files in this directory.
Generated `paper.aux`, `paper.bbl`, `paper.blg`, `paper.fdb_latexmk`,
`paper.fls`, `paper.log`, `paper.out`, and `paper.pdf` must be rebuilt after any
source or bibliography change.

## Source layout

- `sections/`: manuscript prose;
- `tables/`: main paper tables generated from retained evidence;
- `figures/`: paper-facing methodology figures;
- `paper.bib`: cited bibliography;
- `evidence.md`: claim-to-artifact ledger;
- `results_summary.md`: compact quantitative handoff.

The appendix contains detailed sensitivities and the artifact/RQ maps.  Human
validity, another-language evidence, or stability beyond the declared synthetic
worlds must not be inferred from executable completion.
