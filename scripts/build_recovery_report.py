"""Verify the camera-recovery data package and generate tables and aggregate plots."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from analyze import verify_outcome_trace, wilson_interval
from evaluate import file_digest, write_json

ARM_LABELS = {
    "nominal": "Healthy",
    "stale_continuous": "Stale",
    "stale_recover_2000": "Stale + recovery",
    "blank_continuous": "Blank",
    "blank_recover_2000": "Blank + recovery",
}
POLICY_LABELS = {"upstream": r"$\pi_1$", "team": r"$\pi_2$"}


def compare_restoration(directory: Path, seeds: list[int], mode: str) -> dict[str, Any]:
    """Resample paired seeds for restoration versus the same continuous fault."""
    differences = []
    for seed in seeds:
        continuous = json.loads((directory / f"{seed}_{mode}_continuous.json").read_text())
        recovery = json.loads((directory / f"{seed}_{mode}_recover_2000.json").read_text())
        differences.append(int(recovery["joint_success_10"]) - int(continuous["joint_success_10"]))
    paired_differences = np.array(differences)
    improved_seeds = int((paired_differences > 0).sum())
    worsened_seeds = int((paired_differences < 0).sum())
    discordant_seeds = improved_seeds + worsened_seeds
    # Under equal paired success probabilities, discordant directions are fair coin flips.
    exact_p_value = min(
        1.0,
        2
        * sum(
            math.comb(discordant_seeds, count)
            for count in range(min(improved_seeds, worsened_seeds) + 1)
        )
        / 2**discordant_seeds,
    )
    generator = np.random.default_rng(20261014)
    indices = generator.integers(0, len(seeds), (10000, len(seeds)))
    return {
        "difference": float(paired_differences.mean()),
        "paired_bootstrap_95": np.quantile(
            paired_differences[indices].mean(axis=1), [0.025, 0.975]
        ).tolist(),
        "improved_seeds": improved_seeds,
        "worsened_seeds": worsened_seeds,
        "exact_paired_binary_test": {
            "method": "Two-sided exact conditional McNemar test on discordant paired outcomes",
            "discordant_seeds": discordant_seeds,
            "p_value": exact_p_value,
            "scope": "Single fixed primary contrast; secondary p-values are nominal and not multiplicity adjusted. No equivalence claim when pairs are all equal.",
        },
    }


def verify_recovery_pairs(directory: Path, seeds: list[int]) -> dict[str, Any]:
    """Reject missing trials or physical differences preceding camera restoration."""
    configuration = json.loads((directory / "configuration.json").read_text())
    if configuration["seeds"] != seeds:
        raise ValueError("Recovery seed cohort differs from the fixed protocol")
    if [arm["arm"] for arm in configuration["arms"]] != list(ARM_LABELS):
        raise ValueError("Recovery conditions differ from the declared five arms")
    trials = {
        (seed, arm): json.loads((directory / f"{seed}_{arm}.json").read_text())
        for seed in seeds
        for arm in ARM_LABELS
    }
    expected_files = {f"{seed}_{arm}.json" for seed, arm in trials}
    actual_files = {path.name for path in directory.glob("[0-9]*.json")}
    if actual_files != expected_files:
        raise ValueError("Recovery data contain missing or extra trial identities")
    resolved_before_restoration = 0
    for seed in seeds:
        for arm in ARM_LABELS:
            trial = trials[seed, arm]
            verify_outcome_trace(trial)
            previous_time = -math.inf
            for sample in trial["trace"]:
                sample_time = sample["time"]
                if not math.isfinite(sample_time) or sample_time <= previous_time:
                    raise ValueError("Physical trace times must be finite and increasing")
                if not all(math.isfinite(value) for value in sample["pelvis_position_m"]):
                    raise ValueError("Physical trace positions must be finite")
                previous_time = sample_time
        for mode in ("stale", "blank"):
            continuous = trials[seed, f"{mode}_continuous"]
            recovery = trials[seed, f"{mode}_recover_2000"]
            before_continuous = [
                sample for sample in continuous["trace"] if sample["time"] < 2.0 - 1e-9
            ]
            before_recovery = [
                sample for sample in recovery["trace"] if sample["time"] < 2.0 - 1e-9
            ]
            if not before_continuous or before_continuous != before_recovery:
                raise ValueError("Paired physical traces differ before camera restoration")
        if trials[seed, "stale_continuous"]["throws"][0]["resolved_at"] <= 2.0 + 1e-9:
            resolved_before_restoration += 1
    return {
        "trial_count": len(trials),
        "identical_pre_recovery_trace_pairs": 2 * len(seeds),
        "stale_throws_resolved_by_restoration": resolved_before_restoration,
    }


def generate_figure(
    datasets: dict[str, Path], summaries: dict[str, dict[str, Any]], destination: Path
) -> None:
    """Show every held-out seed, without selecting an illustrative trajectory."""
    figure, axes = plt.subplots(2, 2, figsize=(10.8, 7.2))
    colors = ["#777777", "#c66a12", "#1671a9", "#8b609d", "#357e55"]
    for column, (policy, directory) in enumerate(datasets.items()):
        summary = summaries[policy]
        counts = [summary["summaries"][arm]["joint_success_10"]["count"] for arm in ARM_LABELS]
        number_of_seeds = len(summary["configuration"]["seeds"])
        rates = np.array(counts) / number_of_seeds
        intervals = np.array([wilson_interval(count, number_of_seeds) for count in counts])
        axes[0, column].bar(np.arange(5), rates, color=colors, width=0.65)
        axes[0, column].errorbar(
            np.arange(5),
            rates,
            yerr=np.maximum(0, [rates - intervals[:, 0], intervals[:, 1] - rates]),
            fmt="none",
            color="#222222",
            capsize=3,
        )
        for index, count in enumerate(counts):
            axes[0, column].text(
                index,
                intervals[index, 1] + 0.025,
                f"{count}/{number_of_seeds}",
                ha="center",
                fontsize=9,
            )
        axes[0, column].set_xticks(
            np.arange(5), ["Healthy", "Stale", "Stale +\nrecovery", "Blank", "Blank +\nrecovery"]
        )
        axes[0, column].set_ylim(0, 1.15)
        axes[0, column].set_ylabel("Overall success fraction")
        axes[0, column].set_title(POLICY_LABELS[policy])
        for arm, color in zip(list(ARM_LABELS)[:3], colors[:3], strict=True):
            first_exit_times = []
            for seed in summary["configuration"]["seeds"]:
                trial = json.loads((directory / f"{seed}_{arm}.json").read_text())
                first_exit_times.append(
                    next(
                        (
                            sample["time"]
                            for sample in trial["trace"]
                            if math.hypot(*sample["pelvis_position_m"][:2]) > 1.0
                        ),
                        math.inf,
                    )
                )
            sample_times = np.linspace(0, 4, 201)
            fractions = [
                sum(exit_time > time + 1e-9 for exit_time in first_exit_times) / number_of_seeds
                for time in sample_times
            ]
            axes[1, column].step(
                sample_times, fractions, where="post", color=color, label=ARM_LABELS[arm]
            )
        axes[1, column].axvline(1.16, color="#777777", linestyle=":", linewidth=1)
        axes[1, column].axvline(2.0, color="#222222", linestyle="--", linewidth=1)
        axes[1, column].set(
            xlim=(0, 4),
            ylim=(0, 1.05),
            xlabel="Time from trial start (s)",
            ylabel="Fraction with no area exit yet",
        )
        axes[1, column].legend(loc="lower left", fontsize=9)
    for axis in axes.flat:
        axis.spines[["top", "right"]].set_visible(False)
        axis.grid(axis="y", alpha=0.2)
    figure.text(
        0.5,
        0.012,
        r"$\pi_1$: released checkpoint; $\pi_2$: separately trained with the same method and recorded settings",
        ha="center",
        fontsize=8,
    )
    figure.tight_layout(rect=(0, 0.035, 1, 1))
    figure.savefig(destination / "camera-recovery.pdf")
    figure.savefig(destination / "camera-recovery.png", dpi=200)
    plt.close(figure)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    repository = Path(__file__).resolve().parent.parent
    manifest = json.loads((repository / "data/camera-recovery-manifest.json").read_text())
    if file_digest(arguments.data) != manifest["sha256"]:
        raise ValueError("Recovery data archive differs from its recorded digest")
    arguments.output.mkdir(parents=True, exist_ok=False)
    summaries: dict[str, dict[str, Any]] = {}
    audits: dict[str, Any] = {}
    recovery_comparisons: dict[str, Any] = {}
    table_rows = [
        r"\begin{tabular}{llrrr}\toprule",
        r"Policy & Camera input & Dodge & In area & Success\\\midrule",
    ]
    with tempfile.TemporaryDirectory(prefix="dodge-recovery-") as temporary:
        dataset = Path(temporary)
        with tarfile.open(arguments.data) as archive:
            archive.extractall(dataset, filter="data")
        actual_files = {path.relative_to(dataset).as_posix() for path in dataset.glob("*/*/*.json")}
        if actual_files != set(manifest["files"]):
            raise ValueError("Recovery archive has missing or additional files")
        for filename, digest in manifest["files"].items():
            if file_digest(dataset / filename) != digest:
                raise ValueError(f"Recovery file differs from recorded digest: {filename}")
        for policy in POLICY_LABELS:
            for cohort, seeds in (
                ("pilot", list(range(8000, 8016))),
                ("heldout", list(range(9000, 9064))),
            ):
                directory = dataset / policy / cohort
                configuration = json.loads((directory / "configuration.json").read_text())
                declared = json.loads(
                    (repository / f"configs/camera-recovery-{cohort}-{policy}-v1.json").read_text()
                )
                if configuration != declared:
                    raise ValueError("Packaged configuration differs from the recorded protocol")
                audits[f"{policy}/{cohort}"] = verify_recovery_pairs(directory, seeds)
                analysis_directory = arguments.output / f"{policy}-{cohort}"
                subprocess.run(
                    [
                        sys.executable,
                        str(repository / "scripts/analyze.py"),
                        str(directory),
                        "--output",
                        str(analysis_directory),
                    ],
                    check=True,
                )
                if cohort == "heldout":
                    summaries[policy] = json.loads(
                        (analysis_directory / "summary.json").read_text()
                    )
                    recovery_comparisons[policy] = {
                        mode: compare_restoration(directory, seeds, mode)
                        for mode in ("stale", "blank")
                    }
            for index, arm in enumerate(ARM_LABELS):
                summary = summaries[policy]["summaries"][arm]
                policy_label = r"$\pi_1$" if policy == "upstream" else r"$\pi_2$"
                table_rows.append(
                    f"{policy_label if index == 0 else ''} & {ARM_LABELS[arm]} & "
                    f"{summary['dodge']['count']}/64 & {summary['contained_10']['count']}/64 & "
                    f"{summary['joint_success_10']['count']}/64" + r"\\"
                )
            if policy == "upstream":
                table_rows.append(r"\midrule")
        generate_figure(
            {policy: dataset / policy / "heldout" for policy in POLICY_LABELS},
            summaries,
            arguments.output,
        )
    table_rows.append(r"\bottomrule\end{tabular}")
    (arguments.output / "camera-recovery-table.tex").write_text("\n".join(table_rows) + "\n")
    paragraphs = []
    for policy in POLICY_LABELS:
        effect = recovery_comparisons[policy]["stale"]
        lower_bound, upper_bound = effect["paired_bootstrap_95"]
        continuous_count = summaries[policy]["summaries"]["stale_continuous"]["joint_success_10"][
            "count"
        ]
        recovery_count = summaries[policy]["summaries"]["stale_recover_2000"]["joint_success_10"][
            "count"
        ]
        paragraphs.append(
            f"For {POLICY_LABELS[policy]}, restoring fresh images changes overall success "
            f"from {continuous_count}/64 to {recovery_count}/64, a difference of "
            f"{100 * effect['difference']:+.1f} percentage points "
            f"(95\\% paired interval {100 * lower_bound:+.1f} to {100 * upper_bound:+.1f}). "
            f"There are {effect['improved_seeds']} improved seeds and {effect['worsened_seeds']} worsened seeds."
        )
    (arguments.output / "camera-recovery-effects.tex").write_text("\n\n".join(paragraphs) + "\n")
    write_json(arguments.output / "audit.json", audits)
    write_json(
        arguments.output / "report.json",
        {
            "data_sha256": manifest["sha256"],
            "trial_count": sum(audit["trial_count"] for audit in audits.values()),
            "pilot_reported_separately": True,
            "heldout": summaries,
            "restoration_vs_same_continuous_fault": recovery_comparisons,
            "scope": "Two fixed saved models; within-policy matched throws. One prespecified primary contrast; secondary intervals are nominal.",
        },
    )


if __name__ == "__main__":
    main()
