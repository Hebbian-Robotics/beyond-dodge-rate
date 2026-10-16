"""Verify all scientific archives and build the canonical named and anonymous paper."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from evaluate import file_digest, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True, help="Original 2,496-trial archive")
    parser.add_argument(
        "--recovery-data", type=Path, required=True, help="800-trial recovery archive"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--common-data", type=Path, required=True, help="Common-throw control archive"
    )
    parser.add_argument("--tectonic", help="Optional Tectonic executable")
    parser.add_argument(
        "--later-data", type=Path, required=True, help="128-trial later-restoration archive"
    )
    arguments = parser.parse_args()
    repository = Path(__file__).resolve().parent.parent
    arguments.output.mkdir(parents=True, exist_ok=False)
    for script, archive, destination in (
        ("analyze_original_study.py", arguments.data, "original"),
        ("analyze_post_throw_motion.py", arguments.data, "post-throw"),
        ("build_recovery_report.py", arguments.recovery_data, "recovery"),
        ("reproduce_common_throws.py", arguments.common_data, "common"),
    ):
        subprocess.run(
            [
                sys.executable,
                str(repository / "scripts" / script),
                "--data",
                str(archive.resolve()),
                "--output",
                str((arguments.output / destination).resolve()),
            ],
            check=True,
        )
    subprocess.run(
        [
            sys.executable,
            str(repository / "scripts/analyze_recovery_sensitivity.py"),
            "--recovery-data",
            str(arguments.recovery_data.resolve()),
            "--common-data",
            str(arguments.common_data.resolve()),
            "--output",
            str((arguments.output / "recovery-sensitivity").resolve()),
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(repository / "scripts/analyze_later_recovery.py"),
            "--recovery-data",
            str(arguments.recovery_data.resolve()),
            "--later-data",
            str(arguments.later_data.resolve()),
            "--output",
            str((arguments.output / "later-recovery").resolve()),
        ],
        check=True,
    )
    write_json(
        arguments.output / "verification.json",
        {
            "original_data_sha256": file_digest(arguments.data),
            "recovery_data_sha256": file_digest(arguments.recovery_data),
            "common_data_sha256": file_digest(arguments.common_data),
            "later_data_sha256": file_digest(arguments.later_data),
            "later_recovery_new_trial_count": 128,
            "later_recovery_reused_control_count": 256,
            "original_trial_count": 2496,
            "pilot_trial_count": 160,
            "recovery_heldout_trial_count": 640,
            "common_throw_trial_count": 640,
            "common_throw_preflight_trial_count": 20,
            "canonical_source_sha256": file_digest(repository / "paper/main.tex"),
            "demo_appendix_sha256": file_digest(repository / "paper/demo-appendix.tex"),
            "supplement_source_sha256": file_digest(repository / "paper/supplement-main.tex"),
            "extended_methods_sha256": file_digest(repository / "paper/extended-methods.tex"),
            "status": "Verified scientific analysis for the canonical paper; named and anonymous exports share one source",
        },
    )

    command = [
        sys.executable,
        str(repository / "scripts/build_paper.py"),
        "--analysis-output",
        str(arguments.output.resolve()),
        "--output",
        str((arguments.output / "paper").resolve()),
    ]
    if arguments.tectonic:
        command.extend(["--tectonic", arguments.tectonic])
    subprocess.run(command, check=True)


if __name__ == "__main__":
    main()
