# Documentation

Start with [methods](METHODS.md) for what was measured and how to read it, then
[statistical scope](STATISTICAL-SCOPE.md) for what the sample sizes can and cannot
support. Reproduction and access details are separate.

## Understanding the study

| Document | What it covers |
| --- | --- |
| [Methods and interpretation](METHODS.md) | Simulator, throws, outcomes, and how to interpret them |
| [Statistical scope](STATISTICAL-SCOPE.md) | Paired sample sizes, uncertainty, and evaluation seeds versus training runs |
| [Provenance](PROVENANCE.md) | Source revisions, checkpoint hashes, and how the two policies were obtained |

## Experiments

| Document | What it covers |
| --- | --- |
| [Camera recovery](CAMERA-RECOVERY-PROTOCOL.md) | Restoring fresh images at two seconds: pilot and fixed held-out cohort |
| [Common-throw control](COMMON-THROW-CONTROL.md) | Replaying identical recorded ball trajectories for both policies |
| [Recovery sensitivity](RECOVERY-SENSITIVITY.md) | Area boundary, observation window, and distance without a cutoff |
| [Later restoration](LATER-RECOVERY-PROTOCOL.md) | Restoring fresh images at three seconds (exploratory) |

## Reproducing and using the materials

| Document | What it covers |
| --- | --- |
| [Availability](AVAILABILITY.md) | What is released, where it lives, and under which terms |
| [Reproducing the results](REPRODUCIBILITY.md) | Commands to verify the archives, recompute results, and rebuild the paper |
| [Building the manuscript](PAPER.md) | Named and anonymous PDF exports and the supplement |

The video builder and its fonts are documented in [`../demo/README.md`](../demo/README.md).
