# Camera recovery experiment

This exploratory experiment follows a descriptive reanalysis of the existing
main comparison. All 122 area exits for the released model under stale images
occurred after native throw resolution; 121 followed a dodge. These observations
motivated the pilot and are not independent evidence for its hypothesis.

The question is whether restoring fresh camera images at two seconds reduces
late area exits. Two seconds is fixed for every trial, not selected separately
from its observed contact event. The experiment tests a response to renewed
visual information; it cannot establish why particular network weights differ.

## Conditions

Use both saved iteration-4000 policies and the same corrected deployment
simulator. Keep four-second trials and one native throw at one second. For each
policy, run all 16 new seeds, 8000–8015, in all five conditions:

- Healthy camera throughout.
- Stale camera input from 1.16 seconds through trial end.
- Stale camera input from 1.16 seconds, with fresh images restored at 2 seconds.
- Blank camera input from 1.16 seconds through trial end.
- Blank camera input from 1.16 seconds, with fresh images restored at 2 seconds.

These are 80 trials per policy and 160 total. Preserve the original gains,
weights, physical throw generator, camera noise and simulator correction.
Restoration resumes the native frame stream; it does not reset controller history.
Verify camera schedules and exact prelaunch states and throws across conditions
within each policy. Different policies can still face different throws.

## Outcomes and interpretation

The primary outcome remains dodging, staying upright and keeping the pelvis
within 1 m throughout the trial. Also report contacts, falls, area compliance,
maximum displacement, and the first sampled area exit relative to throw resolution.
Compare recovery against continuous failure within each input mode and policy.
Keep every condition and seed regardless of the result.

The pilot is exploratory, selected after inspecting existing outcomes. Its
16 seeds are for protocol development, not a claim of precise population
reliability or repeated-training robustness. Any later confirmation must use a
separately fixed cohort. Preserve the current workshop paper until the new
measurements have been verified and their scope described.

## Fixed held-out follow-up

After the complete pilot, fresh-image restoration changes released-model success
from 10/16 to 16/16 under stale input, with 16/16 dodges in both cases. Team-model
success stays at 11/16 for these two conditions. Under blank input, success is
15/16 with and without recovery for the released model, and 9/16 versus 8/16 for
the team model. All 160 trials are retained. Camera schedules, matching launch
states and throws, and the recorded physical traces before restoration passed
validation. These pilot results informed the following fixed cohort.

Run all 64 fresh seeds, 9000–9063, for each policy and all five conditions:
320 trials per policy and 640 total. Keep the pilot separate. Do not stop or
extend the cohort based on its outcomes. The primary comparison is stale-input
recovery versus continuous stale input for the released model. The team-model
comparison and blank-input comparisons are secondary. Retain the same four-second
horizon, 1 m bound, simulator, inputs, and camera schedule.

This batch gives a more precise estimate of the recovery effect at modest CPU
cost. It does not supply independent training repetitions, a learned fault
detector, matched physical throws across policies, or hardware validation.
Report all outcomes and paired-seed uncertainty; do not treat every secondary
nominal interval as a separately confirmed discovery.

## Recorded follow-up results

All 640 declared trials completed. Stale-input restoration changes released-model
success from 32/64 to 61/64, with 64/64 dodges in both conditions. The paired
difference is +45.3 percentage points (95% bootstrap interval +32.8 to +57.8):
29 seeds improve and none worsen. For π₂, success changes
from 53/64 to 51/64, with 54/64 dodges in both conditions. This secondary difference
is −3.1 points (nominal interval −7.8 to 0.0), from two worsened seeds.

| Policy | Camera condition | Dodged | Stayed within 1 m | Overall success |
| --- | --- | --- | --- | --- |
| π₁ | Healthy | 64/64 | 64/64 | 64/64 |
| π₁ | Stale | 64/64 | 32/64 | 32/64 |
| π₁ | Stale + recovery | 64/64 | 61/64 | 61/64 |
| π₁ | Blank | 60/64 | 57/64 | 54/64 |
| π₁ | Blank + recovery | 60/64 | 60/64 | 56/64 |
| π₂ | Healthy | 57/64 | 62/64 | 57/64 |
| π₂ | Stale | 54/64 | 61/64 | 53/64 |
| π₂ | Stale + recovery | 54/64 | 59/64 | 51/64 |
| π₂ | Blank | 36/64 | 63/64 | 36/64 |
| π₂ | Blank + recovery | 36/64 | 63/64 | 36/64 |

No falls or aborted throws occurred. Every stale-input throw had resolved by
two seconds, allowing floating-point timing tolerance. Restoration changes area
compliance after resolution in this comparison; it does not change the dodge
count. Native miss resolution is a simulator timeout, not an estimated instant
of closest approach to the robot.

All trial identities, native outcomes, trajectory-derived flags, camera schedules,
matching within-policy launch states and throws, and pre-restoration physical
trace equality are checked during report reproduction. See
[reproduction instructions](REPRODUCIBILITY.md). The independent sampling unit is
the seed within each policy, not a trajectory frame or an independent training run.
