"""Reproduce the separate common-throw control and its implementation preflight."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from evaluate import file_digest, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    repository = Path(__file__).resolve().parent.parent
    manifest = json.loads((repository / "data/common-throw-manifest.json").read_text())
    if file_digest(arguments.data) != manifest["sha256"]:
        raise ValueError("Common-throw archive differs from its recorded digest")
    arguments.output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="dodge-common-throws-") as temporary:
        dataset = Path(temporary)
        with tarfile.open(arguments.data) as archive:
            archive.extractall(dataset, filter="data")
        actual_files = {path.relative_to(dataset).as_posix() for path in dataset.glob("*/*/*.json")}
        if actual_files != set(manifest["files"]):
            raise ValueError("Common-throw archive has missing or additional files")
        for filename, digest in manifest["files"].items():
            if file_digest(dataset / filename) != digest:
                raise ValueError(f"Common-throw record differs from its digest: {filename}")
        for cohort in ("preflight", "control"):
            subprocess.run(
                [
                    sys.executable,
                    str(repository / "scripts/analyze_common_throws.py"),
                    "--upstream",
                    str(dataset / "upstream" / cohort),
                    "--team",
                    str(dataset / "team" / cohort),
                    "--output",
                    str((arguments.output / cohort).resolve()),
                ],
                check=True,
            )
    counts = {
        cohort: json.loads((arguments.output / cohort / "summary.json").read_text())["trial_count"]
        for cohort in ("preflight", "control")
    }
    if counts != {"preflight": 20, "control": 640}:
        raise ValueError("Common-throw cohort coverage differs from the fixed design")
    write_json(
        arguments.output / "verification.json",
        {
            "data_sha256": manifest["sha256"],
            "trial_counts": counts,
            "preflight_reported_separately": True,
            "scope": "Exploratory replay of a balanced recorded-throw pool; robot states can differ across policies",
        },
    )


if __name__ == "__main__":
    main()
