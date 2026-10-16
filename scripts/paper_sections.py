"""Generate figures and TeX summaries from recorded trials."""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from evaluate import file_digest, write_json


def exact_paired_binary_probability(comparison: dict[str, Any]) -> float:
    positive = comparison["discordant_positive"]
    negative = comparison["discordant_negative"]
    discordant = positive + negative
    if not discordant:
        return 1.0
    return min(
        1.0,
        2
        * sum(math.comb(discordant, index) for index in range(min(positive, negative) + 1))
        / 2**discordant,
    )


def probability_tex(probability: float) -> str:
    if probability >= 0.0001 or probability == 0:
        return f"{probability:.4g}"
    exponent = math.floor(math.log10(probability))
    coefficient = probability / 10**exponent
    return rf"{coefficient:.2f}\times 10^{{{exponent}}}"


def generate_simulation_figure(
    directory: Path, manifest_path: Path, output_directory: Path
) -> None:
    """Compose high-resolution, event-aligned states with explicit outcome labels."""
    manifest = json.loads(manifest_path.read_text())
    for filename, expected_digest in manifest.items():
        if file_digest(directory / filename) != expected_digest:
            raise ValueError(f"Recorded simulation illustration changed: {filename}")
    verification = json.loads((directory / "verification.json").read_text())
    if verification["seed"] != 3000 or not verification["exact_replay_match"]:
        raise ValueError("Figure must use the first declared seed with exact replay verification")
    arms = ("nominal", "outage_0_continuous", "outage_320_continuous")
    labels = ("Healthy depth", "Freeze at launch", "Freeze after 320 ms")
    figure, axes = plt.subplots(2, 3, figsize=(6.9, 3.6))
    figure.subplots_adjust(left=0.02, right=0.99, top=0.87, bottom=0.11, wspace=0.035, hspace=0.42)
    figure.text(
        0.02,
        0.965,
        f"A  Just before the first {'hit' if verification['encounter_event'] == 'contact' else 'throw ends'} (t = {verification['encounter_time']:.3f} s)",
        fontsize=10,
        weight="bold",
    )
    figure.text(
        0.02,
        0.455,
        "B  End of the four-second trial: dodging can hide leaving the area",
        fontsize=10,
        weight="bold",
    )
    records = []
    for column, (arm, label) in enumerate(zip(arms, labels, strict=True)):
        trial = json.loads((directory / f"{arm}.json").read_text())
        outcomes = trial
        contact_label = (
            "DODGED" if outcomes["dodge"] else "HIT" if outcomes["hit"] else "UNRESOLVED"
        )
        balance_label = " + FALL" if outcomes["fall"] else ""
        area_label = "CONTAINED" if outcomes["contained_10"] else "LEFT AREA"
        outcome_label = f"{contact_label}{balance_label} + {area_label}"
        for row in (0, 1):
            frame = next(
                record
                for record in verification["frames"]
                if record["arm"] == arm and record["row"] == row
            )
            path = directory / frame["file"]
            if file_digest(path) != frame["sha256"]:
                raise ValueError("Rendered event frame does not match its replay record")
            image = plt.imread(path)
            if image.shape[:2] != (1440, 2560):
                raise ValueError("Publication still must be rendered at 2560 by 1440 pixels")
            # Same crop across arms within each row. The encounter is a close-up;
            # the final row shows the complete spatial requirement and trajectory.
            crop = (400, 1010, 900, 1680) if row == 0 else (350, 1280, 450, 2100)
            top, bottom, left, right = crop
            axis = axes[row, column]
            axis.imshow(image[top:bottom, left:right], interpolation="none")
            axis.set_axis_off()
            if row == 0:
                axis.set_title(label, fontsize=10, pad=5)
                message = (
                    f"Contact at {trial['throws'][0]['resolved_at']:.3f} s"
                    if outcomes["hit"]
                    else "Throw subsequently dodged"
                    if outcomes["dodge"]
                    else "Throw unresolved"
                )
                axis.text(
                    0.5,
                    -0.04,
                    message,
                    transform=axis.transAxes,
                    ha="center",
                    fontsize=8,
                    color="#a32720" if outcomes["hit"] else "#176b68",
                )
            else:
                axis.text(
                    0.5,
                    -0.04,
                    outcome_label,
                    transform=axis.transAxes,
                    ha="center",
                    fontsize=8,
                    weight="bold",
                    color="#176b68" if outcomes["joint_success_10"] else "#a32720",
                )
                axis.text(
                    0.5,
                    -0.18,
                    f"Max. distance from start: {trial['episode']['station_max']:.2f} m",
                    transform=axis.transAxes,
                    ha="center",
                    fontsize=8,
                )
            records.append({**frame, "crop_pixels": list(crop)})
    figure.text(
        0.5,
        0.01,
        "Red: active ball     Teal circle: 1 m limit     Orange line: measured pelvis ground trace",
        ha="center",
        fontsize=8,
    )
    figure.savefig(output_directory / "simulation-snapshots.pdf", dpi=400)
    figure.savefig(output_directory / "simulation-snapshots.png", dpi=400)
    plt.close(figure)
    write_json(
        output_directory / "simulation-snapshots.json",
        {
            "role": "Event-aligned exact simulation replays, not new independent trials",
            "selection": verification["selection"],
            "replay": verification,
            "frames": records,
        },
    )


