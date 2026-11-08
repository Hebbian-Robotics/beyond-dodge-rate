# Reproducing the results

Read [current code, data and model availability](AVAILABILITY.md) first.
The four original trial archives are in the
[Hugging Face dataset](https://huggingface.co/datasets/hebbianrobotics/beyond-dodge-rate).
Download them into `data/` before running the commands below. The revised
manuscript also uses a separate stale-to-blank control whose recorded-trial
archive awaits public release. Its code, configurations, and reference results
are included in this repository, as described below.

```sh
uvx --from huggingface_hub hf download hebbianrobotics/beyond-dodge-rate \
  --repo-type dataset --include "*.tar.gz" --local-dir data
```

Each archive's SHA-256 is listed in its manifest under `data/`, and the analysis
commands verify it before reading any trial. Full paper builds additionally need
the pinned Tectonic typesetter described below.

## Recorded-data analysis

The prepared `evaluation-data.tar.gz` package contains all 2,496 corrected trial
records, eight configurations, 12 replay stills, a separate original-task
baseline report, and reference figures. Its SHA-256 and per-file hashes are in
[`data/manifest.json`](../data/manifest.json). It is excluded from Git to keep raw
experimental data separate from source code. With the archive at
`data/evaluation-data.tar.gz`, run:

```sh
uv sync --locked
uv run python scripts/analyze_original_study.py \
  --data data/evaluation-data.tar.gz \
  --output outputs/reproduced
```

The command verifies every input hash and scientific configuration, requires
complete paired trial coverage, recomputes outcomes from traces, generates the
analyses, and reproduces the four main figure PNGs exactly. The archive contains
data and measured images, not an executable environment or model checkpoint.
Python and plotting dependencies are locked in `uv.lock`.

The evaluated Tectonic typesetter has SHA-256
`2b3a86250906c92ed0a3ae8aaa454ec55bd6cede8593b3e549640177f6aecaa3`.
Typesetting can download TeX packages on first use. Numerical results are the
primary evidence across platforms with different installed fonts.

## Canonical paper and complete analysis

The separate `camera-recovery-data-v1.tar.gz` package contains
160 pilot trials and 640 fixed follow-up trials. The digest and all 804
file hashes are in `data/camera-recovery-manifest.json`. This package is in the
Hugging Face dataset. It contains records and
configurations, without simulator code or policy weights.

The separate `common-throw-data-v1.tar.gz` package retains all 640 exploratory
control trials and the 20 implementation-preflight trials. Its 664 file hashes
and archive digest are in `data/common-throw-manifest.json`. It is also in the
Hugging Face dataset.

The `later-recovery-data-v1.tar.gz` package adds 128 three-second-restoration
trials, using the same held-out seeds. Its 130 file hashes and archive digest
are in `data/later-recovery-manifest.json`. The earlier two-second and
continuous-stale conditions are reused controls, not new simulations.

The revision adds a separate 384-trial stale-to-blank control on reused recovery
seed IDs. Its archive and 388 file hashes are recorded in
`data/stale-to-blank-manifest.json`. These local trials are not pooled with the
original recovery estimate. The recorded archive awaits public release; when
obtained, place it at `data/stale-to-blank-data-v1.tar.gz`. Its manifest alone
does not supply the recordings. The analysis command below requires this
archive in addition to the four original datasets. Running fresh control
simulations is described under [stale-to-blank control](#stale-to-blank-control).

To verify all five datasets and prepare the paper sources (add `--tectonic
tectonic` to compile the PDFs):

```sh
uv run python scripts/reproduce.py \
  --data data/evaluation-data.tar.gz \
  --recovery-data data/camera-recovery-data-v1.tar.gz \
  --common-data data/common-throw-data-v1.tar.gz \
  --later-data data/later-recovery-data-v1.tar.gz \
  --switch-data data/stale-to-blank-data-v1.tar.gz \
  --output outputs/extended
```

The command verifies all five archives, recomputes the analyses and produces
one manuscript from `paper/main.tex`. With `--tectonic`, it writes a named
`outputs/extended/paper/paper.pdf` and an anonymous
`outputs/extended/paper/paper-anonymous.pdf`. Their scientific content and
figures are identical, with at most four main-content pages followed by references.
It also writes `outputs/extended/paper/supplement.pdf`, containing additional
methods, the full shared-throw table, and the demo description. The supplement
is submitted separately from the main paper.
Raw analyses and generated outputs remain outside source control; selected publication assets are copied into the site
only after verification. The stale-to-blank step also regenerates
`outputs/extended/stale-to-blank/switch-table.tex`, used in the supplement.

The data packages also retain exploratory timing and diagnostic analyses.
These are reported separately from the fixed recovery cohort. See
[methods](METHODS.md) for cohort definitions and
[the manuscript build](PAPER.md) for the PDF exports.

To generate only the recovery analyses and figure, use `scripts/build_recovery_report.py`
with `--data`, pointing at the recovery archive, and a fresh `--output` directory.
This checks the manifest, all declared cohorts and seeds, outcome flags, camera
schedules, matching throws, and physical equality before camera restoration.

To reproduce only the shared-trajectory control, run
`scripts/reproduce_common_throws.py` with `--data data/common-throw-data-v1.tar.gz`
and a fresh `--output` directory. It verifies every file hash and regenerates both
the 20-trial preflight and 640-trial control reports, keeping them separate.

## New simulations

New trials require the simulator source, populated G1 assets and verified ONNX
weights. Obtain them from the sources in [provenance](PROVENANCE.md), under their
respective terms. The π₂ actor and perception files come from
[hebbianrobotics/g1-depth-dodge](https://huggingface.co/hebbianrobotics/g1-depth-dodge);
its shared SONIC and Theia encoders come from the π₁ release.

Create an input archive from an already acquired source tree whose files match
`data/inputs/upstream-original.json`:

```sh
uv run python scripts/freeze_inputs.py \
  --source /path/to/g1-depth-dodge \
  --expected-manifest data/inputs/upstream-original.json \
  --output inputs/upstream-original.tar.gz
```

Use its printed SHA-256 to apply the inactive-ball correction:

```sh
uv run python scripts/correct_inactive_ball.py \
  --parent-archive inputs/upstream-original.tar.gz \
  --parent-sha256 SHA256_FROM_PREVIOUS_COMMAND \
  --output inputs/upstream-corrected
```

Then run a declared scientific configuration with the corrected archive and its
printed SHA-256:

```sh
uv run python scripts/evaluate.py \
  --input-archive inputs/upstream-corrected/input.tar.gz \
  --input-sha256 SHA256_OF_CORRECTED_ARCHIVE \
  --config configs/outage-v1.json \
  --output outputs/new-timing-trials
```

Every new output directory must be fresh. Configurations identify all seeds and
arms; evaluation never chooses a condition based on results. Physics, inference,
floating-point libraries and hardware must be qualified for a fresh replication.
New scientific results must not overwrite or be substituted into recorded data.

### Stale-to-blank control

`scripts/evaluate.py` implements the two-second stale-to-blank switch and
records hashes of the native and supplied depth frames. The configurations
`configs/stale-to-blank-upstream-v1.json` and
`configs/stale-to-blank-team-v1.json` declare all 64 seeds and three camera
conditions for each policy, giving 384 trials in total. Use separately frozen,
inactive-ball-corrected input archives with the corresponding policy weights.
The native source and weight files must match `data/inputs/upstream-corrected.json`
and `data/inputs/team-corrected.json`, respectively. Run from the repository root:

```sh
uv run python scripts/evaluate.py \
  --input-archive inputs/upstream-corrected/input.tar.gz \
  --input-sha256 SHA256_OF_UPSTREAM_CORRECTED_ARCHIVE \
  --config configs/stale-to-blank-upstream-v1.json \
  --output outputs/stale-to-blank/upstream
uv run python scripts/evaluate.py \
  --input-archive inputs/team-corrected/input.tar.gz \
  --input-sha256 SHA256_OF_TEAM_CORRECTED_ARCHIVE \
  --config configs/stale-to-blank-team-v1.json \
  --output outputs/stale-to-blank/team
uv run python scripts/analyze_stale_to_blank.py \
  --trials outputs/stale-to-blank \
  --recovery-data data/camera-recovery-data-v1.tar.gz \
  --output outputs/stale-to-blank-analysis
```

Replace the two SHA-256 placeholders with the digests of the corrected archives.
The analyser checks camera schedules, all 128 matched triplets, pre-switch
physical and supplied-frame histories, and outcome accounting. It writes
`summary.json`, `trials.csv`, and the supplementary `switch-table.tex`, using
10,000 paired bootstrap resamples. The archived reference results are retained
in `results/stale-to-blank-v1/`. Fresh simulation outputs may differ across
runtimes and must remain separate from those references.

## Figures and videos

`render_stills.py` and `render_videos.py` accept the same input archive, its
SHA-256 and a trial directory. They rerun selected first seeds and require exact
agreement with recorded state, throw, trace and episode evidence before rendering.
For the held-out handling example, pass
`--arms nominal outage_160_continuous zero_160_continuous`.
Use `--presentation` for half-speed videos with synchronized event holds and the
labeled retained-ball marker. Rendering needs a working MuJoCo/OpenGL backend.

All reported outcomes are simulation measurements. See [methods](METHODS.md) for
the exploratory versus held-out distinction and the study's limits.
