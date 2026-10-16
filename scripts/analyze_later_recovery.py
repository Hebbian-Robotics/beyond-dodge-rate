"""Verify the later-restoration extension against its archived paired controls."""

from __future__ import annotations

import argparse
import csv
import json
import math
import tarfile
import tempfile
from pathlib import Path
from typing import Any

import numpy as np
from analyze import verify_outcome_trace
from build_recovery_report import verify_recovery_pairs
from evaluate import file_digest, write_json

SEEDS = list(range(9000, 9064))
CONDITIONS = ("stale_continuous", "stale_recover_2000", "stale_recover_3000")


def unpack_verified_archive(archive_path: Path, manifest_path: Path, destination: Path) -> str:
    manifest = json.loads(manifest_path.read_text())
    if file_digest(archive_path) != manifest["sha256"]:
        raise ValueError("Archive digest differs from its retained manifest")
    with tarfile.open(archive_path) as archive:
        archive.extractall(destination, filter="data")
    actual_files = {
        path.relative_to(destination).as_posix()
        for path in destination.rglob("*")
        if path.is_file()
    }
    if actual_files != set(manifest["files"]):
        raise ValueError("Archive has missing or additional files")
    for filename, digest in manifest["files"].items():
        if file_digest(destination / filename) != digest:
            raise ValueError(f"Trial digest differs: {filename}")
    return manifest["sha256"]


def summarize_trial(trial: dict[str, Any]) -> dict[str, Any]:
    verify_outcome_trace(trial)
    trace = trial["trace"]
    if len(trace) != 200 or any(
        not math.isclose(sample["time"], (index + 1) * 0.02, abs_tol=1e-9)
        for index, sample in enumerate(trace)
    ):
        raise ValueError("Expected a complete four-second recording")
    radii = [math.hypot(*sample["pelvis_position_m"][:2]) for sample in trace]
    first_exit = next(
        (sample["time"] for sample, radius in zip(trace, radii, strict=True) if radius > 1), None
    )
    return {
        "seed": trial["seed"],
        "condition": trial["arm"],
        "dodge": int(trial["dodge"]),
        "contained": int(trial["contained_10"]),
        "fall": int(trial["fall"]),
        "aborted": trial["episode"]["aborted"],
        "success": int(trial["joint_success_10"]),
        "maximum_radius_m": max(radii),
        "final_radius_m": radii[-1],
        "first_exit_seconds": first_exit,
    }