def generate_team_encounter_figure(
    directory: Path, manifest_path: Path, output_directory: Path
) -> None:
    """Show the first held-out team-policy encounter without outcome selection."""
    manifest = json.loads(manifest_path.read_text())
    for filename, expected_digest in manifest.items():
        if file_digest(directory / filename) != expected_digest:
            raise ValueError(f"Team encounter illustration changed: {filename}")
    verification = json.loads((directory / "verification.json").read_text())
    if verification["seed"] != 7300 or not verification["exact_replay_match"]:
        raise ValueError("Team figure requires the first held-out seed and exact replay")
    arms = ("nominal", "outage_160_continuous", "zero_160_continuous")
    labels = ("Healthy images", "Stale images", "Blank images")
    figure, axes = plt.subplots(1, 3, figsize=(3.45, 1.45))
    figure.subplots_adjust(left=0.01, right=0.99, top=0.82, bottom=0.23, wspace=0.03)
    frame_records = []
    for axis, arm, label in zip(axes, arms, labels, strict=True):
        frame = next(
            record
            for record in verification["frames"]
            if record["arm"] == arm and record["row"] == 0
        )
        image = plt.imread(directory / frame["file"])
        if image.shape[:2] != (1440, 2560):
            raise ValueError("Team encounter still must be 2560 by 1440 pixels")
        trial = json.loads((directory / f"{arm}.json").read_text())
        axis.imshow(image[400:1010, 900:1680], interpolation="none")
        axis.set_axis_off()
        axis.set_title(label, fontsize=7.5, pad=3)
        outcome_label = (
            f"Hit at {trial['throws'][0]['resolved_at']:.3f} s"
            if trial["hit"]
            else "Later dodged"
            if trial["dodge"]
            else "Unresolved"
        )
        axis.text(
            0.5,
            -0.05,
            outcome_label,
            transform=axis.transAxes,
            ha="center",
            fontsize=7,
            color="#a32720" if trial["hit"] else "#176b68",
        )
        frame_records.append({**frame, "crop_pixels": [400, 1010, 900, 1680]})
    figure.text(
        0.5,
        0.02,
        f"Same simulation time: {verification['encounter_time']:.3f} s",
        ha="center",
        fontsize=7,
    )
    figure.savefig(output_directory / "team-encounter.pdf", dpi=400)
    figure.savefig(output_directory / "team-encounter.png", dpi=400)
    plt.close(figure)
    write_json(
        output_directory / "team-encounter.json",
        {
            "role": "First held-out team seed; exact illustrative replays, not new trials",
            "replay": verification,
            "frames": frame_records,
        },
    )


