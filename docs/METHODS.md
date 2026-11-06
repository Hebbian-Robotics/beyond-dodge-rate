# Methods and interpretation

We evaluate a G1 humanoid in a deployment simulator with one throw at one second
and a four-second trial. We retain the original controller gains, active-ball
physics, depth noise, and fall definitions. The controller updates at 50 Hz;
depth images arrive at 25 Hz.

The simulator originally left collisions enabled on an inactive ball below the
floor. We disable its contact masks while inactive and restore their original
values at launch. The exact correction is implemented in
`scripts/correct_inactive_ball.py`. Twelve corrected replay checks found no
inactive-ball robot contacts or camera visibility. All reported results use the
corrected simulator.

## Success and camera conditions

Success requires avoiding ball contact, staying upright, and keeping the pelvis
within 1 m of its initial position throughout the trial. We also report the
components separately. A fall means pelvis height below 0.45 m or upright-axis
cosine below 0.4. Aborted throws remain failures in the all-trial denominator.
The area radius is an illustrative task requirement, not an official sport rule
or an injury threshold.

Healthy depth supplies new camera images. Stale depth repeats the last image
before a camera interruption; blank depth supplies zeros. We keep updating the
controller and its action history. We know when the injected fault starts;
there is no learned failure detector.

For each policy and seed, robot state and physical throw match exactly across
camera conditions. The policies move differently before launch, so the same
seed does not yield the same throw across policies. These are within-policy
comparisons of camera-input choices, not a policy leaderboard.

## Cohorts and uncertainty

The main comparison uses 192 seeds, 7300–7491, for each of two saved policies,
with healthy, stale and blank depth: 1,152 trials. Interruptions begin 160 ms
after launch and continue to the end. The seed set was fixed before outcomes
were observed, without outcome-dependent stopping or extension.

The other six cohorts total 1,344 trials and reuse seeds previously evaluated
before the simulator correction. They are exploratory reanalyses, even where
their historical configuration names contain “confirmation” or “replication.”
The timing sweep uses π₁ only. The 18-cell area/time analysis
re-scores the same 64 π₁ seed pairs and is post hoc.

Paired intervals use 10,000 resamples of whole test seeds and random seed
20261014. Camera conditions stay together in each resample. Intervals are
nominal for each contrast, without simultaneous coverage across all contrasts.
Individual-condition rates also include 95% Wilson intervals.

## Visual evidence and limits

Simulation examples use the first declared seed: 3000 for timing and 7300 for
the second-policy input comparison. Stills show a common state just before the
earliest contact and the final trial endpoint. Labels use measured contact
events and traces. Main-still distances are maximum distances over the trial;
video labels show instantaneous distance. The orange retained ball marker is a
display aid, not continued physics or a measured rebound.

Findings cover two saved policies, one model and throw distribution in
simulation. Both training configurations use seed 42. We do not establish
training-seed robustness, hardware safety, human interaction, or team play.
Being inside the area with the pelvis does not guarantee whole-body containment.
