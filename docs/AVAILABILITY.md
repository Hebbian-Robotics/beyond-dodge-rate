# Code, data and model availability

The repository includes evaluation and analysis code, configurations, the
manuscript, and selected figures and videos. The recorded trial archives and
the separately trained weights are released on Hugging Face.

| Material | Current availability |
| --- | --- |
| Evaluation and analysis code | Included in this repository, with scientific configurations, dependency locks, figure builders and manuscript source. |
| Recorded trial data | Four verified archives are released as the [Hugging Face dataset](https://huggingface.co/datasets/hebbianrobotics/beyond-dodge-rate) under CC BY 4.0. The archives are excluded from Git; file hashes and archive manifests are included under `data/`. |
| Released reference policy | Available from [the original model release](https://huggingface.co/nepyope/g1_depth_dodge/tree/10e207cb734a6c3edf792d4995ca59ae4641bf29), under its original terms. We do not bundle its weights. |
| Separately trained policy | The evaluated actor and perception ONNX files are at [hebbianrobotics/g1-depth-dodge](https://huggingface.co/hebbianrobotics/g1-depth-dodge) under the NVIDIA Open Model License; their hashes are documented in [provenance](PROVENANCE.md). The shared SONIC and Theia encoders are byte-identical to the reference release and are obtained from it. |
| Simulator and robot assets | Obtained separately from the original sources and checked against the input manifests. They retain their original licenses and are not bundled here. |
| Figures, videos and paper | Selected publication files are included in the repository. |

## What can be reproduced

The analysis scripts recompute the reported statistics and figures from the
four recorded-data archives. This does not require policy weights, but it does
require access to those archives; the manifests alone are not the data.

Fresh simulation runs additionally require the pinned simulator inputs, robot
assets and the relevant policy weights. Both sets of evaluated weights are
publicly available; simulator and robot assets come from their original sources.

See [reproduction instructions](REPRODUCIBILITY.md) for commands and
[provenance](PROVENANCE.md) for source revisions and model hashes. This document
describes current access; it does not promise a release date or permission to
redistribute third-party assets.