def generate_radius_horizon_sensitivity(trial_directory: Path, output_directory: Path) -> None:
    """Recompute every declared post-hoc setting from existing matched traces."""
    radii = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)
    horizons = (2.5, 3.0, 4.0)
    arms = ("outage_160_continuous", "zero_160_continuous")
    trials = {
        arm: [
            json.loads((trial_directory / f"{seed}_{arm}.json").read_text())
            for seed in range(6000, 6064)
        ]
        for arm in arms
    }
    generator = np.random.default_rng(20261014)
    resampled_indices = generator.integers(0, 64, (10000, 64))
    cells = []
    all_throws_resolved = True
    grid = np.zeros((len(horizons), len(radii)))
    for row, horizon in enumerate(horizons):
        for column, radius in enumerate(radii):
            outcomes: dict[str, list[int]] = {}
            unresolved_counts: dict[str, int] = {}
            for arm in arms:
                outcomes[arm] = []
                unresolved_counts[arm] = 0
                for trial in trials[arm]:
                    trace = [
                        sample for sample in trial["trace"] if sample["time"] <= horizon + 1e-9
                    ]
                    if not trace:
                        raise ValueError("Sensitivity horizon has no physical trace")
                    maximum_displacement = max(
                        math.hypot(*sample["pelvis_position_m"][:2]) for sample in trace
                    )
                    fell = any(
                        sample["pelvis_position_m"][2] < 0.45 or sample["upright_cosine"] < 0.4
                        for sample in trace
                    )
                    resolved = trial["throws"][0]["resolved_at"] <= horizon + 1e-9
                    avoided = resolved and trial["throws"][0]["result"] == "misses"
                    joint = int(avoided and not fell and maximum_displacement <= radius)
                    if (
                        horizon == 4.0
                        and radius == 1.0
                        and bool(joint) != trial["joint_success_10"]
                    ):
                        raise ValueError("Sensitivity fails to reproduce the primary outcome")
                    outcomes[arm].append(joint)
                    unresolved_counts[arm] += int(not resolved)
                    all_throws_resolved = all_throws_resolved and resolved
            differences = np.asarray(outcomes[arms[1]]) - np.asarray(outcomes[arms[0]])
            difference = float(differences.mean())
            interval = np.quantile(
                differences[resampled_indices].mean(axis=1), [0.025, 0.975]
            ).tolist()
            grid[row, column] = difference * 100
            cells.append(
                {
                    "radius_m": radius,
                    "horizon_seconds": horizon,
                    "freeze_joint_count": sum(outcomes[arms[0]]),
                    "zero_depth_joint_count": sum(outcomes[arms[1]]),
                    "paired_difference": difference,
                    "nominal_paired_bootstrap_95": interval,
                    "unresolved_by_arm": unresolved_counts,
                }
            )
    write_json(
        output_directory / "radius-horizon-sensitivity.json",
        {
            "role": "post-hoc, existing handling-replication traces; no new trials",
            "count_per_arm": 64,
            "radii_m": radii,
            "horizons_seconds": horizons,
            "cells": cells,
            "uncertainty": "nominal paired bootstrap, 10000 common seed resamples; no simultaneous coverage or confirmatory grid tests",
        },
    )
    positive = int((grid > 0).sum())
    negative = int((grid < 0).sum())
    resolution_note = (
        "Every throw resolved before the earliest horizon. "
        if all_throws_resolved
        else "Throws unresolved at each horizon remain failures in its all-trial denominator. "
    )
    one_metre_differences = ", ".join(f"{grid[row, 2]:+.1f}" for row in range(3))
    (output_directory / "sensitivity-results.tex").write_text(
        "We recomputed the handling replication post hoc at radii "
        "0.5, 0.75, 1, 1.25, 1.5 and 2 m and horizons 2.5, 3 and 4 s "
        "from trial start, using existing traces without new trials "
        "(Fig.~\\ref{fig:sensitivity}). "
        f"{resolution_note}Zero-depth-minus-freeze joint differences span {grid.min():+.1f} "
        f"to {grid.max():+.1f} percentage points: positive in {positive}/18 settings "
        f"and negative in {negative}/18. At 1 m, differences at the three horizons "
        f"were {one_metre_differences} points. The 2 m, four-second difference was "
        f"{grid[2, 5]:+.1f} points. Nominal paired bootstrap intervals are retained "
        "for every cell; they are not simultaneous or confirmatory grid tests. "
        "The score preference is therefore conditional on declared spatial and "
        "temporal requirements, rather than a radius-independent superiority claim.\n"
    )
    figure, axis = plt.subplots(figsize=(3.45, 1.9), constrained_layout=True)
    scale = max(abs(float(grid.min())), abs(float(grid.max())), 1.0)
    axis.imshow(grid, cmap="RdBu", vmin=-scale, vmax=scale, aspect="auto")
    for row in range(3):
        for column in range(6):
            axis.text(
                column,
                row,
                f"{grid[row, column]:+.1f}",
                ha="center",
                va="center",
                fontsize=7.5,
                color="white" if abs(grid[row, column]) > scale * 0.6 else "black",
            )
    axis.set_xticks(range(6), ("0.5", "0.75", "1.0", "1.25", "1.5", "2.0"))
    axis.set_yticks(range(3), ("2.5", "3.0", "4.0"))
    axis.tick_params(labelsize=8)
    axis.set_xlabel("Allowed distance from start (m)", fontsize=8)
    axis.set_ylabel("Trial length (s)", fontsize=8)
    axis.set_title("Success change: blank minus stale (points)", fontsize=8)
    figure.savefig(output_directory / "radius-horizon-sensitivity.pdf")
    figure.savefig(output_directory / "radius-horizon-sensitivity.png", dpi=180)
    plt.close(figure)


