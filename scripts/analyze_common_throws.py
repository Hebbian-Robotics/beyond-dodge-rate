"""Verify common ball trajectories across policies and report paired input effects."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import numpy as np
from build_recovery_report import ARM_LABELS, verify_recovery_pairs
from evaluate import write_json


def summarize_differences(differences: list[int]) -> dict[str, Any]:
    generator = np.random.default_rng(20261014)
    indices = generator.integers(0, len(differences), (10000, len(differences)))
    values = np.array(differences)
    return {
        "difference": float(values.mean()),
        "paired_bootstrap_95": np.quantile(values[indices].mean(axis=1), [0.025, 0.975]).tolist(),
        "paired_seed_count": len(differences),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream", type=Path, required=True)
    parser.add_argument("--team", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    directories = {"upstream": arguments.upstream, "team": arguments.team}
    configurations = {
        policy: json.loads((directory / "configuration.json").read_text())
        for policy, directory in directories.items()
    }
    seeds = configurations["upstream"]["seeds"]
    if seeds != configurations["team"]["seeds"]:
        raise ValueError("Common-throw policies must use the same declared seeds")
    if seeds not in ([9998, 9999], list(range(10000, 10064))):
        raise ValueError("Common-throw data differ from the fixed preflight or control cohort")
    repository = Path(__file__).resolve().parent.parent
    cohort = "preflight" if seeds == [9998, 9999] else "control"
    for policy, configuration in configurations.items():
        declared = json.loads(
            (repository / f"configs/common-throw-{cohort}-{policy}-v1.json").read_text()
        )
        if configuration != declared:
            raise ValueError("Recorded common-throw configuration differs from the fixed protocol")
    if configurations["upstream"]["replayed_throws"] != configurations["team"]["replayed_throws"]:
        raise ValueError("The two policies use different common-throw schedules")
    trials = {
        (policy, seed, arm): json.loads((directory / f"{seed}_{arm}.json").read_text())
        for policy, directory in directories.items()
        for seed in seeds
        for arm in ARM_LABELS
    }
    audits = {
        policy: verify_recovery_pairs(directory, seeds) for policy, directory in directories.items()
    }
    fields = ("time", "target", "start", "velocity", "flight")
    for seed in seeds:
        declared = configurations["upstream"]["replayed_throws"][str(seed)]
        reference = trials["upstream", seed, "nominal"]["throws"][0]
        for name in fields:
            if reference[name] != declared[name]:
                raise ValueError("Recorded physical throw differs from its declared replay")
        for policy in directories:
            launch_state = trials[policy, seed, "nominal"]["launch_state"]
            for arm in ARM_LABELS:
                trial = trials[policy, seed, arm]
                if trial["seed"] != seed or trial["arm"] != arm:
                    raise ValueError("Common-throw trial identity mismatch")
                declared_arm = next(
                    condition
                    for condition in configurations[policy]["arms"]
                    if condition["arm"] == arm
                )
                onset = 1.0 + declared_arm.get("fault_onset_offset_seconds", 0.0)
                duration = declared_arm.get("fault_duration_seconds")
                if not trial["capture_events"] or any(
                    event["frozen"]
                    != (
                        declared_arm["fault"]
                        and event["time"] + 1e-9 >= onset
                        and (duration is None or event["time"] + 1e-9 < onset + duration)
                    )
                    for event in trial["capture_events"]
                ):
                    raise ValueError("Common-throw camera schedule differs from the fixed protocol")
                if trial["launch_state"] != launch_state:
                    raise ValueError("Unmatched within-policy state before camera intervention")
                if len(trial["throws"]) != 1 or any(
                    trial["throws"][0][name] != reference[name] for name in fields
                ):
                    raise ValueError(
                        "Policies or conditions did not face identical physical throws"
                    )
    effects = {}
    paired_differences = {}
    for policy in directories:
        paired_differences[policy] = [
            int(trials[policy, seed, "blank_continuous"]["joint_success_10"])
            - int(trials[policy, seed, "stale_continuous"]["joint_success_10"])
            for seed in seeds
        ]
        effects[policy] = summarize_differences(paired_differences[policy])
    interaction = summarize_differences(
        [
            released - team
            for released, team in zip(
                paired_differences["upstream"], paired_differences["team"], strict=True
            )
        ]
    )
    counts = {
        policy: {
            arm: {
                outcome: sum(int(trials[policy, seed, arm][outcome]) for seed in seeds)
                for outcome in ("dodge", "fall", "contained_10", "joint_success_10")
            }
            for arm in ARM_LABELS
        }
        for policy in directories
    }
    recovery_effects = {
        policy: {
            mode: summarize_differences(
                [
                    int(trials[policy, seed, f"{mode}_recover_2000"]["joint_success_10"])
                    - int(trials[policy, seed, f"{mode}_continuous"]["joint_success_10"])
                    for seed in seeds
                ]
            )
            for mode in ("stale", "blank")
        }
        for policy in directories
    }
    donor_strata = {}
    for donor_policy in directories:
        donor_seeds = [
            seed
            for seed in seeds
            if configurations["upstream"]["replayed_throws"][str(seed)]["source_policy"]
            == donor_policy
        ]
        donor_strata[donor_policy] = {
            "seed_count": len(donor_seeds),
            "success_counts": {
                policy: {
                    arm: sum(
                        int(trials[policy, seed, arm]["joint_success_10"]) for seed in donor_seeds
                    )
                    for arm in ARM_LABELS
                }
                for policy in directories
            },
        }
    arguments.output.mkdir(parents=True, exist_ok=False)
    write_json(
        arguments.output / "summary.json",
        {
            "trial_count": len(trials),
            "seeds": seeds,
            "audits": audits,
            "common_throws_verified_across_policies": True,
            "counts": counts,
            "blank_minus_stale_success": effects,
            "released_minus_team_input_effect": interaction,
            "restoration_vs_same_continuous_fault": recovery_effects,
            "donor_policy_strata": donor_strata,
            "scope": "Exploratory common-trajectory replay, not new training or independent confirmation. Policies may have different robot states at launch.",
            "uncertainty": "Paired-seed bootstrap with 10000 replicates, seed 20261014; nominal intervals without multiplicity correction.",
        },
    )
    lines = [
        "# Common-throw outcomes",
        "",
        "| Policy | Input | Dodged | Falls | In area | Success |",
        "| --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for policy, arm_counts in counts.items():
        for arm, values in arm_counts.items():
            lines.append(
                f"| {policy} | {ARM_LABELS[arm]} | {values['dodge']}/{len(seeds)} | {values['fall']} | {values['contained_10']}/{len(seeds)} | {values['joint_success_10']}/{len(seeds)} |"
            )
    (arguments.output / "results.md").write_text("\n".join(lines) + "\n")
    table = [
        r"\begin{tabular}{llrrr}\toprule",
        r"Policy & Camera input & Dodge & In area & Success\\\midrule",
    ]
    paragraphs = []
    for policy, arm_counts in counts.items():
        label = r"$\pi_1$" if policy == "upstream" else r"$\pi_2$"
        for index, (arm, values) in enumerate(arm_counts.items()):
            table.append(
                f"{label if index == 0 else ''} & {ARM_LABELS[arm]} & "
                f"{values['dodge']}/{len(seeds)} & {values['contained_10']}/{len(seeds)} & "
                f"{values['joint_success_10']}/{len(seeds)}" + r"\\"
            )
        if policy == "upstream":
            table.append(r"\midrule")
        lower_bound, upper_bound = effects[policy]["paired_bootstrap_95"]
        paragraphs.append(
            f"For {label}, blank rather than stale images changes success "
            f"from {arm_counts['stale_continuous']['joint_success_10']}/{len(seeds)} to "
            f"{arm_counts['blank_continuous']['joint_success_10']}/{len(seeds)} "
            f"({100 * effects[policy]['difference']:+.1f} percentage points; "
            f"nominal 95\\% paired interval {100 * lower_bound:+.1f} to {100 * upper_bound:+.1f})."
        )
    table.append(r"\bottomrule\end{tabular}")
    lower_bound, upper_bound = interaction["paired_bootstrap_95"]
    paragraphs.append(
        r"The $\pi_1$ input effect minus the $\pi_2$ input effect is "
        f"{100 * interaction['difference']:+.1f} percentage points "
        f"(nominal 95\\% paired interval {100 * lower_bound:+.1f} to {100 * upper_bound:+.1f}). "
        "This comparison resamples each common-throw seed with both policies and all conditions together."
    )
    (arguments.output / "common-throw-table.tex").write_text("\n".join(table) + "\n")
    (arguments.output / "common-throw-effects.tex").write_text("\n\n".join(paragraphs) + "\n")


if __name__ == "__main__":
    main()
