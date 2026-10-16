# Restoring vision later

The original recovery experiment restores fresh images at two seconds. Its
results and the subsequent distance analysis suggest that vision affects motion
after the throw resolves. This exploratory extension asks whether restoring
images at three seconds still reduces drift, and what is lost by waiting.

We fixed this follow-up after seeing the earlier results. It is not a timing
search or an independent confirmation of the original experiment.

## Fixed design

For each of the same two saved policies, run all 64 existing held-out seeds
(9000–9063) with one added condition: stale images from 1.16 to 3.00 seconds,
then fresh images until the four-second trial ends. This adds 128 simulations.
All simulator settings, model weights, camera updates, native noise draws,
throw generation, and action history remain as in the original experiment.
No policy is retrained and no image history is reset.

The comparisons use the archived continuous-stale and two-second-restoration
conditions for the same seeds and policy. Before using those controls, verify
identical launch states, physical throws, and retained physical traces before
three seconds against continuous stale input. Check the actual camera ledger
against the declared onset and restoration times and recompute native outcomes
from the retained traces. Any mismatch invalidates the comparison and must be
resolved before interpreting its effect.

## Outcomes and reporting

Report all 64 seeds per condition. The principal exploratory contrast is
three-second minus two-second restoration for overall success (dodge, upright,
and pelvis within 1 m throughout four seconds). Also compare three-second
restoration with continuous stale input and report maximum and final station
radius without an area cutoff. Report dodges, area compliance, falls, and
aborted throws separately.

Use 10,000 paired-seed bootstrap resamples for mean differences, with a fixed
analysis seed. All intervals are nominal and pointwise. Report both policies
and both comparisons regardless of the outcome, without pooling them or
increasing the sample after seeing a result. Retain all raw recordings and
hashes. Reusing the original seeds does not create another independent
evaluation cohort.

A later restoration cannot undo an earlier area exit. Count exits already
recorded by three seconds separately from subsequent exits. This distinguishes
an irreversible scoring failure from motion that continues after restoration.
The experiment does not estimate an optimal recovery time or a neural cause.

## Reproduction

`data/later-recovery-manifest.json` identifies the 128 added recordings and two
configurations. The archived controls are identified by
`data/camera-recovery-manifest.json`. The raw packages remain outside Git,
alongside the other scientific archives.

```sh
uv run python scripts/analyze_later_recovery.py \
  --recovery-data /path/to/camera-recovery-data-v1.tar.gz \
  --later-data /path/to/later-recovery-data-v1.tar.gz \
  --output /path/to/new-output-directory
```

The command verifies every archive and record digest, control pairing and camera
schedule. It writes `summary.json`, all 384 new and reused condition records to
`trials.csv`, and a compact results table to `results.md`. The archived control
records are not counted as new simulations.

## Results

All 128 new trials completed. Every three-second condition matches its archived
continuous-stale control in launch state, resolved native throw, and physical
trace before restoration. Actual camera schedules match the protocol. The
following table keeps the 256 archived controls and 128 new trials distinct.

| Policy | Vision resumes | Recordings | Dodges | Overall success | Mean maximum radius | Mean final radius |
| --- | --- | --- | --- | --- | --- | --- |
| π₁ | Never | Archived | 64/64 | 32/64 | 1.043 m | 1.028 m |
| π₁ | 2 s | Archived | 64/64 | 61/64 | 0.860 m | 0.421 m |
| π₁ | 3 s | New | 64/64 | 47/64 | 0.965 m | 0.780 m |
| π₂ | Never | Archived | 54/64 | 53/64 | 0.692 m | 0.558 m |
| π₂ | 2 s | Archived | 54/64 | 51/64 | 0.703 m | 0.488 m |
| π₂ | 3 s | New | 54/64 | 53/64 | 0.691 m | 0.515 m |

No falls or aborted throws occur. For π₁, waiting until three
seconds reduces success by 14/64 relative to restoration at two seconds:
−21.9 percentage points (nominal paired 95% interval −32.8 to −12.5). It still
improves success by 15/64 relative to never restoring images: +23.4 points
(+14.1 to +34.4). Maximum excursion is 0.106 m larger than with two-second
restoration (interval +0.081 to +0.134 m), but 0.078 m smaller than with
continuous stale input (−0.097 to −0.060 m).

π₁ has eight area exits already recorded by three seconds
under both continuous stale input and three-second restoration. Subsequent
first exits decrease from 24 to nine when fresh images resume at three seconds.
Thus restoration can still change later motion, but cannot undo earlier exits.
These paired observations support an effect of restoration timing in this
cohort; they do not identify an optimal time or establish generality across
policies or independently sampled cohorts.

For π₂, three-second restoration has the same 53/64
overall successes as continuous stale input and two more than restoration at
two seconds. The latter difference has a nominal interval from 0 to +7.8 points.
All 64 success differences against continuous stale input are zero, so their
empirical bootstrap interval collapses to zero. This describes the observed
pairs; it does not prove population equivalence or an absence of possible
effects. Final radius still decreases on average relative to continuous stale
input, while maximum excursion barely changes.

## Illustrative replay

The recovery comparison video uses seed 9000, the first declared held-out seed,
for π₁. It shows continuous stale input, restoration at two
seconds, and restoration at three seconds with a shared camera view and clock.
All three reruns must exactly reproduce their archived launch state, throw,
physical trace and episode outcomes before they can be used as illustrations.
They do not add independent observations to the statistical analysis.

Use `scripts/render_videos.py --presentation` with those three arm names and a
trial directory containing their recorded JSON files and arm definitions from
the two recovery configurations. Keep seed 9000 first. The rendering command
and simulator requirements are described in [Reproducibility](REPRODUCIBILITY.md).

The presentation runs at half speed and pauses at native throw resolution,
restoration times, and the final horizon. Its depth label follows the capture
ledger. The teal circle marks the one-metre pelvis constraint and the orange
line shows the measured pelvis path. An orange ball marker retains the last
observed position for one second after removal; it is a display aid, not
continued ball physics. This one seed illustrates the outcome differences;
the 64-seed tables provide the aggregate evidence.