def generate_replication_material(summary: dict[str, Any], output_directory: Path) -> None:
    """Report the declared primary contrast without pooling exploratory seeds."""
    summaries = summary["summaries"]
    reference = summaries["nominal"]
    continuous = summaries["outage_160_continuous"]
    temporary = summaries["outage_160_160"]
    count = reference["count"]
    primary_comparison = next(
        item for item in summary["comparisons"] if item["arm"] == "outage_160_continuous"
    )
    comparison = primary_comparison["joint_success_10"]
    positive = comparison["discordant_positive"]
    negative = comparison["discordant_negative"]
    exact_probability = exact_paired_binary_probability(comparison)
    rows = [
        r"\begin{tabular}{lrrrr}\toprule",
        r"Condition & $D$ & $F$ & $C$ & $J$ \\\midrule",
        r"\multicolumn{5}{l}{Outage replication} \\",
    ]
    for label, arm in (
        ("Healthy", reference),
        ("160 ms recovery", temporary),
        ("Continuous freeze", continuous),
    ):
        rows.append(
            label
            + " & "
            + " & ".join(
                str(arm[outcome]["count"])
                for outcome in ("dodge", "fall", "contained_10", "joint_success_10")
            )
            + r" \\"
        )
    rows.append(r"\bottomrule\end{tabular}")
    (output_directory / "replication-table.tex").write_text("\n".join(rows) + "\n")
    lower, upper = comparison["paired_bootstrap_95"]
    text = (
        f"We reanalyzed the historical targeted contrast on {count} "
        "previously evaluated seeds, 4000--4063, comparing healthy vision with a continuous freeze "
        "at 160 ms onset and a 160 ms temporary freeze at the same onset. This "
        "outcome-informed selection is separate from the exploratory sweep. "
        "The primary contrast is continuous freeze minus healthy vision in "
        "$J_{1\\,\\mathrm{m}}$; the temporary-outage arm is secondary. "
        f"All {count * 3} trials passed matching, outcome and capture auditing. "
        f"Joint success was {reference['joint_success_10']['count']}/{count} for "
        f"healthy vision, {continuous['joint_success_10']['count']}/{count} for "
        f"continuous freeze, and {temporary['joint_success_10']['count']}/{count} "
        "for temporary freeze (Table~\\ref{tab:replication}). "
        f"The primary paired difference was {comparison['difference'] * 100:.1f} "
        f"percentage points (95\\% percentile bootstrap interval {lower * 100:.1f} "
        f"to {upper * 100:.1f}); discordant pairs were {positive} favorable and "
        f"{negative} unfavorable to continuous freeze. The two-sided exact "
        f"McNemar test gives $p={probability_tex(exact_probability)}$. "
        f"Contact avoidance was {reference['dodge']['count']}/{count}, "
        f"{continuous['dodge']['count']}/{count}, and {temporary['dodge']['count']}/{count}, "
        "respectively. These seeds are not pooled with the sweep and do not "
        "supply independent policy-training replication.\n"
    )
    displacement = primary_comparison["station_max_paired_mean_difference_m"]
    displacement_lower, displacement_upper = displacement["paired_bootstrap_95"]
    text += (
        "As a secondary continuous diagnostic, the paired mean change in maximum "
        f"displacement was {displacement['difference']:.3f} m (bootstrap interval "
        f"{displacement_lower:.3f} to {displacement_upper:.3f} m). "
        "The 0.5 m sensitivity gave joint counts "
        f"{reference['joint_success_05']['count']}/{count} for healthy vision and "
        f"{continuous['joint_success_05']['count']}/{count} for continuous freeze. "
        "Threshold choice therefore remains part of the benchmark specification, "
        "rather than a universal definition of athletic success.\n"
    )
    (output_directory / "replication-results.tex").write_text(text)
    write_json(
        output_directory / "primary-replication.json",
        {
            "contrast": "outage_160_continuous minus nominal",
            "outcome": "joint_success_10",
            "count": count,
            "paired_difference": comparison,
            "exact_mcnemar_two_sided_p": exact_probability,
            "secondary_displacement": displacement,
            "selection": "corrected exploratory reanalysis of historical targeted seeds",
        },
    )
    abstract = output_directory / "abstract-results.tex"
    with abstract.open("a") as abstract_file:
        abstract_file.write(
            f"A corrected {count}-seed reanalysis measured joint success "
            f"{reference['joint_success_10']['count']}/{count} with healthy vision "
            f"versus {continuous['joint_success_10']['count']}/{count} under a "
            "continuous freeze beginning 160 ms after launch, while contact "
            f"avoidance remained {reference['dodge']['count']}/{count} versus "
            f"{continuous['dodge']['count']}/{count}.\n"
        )


def generate_outage_material(summary: dict[str, Any], output_directory: Path) -> None:
    """Generate counts and bounded interpretations directly from verified analysis."""
    summaries = summary["summaries"]
    count = summaries["nominal"]["count"]
    healthy = summaries["nominal"]
    rows = [
        r"\begin{tabular}{rrrrrr}\toprule",
        r"Onset & Duration & $D$ & $F$ & $C$ & $J$ \\\midrule",
    ]
    rows.append(
        "Healthy & --- & "
        + " & ".join(
            str(healthy[outcome]["count"])
            for outcome in ("dodge", "fall", "contained_10", "joint_success_10")
        )
        + r" \\"
    )
    for onset in (0, 160, 320):
        for duration in (160, 320, "continuous"):
            arm = summaries[f"outage_{onset}_{duration}"]
            duration_label = r"$\infty$" if duration == "continuous" else str(duration)
            rows.append(
                f"{onset} & {duration_label} & "
                + " & ".join(
                    str(arm[outcome]["count"])
                    for outcome in ("dodge", "fall", "contained_10", "joint_success_10")
                )
                + r" \\"
            )
    rows.append(r"\bottomrule\end{tabular}")
    (output_directory / "outage-table.tex").write_text("\n".join(rows) + "\n")
    onset_zero = summaries["outage_0_continuous"]
    onset_late = summaries["outage_320_continuous"]
    (output_directory / "abstract-results.tex").write_text(
        f"An exploratory {count * 10}-trial onset--duration sweep motivated "
        "two corrected exploratory reanalyses.\n"
    )
    total_falls = sum(arm["fall"]["count"] for arm in summaries.values())
    total_aborts = sum(arm["aborted"] for arm in summaries.values())
    healthy_interval = healthy["joint_success_10"]["wilson_95"]
    result_text = (
        f"All {count * 10} declared trials passed exact state and throw matching, "
        "outcome accounting and camera-schedule auditing. "
        f"The extension recorded {total_falls} falls and {total_aborts} aborted throws "
        "across all arms. Full per-arm outcome vectors remain in the analysis package. "
        f"Healthy joint success was {healthy['joint_success_10']['rate'] * 100:.1f}\\% "
        f"(95\\% Wilson interval {healthy_interval[0] * 100:.1f}--"
        f"{healthy_interval[1] * 100:.1f}\\%). "
        "Figure~\\ref{fig:grid} shows contact avoidance and joint success separately.\n"
    )
    result_text += (
        "The complete analysis retains paired differences from healthy vision, "
        "their bootstrap intervals, the 0.5 m sensitivity and unthresholded "
        "displacement; the paper reports the prespecified primary 1 m constraint.\n"
    )
    (output_directory / "outage-results.tex").write_text(result_text)
    if onset_late["dodge"]["count"] > onset_zero["dodge"]["count"]:
        interpretation = (
            "Late onset improves avoidance in matched throws, permitting more "
            "post-launch observations and motion; this does not isolate memory. "
        )
    else:
        interpretation = "Late onset did not improve avoidance in these matched throws. "
    interpretation += (
        "Temporary recovery does not reset temporal state, so temporary and "
        "permanent outages require separate reporting.\n"
    )
    (output_directory / "interpretation.tex").write_text(interpretation)
    figure, axes = plt.subplots(1, 2, figsize=(3.45, 2.0), sharey=True, constrained_layout=True)
    for axis, outcome, title in zip(
        axes,
        ("dodge", "joint_success_10"),
        ("Avoided contact", "Overall success"),
        strict=True,
    ):
        counts = np.array(
            [
                [
                    summaries[f"outage_{onset}_{duration}"][outcome]["count"]
                    for onset in (0, 160, 320)
                ]
                for duration in (160, 320, "continuous")
            ]
        )
        axis.imshow(counts / count, vmin=0, vmax=1, cmap="Blues")
        for row in range(3):
            for column in range(3):
                axis.text(
                    column,
                    row,
                    f"{counts[row, column]}/{count}",
                    ha="center",
                    va="center",
                    color="white" if counts[row, column] / count > 0.55 else "black",
                    fontsize=7.5,
                )
        axis.set_xticks(range(3), ("0", "160", "320"))
        axis.set_yticks(range(3), ("160", "320", "Continuous"))
        axis.tick_params(labelsize=7.5)
        axis.set_xlabel("Start after throw (ms)", fontsize=7.5)
        axis.set_title(title, fontsize=8)
    axes[0].set_ylabel("Freeze lasts (ms)", fontsize=7.5)
    figure.savefig(output_directory / "outage-grid.pdf")
    figure.savefig(output_directory / "outage-grid.png", dpi=180)
    plt.close(figure)


