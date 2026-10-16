"""Recompute the study's analyses and figures from its scientific data package."""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tarfile
import tempfile
from pathlib import Path

from evaluate import file_digest, write_json
from paper_sections import (
    generate_handling_replication_material,
    generate_outage_material,
    generate_plain_language_sections,
    generate_policy_comparison_material,
    generate_radius_horizon_sensitivity,
    generate_replication_material,
    generate_simulation_figure,
    generate_stale_material,
    generate_team_encounter_figure,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    repository = Path(__file__).resolve().parent.parent
    manifest = json.loads((repository / "data/manifest.json").read_text())
    if file_digest(arguments.data) != manifest["sha256"]:
        raise ValueError("Scientific data archive does not match its published hash")
    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="beyond-dodge-rate-") as temporary:
        dataset = Path(temporary)
        with tarfile.open(arguments.data) as archive:
            archive.extractall(dataset, filter="data")
        for relative, expected in manifest["files"].items():
            if file_digest(dataset / relative) != expected:
                raise ValueError(f"Scientific data changed: {relative}")
        if json.loads((dataset / "files.json").read_text()) != manifest["files"]:
            raise ValueError("Archive manifest differs from the published file manifest")
        input_root = dataset / "trials"
        phase_names = sorted(path.name for path in input_root.iterdir() if path.is_dir())
        trial_count = 0
        for phase in phase_names:
            configuration = json.loads((input_root / phase / "configuration.json").read_text())
            expected_configuration = json.loads(
                (repository / "configs" / f"{phase}.json").read_text()
            )
            if configuration != expected_configuration:
                raise ValueError(f"Scientific configuration differs: {phase}")
            if configuration["environment_version"] != "inactive-ball-collision-corrected-v1":
                raise ValueError("All publication cohorts must use corrected physics")
            trial_count += len(configuration["seeds"]) * len(configuration["arms"])
            subprocess.run(
                [
                    sys.executable,
                    str(repository / "scripts/analyze.py"),
                    str(input_root / phase),
                    "--output",
                    str(output / phase),
                ],
                check=True,
            )
        if trial_count != manifest["trial_count"] or len(phase_names) != 8:
            raise ValueError("Incomplete study cohort coverage")
        generated = output / "generated"
        generated.mkdir()
        for phase, generator in (
            ("roboletics-outage-v1", generate_outage_material),
            ("roboletics-outage-confirmation-v1", generate_replication_material),
            ("roboletics-stale-handling-v1", generate_stale_material),
            ("roboletics-stale-replication-v1", generate_handling_replication_material),
        ):
            generator(json.loads((output / phase / "summary.json").read_text()), generated)
        for label, generator in (
            ("timing", generate_simulation_figure),
            ("handling", generate_team_encounter_figure),
        ):
            directory = dataset / "stills" / label
            frame_manifest = {
                path.name: file_digest(path) for path in directory.iterdir() if path.is_file()
            }
            manifest_path = output / f"{label}-frames.json"
            write_json(manifest_path, frame_manifest)
            generator(directory, manifest_path, generated)
        generate_radius_horizon_sensitivity(
            input_root / "roboletics-stale-replication-v1", generated
        )
        generate_policy_comparison_material(input_root, output, generated)
        generate_plain_language_sections(output, generated)
        for name in (
            "simulation-snapshots.png",
            "team-encounter.png",
            "outage-grid.png",
            "radius-horizon-sensitivity.png",
        ):
            if file_digest(generated / name) != file_digest(dataset / "reference-figures" / name):
                raise ValueError(f"Figure pixels differ from the checked reference: {name}")
        write_json(
            output / "verification.json",
            {
                "scientific_data_sha256": manifest["sha256"],
                "verified_input_files": len(manifest["files"]),
                "trials": trial_count,
                "phases": phase_names,
                "main_figure_pixels_match": True,
            },
        )


if __name__ == "__main__":
    main()
