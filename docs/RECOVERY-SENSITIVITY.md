# Recovery sensitivity

This post-hoc check asks how the camera-restoration result depends on the area
boundary and observation window. It reuses existing recordings; it adds no
simulation trials or independent confirmation.

Before running this analysis, we fixed all combinations of radii 0.5, 0.75, 1.0,
1.25, 1.5, and 2.0 m and windows 2.0, 2.5, 3.0, and 4.0 s. We report both saved
policies, both faults (stale and blank), and both cohorts (held-out recovery and
shared trajectories). Pilot and implementation-preflight trials are excluded.
The original primary comparison remains the one-metre, four-second result.

At each window, success requires the native throw to have resolved as a miss,
with no sampled fall or area exit from trial onset through that window. A later
miss cannot count as a successful dodge at an earlier window. Traces are sampled
at 20 ms; no interpolation is used. The 2.0 s window checks equality at restoration
onset, before its effect can accumulate. The analysis checks that the original
one-metre, four-second outcomes are reproduced exactly.

Each difference compares fresh images restored at 2.0 s against the same fault
continued, using all 64 paired seeds. Bootstrap intervals use 10,000 resamples of
paired seeds and a fixed analysis seed. They are pointwise nominal intervals;
they do not provide simultaneous coverage of the grid. We report every cell
rather than selecting the strongest effect. Cohorts are kept separate because
the shared-trajectory control reuses recorded physical throws.

Run from the repository root with the two immutable archives described in
[Reproducibility](REPRODUCIBILITY.md):

```sh
uv run python scripts/analyze_recovery_sensitivity.py \
  --recovery-data /path/to/camera-recovery-data-v1.tar.gz \
  --common-data /path/to/common-throw-data-v1.tar.gz \
  --output /path/to/new-output-directory
```

The command verifies archive and record hashes, writes every cell and its paired
interval to `summary.json`, and plots the complete stale-image grid. Blank-image
results remain in the JSON, including negative and zero differences.

## Results

All 192 cells completed. The 1,024 distinct fault-condition recordings reproduce
their original one-metre, four-second outcomes exactly. All restoration-onset
comparisons are equal, as expected.

The π₁ stale-image benefit is concentrated in late area exits near
the original boundary. At 1 m, the held-out benefit grows from 0/64 at 2.5 s to
6/64 at 3 s and 29/64 at 4 s. The shared-trajectory cohort shows gains of 3/64,
11/64, and 37/64 at those windows.

At four seconds, the stale-image results are:

| Cohort | Policy | Radius | Continuous success | Restored success |
| --- | --- | --- | --- | --- |
| Held-out | π₁ | 1.0 m | 32/64 | 61/64 |
| Held-out | π₁ | 1.25 m | 59/64 | 64/64 |
| Held-out | π₁ | 1.5 m | 62/64 | 64/64 |
| Held-out | π₁ | 2.0 m | 63/64 | 64/64 |
| Shared trajectories | π₁ | 1.0 m | 23/64 | 60/64 |
| Shared trajectories | π₁ | 1.25 m | 53/64 | 60/64 |
| Shared trajectories | π₁ | 1.5 m | 59/64 | 60/64 |
| Shared trajectories | π₁ | 2.0 m | 60/64 | 60/64 |

At 0.5 m, neither π₁ stale condition succeeds in either cohort:
restoration at two seconds cannot undo an earlier exit. π₂
has no consistent positive restoration effect across the grid. Blank-input
restoration differences are small and vary with policy and scoring choice.

The primary result therefore concerns the declared one-metre area constraint;
it should not be presented as a boundary-independent improvement. Short windows
also miss the late failures this experiment was designed to measure. These
observations describe the recordings and do not establish a neural mechanism.

## Motion without an area cutoff

The boundary check motivates a separate post-hoc question: does restoration
change physical excursion even when no success threshold is applied? Before
running this extension, we fixed two summaries for each complete four-second
trace: maximum and final horizontal pelvis distance from the fixed station
origin. Maximum radius measures the largest excursion; final radius describes
where the trial ends. Neither measures energy use or whole-body safety.

We retain all 64 paired seeds per policy, fault, and cohort, including hits and
area exits. We report paired mean and median differences, seed counts, and
10,000-resample paired bootstrap intervals for the mean difference. Negative
differences mean less excursion after restoration. These remain descriptive,
pointwise intervals on reused recordings. We do not pool cohorts or condition
on successful dodges. Full paired values are written to `motion-pairs.csv`;
the scatter plot shows all stale-input pairs with a line marking equal excursion.

### Distance results

Changes below are restored minus continuous input, in metres. Negative values
mean less excursion. Intervals are nominal paired intervals for the mean.
Maximum and final radius answer different questions; a lower final radius does
not undo an earlier area exit.

| Cohort | Policy | Fault | Mean maximum-radius change (95% interval) | Mean final-radius change |
| --- | --- | --- | --- | --- |
| Held-out | π₁ | Stale | -0.184 (-0.226, -0.146) | -0.608 |
| Held-out | π₁ | Blank | -0.020 (-0.026, -0.014) | -0.118 |
| Held-out | π₂ | Stale | +0.010 (+0.005, +0.018) | -0.070 |
| Held-out | π₂ | Blank | -0.001 (-0.006, +0.004) | -0.015 |
| Shared trajectories | π₁ | Stale | -0.179 (-0.216, -0.143) | -0.581 |
| Shared trajectories | π₁ | Blank | -0.023 (-0.032, -0.015) | -0.110 |
| Shared trajectories | π₂ | Stale | -0.002 (-0.019, +0.012) | -0.060 |
| Shared trajectories | π₂ | Blank | +0.001 (-0.004, +0.007) | -0.015 |

For stale input, π₁ has smaller maximum excursion in 63/64
seeds in each cohort, with one unchanged and none larger. Its final distance
decreases in 64/64 held-out pairs and 63/64 shared-trajectory pairs. Thus its
response is visible in continuous distances as well as the one-metre score.

π₂ shows a smaller final radius on average in both
cohorts but no comparable improvement in maximum radius. The observed lack of
improvement concerns overall success and maximum excursion; its final distance
can still improve. These results do not identify why the weights respond
differently.
