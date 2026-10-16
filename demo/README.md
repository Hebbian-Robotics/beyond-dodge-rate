# Demo: Beyond Dodge Rate

Camera Failures in Simulated Humanoid Dodgeball

Kingston Kuan and Brandon Ong · Hebbian Robotics

The demo shows why avoiding a ball is only one part of a successful dodge.
Viewers compare synchronized simulation replays, pause at measured contact
events, and check whether the robot stays inside a 1 m area.

## What viewers see

The 77-second video opens with the three parts of success: avoiding contact,
staying upright, and remaining within the 1 m area. A short key defines π₁ as
Martino Russi's released weights and π₂ as the weights trained separately by
Hebbian Robotics. They use the same PPO method, architecture, objective, and
recorded settings. Their learned weights differ; the cause of their different
responses to camera failures is unresolved.

Three synchronized comparisons show camera-freeze timing (π₁, seed 3000),
restoration of fresh images (π₁, seed 9000), and stale versus blank depth
(π₂, seed 7300). The recordings retain their event pauses, ball markers, simulation
timestamps, and measured pelvis distances. Large outcome labels appear during
the final two seconds of each replay. The three-second restoration example is
explicitly labeled exploratory.

Two result tables distinguish these individual replays from aggregate evidence.
The first reports the fixed recovery cohort with 64 test seeds per condition;
the second reports stale versus blank images with 192 seeds per condition.
Both include paired 95% intervals. Neither table ranks the two policies.

Blank input improves area compliance for both models. Our separately trained
model loses enough dodges to outweigh that improvement; π₁ does
not. This describes the observed trade-off, not its cause inside the networks.

The videos replay recorded simulations. The site supports pause, seeking,
fullscreen viewing, and separate condition clips. It does not run a policy live
or control a physical robot.

## Equipment

One laptop with a browser is sufficient. A power outlet and optional external
display are useful. YouTube playback requires internet access. Locally generated
video files play offline; no GPU, robot, or special floor area is required. The
presenters bring the laptop.

## Files

- [Supplement](../paper/supplement.pdf): additional methods and demo description.
- [Demo source](../paper/demo-appendix.tex): presentation setup and video link.
- [YouTube video](https://youtu.be/MG4fqtBPVOY): captioned simulation comparisons.

## Rebuild

```sh
uv run python scripts/build_demo.py --output outputs/demo.mp4
```

The video builder verifies all three source comparison hashes and writes a new file.
Use a fresh output path when rebuilding an existing video.

The standalone comparison videos use π₁ and π₂ in their headers. To create these
versions, run `scripts/label_comparison_video.py` with the source path, its SHA-256,
a fresh output path, the policy symbol, and three camera-condition labels. This
replaces the presentation header and preserves the frame count and frame rate.
The script records input and output hashes in a JSON sidecar. The original
comparison clips remain the verified inputs to the overview video builder.

The recovery table reads `results/demo-recovery.json`, an aggregate extract from
the fixed-cohort recovery report. It records the report and trial-data hashes.
The stale-versus-blank table reads `results/summary.json`. The build checks the
counts against their paired differences. No simulation runs are needed to
rebuild the video. The slide layouts are original; their white background,
black headings, and synchronized comparisons take visual inspiration from the
[HapticWorld research video](https://www.youtube.com/watch?v=UGhT2hnDrBE).

The files `timing-comparison.mp4`, `recovery-comparison.mp4`, and
`team-comparison.mp4` under `site/assets/` are the source recordings used by the
video builder. The labeled recovery and π₂ exports are used for standalone
website playback. These files serve different presentation roles and retain
the same recorded simulation evidence.

The website embeds the YouTube overview. Rebuilt overview videos go under
`outputs/` and are excluded from Git.
