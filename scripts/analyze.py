"""Check matched first-throw trials and report paired-seed uncertainty without dropping failures."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from evaluate import write_json

OUTCOMES = (
    "dodge",
    "hit",
    "fall",
    "contained_05",
    "contained_10",
    "joint_success_05",
    "joint_success_10",
)


def verify_outcome_trace(trial: dict[str, Any]) -> None:
    """Recompute reported flags from retained native outcomes and physical traces."""
    trace = trial["trace"]
    if not trace:
        raise ValueError("Trial has no physical trace")
    maximum_displacement = max(math.hypot(*sample["pelvis_position_m"][:2]) for sample in trace)
    if not math.isclose(maximum_displacement, trial["episode"]["station_max"], abs_tol=1e-12):
        raise ValueError("Native maximum displacement differs from retained trajectory")
    fall = any(
        sample["pelvis_position_m"][2] < 0.45 or sample["upright_cosine"] < 0.4 for sample in trace
    )
    results = [throw["result"] for throw in trial["throws"]]
    dodge = results == ["misses"]
    expected = {"dodge": dodge, "hit": "hits" in results, "fall": fall}
    for radius, suffix in ((0.5, "05"), (1.0, "10")):
        contained = maximum_displacement <= radius
        expected[f"contained_{suffix}"] = contained
        expected[f"joint_success_{suffix}"] = dodge and not fall and contained
    if any(trial[outcome] != value for outcome, value in expected.items()):
        raise ValueError("Outcome flags differ from native events and physical trace")


def wilson_interval(successes: int, count: int) -> list[float]:
    proportion = successes / count
    denominator = 1 + 1.96**2 / count
    center = (proportion + 1.96**2 / (2 * count)) / denominator
    radius = (
        1.96
        * math.sqrt(
            proportion * (1 - proportion) / count + 1.96**2 / (4 * count**2),
        )
        / denominator
    )
    lower_bound = 0.0 if successes == 0 else max(0, center - radius)
    upper_bound = 1.0 if successes == count else min(1, center + radius)
    return [lower_bound, upper_bound]


def plot_first_seed(trials: dict[str, list[dict[str, Any]]], output_directory: Path) -> None:
    """Show the first declared seed, without selecting a favorable trajectory."""
    figure, axes = plt.subplots(3, 1, figsize=(7, 7), sharex=True)
    illustrative_arms = (
        "nominal",
        "freeze_continue",
        "freeze_plain_0",
        "freeze_hold_0",
        "freeze_default_0",
    )
    if not all(name in trials for name in illustrative_arms):
        illustrative_arms = tuple(trials)
    for arm_name in illustrative_arms:
        trial = trials[arm_name][0]
        times = [sample["time"] for sample in trial["trace"]]
        positions = np.array([sample["pelvis_position_m"] for sample in trial["trace"]])
        axes[0].plot(times, np.linalg.norm(positions[:, :2], axis=1), label=arm_name)
        axes[1].plot(times, positions[:, 2])
        axes[2].plot(times, [sample["upright_cosine"] for sample in trial["trace"]])
    for axis, threshold, label in zip(
        axes,
        (1.0, 0.45, 0.4),
        (
            "Horizontal pelvis displacement (m)",
            "Pelvis height (m)",
            "Pelvis upright cosine",
        ),
        strict=True,
    ):
        axis.axhline(threshold, color="black", linestyle=":", linewidth=1)
        axis.axvline(1.0, color="gray", linestyle="--", linewidth=1)
        axis.set_ylabel(label)
        axis.grid(alpha=0.2)
    axes[0].legend(fontsize=8)
    axes[-1].set_xlabel("Time from trial start (s); dashed line: ball launch")
    first_trial = next(iter(trials.values()))[0]
    figure.suptitle(
        f"First declared seed {first_trial['seed']} · illustrative traces, simulation only"
    )
    figure.tight_layout()
    figure.savefig(output_directory / "first-seed-trajectories.png", dpi=160)
    figure.savefig(output_directory / "first-seed-trajectories.pdf")
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    configuration = json.loads((arguments.directory / "configuration.json").read_text())
    seed_values = configuration["seeds"]
    arm_names = [arm["arm"] for arm in configuration["arms"]]
    reference_arm = configuration.get("analysis_reference", "freeze_continue")
    if len(seed_values) != len(set(seed_values)) or len(arm_names) != len(set(arm_names)):
        raise ValueError("Repeated identities")
    trials: dict[str, list[dict[str, Any]]] = {name: [] for name in arm_names}
    for seed in seed_values:
        reference_state = None
        reference_throw = None
        for arm_name in arm_names:
            trial = json.loads((arguments.directory / f"{seed}_{arm_name}.json").read_text())
            if trial["seed"] != seed or trial["arm"] != arm_name:
                raise ValueError("Trial identity mismatch")
            verify_outcome_trace(trial)
            if (
                configuration["phase"].startswith("roboletics_outage")
                or configuration["phase"].startswith("camera_recovery")
                or configuration["phase"].startswith("common_throw")
                or configuration["phase"] == "two_checkpoint_outage_comparison"
            ):
                declared_arm = next(arm for arm in configuration["arms"] if arm["arm"] == arm_name)
                onset = 1.0 + declared_arm.get("fault_onset_offset_seconds", 0.0)
                duration = declared_arm.get("fault_duration_seconds")
                captures = trial["capture_events"]
                if not captures or any(
                    event["frozen"]
                    != (
                        declared_arm["fault"]
                        and event["time"] + 1e-9 >= onset
                        and (duration is None or event["time"] + 1e-9 < onset + duration)
                    )
                    for event in captures
                ):
                    raise ValueError("Camera fault ledger differs from the declared schedule")
            expected_throws = int(configuration.get("projectile", True))
            if int(trial["launched"]) != expected_throws or len(trial["throws"]) != expected_throws:
                raise ValueError(
                    "Trial lacks its declared throw coverage; keep as invalid evidence"
                )
            current_throw = (
                {
                    key: trial["throws"][0][key]
                    for key in ("time", "target", "start", "velocity", "flight")
                }
                if expected_throws
                else {}
            )
            if reference_state is None:
                reference_state = trial["launch_state"]
                reference_throw = current_throw
            if trial["launch_state"] != reference_state or current_throw != reference_throw:
                raise ValueError("Unmatched pre-intervention state or physical throw")
            episode = trial["episode"]
            if episode["launches"] != episode["hits"] + episode["misses"] + episode["aborted"]:
                raise ValueError("Incomplete outcome accounting")
            trials[arm_name].append(trial)
    summaries: dict[str, Any] = {}
    for arm_name, arm_trials in trials.items():
        summary: dict[str, Any] = {"count": len(arm_trials)}
        for outcome in OUTCOMES:
            successes = sum(int(trial[outcome]) for trial in arm_trials)
            summary[outcome] = {
                "count": successes,
                "rate": successes / len(arm_trials),
                "wilson_95": wilson_interval(successes, len(arm_trials)),
            }
        summary["aborted"] = sum(trial["episode"]["aborted"] for trial in arm_trials)
        summary["station_max_median_m"] = float(
            np.median([trial["episode"]["station_max"] for trial in arm_trials])
        )
        resolved_count = sum(int(trial["resolved"]) for trial in arm_trials)
        summary["resolved_count"] = resolved_count
        summary["dodge_rate_resolved_only"] = (
            summary["dodge"]["count"] / resolved_count if resolved_count else None
        )
        summaries[arm_name] = summary
    generator = np.random.default_rng(20261014)
    resampled_indices = generator.integers(0, len(seed_values), (10000, len(seed_values)))
    comparisons: list[dict[str, Any]] = []
    for arm_name in arm_names:
        if arm_name == reference_arm:
            continue
        comparison: dict[str, Any] = {"arm": arm_name, "reference": reference_arm}
        for outcome in OUTCOMES:
            paired_differences = np.array(
                [
                    int(trial[outcome]) - int(reference[outcome])
                    for trial, reference in zip(
                        trials[arm_name], trials[reference_arm], strict=True
                    )
                ]
            )
            comparison[outcome] = {
                "difference": float(paired_differences.mean()),
                "paired_bootstrap_95": np.quantile(
                    paired_differences[resampled_indices].mean(axis=1),
                    [0.025, 0.975],
                ).tolist(),
                "discordant_positive": int((paired_differences > 0).sum()),
                "discordant_negative": int((paired_differences < 0).sum()),
            }
        displacement_differences = np.array(
            [
                trial["episode"]["station_max"] - reference["episode"]["station_max"]
                for trial, reference in zip(trials[arm_name], trials[reference_arm], strict=True)
            ]
        )
        comparison["station_max_paired_mean_difference_m"] = {
            "difference": float(displacement_differences.mean()),
            "paired_bootstrap_95": np.quantile(
                displacement_differences[resampled_indices].mean(axis=1), [0.025, 0.975]
            ).tolist(),
            "role": "secondary continuous diagnostic; not the primary binary contrast",
        }
        comparisons.append(comparison)
    arguments.output.mkdir(parents=True, exist_ok=False)
    write_json(
        arguments.output / "summary.json",
        {
            "complete_matched_coverage": True,
            "configuration": configuration,
            "summaries": summaries,
            "comparisons": comparisons,
            "uncertainty": "Wilson per-arm intervals; paired-seed percentile bootstrap, 10000 replicates; exploratory, no multiplicity correction",
        },
    )
    table_lines = [
        "# Measured outcomes",
        "",
        "| Arm | Dodge / all | Falls | Within 1 m | Dodge + upright + within 1 m | Aborted |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for arm_name, summary in summaries.items():
        count = summary["count"]
        dodge_count = (
            f"{summary['dodge']['count']}/{count}"
            if configuration.get("projectile", True)
            else "n/a"
        )
        joint_count = (
            f"{summary['joint_success_10']['count']}/{count}"
            if configuration.get("projectile", True)
            else "n/a"
        )
        table_lines.append(
            f"| {arm_name} | {dodge_count} | {summary['fall']['count']}/{count} "
            f"| {summary['contained_10']['count']}/{count} | {joint_count} "
            f"| {summary['aborted']} |",
        )
    (arguments.output / "results.md").write_text("\n".join(table_lines) + "\n")
    figure, axes = plt.subplots(1, 2, figsize=(12, max(4, len(arm_names) * 0.4)), sharey=True)
    labels = [name.replace("freeze_", "").replace("_", " ") for name in arm_names]
    plotted_outcomes = (
        ("dodge", "joint_success_10")
        if configuration.get("projectile", True)
        else ("fall", "contained_10")
    )
    plotted_titles = (
        ("Avoided ball contact (all trials)", "Avoided contact, upright, within 1 m")
        if configuration.get("projectile", True)
        else ("Any fall without a projectile", "Stayed within 1 m")
    )
    for axis, outcome, title in zip(
        axes,
        plotted_outcomes,
        plotted_titles,
        strict=True,
    ):
        rates = np.array([summaries[name][outcome]["rate"] for name in arm_names])
        intervals = np.array([summaries[name][outcome]["wilson_95"] for name in arm_names])
        axis.errorbar(
            rates * 100,
            np.arange(len(arm_names)),
            xerr=np.stack((rates - intervals[:, 0], intervals[:, 1] - rates)) * 100,
            fmt="o",
            color="#176b68",
            capsize=3,
        )
        axis.set(xlim=(-3, 103), xlabel="Trials (%) · 95% Wilson interval", title=title)
        axis.grid(axis="x", alpha=0.25)
    axes[0].set_yticks(np.arange(len(labels)), labels)
    axes[0].invert_yaxis()
    context = configuration.get("plot_context") or (
        "Sensor freeze at first throw"
        if configuration.get("projectile", True)
        else "Sensor freeze without a projectile"
    )
    if configuration["phase"].startswith("roboletics_outage"):
        context = "Outage onset and duration sensitivity"
    figure.suptitle(f"{context} · {len(seed_values)} paired seeds per arm · simulation only")
    figure.tight_layout()
    figure.savefig(arguments.output / "outcomes.png", dpi=180)
    figure.savefig(arguments.output / "outcomes.pdf")
    plt.close(figure)
    plot_first_seed(trials, arguments.output)
    print("\n".join(table_lines))


if __name__ == "__main__":
    main()
