"""Re-score recorded recovery trials across a fixed radius and observation grid."""

from __future__ import annotations

import argparse
import csv
import json
import math
import tarfile
import tempfile
from pathlib import Path
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
from analyze import verify_outcome_trace
from build_recovery_report import POLICY_LABELS
from evaluate import file_digest, write_json

RADII = (0.5, 0.75, 1.0, 1.25, 1.5, 2.0)
HORIZONS = (2.0, 2.5, 3.0, 4.0)


def summarize_motion_pairs(directory: Path, seeds: list[int]) -> dict[str, Any]:
    """Compare distances for every paired seed without selecting successful dodges."""
    results = {}
    generator = np.random.default_rng(20261016)
    bootstrap_indices = generator.integers(0, len(seeds), (10000, len(seeds)))
    for mode in ("stale", "blank"):
        pairs = []
        for seed in seeds:
            pair: dict[str, Any] = {"seed": seed}
            before_restoration = []
            for condition in ("continuous", "recover_2000"):
                trial = json.loads((directory / f"{seed}_{mode}_{condition}.json").read_text())
                verify_outcome_trace(trial)
                trace = trial["trace"]
                times = np.array([sample["time"] for sample in trace])
                positions = np.array([sample["pelvis_position_m"][:2] for sample in trace])
                if (
                    not np.isfinite(positions).all()
                    or not np.isfinite(times).all()
                    or not np.allclose(times, np.arange(1, 201) * 0.02, atol=1e-9, rtol=0)
                ):
                    raise ValueError("Motion analysis requires the complete finite 50 Hz trace")
                radii = np.linalg.norm(positions, axis=1)
                pair[f"{condition}_maximum_radius_m"] = float(radii.max())
                pair[f"{condition}_final_radius_m"] = float(radii[-1])
                before_restoration.append([sample for sample in trace if sample["time"] < 2 - 1e-9])
            if before_restoration[0] != before_restoration[1]:
                raise ValueError("Paired motion differs before restoration")
            pairs.append(pair)
        metrics = {}
        for metric in ("maximum_radius_m", "final_radius_m"):
            continuous = np.array([pair[f"continuous_{metric}"] for pair in pairs])
            restored = np.array([pair[f"recover_2000_{metric}"] for pair in pairs])
            differences = restored - continuous
            metrics[metric] = {
                "continuous_mean": float(continuous.mean()),
                "restored_mean": float(restored.mean()),
                "mean_paired_difference": float(differences.mean()),
                "median_paired_difference": float(np.median(differences)),
                "nominal_paired_bootstrap_95": np.quantile(
                    differences[bootstrap_indices].mean(axis=1), [0.025, 0.975]
                ).tolist(),
                "smaller_radius_seeds": int((differences < -1e-12).sum()),
                "larger_radius_seeds": int((differences > 1e-12).sum()),
                "equal_within_1e_minus12_seeds": int((np.abs(differences) <= 1e-12).sum()),
            }
        results[mode] = {"seeds": len(seeds), "metrics": metrics, "pairs": pairs}
    return results


def score_recording(trial: dict[str, Any], radius: float, horizon: float) -> bool:
    """Require a resolved miss and no sampled fall or area exit by the horizon."""
    trace = [sample for sample in trial["trace"] if sample["time"] <= horizon + 1e-9]
    if not trace or trial["trace"][-1]["time"] < horizon - 0.021:
        raise ValueError("Recording does not cover the requested observation window")
    throws = trial["throws"]
    if len(throws) != 1:
        raise ValueError("Expected exactly one native throw")
    resolved_miss = throws[0]["result"] == "misses" and throws[0]["resolved_at"] <= horizon + 1e-9
    return resolved_miss and all(
        math.hypot(*sample["pelvis_position_m"][:2]) <= radius
        and sample["pelvis_position_m"][2] >= 0.45
        and sample["upright_cosine"] >= 0.4
        for sample in trace
    )


