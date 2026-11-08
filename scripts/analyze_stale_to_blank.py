"""Audit matched two-second stale/blank/fresh trials and report within-policy contrasts."""

from __future__ import annotations

import argparse
import csv
import json
import math
import tempfile
from itertools import combinations
from pathlib import Path
from typing import Any

import numpy as np
from analyze import verify_outcome_trace
from analyze_later_recovery import unpack_verified_archive
from evaluate import write_json

SEEDS = range(9000, 9064)
STALE = "stale_continuous"
BLANK = "stale_blank_2000"
FRESH = "stale_recover_2000"
ARMS = (STALE, BLANK, FRESH)
TOL = 1e-9
ROOT = Path(__file__).resolve().parent.parent


def verify_trial(trial: dict[str, Any], seed: int, arm: str) -> None:
    verify_outcome_trace(trial)
    if (trial["seed"], trial["arm"]) != (seed, arm):
        raise ValueError("Trial identity differs from filename")
    if not trial["fall"] and not math.isclose(trial["trace"][-1]["time"], 4, abs_tol=TOL):
        raise ValueError("Surviving trial ended early")
    end = trial["trace"][-1]["time"]
    samples = trial["trace"]
    if len(samples) != round(end / 0.02) or any(
        abs(sample["time"] - i * 0.02) > TOL for i, sample in enumerate(samples, 1)
    ):
        raise ValueError("Incomplete physical trace")
    events = trial["capture_events"]
    if len(events) != math.ceil((end - TOL) / 0.04) - 1:
        raise ValueError("Incomplete camera schedule")
    last_fresh = None
    for i, event in enumerate(events, 1):
        t = event["time"]
        fault = t >= 1.16 - TOL and (arm != FRESH or t < 2 - TOL)
        if abs(t - i * 0.04) > TOL or event["frozen"] != fault:
            raise ValueError("Incorrect camera timing")
        supplied = event["supplied_sha256"]
        if not fault:
            if supplied != event["native_sha256"]:
                raise ValueError("Fresh input differs from the native frame")
            last_fresh = supplied
        elif arm == BLANK and t >= 2 - TOL:
            if event["supplied_nonzero"] != 0:
                raise ValueError("Blank input has nonzero pixels")
        elif supplied != last_fresh or not event["supplied_nonzero"]:
            raise ValueError("Stale frame differs from the last pre-fault frame or is blank")


def summarize_policy(directory: Path, archived: Path, policy: str) -> dict[str, Any]:
    trials_dir = directory / policy
    config = json.loads((trials_dir / "configuration.json").read_text())
    if config != json.loads((ROOT / f"configs/stale-to-blank-{policy}-v1.json").read_text()):
        raise ValueError("Unexpected run configuration")
    if config["seeds"] != list(SEEDS) or [a["arm"] for a in config["arms"]] != list(ARMS):
        raise ValueError("Unexpected cohort or conditions")
    expected = {f"{seed}_{arm}.json" for seed in SEEDS for arm in ARMS}
    if {p.name for p in trials_dir.glob("[0-9]*.json")} != expected:
        raise ValueError("Missing or extra trials")
    archived_counts = {
        arm: {"success": 0, "dodge": 0, "identical_traces": 0} for arm in (STALE, FRESH)
    }
    records: dict[str, list[dict[str, Any]]] = {arm: [] for arm in ARMS}
    for seed in SEEDS:
        reference = None
        for arm in ARMS:
            name = f"{seed}_{arm}.json"
            trial = json.loads((trials_dir / name).read_text())
            verify_trial(trial, seed, arm)
            if len(trial["throws"]) != 1 or trial["throws"][0]["resolved_at"] > 2 + TOL:
                raise ValueError("Throw did not resolve by the two-second switch")
            # At t=2 the trace is sampled before the camera capture at that same time.
            switch_frames = [
                e["native_sha256"] for e in trial["capture_events"] if abs(e["time"] - 2) <= TOL
            ]
            if len(switch_frames) != 1:
                raise ValueError("Missing camera sample at the switch")
            history = (
                trial["launch_state"],
                trial["throws"],
                [s for s in trial["trace"] if s["time"] <= 2 + TOL],
                [e for e in trial["capture_events"] if e["time"] < 2 - TOL],
                switch_frames,
            )
            if arm == STALE:
                reference = history
            elif history != reference:
                raise ValueError(f"Unmatched physical or camera history: {policy}/{name}")
            if arm in archived_counts:
                old = json.loads((archived / policy / "heldout" / name).read_text())
                archived_counts[arm]["success"] += old["joint_success_10"]
                archived_counts[arm]["dodge"] += old["dodge"]
                archived_counts[arm]["identical_traces"] += trial["trace"] == old["trace"]
            records[arm].append(
                {
                    "policy": policy,
                    "seed": seed,
                    "condition": arm,
                    "dodge": int(trial["dodge"]),
                    "hit": int(trial["hit"]),
                    "fall": int(trial["fall"]),
                    "aborted": trial["episode"]["aborted"],
                    "contained": int(trial["contained_10"]),
                    "success": int(trial["joint_success_10"]),
                    "max_radius_m": trial["episode"]["station_max"],
                    "final_radius_m": math.hypot(*trial["trace"][-1]["pelvis_position_m"][:2]),
                }
            )
    summaries = {
        arm: {
            **{
                key: sum(r[key] for r in rows)
                for key in ("dodge", "hit", "fall", "aborted", "contained", "success")
            },
            **{
                key: np.mean([r[key] for r in rows]).item()
                for key in ("max_radius_m", "final_radius_m")
            },
        }
        for arm, rows in records.items()
    }
    draws = np.random.default_rng(20261014).integers(0, len(SEEDS), (10000, len(SEEDS)))
    comparisons = {}
    for reference_arm, intervention in combinations(ARMS, 2):
        effects = {}
        for metric in ("success", "contained", "dodge", "max_radius_m", "final_radius_m"):
            diffs = np.array(
                [
                    new[metric] - old[metric]
                    for old, new in zip(records[reference_arm], records[intervention], strict=True)
                ]
            )
            effects[metric] = {
                "difference": diffs.mean().item(),
                "paired_95": np.quantile(diffs[draws].mean(axis=1), [0.025, 0.975]).tolist(),
                "positive_pairs": int((diffs > 0).sum()),
                "negative_pairs": int((diffs < 0).sum()),
            }
            if metric == "success" and not np.any(diffs):
                # With no discordant pairs, the empirical bootstrap has zero width.
                # Invert P(no discordances) = (1 - p)**n for a one-sided bound.
                effects[metric]["discordance_exact_upper_95"] = 1 - 0.05 ** (1 / len(diffs))
        comparisons[f"{intervention}_minus_{reference_arm}"] = effects
    return {
        "execution": json.loads((trials_dir / "execution.json").read_text()),
        "verified_triplets": len(SEEDS),
        "conditions": summaries,
        "contrasts": comparisons,
        "archived_controls": archived_counts,
        "rows": [r for rows in records.values() for r in rows],
    }