def generate_stale_material(summary: dict[str, Any], output_directory: Path) -> None:
    """Retain the exploratory input-handling diagnostic, including null outcomes."""
    summaries = summary["summaries"]
    count = summaries["nominal"]["count"]
    freeze = summaries["outage_160_continuous"]
    blank = summaries["zero_160_continuous"]
    comparison = next(
        item for item in summary["comparisons"] if item["arm"] == "zero_160_continuous"
    )
    joint = comparison["joint_success_10"]
    lower, upper = joint["paired_bootstrap_95"]
    text = (
        "We reanalyzed the historical exploratory handling "
        f"diagnostic on {count} previously evaluated seeds, 5000--5031: healthy vision, continuous "
        "freeze at 160 ms onset, and the upstream zero-depth representation "
        "beginning at the same onset. The actor and its temporal history remain "
        "unchanged. This assumes ideal knowledge of the injected fault and "
        "evaluates an existing observation representation, not a new trained "
        "controller or failure detector. "
        f"Joint counts were {summaries['nominal']['joint_success_10']['count']}/{count}, "
        f"{freeze['joint_success_10']['count']}/{count} and "
        f"{blank['joint_success_10']['count']}/{count}, respectively; avoidance "
        f"counts were {summaries['nominal']['dodge']['count']}/{count}, "
        f"{freeze['dodge']['count']}/{count} and {blank['dodge']['count']}/{count}. "
        f"Zero-depth minus freeze had joint difference {joint['difference'] * 100:.1f} "
        f"percentage points (paired bootstrap interval {lower * 100:.1f} to "
        f"{upper * 100:.1f}). These exploratory corrected-port measurements do not "
        "establish a universally effective outage response.\n"
    )
    (output_directory / "stale-results.tex").write_text(text)
    write_json(
        output_directory / "stale-handling.json",
        {
            "count": count,
            "role": "exploratory, idealized known fault",
            "summaries": summaries,
            "comparisons": summary["comparisons"],
        },
    )


