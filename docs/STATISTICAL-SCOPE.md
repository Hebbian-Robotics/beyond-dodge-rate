# Sample size and statistical scope

The primary recovery comparison has 64 paired evaluation seeds for one fixed
π₁. Each seed supplies continuous-stale and restored-camera
outcomes with the same physical throw and pre-restoration history. Seeds, not
individual frames or conditions, are the resampling units.

Restoration at two seconds changes overall success from 32/64 to 61/64:
29 seeds improve and none worsen. The paired mean difference is +45.3 percentage
points, with the declared bootstrap 95% interval from +32.8 to +57.8 points.
As an additional post-hoc check, the two-sided exact conditional paired binary test gives
`2 × (1/2)^29 = 3.73 × 10^-9`. The test conditions on discordant pairs and assumes
independent seed pairs under the fixed evaluation distribution. It corroborates
the large effect in this model and setup; it does not quantify hardware safety
or guarantee conference acceptance.

This primary contrast and the 64-seed follow-up were fixed after a separate
16-seed pilot. Pilot outcomes are not pooled into the effect estimate. The
other policy, blank-input responses, timing extension, and distance summaries
are secondary or exploratory. Their intervals and any reported p-values are
pointwise nominal, without simultaneous or multiplicity-adjusted guarantees.

Maximum excursion decreases by 0.184 m in the π₁ held-out stale
comparison, with a nominal paired interval from −0.226 to −0.146 m for restored
minus continuous input. This post-hoc result uses the same recordings; it is
supporting evidence, not another independent experiment. Small or uncertain
effects elsewhere should retain their full intervals. An interval that includes
zero is not proof of equivalence. When every observed paired outcome is equal,
the empirical bootstrap interval can collapse to zero; that does not imply zero
population uncertainty.

The complete study has 4,064 scientific simulation trials across several
cohorts and conditions. This total is not an independent sample size for one
hypothesis. Archived controls, re-scored recordings and illustrative replays do
not create new independent units. The 20 implementation-preflight trials and
rendering replays are excluded from scientific effect estimates.

The results support large effects in the tested fixed models. Precision for
smaller effects may need more independent evaluation seeds. Generality across
training runs instead requires independently trained policies: the two saved
models do not constitute a controlled training-seed study, regardless of how
many simulation rollouts they receive.
