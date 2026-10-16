# Contributing

## Development checks

Install the locked Python and documentation dependencies:

```sh
uv sync --locked
pnpm install --frozen-lockfile
```

Before committing changes, run:

```sh
uv run ruff check --fix scripts
uv run ruff format scripts
uv run ty check scripts
pnpm check
uv run python scripts/check_publication.py
```

Keep raw data, weights, and simulator inputs outside Git. Follow the
[reproduction instructions](docs/REPRODUCIBILITY.md) when checking analysis
changes. Preserve all declared seeds, paired conditions, and failed outcomes.
Keep the distinction between exploratory cohorts and held-out tests explicit.

## Paper and website

The manuscript source is `paper/main.tex`. The website lives in `site/` and uses
relative asset URLs. Changes to numerical claims must agree with the recorded
trial evidence and generated analyses. Update `results/publication-files.json`
when reviewed paper, demo, or website files change.

Keep the Nerfies template section order: teaser, Abstract, Video, two examples,
detailed results, Related Links, and BibTeX. Change topic-specific headings to
match the study. Preserve the upstream `site/static/css/index.css`; put necessary
media or accessibility additions in `site/static/css/project.css`.

The manual Pages workflow checks the site before deployment. Deployment requires
a public repository and the workflow's `publish` input. While the repository is
private, the workflow cannot publish a public site.

Changes to the code license do not change the licenses of external software,
model weights, or robot assets. Retain source attribution and relevant notices.