def generate_handling_replication_material(summary: dict[str, Any], output_directory: Path) -> None:
    """Report the second targeted contrast and adjust both primary tests together."""
    freeze = summary["summaries"]["outage_160_continuous"]
    blank = summary["summaries"]["zero_160_continuous"]
    count = freeze["count"]
    comparisons = next(
        item for item in summary["comparisons"] if item["arm"] == "zero_160_continuous"
    )
    joint = comparisons["joint_success_10"]
    dodge = comparisons["dodge"]
    probability = exact_paired_binary_probability(joint)
    first_test = json.loads((output_directory / "primary-replication.json").read_text())
    probabilities = [first_test["exact_mcnemar_two_sided_p"], probability]
    ordering = sorted(range(2), key=lambda index: probabilities[index])
    adjusted = [0.0, 0.0]
    previous = 0.0
    for rank, index in enumerate(ordering):
        previous = max(previous, min(1.0, (2 - rank) * probabilities[index]))
        adjusted[index] = previous
    text = (
        f"We also reanalyzed the historical two-arm contrast on {count} previously evaluated seeds, "
        "6000--6063, selected after the handling diagnostic. "
        f"Freeze avoided {freeze['dodge']['count']}/{count} throws with joint "
        f"success {freeze['joint_success_10']['count']}/{count}; zero-depth avoided "
        f"{blank['dodge']['count']}/{count} with joint success "
        f"{blank['joint_success_10']['count']}/{count}. "
        f"The primary zero-depth-minus-freeze joint difference was "
        f"{joint['difference'] * 100:.1f} percentage points (paired bootstrap "
        f"interval {joint['paired_bootstrap_95'][0] * 100:.1f} to "
        f"{joint['paired_bootstrap_95'][1] * 100:.1f}); discordant pairs were "
        f"{joint['discordant_positive']} favorable and {joint['discordant_negative']} "
        f"unfavorable to zero-depth. The secondary avoidance difference was "
        f"{dodge['difference'] * 100:.1f} points (interval "
        f"{dodge['paired_bootstrap_95'][0] * 100:.1f} to "
        f"{dodge['paired_bootstrap_95'][1] * 100:.1f}). "
        "Holm adjustment across the two targeted primary McNemar tests gives "
        f"$p_{{\\mathrm{{adj}}}}={probability_tex(adjusted[0])}$ for the outage "
        f"contrast and $p_{{\\mathrm{{adj}}}}={probability_tex(adjusted[1])}$ for "
        "the handling contrast. These are descriptive tests on previously seen cohorts. All corrected trials passed state, throw and "
        "camera auditing; neither cohort is pooled with the sweep or diagnostic stage.\n"
    )
    (output_directory / "handling-replication-results.tex").write_text(text)
    write_json(
        output_directory / "handling-replication.json",
        {
            "count": count,
            "joint_difference": joint,
            "secondary_dodge_difference": dodge,
            "exact_primary_p": probability,
            "holm_adjusted_primary_p": adjusted,
            "selection": "corrected exploratory reanalysis of historical handling seeds",
        },
    )
    with (output_directory / "abstract-results.tex").open("a") as abstract:
        abstract.write(
            f"A corrected {count}-seed reanalysis compared repeating stale frames "
            f"with supplying blank depth: avoidance was {freeze['dodge']['count']}/{count} "
            f"versus {blank['dodge']['count']}/{count}, while joint success was "
            f"{freeze['joint_success_10']['count']}/{count} versus "
            f"{blank['joint_success_10']['count']}/{count}.\n"
        )
    ranking_reversal = dodge["difference"] * joint["difference"] < 0
    balance_equal = freeze["fall"]["count"] == blank["fall"]["count"] == 0
    interpretation = (
        "The corrected packaged-policy handling cohort ranks the strategies differently "
        "under avoidance and joint scoring. "
        if ranking_reversal
        else "The corrected packaged-policy handling cohort does not show a reversal "
        "between avoidance and joint scoring. "
    )
    interpretation += (
        "Both arms remain upright; differences concern contact and containment. "
        if balance_equal
        else "Falls, contact, and containment must be interpreted separately. "
    )
    interpretation += "Blank depth assumes a known fault and is not universally preferable.\n"
    (output_directory / "ranking-interpretation.tex").write_text(interpretation)
    table_path = output_directory / "replication-table.tex"
    extra_rows = [r"\midrule\multicolumn{5}{l}{Handling replication} \\"]
    for label, arm in (("Continuous freeze", freeze), ("Blank depth", blank)):
        extra_rows.append(
            label
            + " & "
            + " & ".join(
                str(arm[outcome]["count"])
                for outcome in ("dodge", "fall", "contained_10", "joint_success_10")
            )
            + r" \\"
        )
    table_path.write_text(
        table_path.read_text().replace(
            r"\bottomrule\end{tabular}", "\n".join(extra_rows) + "\n" + r"\bottomrule\end{tabular}"
        )
    )


