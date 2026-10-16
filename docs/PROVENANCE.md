# Simulation and policy provenance

The environment and training implementation originate from Martino Russi's
[G1 Depth Dodge](https://github.com/nepyope/g1_sim_to_real), Git revision
`0df547b86578dcc8633f490784a14033f0189690`.
It adapts ViBe/ORCS and combines frozen SONIC and Theia bases with learned depth
adaptation. Training uses RSL-RL PPO in mjlab/MuJoCo Warp. LeRobot supplies G1
deployment assets; it is not the algorithm used to train these policies.

## Evaluated checkpoints

| Checkpoint | Actor ONNX SHA-256 | Perception ONNX SHA-256 |
| --- | --- | --- |
| π₁ iteration 4000 | `d51c90007160f4a3df878cf8353fac4ea80a47d1b285174952da652b2961cf9b` | `8610ee92c5cb6c0c86d17e2a8fcffb844656d1ababd6ba3309f3ba023cba2471` |
| π₂ iteration 4000 | `22c6fd3c437558947d29874a61e35a57870346e5d03abbb1a4c8951567a43e01` | `250c5e76f4393b8e41d63e7205211bde88c1b14e4fead670b4843e40b34d636f` |

The π₁ weights are identified by the
[release revision](https://huggingface.co/nepyope/g1_depth_dodge/tree/10e207cb734a6c3edf792d4995ca59ae4641bf29).
Our team trained a separate depth adaptation using the same PPO training method,
architecture, and objective: 4,000 updates, 512 global environments across eight
GPUs, and 49,152,000 transitions. All 60 fields of the retained team configuration match
the released reference configuration, including seed 42. The inspected model,
optimizer, environment, configuration, and single-GPU and distributed training
files also match byte-for-byte between the retained source trees.

π₁ identifies the weights released by Russi; π₂ identifies
the separate weights trained by Hebbian Robotics. These labels describe where
the evaluated weights came from, not different proposed training methods.
The released training guide describes an H100 reference setup; our retained run
used eight GPUs. Matching settings do not establish identical training execution.
The distributed entrypoint offsets environment seeds by GPU rank; it also supports initialization
and resume. Available records do not establish the complete initialization and
resume history for both models. We therefore cannot attribute their different
camera-failure responses to a particular training difference.

The retained π₂ checkpoint SHA-256 is
`23069f416d89f257c4ec889d47d9cac5f56570a2822f03e08bf9fc72f4d58714`.
The evaluation holds both checkpoints fixed. Model weights are not bundled;
team-weight release and external redistribution rights remain pending.

MuJoCo 3.3.7, ONNX Runtime 1.23.2, and NumPy 2.2.6 were used in the first-throw
evaluations. Frozen input file hashes are recorded under `data/inputs/`.
Changing simulator bytes or model graphs creates a new experiment, even if the
source revision or seed numbers stay the same.

## Scientific data

The prepared data archive contains all 2,496 corrected trial JSON records,
scientific configurations, measured replay stills, and a manifest of file hashes.
It excludes model weights, private infrastructure metadata and execution logs.
Trial records preserve launches, native contact events, camera capture schedules,
physical traces and all outcome flags. Dataset file hashes describe the
exported scientific files; they are independent of archive timestamps.

Archived configurations and directory names retain the identifiers `upstream`
and `team`, corresponding to π₁ and π₂. These identifiers are part of the
recorded evidence; display labels do not change the model or trial identities.