def analyze_cohort(directory: Path, seeds: list[int]) -> list[dict[str, Any]]:
    trials = {
        (seed, mode, condition): json.loads(
            (directory / f"{seed}_{mode}_{condition}.json").read_text()
        )
        for seed in seeds
        for mode in ("stale", "blank")
        for condition in ("continuous", "recover_2000")
    }
    for trial in trials.values():
        verify_outcome_trace(trial)
        if score_recording(trial, 1.0, 4.0) != trial["joint_success_10"]:
            raise ValueError("Four-second score differs from the original outcome")
    generator = np.random.default_rng(20261015)
    indices = generator.integers(0, len(seeds), (10000, len(seeds)))
    rows = []
    for mode in ("stale", "blank"):
        for horizon in HORIZONS:
            for radius in RADII:
                continuous = np.array(
                    [
                        score_recording(trials[seed, mode, "continuous"], radius, horizon)
                        for seed in seeds
                    ],
                    dtype=int,
                )
                restored = np.array(
                    [
                        score_recording(trials[seed, mode, "recover_2000"], radius, horizon)
                        for seed in seeds
                    ],
                    dtype=int,
                )
                differences = restored - continuous
                if horizon == 2.0 and np.any(differences):
                    raise ValueError("Restoration changes outcomes at its own onset")
                rows.append(
                    {
                        "mode": mode,
                        "horizon_seconds": horizon,
                        "radius_m": radius,
                        "seeds": len(seeds),
                        "continuous_successes": int(continuous.sum()),
                        "restored_successes": int(restored.sum()),
                        "difference": float(differences.mean()),
                        "nominal_paired_bootstrap_95": np.quantile(
                            differences[indices].mean(axis=1), [0.025, 0.975]
                        ).tolist(),
                        "improved_seeds": int((differences > 0).sum()),
                        "worsened_seeds": int((differences < 0).sum()),
                    }
                )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recovery-data", type=Path, required=True)
    parser.add_argument("--common-data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    repository = Path(__file__).resolve().parent.parent
    arguments.output.mkdir(parents=True, exist_ok=False)
    results = {}
    motion_results = {}
    archive_hashes = {}
    for cohort, archive_path, manifest_name, cohort_folder, seeds in (
        ("heldout", arguments.recovery_data, "camera-recovery", "heldout", list(range(9000, 9064))),
        ("common", arguments.common_data, "common-throw", "control", list(range(10000, 10064))),
    ):
        manifest = json.loads((repository / f"data/{manifest_name}-manifest.json").read_text())
        if file_digest(archive_path) != manifest["sha256"]:
            raise ValueError("Archive digest differs from the recorded manifest")
        archive_hashes[cohort] = manifest["sha256"]
        with tempfile.TemporaryDirectory(prefix="recovery-sensitivity-") as temporary:
            dataset = Path(temporary)
            with tarfile.open(archive_path) as archive:
                archive.extractall(dataset, filter="data")
            actual_files = {
                path.relative_to(dataset).as_posix()
                for path in dataset.rglob("*")
                if path.is_file()
            }
            if actual_files != set(manifest["files"]):
                raise ValueError("Archive file coverage differs from the manifest")
            for filename, digest in manifest["files"].items():
                if file_digest(dataset / filename) != digest:
                    raise ValueError(f"Record digest differs: {filename}")
            results[cohort] = {
                policy: analyze_cohort(dataset / policy / cohort_folder, seeds)
                for policy in POLICY_LABELS
            }
            motion_results[cohort] = {
                policy: summarize_motion_pairs(dataset / policy / cohort_folder, seeds)
                for policy in POLICY_LABELS
            }
    figure, axes = plt.subplots(2, 2, figsize=(10, 7), constrained_layout=True)
    for row_index, (cohort, policies) in enumerate(results.items()):
        for column_index, (policy, rows) in enumerate(policies.items()):
            axis = axes[row_index, column_index]
            matrix = np.array(
                [row["difference"] * 100 for row in rows if row["mode"] == "stale"]
            ).reshape(len(HORIZONS), len(RADII))
            plot = axis.imshow(matrix, vmin=-65, vmax=65, cmap="RdBu", aspect="auto")
            axis.set_xticks(range(len(RADII)), [str(value) for value in RADII])
            axis.set_yticks(range(len(HORIZONS)), [str(value) for value in HORIZONS])
            axis.set_xlabel("Area radius (m)")
            axis.set_ylabel("Observation window (s)")
            axis.set_title(f"{cohort.capitalize()} · {POLICY_LABELS[policy]}")
            for (vertical, horizontal), value in np.ndenumerate(matrix):
                axis.text(
                    horizontal,
                    vertical,
                    f"{value:+.1f}",
                    ha="center",
                    va="center",
                    fontsize=9,
                    color="white" if abs(value) > 40 else "black",
                )
    figure.colorbar(
        plot,
        ax=axes,
        label="Restored minus continuous stale success (percentage points)",
        shrink=0.8,
    )
    figure.savefig(arguments.output / "stale-recovery-sensitivity.png", dpi=200)
    plt.close(figure)
    motion_figure, motion_axes = plt.subplots(2, 2, figsize=(8, 8), constrained_layout=True)
    csv_rows = []
    for row_index, (cohort, policies) in enumerate(motion_results.items()):
        for column_index, (policy, modes) in enumerate(policies.items()):
            axis = motion_axes[row_index, column_index]
            pairs = modes["stale"]["pairs"]
            continuous = [pair["continuous_maximum_radius_m"] for pair in pairs]
            restored = [pair["recover_2000_maximum_radius_m"] for pair in pairs]
            upper_bound = max(*continuous, *restored) * 1.05
            axis.scatter(continuous, restored, alpha=0.65, s=22, edgecolors="none")
            axis.plot([0, upper_bound], [0, upper_bound], color="gray", linestyle="--")
            axis.set(xlim=(0, upper_bound), ylim=(0, upper_bound), aspect="equal")
            axis.set_xlabel("Continuous stale: maximum radius (m)")
            axis.set_ylabel("Restored: maximum radius (m)")
            axis.set_title(
                f"{cohort.capitalize()} · {POLICY_LABELS[policy]}\nAll 64 paired seeds; lower means less excursion",
                fontsize=10,
            )
            for mode, result in modes.items():
                csv_rows.extend(
                    {"cohort": cohort, "policy": policy, "mode": mode, **pair}
                    for pair in result["pairs"]
                )
    motion_figure.savefig(arguments.output / "stale-recovery-displacement.png", dpi=200)
    plt.close(motion_figure)
    with (arguments.output / "motion-pairs.csv").open("w", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=list(csv_rows[0]))
        writer.writeheader()
        writer.writerows(csv_rows)
    heldout_maximum = motion_results["heldout"]["upstream"]["stale"]["metrics"]["maximum_radius_m"]
    common_maximum = motion_results["common"]["upstream"]["stale"]["metrics"]["maximum_radius_m"]
    lower_bound, upper_bound = heldout_maximum["nominal_paired_bootstrap_95"]
    (arguments.output / "recovery-motion-effects.tex").write_text(
        r"Without an area cutoff, restoring vision reduces $\pi_1$ mean maximum "
        f"pelvis radius from {heldout_maximum['continuous_mean']:.3f} to "
        f"{heldout_maximum['restored_mean']:.3f} m "
        f"(paired mean difference {heldout_maximum['mean_paired_difference']:+.3f} m; "
        f"nominal 95\\% interval {lower_bound:+.3f} to {upper_bound:+.3f}). "
        "The shared-trajectory difference is "
        f"{common_maximum['mean_paired_difference']:+.3f} m. "
        r"$\pi_2$ ends closer to the station but shows little improvement in "
        "maximum excursion. Both distance summaries include all 64 paired seeds, "
        "including hits. These post-hoc reanalyses are not independent confirmations.\n"
    )
    write_json(
        arguments.output / "summary.json",
        {
            "scope": "Post-hoc descriptive sensitivity; existing trials, not new independent evidence. Intervals are pointwise nominal, not simultaneous or multiplicity adjusted.",
            "radii_m": RADII,
            "horizons_seconds": HORIZONS,
            "archive_sha256": archive_hashes,
            "unique_trials_scored": 1024,
            "pilot_and_preflight_excluded": True,
            "results": results,
            "motion_scope": "Post-hoc maximum and final horizontal pelvis radius from the fixed station origin over four seconds, without a radius cutoff. Negative restored-minus-continuous differences mean less excursion. All paired seeds included regardless of hit or containment; no claim of reduced energy, safer motion, or return to the initial pose.",
            "motion_results": motion_results,
        },
    )


if __name__ == "__main__":
    main()