def generate_policy_comparison_material(
    input_root: Path, output_root: Path, generated: Path
) -> None:
    """Report both independently trained checkpoints without pooling their launches."""
    phases = ("policy-comparison-packaged-merged-v1", "policy-comparison-team-merged-v1")
    names = (r"$\pi_1$", r"$\pi_2$")
    summaries = [json.loads((output_root / phase / "summary.json").read_text()) for phase in phases]
    rows = [
        r"\begin{tabular}{llrrrr}\toprule",
        r"Policy & Depth & Dodged & Fell & In area & Success \\\midrule",
    ]
    arms = ("nominal", "outage_160_continuous", "zero_160_continuous")
    labels = ("Healthy", "Stale", "Blank")
    records = []
    contrasts = []
    for name, phase, summary in zip(names, phases, summaries, strict=True):
        for arm, label in zip(arms, labels, strict=True):
            counts = summary["summaries"][arm]
            rows.append(
                f"{name} & {label} & "
                + " & ".join(
                    str(counts[outcome]["count"])
                    for outcome in ("dodge", "fall", "contained_10", "joint_success_10")
                )
                + r" \\"
            )
        comparison = next(
            comparison
            for comparison in summary["comparisons"]
            if comparison["arm"] == "zero_160_continuous"
        )["joint_success_10"]
        interval = comparison["paired_bootstrap_95"]
        contrasts.append(
            f"{comparison['difference'] * 100:+.1f} percentage points "
            f"(nominal paired 95\\% interval {interval[0] * 100:+.1f} to {interval[1] * 100:+.1f})"
        )
        stages: list[dict[str, Any]] = []
        for stage in summary["configuration"]["stages"]:
            samples = {
                arm: [
                    json.loads((input_root / phase / f"{seed}_{arm}.json").read_text())
                    for seed in stage["seeds"]
                ]
                for arm in arms
            }
            differences = np.asarray(
                [
                    int(blank["joint_success_10"]) - int(stale["joint_success_10"])
                    for blank, stale in zip(
                        samples["zero_160_continuous"],
                        samples["outage_160_continuous"],
                        strict=True,
                    )
                ]
            )
            generator = np.random.default_rng(20261014)
            indices = generator.integers(0, len(differences), (10000, len(differences)))
            stages.append(
                {
                    "phase": stage["phase"],
                    "count": len(differences),
                    "joint_difference": float(differences.mean()),
                    "paired_bootstrap_95": np.quantile(
                        differences[indices].mean(axis=1), [0.025, 0.975]
                    ).tolist(),
                    "counts": {
                        arm: {
                            outcome: sum(int(trial[outcome]) for trial in samples[arm])
                            for outcome in ("dodge", "fall", "contained_10", "joint_success_10")
                        }
                        for arm in arms
                    },
                }
            )
        records.append({"policy": name, "summary": summary, "stages": stages})
    rows.append(r"\bottomrule\end{tabular}")
    (generated / "policy-comparison-table.tex").write_text("\n".join(rows) + "\n")
    seeds = summaries[0]["configuration"]["seeds"]
    if seeds != summaries[1]["configuration"]["seeds"]:
        raise ValueError("Checkpoint comparison seed lists differ")
    equal_launches = 0
    for seed in seeds:
        trials = [
            json.loads((input_root / phase / f"{seed}_nominal.json").read_text())
            for phase in phases
        ]
        if trials[0]["launch_state"] == trials[1]["launch_state"] and all(
            trials[0]["throws"][0][field] == trials[1]["throws"][0][field]
            for field in ("time", "target", "start", "velocity", "flight")
        ):
            equal_launches += 1
    count = len(seeds)
    (generated / "policy-comparison-results.tex").write_text(
        "After correcting inactive-ball collision masks, we evaluated both checkpoints "
        "on one fixed held-out cohort of 192 seeds (7300--7491). No outcomes from "
        "this cohort were used to select the correction or sample size. "
        f"Table~\\ref{{tab:policies}} reports all {count} pairs per checkpoint "
        f"({count * 6} trials). $\\pi_2$ uses the same frozen "
        "SONIC/Theia architecture and PPO plus auxiliary objective: 4,000 updates, "
        "512 worlds across eight GPUs, and 49.15 million transitions. "
        "Both historical configurations use training seed 42. "
        f"Held-out effects were {contrasts[0]} and {contrasts[1]}, respectively. "
        "Intervals are exploratory; no significance-based stopping or additional "
        "confirmatory test is used. Within-policy states and throws match exactly; "
        f"{equal_launches}/{count} match across checkpoints, because earlier actions "
        "change native aiming. These are handling effects, not causal policy "
        "superiority or training-seed variability.\n"
    )
    team_contrast = next(
        comparison
        for comparison in summaries[1]["comparisons"]
        if comparison["arm"] == "zero_160_continuous"
    )["joint_success_10"]
    packaged_contrast = next(
        comparison
        for comparison in summaries[0]["comparisons"]
        if comparison["arm"] == "zero_160_continuous"
    )["joint_success_10"]
    team_lower, team_upper = team_contrast["paired_bootstrap_95"]
    packaged_lower, packaged_upper = packaged_contrast["paired_bootstrap_95"]
    if packaged_lower > 0 and team_upper < 0:
        interpretation = (
            "The held-out estimates have opposite signs: blank depth improves joint "
            "success for $\\pi_1$ and reduces it for $\\pi_2$ "
            ". Neither nominal paired interval includes zero. This rules "
            "out recommending one of these two observation representations uniformly "
            "for both evaluated checkpoints under this protocol; it does not "
            "establish a mechanism or variability across training seeds.\n"
        )
    elif team_lower <= 0 <= team_upper:
        interpretation = (
            "$\\pi_2$'s interval includes zero: these data do "
            "not establish a joint-success advantage for blank depth on that policy. "
            "Each checkpoint requires its own handling-effect estimate.\n"
        )
    else:
        interpretation = "The checkpoint-specific effects must be interpreted separately.\n"
    (generated / "policy-comparison-interpretation.tex").write_text(interpretation)
    packaged_lower, packaged_upper = packaged_contrast["paired_bootstrap_95"]
    team_lower, team_upper = team_contrast["paired_bootstrap_95"]
    (generated / "abstract-results.tex").write_text(
        "An onset--duration sweep and corrected exploratory reanalyses measure "
        "contact, balance, and spatial outcomes separately. A fixed held-out "
        f"{count}-pair comparison per checkpoint found blank-minus-stale joint "
        f"differences of {packaged_contrast['difference'] * 100:+.1f} percentage points "
        f"for $\\pi_1$ (95\\% paired interval {packaged_lower * 100:+.1f} "
        f"to {packaged_upper * 100:+.1f}) and {team_contrast['difference'] * 100:+.1f} "
        f"for $\\pi_2$ ({team_lower * 100:+.1f} to "
        f"{team_upper * 100:+.1f}). These estimates are specific to two "
        "checkpoints in one corrected deployment port.\n"
    )
    write_json(
        generated / "policy-comparison.json",
        {"policies": records, "identical_cross_checkpoint_launches": equal_launches},
    )


