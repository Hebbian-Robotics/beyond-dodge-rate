"""Derive an immutable deployment input with inactive projectile collisions disabled."""

from __future__ import annotations

import argparse
import difflib
import json
import tarfile
import tempfile
from pathlib import Path

from evaluate import file_digest, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parent-archive", type=Path, required=True)
    parser.add_argument("--parent-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if file_digest(arguments.parent_archive) != arguments.parent_sha256:
        raise ValueError("Parent simulator input changed")
    arguments.output.mkdir(parents=True, exist_ok=False)
    with tempfile.TemporaryDirectory(prefix="dodgeball-corrected-port-") as temporary:
        root = Path(temporary)
        with tarfile.open(arguments.parent_archive) as archive:
            archive.extractall(root, filter="data")
        manifest = json.loads((root / "input-files.json").read_text())
        for relative, digest in manifest.items():
            if file_digest(root / relative) != digest:
                raise ValueError(f"Parent file changed: {relative}")
        simulator_path = root / "sim/sim.py"
        original = simulator_path.read_text()
        replacements = (
            (
                "        self.ball=self.model.body('ball').id;self.ball_geom=self.model.geom('ball_geom').id\n",
                "        self.ball=self.model.body('ball').id;self.ball_geom=self.model.geom('ball_geom').id\n        self.ball_contact_type=int(self.model.geom_contype[self.ball_geom])\n        self.ball_contact_affinity=int(self.model.geom_conaffinity[self.ball_geom])\n",
            ),
            (
                "    def hide_ball(self):\n",
                "    def hide_ball(self):\n        self.model.geom_contype[self.ball_geom]=0\n        self.model.geom_conaffinity[self.ball_geom]=0\n",
            ),
            (
                "    def launch(self):\n        if self.active:return\n",
                "    def launch(self):\n        if self.active:return\n        self.model.geom_contype[self.ball_geom]=self.ball_contact_type\n        self.model.geom_conaffinity[self.ball_geom]=self.ball_contact_affinity\n",
            ),
        )
        corrected = original
        for old, new in replacements:
            if corrected.count(old) != 1:
                raise ValueError("Frozen simulator no longer matches the reviewed correction")
            corrected = corrected.replace(old, new)
        simulator_path.write_text(corrected)
        correction = {
            "parent_archive_sha256": arguments.parent_sha256,
            "original_simulator_sha256": manifest["sim/sim.py"],
            "corrected_simulator_sha256": file_digest(simulator_path),
            "scope": "Disable inactive ball contact type/affinity; restore original active masks at launch. All other checked files and simulation settings are unchanged.",
            "patch": "".join(
                difflib.unified_diff(
                    original.splitlines(keepends=True),
                    corrected.splitlines(keepends=True),
                    fromfile="original/sim/sim.py",
                    tofile="corrected/sim/sim.py",
                )
            ),
        }
        write_json(root / "port-correction.json", correction)
        manifest["sim/sim.py"] = file_digest(simulator_path)
        manifest["port-correction.json"] = file_digest(root / "port-correction.json")
        write_json(root / "input-files.json", manifest)
        with tarfile.open(arguments.output / "input.tar.gz", "w:gz") as archive:
            for relative in sorted([*manifest, "input-files.json"]):
                archive.add(root / relative, arcname=relative, recursive=False)
        write_json(arguments.output / "correction.json", correction)
        write_json(arguments.output / "files.json", manifest)
    print(
        json.dumps(
            {
                "archive_sha256": file_digest(arguments.output / "input.tar.gz"),
                "corrected_simulator_sha256": correction["corrected_simulator_sha256"],
            }
        )
    )


if __name__ == "__main__":
    main()