def analyze_policy(
    old_directory: Path, later_directory: Path, repository: Path, policy: str
) -> dict[str, Any]:
    old_audit = verify_recovery_pairs(old_directory, SEEDS)
    configuration = json.loads((later_directory / "configuration.json").read_text())
    declared = json.loads(
        (repository / f"configs/camera-recovery-later-{policy}-v1.json").read_text()
    )
    if configuration != declared or configuration["seeds"] != SEEDS:
        raise ValueError("Later-recovery configuration differs from the fixed design")
    records = []
    for seed in SEEDS:
        controls = [
            json.loads((old_directory / f"{seed}_{arm}.json").read_text()) for arm in CONDITIONS[:2]
        ]
        later = json.loads((later_directory / f"{seed}_stale_recover_3000.json").read_text())
        if later["seed"] != seed or later["arm"] != CONDITIONS[2]:
            raise ValueError("Later-recovery identity differs from its filename")
        if (
            later["launch_state"] != controls[0]["launch_state"]
            or later["throws"] != controls[0]["throws"]
        ):
            raise ValueError(
                "Later-recovery launch state or resolved throw differs from its control"
            )
        before_later = [sample for sample in later["trace"] if sample["time"] < 3 - 1e-9]
        before_control = [sample for sample in controls[0]["trace"] if sample["time"] < 3 - 1e-9]
        if not before_later or before_later != before_control:
            raise ValueError("Later-recovery physical trace differs before restoration")
        captures = later["capture_events"]
        if (
            not captures
            or not any(event["time"] >= 3 - 1e-9 and not event["frozen"] for event in captures)
            or any(
                event["frozen"] != (1.16 - 1e-9 <= event["time"] < 3 - 1e-9) for event in captures
            )
            or later["fault_frame_mode"] != "freeze"
            or not math.isclose(later["fault_duration_seconds"], 1.84, abs_tol=1e-12)
        ):
            raise ValueError("Actual camera restoration differs from the declared schedule")
        for trial in [*controls, later]:
            records.append(summarize_trial(trial))
    by_condition = {
        condition: [record for record in records if record["condition"] == condition]
        for condition in CONDITIONS
    }
    summaries = {}
    for condition, trials in by_condition.items():
        summaries[condition] = {
            **{
                outcome: sum(trial[outcome] for trial in trials)
                for outcome in ("dodge", "contained", "fall", "aborted", "success")
            },
            "seeds": len(trials),
            "maximum_radius_mean_m": float(
                np.mean([trial["maximum_radius_m"] for trial in trials])
            ),
            "final_radius_mean_m": float(np.mean([trial["final_radius_m"] for trial in trials])),
            "exits_by_three_seconds": sum(
                trial["first_exit_seconds"] is not None and trial["first_exit_seconds"] <= 3 + 1e-9
                for trial in trials
            ),
            "exits_after_three_seconds": sum(
                trial["first_exit_seconds"] is not None and trial["first_exit_seconds"] > 3 + 1e-9
                for trial in trials
            ),
        }
    indices = np.random.default_rng(20261017).integers(0, 64, (10000, 64))
    comparisons = {}
    for reference in CONDITIONS[:2]:
        effects = {}
        for outcome in ("success", "maximum_radius_m", "final_radius_m"):
            differences = np.array(
                [
                    later[outcome] - control[outcome]
                    for later, control in zip(
                        by_condition[CONDITIONS[2]], by_condition[reference], strict=True
                    )
                ]
            )
            effects[outcome] = {
                "mean_difference": float(differences.mean()),
                "nominal_paired_bootstrap_95": np.quantile(
                    differences[indices].mean(axis=1), [0.025, 0.975]
                ).tolist(),
                "positive_seeds": int((differences > 1e-12).sum()),
                "negative_seeds": int((differences < -1e-12).sum()),
                "equal_seeds": int((np.abs(differences) <= 1e-12).sum()),
            }
        comparisons[f"later_minus_{reference}"] = effects
    return {
        "summaries": summaries,
        "comparisons": comparisons,
        "records": records,
        "audit": {
            "archived_control_audit": old_audit,
            "new_trials": 64,
            "identical_pre_three_second_trace_pairs": 64,
            "matching_native_throw_records": 64,
            "camera_schedules_verified": 64,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recovery-data", type=Path, required=True)
    parser.add_argument("--later-data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    repository = Path(__file__).resolve().parent.parent
    arguments.output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="later-recovery-") as temporary:
        dataset = Path(temporary)
        old_hash = unpack_verified_archive(
            arguments.recovery_data,
            repository / "data/camera-recovery-manifest.json",
            dataset / "old",
        )
        later_hash = unpack_verified_archive(
            arguments.later_data,
            repository / "data/later-recovery-manifest.json",
            dataset / "later",
        )
        results = {
            policy: analyze_policy(
                dataset / "old" / policy / "heldout", dataset / "later" / policy, repository, policy
            )
            for policy in ("upstream", "team")
        }
    records = [
        {"policy": policy, **record}
        for policy, result in results.items()
        for record in result.pop("records")
    ]
    with (arguments.output / "trials.csv").open("w", newline="") as destination:
        writer = csv.DictWriter(destination, fieldnames=list(records[0]))
        writer.writeheader()
        writer.writerows(records)
    write_json(
        arguments.output / "summary.json",
        {
            "scope": "Exploratory timing extension using the original held-out seeds and archived controls; 128 new simulations and 256 reused controls. All intervals nominal; no independent replication or optimal-time claim.",
            "recovery_data_sha256": old_hash,
            "later_data_sha256": later_hash,
            "results": results,
        },
    )
    lines = [
        "# Later camera restoration",
        "",
        "Exploratory extension on the existing held-out seeds. Each row has 64 trials.",
        "",
        "| Policy | Condition | Dodge | Inside 1 m | Overall success | Maximum radius mean (m) | Final radius mean (m) |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for policy, result in results.items():
        for condition, summary in result["summaries"].items():
            lines.append(
                f"| {policy} | {condition} | {summary['dodge']}/64 | {summary['contained']}/64 | {summary['success']}/64 | {summary['maximum_radius_mean_m']:.3f} | {summary['final_radius_mean_m']:.3f} |"
            )
    (arguments.output / "results.md").write_text("\n".join(lines) + "\n")
    table_rows = [
        r"\begin{tabular}{llrrr}\toprule",
        r"Policy & Vision resumes & Dodge & In area & Success\\\midrule",
    ]
    labels = {"stale_continuous": "Never", "stale_recover_2000": "2 s", "stale_recover_3000": "3 s"}
    for policy, result in results.items():
        for index, (condition, summary) in enumerate(result["summaries"].items()):
            label = (r"$\pi_1$" if policy == "upstream" else r"$\pi_2$") if index == 0 else ""
            table_rows.append(
                f"{label} & {labels[condition]} & {summary['dodge']}/64 & {summary['contained']}/64 & {summary['success']}/64"
                + r"\\"
            )
        if policy == "upstream":
            table_rows.append(r"\midrule")
    table_rows.append(r"\bottomrule\end{tabular}")
    (arguments.output / "later-recovery-table.tex").write_text("\n".join(table_rows) + "\n")
    paragraphs = []
    for policy, result in results.items():
        summary = result["summaries"]
        effect = result["comparisons"]["later_minus_stale_recover_2000"]["success"]
        lower_bound, upper_bound = effect["nominal_paired_bootstrap_95"]
        label = r"$\pi_1$" if policy == "upstream" else r"$\pi_2$"
        paragraphs.append(
            f"For {label}, overall success is {summary['stale_continuous']['success']}/64 "
            f"without restoration, {summary['stale_recover_2000']['success']}/64 with restoration at two seconds, "
            f"and {summary['stale_recover_3000']['success']}/64 at three seconds. "
            f"The three-minus-two-second difference is {100 * effect['mean_difference']:+.1f} percentage points "
            f"(nominal 95\\% paired interval {100 * lower_bound:+.1f} to {100 * upper_bound:+.1f})."
        )
    (arguments.output / "later-recovery-effects.tex").write_text("\n\n".join(paragraphs) + "\n")


if __name__ == "__main__":
    main()