def generate_plain_language_sections(analysis_root: Path, generated_directory: Path) -> None:
    """Explain verified results while retaining detailed calculations in the package."""
    comparison = json.loads((generated_directory / "policy-comparison.json").read_text())
    policies = comparison["policies"]
    comparison_sentences = []
    effects = []
    for label, policy in zip((r"$\pi_1$", r"$\pi_2$"), policies, strict=True):
        summary = policy["summary"]
        stale = summary["summaries"]["outage_160_continuous"]
        blank = summary["summaries"]["zero_160_continuous"]
        count = stale["count"]
        effect = next(
            item for item in summary["comparisons"] if item["arm"] == "zero_160_continuous"
        )["joint_success_10"]
        lower, upper = effect["paired_bootstrap_95"]
        effects.append(
            f"{effect['difference'] * 100:+.1f} percentage points "
            f"(95\\% paired interval {lower * 100:+.1f} to {upper * 100:+.1f})"
        )
        comparison_sentences.append(
            f"For {label}, stale images gave "
            f"{stale['joint_success_10']['count']}/{count} successful trials, "
            f"compared with {blank['joint_success_10']['count']}/{count} for blank images. "
            f"The blank-minus-stale difference was {effects[-1]}. "
            f"The robot dodged {stale['dodge']['count']}/{count} balls with stale images "
            f"and {blank['dodge']['count']}/{count} with blank images. "
            f"Falls were {stale['fall']['count']}/{count} and {blank['fall']['count']}/{count}, "
            "respectively."
        )
    (generated_directory / "comparison-plain.tex").write_text(
        " ".join(comparison_sentences)
        + " Table~\\ref{tab:policies} also shows healthy-camera performance and area counts. "
        "The same input choice therefore has different effects on these two policies. "
        "These are within-policy comparisons; they do not establish which policy is better overall.\n"
    )
    (generated_directory / "abstract-plain.tex").write_text(
        "In 192 new test seeds per policy, replacing stale images with blank images "
        f"changed overall success by {effects[0]} for $\\pi_1$ and "
        f"{effects[1]} for $\\pi_2$. Camera-failure handling therefore needs "
        "to be evaluated on the policy in use, with the area and trial length stated.\n"
    )
    timing = json.loads((analysis_root / "roboletics-outage-v1/summary.json").read_text())[
        "summaries"
    ]
    timing_count = timing["nominal"]["count"]
    (generated_directory / "timing-plain.tex").write_text(
        "An exploratory timing analysis uses 32 paired seeds. Camera freezes start "
        "0, 160, or 320 ms after launch and last 160 ms, 320 ms, or to the trial's end. "
        f"Healthy images gave {timing['nominal']['joint_success_10']['count']}/{timing_count} "
        "successful trials. A freeze starting at launch and continuing to the end "
        f"gave {timing['outage_0_continuous']['dodge']['count']}/{timing_count} dodges. "
        "Starting the same continuous freeze 160 ms later gave "
        f"{timing['outage_160_continuous']['dodge']['count']}/{timing_count} dodges, but only "
        f"{timing['outage_160_continuous']['joint_success_10']['count']}/{timing_count} "
        "successful trials: movement outside the area changed the score "
        "(Fig.~\\ref{fig:grid}). Temporary camera recovery is shown separately. "
        "This study changes both when the interruption begins and how much fresh "
        "information the robot has already received; it does not isolate a memory mechanism.\n"
    )
    followup = json.loads(
        (analysis_root / "roboletics-outage-confirmation-v1/summary.json").read_text()
    )["summaries"]
    followup_count = followup["nominal"]["count"]
    (generated_directory / "followup-plain.tex").write_text(
        f"In the {followup_count}-seed duration comparison, healthy images and a "
        "160 ms freeze followed by recovery each gave "
        f"{followup['nominal']['joint_success_10']['count']}/{followup_count} successful trials. "
        "A continuous freeze gave "
        f"{followup['outage_160_continuous']['dodge']['count']}/{followup_count} dodges but "
        f"{followup['outage_160_continuous']['joint_success_10']['count']}/{followup_count} "
        "successful trials. These are reused seeds after the simulator correction, "
        "so this comparison is exploratory, not independent held-out evidence. "
        "The package retains its intervals and the separate 32-seed handling diagnostic.\n"
    )
    sensitivity = json.loads((generated_directory / "radius-horizon-sensitivity.json").read_text())
    one_metre_cells = [cell for cell in sensitivity["cells"] if cell["radius_m"] == 1.0]
    differences = ", ".join(f"{cell['paired_difference'] * 100:+.1f}" for cell in one_metre_cells)
    (generated_directory / "sensitivity-plain.tex").write_text(
        "A post-hoc analysis scores 64 upstream-policy handling seeds with six "
        "area radii and three trial lengths, without running new trials "
        "(Fig.~\\ref{fig:sensitivity}). At a 1 m radius, blank-minus-stale success "
        f"differences were {differences} percentage points at 2.5, 3, and 4 seconds. "
        "A policy can stay inside the area early in a trial and move outside it later. "
        "The preferred camera input therefore depends on the time and area requirements. "
        "This additional analysis was chosen after the outcome definition. All "
        "per-cell paired intervals are retained in the package; they are not adjusted "
        "to cover the whole grid at once.\n"
    )