def write_switch_table(policies: dict[str, Any], destination: Path) -> None:
    """Typeset the complete control counts and continuous-distance means."""
    lines = [
        r"\begin{tabular}{llrrrrr}\toprule",
        r"Policy & Input after 2 s & Dodged & Area-compliant & Successful & Mean maximum & Mean final\\\midrule",
    ]
    for index, policy in enumerate(("upstream", "team"), 1):
        if index > 1:
            lines.append(r"\midrule")
        for arm_index, (arm, label) in enumerate(
            zip(ARMS, ("Stale", "Blank", "Fresh"), strict=True)
        ):
            row = policies[policy]["conditions"][arm]
            policy_label = rf"$\pi_{index}$" if arm_index == 0 else ""
            lines.append(
                f"{policy_label} & {label} & {row['dodge']} & {row['contained']} & "
                f"{row['success']} & {row['max_radius_m']:.3f} & {row['final_radius_m']:.3f}"
                + r"\\"
            )
    lines.append(r"\bottomrule\end{tabular}")
    destination.write_text("\n".join(lines) + "\n")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trials", type=Path, required=True)
    parser.add_argument("--recovery-data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="stale-blank-archive-") as temp:
        archive_dir = Path(temp)
        digest = unpack_verified_archive(
            args.recovery_data, ROOT / "data/camera-recovery-manifest.json", archive_dir
        )
        policies = {
            policy: summarize_policy(args.trials, archive_dir, policy)
            for policy in ("upstream", "team")
        }
    rows = [row for policy in policies.values() for row in policy.pop("rows")]
    args.output.mkdir(parents=True, exist_ok=False)
    with (args.output / "trials.csv").open("w", newline="") as out:
        writer = csv.DictWriter(out, list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    write_switch_table(policies, args.output / "switch-table.tex")
    write_json(
        args.output / "summary.json",
        {
            "design": "Three local arms per seed, seeds 9000-9063. Exploratory extension on reused seed IDs. Archived trials are separate.",
            "statistics": "Rates use all 64 seeds per policy. Contrasts are paired mean differences; nominal percentile intervals from 10,000 whole-seed bootstrap draws with RNG seed 20261014.",
            "archived_recovery_sha256": digest,
            "runtime_scope": "Published controls have different physical traces. All paired effects use only the three arms rerun on the same local runtime. Joint success requires a dodge, no fall and containment within 1 m throughout the four-second trial.",
            "policies": policies,
        },
    )


if __name__ == "__main__":
    main()
