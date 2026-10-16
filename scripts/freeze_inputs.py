"""Package already acquired simulator files after checking their expected hashes."""

from __future__ import annotations

import argparse
import json
import tarfile
import tempfile
from pathlib import Path

from evaluate import file_digest, write_json


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--expected-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    manifest = json.loads(arguments.expected_manifest.read_text())
    for relative, expected in manifest.items():
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("Manifest paths must stay inside the simulator directory")
        if file_digest(arguments.source / path) != expected:
            raise ValueError(f"Simulator or model file differs: {relative}")
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dodgeball-input-") as temporary:
        manifest_path = Path(temporary) / "input-files.json"
        write_json(manifest_path, manifest)
        with tarfile.open(arguments.output, "x:gz") as archive:
            for relative in sorted(manifest):
                archive.add(arguments.source / relative, arcname=relative, recursive=False)
            archive.add(manifest_path, arcname="input-files.json")
    print(file_digest(arguments.output))


if __name__ == "__main__":
    main()
