"""Run a declared simulation cohort and analyze its complete matched outcomes."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-archive", type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    arguments.output.mkdir(parents=True, exist_ok=False)
    scripts_directory = Path(__file__).resolve().parent
    subprocess.run(
        [
            sys.executable,
            str(scripts_directory / "evaluate.py"),
            "--input-archive",
            str(arguments.input_archive),
            "--input-sha256",
            arguments.input_sha256,
            "--config",
            str(arguments.config),
            "--output",
            str(arguments.output / "trials"),
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(scripts_directory / "analyze.py"),
            str(arguments.output / "trials"),
            "--output",
            str(arguments.output / "analysis"),
        ],
        check=True,
    )


if __name__ == "__main__":
    main()
