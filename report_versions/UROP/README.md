# Grammar--KT UROP report

This directory contains the current UROP report source and its compiled PDF.
The report describes the final executable methodology in the repository and
explicitly separates implemented software properties from research results
that still require a fresh, validated run.

## Build

From this directory, run:

```bash
latexmk -pdf -interaction=nonstopmode -halt-on-error acl_latex.tex
```

The output is `acl_latex.pdf`. Use `latexmk -c` to remove intermediate build
files while retaining the PDF.

## Structure

- `acl_latex.tex` is the main document.
- `sections/` contains one file per report section.
- `tables/` contains the declared domains, pilot design, ontology conditions,
  evidence boundary, and results contract.
- `figures/pipeline.tex` is the TikZ pipeline figure.
- `paper.bib` contains every cited source.

## Evidence boundary

The archived `runs/base` output predates the final fixed-bank,
ontology-independent simulation and development-only selection pipeline. It
does not pass the current run validator and is not used for quantitative claims
in this report. The exact remaining steps are recorded in Appendix B of the
PDF: restore the digest-matching consult-only EGP source, generate and validate
one fresh parent run, execute all six ontology conditions on the same bank and
event stream, complete the manual audit notebook, and populate the declared
results contract from the saved artifacts.
