# Building the manuscript

`paper/main.tex` contains the research text, results and figures. The named and
anonymous exports share this source and contain at most four main-content pages,
followed by references. The appendix is a separate supplementary PDF.

Run the complete analysis and paper build in
[Reproducibility](REPRODUCIBILITY.md). To rebuild the PDFs from an existing
verified analysis directory:

```sh
uv run python scripts/build_paper.py \
  --analysis-output /path/to/verified-analysis \
  --output /path/to/new-paper-directory \
  --tectonic tectonic
```

The builder checks all manuscript sources against the analysis record, verifies
data and template identities, and copies the generated inputs into the output
directory. It rejects unresolved references, overflowing text, and main papers
whose references begin after page five.

- `paper.pdf`: named main paper, including references.
- `paper-anonymous.pdf`: the same research without author identification or external links.
- `supplement.pdf`: additional methods, the full shared-throw table, and the demo description.

`paper/supplement-main.tex` combines `extended-methods.tex` and
`demo-appendix.tex`. Submit the main paper in the PDF field and the supplement
separately wherever supplementary material is accepted. The main paper is
self-contained; the supplement provides implementation detail and the demo link.

The repository includes the named PDF at `paper/paper.pdf` and supplement at
`paper/supplement.pdf`. Identical copies under `site/` support website downloads.
Intermediate TeX fragments and figures are generated in the analysis output
directory and are not maintained separately in the source tree.
