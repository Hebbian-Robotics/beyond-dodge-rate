"""Locate area exits relative to throw resolution in the recorded main comparison."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import math
import statistics
import tarfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from analyze import verify_outcome_trace
from evaluate import file_digest, write_json

POLICY_PHASES = {
    "policy-comparison-packaged-merged-v1": "π₁",
    "policy-comparison-team-merged-v1": "π₂",
}
CONDITIONS = {
    "nominal": "Healthy",
    "outage_160_continuous": "Stale",
    "zero_160_continuous": "Blank",
}


def measure_trial(trial: dict[str, Any], policy: str) -> dict[str, Any]:
    verify_outcome_trace(trial)
    if len(trial["throws"]) != 1 or not trial["resolved"]:
        raise ValueError("Post-throw analysis requires one resolved throw per trial")
    resolution_time = float(trial["throws"][0]["resolved_at"])
    first_exit_time = None
    maximum_radius_before_resolution = 0.0
    maximum_radius_after_resolution = 0.0
    previous_time = -math.inf
    for sample in trial["trace"]:
        sample_time = float(sample["time"])
        if not math.isfinite(sample_time) or sample_time <= previous_time:
            raise ValueError("Trace timestamps must be finite and strictly increasing")
        previous_time = sample_time
        radius = math.hypot(*sample["pelvis_position_m"][:2])
        if not math.isfinite(radius):
            raise ValueError("Trace displacement must be finite")
        if sample_time <= resolution_time + 1e-9:
            maximum_radius_before_resolution = max(maximum_radius_before_resolution, radius)
        else:
            maximum_radius_after_resolution = max(maximum_radius_after_resolution, radius)
        if radius > 1.0 and first_exit_time is None:
            first_exit_time = sample_time
    exit_timing = (
        "no_exit"
        if first_exit_time is None
        else "by_resolution"
        if first_exit_time <= resolution_time + 1e-9
        else "after_resolution"
    )
    if (first_exit_time is None) != trial["contained_10"]:
        raise ValueError("Area-exit timing disagrees with the original containment outcome")
    return {
        "policy": policy,
        "seed": trial["seed"],
        "condition": CONDITIONS[trial["arm"]],
        "dodge": trial["dodge"],
        "fall": trial["fall"],
        "in_area": trial["contained_10"],
        "success": trial["joint_success_10"],
        "resolution_seconds": resolution_time,
        "first_exit_seconds": first_exit_time,
        "exit_timing": exit_timing,
        "max_radius_by_resolution_m": maximum_radius_before_resolution,
        "max_radius_after_resolution_m": maximum_radius_after_resolution,
    }


def analyze_archive(data_path: Path, manifest: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    if file_digest(data_path) != manifest["sha256"]:
        raise ValueError("Data archive differs from the recorded scientific package")
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    matching_conditions: dict[tuple[str, int], tuple[Any, Any]] = {}
    seen_trials: set[tuple[str, int, str]] = set()
    with tarfile.open(data_path) as archive:
        for member in archive:
            path_parts = Path(member.name).parts
            if len(path_parts) != 3 or path_parts[0] != "trials":
                continue
            phase = path_parts[1]
            if phase not in POLICY_PHASES or not member.name.endswith(".json"):
                continue
            if path_parts[2] in {"configuration.json", "execution.json"}:
                continue
            source = archive.extractfile(member)
            if source is None:
                raise ValueError("Scientific trial must be a regular archive file")
            raw_trial = source.read()
            if hashlib.sha256(raw_trial).hexdigest() != manifest["files"][member.name]:
                raise ValueError(f"Scientific trial hash differs: {member.name}")
            trial = json.loads(raw_trial)
            policy = POLICY_PHASES[phase]
            if trial["seed"] not in range(7300, 7492) or trial["arm"] not in CONDITIONS:
                raise ValueError("Trial is outside the declared main comparison")
            trial_identity = (policy, trial["seed"], trial["arm"])
            if trial_identity in seen_trials:
                raise ValueError("Duplicate scientific trial")
            seen_trials.add(trial_identity)
            physical_throw = {
                key: trial["throws"][0][key]
                for key in ("time", "target", "start", "velocity", "flight")
            }
            condition_identity = (policy, trial["seed"])
            state_and_throw = (trial["launch_state"], physical_throw)
            reference = matching_conditions.setdefault(condition_identity, state_and_throw)
            if state_and_throw != reference:
                raise ValueError("Camera conditions do not have matched launch states and throws")
            measurement = measure_trial(trial, policy)
            groups[f"{policy}/{measurement['condition']}"].append(measurement)
    if (
        len(seen_trials) != 1152
        or len(groups) != 6
        or any(len(rows) != 192 for rows in groups.values())
    ):
        raise ValueError("Main-comparison coverage is incomplete")
    return groups


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    repository = Path(__file__).resolve().parent.parent
    manifest = json.loads((repository / "data/manifest.json").read_text())
    groups = analyze_archive(arguments.data, manifest)
    published = json.loads((repository / "results/summary.json").read_text())
    summary_rows = []
    measurements = []
    for group_name, group_rows in sorted(groups.items()):
        group_rows.sort(key=lambda row: row["seed"])
        policy, condition = group_name.split("/")
        counts = {
            name: sum(row[name] for row in group_rows)
            for name in ("dodge", "fall", "in_area", "success")
        }
        published_row = next(
            row
            for row in published["conditions"]
            if row["policy"] == policy and row["input"] == condition
        )
        for measured_key, published_key in (
            ("dodge", "dodged"),
            ("fall", "falls"),
            ("in_area", "in_area"),
            ("success", "success"),
        ):
            if counts[measured_key] != published_row[published_key]:
                raise ValueError("Recomputed counts differ from the published comparison")
        summary_rows.append(
            {
                "policy": policy,
                "condition": condition,
                "trials": len(group_rows),
                **counts,
                "area_exits_by_resolution": sum(
                    row["exit_timing"] == "by_resolution" for row in group_rows
                ),
                "area_exits_after_resolution": sum(
                    row["exit_timing"] == "after_resolution" for row in group_rows
                ),
                "dodges_with_area_exit_after_resolution": sum(
                    row["dodge"] and row["exit_timing"] == "after_resolution" for row in group_rows
                ),
                "median_max_radius_by_resolution_m": statistics.median(
                    row["max_radius_by_resolution_m"] for row in group_rows
                ),
                "median_max_radius_after_resolution_m": statistics.median(
                    row["max_radius_after_resolution_m"] for row in group_rows
                ),
            }
        )
        measurements.extend(group_rows)
    arguments.output.mkdir(parents=True, exist_ok=False)
    write_json(
        arguments.output / "summary.json",
        {
            "analysis_status": "post_hoc_descriptive_reanalysis",
            "scientific_data_sha256": manifest["sha256"],
            "trial_count": len(measurements),
            "area_radius_m": 1.0,
            "timing_rule": "First sampled exit strictly after native throw resolution; ties count as by-resolution. Traces sampled at 50 Hz; no interpolation.",
            "scope": "Recorded encounters only; this is not a neural explanation, new simulation, or independent confirmation.",
            "conditions": summary_rows,
        },
    )
    csv_buffer = io.StringIO(newline="")
    csv_writer = csv.DictWriter(csv_buffer, fieldnames=list(measurements[0]))
    csv_writer.writeheader()
    csv_writer.writerows(measurements)
    (arguments.output / "trials.csv").write_text(csv_buffer.getvalue())
    print(
        json.dumps({"verified_trials": len(measurements), "conditions": summary_rows}), flush=True
    )


if __name__ == "__main__":
    main()
