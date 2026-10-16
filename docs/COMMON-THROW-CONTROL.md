# Common-throw control

The original simulator aims using the robot's pose and velocity at launch.
Two policies can therefore face different physical throws even with the same
random seed. The original paper compares camera conditions within each policy
and does not rank the policies overall.

This exploratory control asks whether the different blank-versus-stale responses
persist when both fixed policies face the same ball trajectories in world
coordinates. It does not control their different learned weights or prelaunch
motion, and is not a study of independent training seeds.

## Fixed design

Use 64 new simulation seeds, 10000–10063, with the same five camera conditions
as the recovery experiment. Use both saved policies, for 640 total trials.
Each throw is a healthy-condition trajectory already recorded in the recovery
follow-up. For index 0–63, use donor seed 9000 plus the index, alternating released
and team policies by index parity. This includes 32 donors from each policy and
uses no outcome filter. New simulation seeds affect the native noise stream;
these are reused throw trajectories, not 64 newly sampled physical throws.

Each configuration embeds the exact launch position, velocity, flight parameter,
target label, and donor identity. At one second, call the native launch function
to retain its collision setup, accounting, and random-number consumption. Before
any integration, replace only the ball's launch position and velocity with the
recorded values. Keep the original camera, weights, gains, active-ball physics,
resolution rules, 1 m radius, and four-second horizon. Recovery remains fixed at
two seconds and never resets policy history.

The target label describes the donor's original aim. It does not mean that the
replayed ball is aimed at the same body part of the receiving policy. Different
robot states at launch remain a limitation of the comparison.

Run a separate two-seed implementation preflight (9998–9999) on both policies,
using donor seeds 9000–9001. Keep those 20 trials separate from the control.
The preflight verifies the injected launch state and evidence checks, rather
than selecting the experiment according to policy performance.

## Analysis

Keep every seed and condition. Verify exact physical throw equality across
all ten policy-condition combinations for each control seed. Continue verifying
matching robot states across conditions within a policy, and physical equality
before restoration in recovery pairs.

The main contrasts are blank minus stale success within each policy. Report the
paired difference between these effects across policies, resampling common-throw
seeds together. Recovery contrasts and donor-policy strata are secondary.
Report dodges, falls, area compliance and joint success separately, with nominal
paired intervals. Do not pool this exploratory cohort into the earlier held-out
estimate or treat unchanged point estimates as proof of policy equivalence.

## Recorded outcomes

All 640 trials completed and passed the shared-trajectory audit. Each row has
64 seeds. No falls or aborted throws occurred.

| Policy | Input | Dodged | In area | Overall success |
| --- | --- | --- | --- | --- |
| π₁ | Healthy | 61/64 | 64/64 | 61/64 |
| π₁ | Stale | 60/64 | 27/64 | 23/64 |
| π₁ | Stale + recovery | 60/64 | 64/64 | 60/64 |
| π₁ | Blank | 57/64 | 60/64 | 53/64 |
| π₁ | Blank + recovery | 57/64 | 62/64 | 55/64 |
| π₂ | Healthy | 51/64 | 60/64 | 47/64 |
| π₂ | Stale | 52/64 | 58/64 | 46/64 |
| π₂ | Stale + recovery | 52/64 | 57/64 | 45/64 |
| π₂ | Blank | 41/64 | 62/64 | 39/64 |
| π₂ | Blank + recovery | 41/64 | 61/64 | 38/64 |

Blank minus stale success is +46.9 percentage points for π₁
(nominal 95% paired interval +31.2 to +62.5) and −10.9 for π₂
(−21.9 to 0.0). The π₂ point estimate is negative, but this cohort alone
does not establish harm. The paired difference between these input effects is
+57.8 points (+40.6 to +75.0), resampling the shared seeds with both policies
and all conditions together.

Fresh-image restoration changes π₁ success from 23/64 to 60/64
under stale input, with 60/64 dodges in both cases. π₂ changes from
46/64 to 45/64, with 52/64 dodges in both cases. The input-effect difference and
π₁ recovery benefit therefore persist with identical ball trajectories;
prelaunch robot states and training histories remain different.

Two additional readbacks of the first declared control seed reproduce the full
healthy trial exactly and confirm the actual ball position and velocity before
integration. These checks and the 20-trial preflight are implementation validation,
not additional independent evidence for the camera-input effect.
