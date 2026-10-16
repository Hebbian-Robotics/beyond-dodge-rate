# Code, data and model availability

The repository includes evaluation and analysis code, configurations, the
manuscript, and selected figures and videos. The recorded trial archives and
separately trained weights have not been released.

| Material | Current availability |
| --- | --- |
| Evaluation and analysis code | Included in this repository, with scientific configurations, dependency locks, figure builders and manuscript source. |
| Recorded trial data | Four verified archives are prepared locally but have not been publicly released. The archives are excluded from Git; file hashes and archive manifests are included under `data/`. |
| Released reference policy | Available from [the original model release](https://huggingface.co/nepyope/g1_depth_dodge/tree/10e207cb734a6c3edf792d4995ca59ae4641bf29), under its original terms. We do not bundle its weights. |
| Separately trained policy | Its weights are not distributed. The evaluated actor and perception hashes are documented in [provenance](PROVENANCE.md). |
| Simulator and robot assets | Obtained separately from the original sources and checked against the input manifests. They retain their original licenses and are not bundled here. |
| Figures, videos and paper | Selected publication files are included in the repository. |

## What can be reproduced

The analysis scripts recompute the reported statistics and figures from the
four recorded-data archives. This does not require policy weights, but it does
require access to those archives; the manifests alone are not the data.

Fresh simulation runs additionally require the pinned simulator inputs, robot
assets and the relevant policy weights. A full two-policy simulation replication
cannot currently be performed from the public materials alone because the
separately trained weights are not distributed.

See [reproduction instructions](REPRODUCIBILITY.md) for commands and
[provenance](PROVENANCE.md) for source revisions and model hashes. This document
describes current access; it does not promise a release date or permission to
redistribute third-party assets.
