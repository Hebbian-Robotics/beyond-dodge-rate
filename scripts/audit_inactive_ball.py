"""Observe inactive-ball contacts and visibility without changing native physics."""

from __future__ import annotations

import argparse
import importlib
import json
import sys
import tarfile
import tempfile
from pathlib import Path
from typing import Any

import mujoco
import numpy as np
from evaluate import evaluate_trial, file_digest, write_json


def audit_trial(request: dict[str, Any]) -> dict[str, Any]:
    simulator: Any = importlib.import_module("sim")
    native_world_class = simulator.World
    # MuJoCo's compiled entry points are absent from the installed type stubs.
    extension: Any = mujoco
    native_step = extension.mj_step
    contacts = []
    visibility = []
    worlds: list[Any] = []

    class ObservedWorld(native_world_class):
        def __init__(self, *arguments: Any, **keywords: Any) -> None:
            super().__init__(*arguments, **keywords)
            worlds.append(self)

        def capture_depth(self) -> Any:
            depth = super().capture_depth()
            if not self.active and self.ball_pixels:
                visibility.append({"time": float(self.data.time), "pixels": self.ball_pixels})
            return depth

    def observed_step(model: Any, data: Any) -> None:
        native_step(model, data)
        if not worlds or worlds[-1].active:
            return
        world = worlds[-1]
        for index, contact in enumerate(data.contact[: data.ncon]):
            geoms = (contact.geom1, contact.geom2)
            if world.ball_geom not in geoms:
                continue
            other = geoms[1] if geoms[0] == world.ball_geom else geoms[0]
            if model.geom_bodyid[other] in (0, world.ball):
                continue
            force = np.zeros(6)
            extension.mj_contactForce(model, data, index, force)
            contacts.append(
                {
                    "time": float(data.time),
                    "body": model.body(model.geom_bodyid[other]).name,
                    "normal_force_n": float(force[0]),
                    "ball_position": data.qpos[world.ball_q : world.ball_q + 3].tolist(),
                }
            )

    simulator.World = ObservedWorld
    extension.mj_step = observed_step
    try:
        result = evaluate_trial(request)
    finally:
        extension.mj_step = native_step
        simulator.World = native_world_class
    return {
        "trial": result,
        "inactive_ball_robot_contacts": contacts,
        "inactive_ball_visible_captures": visibility,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-archive", type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--trial-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if file_digest(arguments.input_archive) != arguments.input_sha256:
        raise ValueError("Audit input archive changed")
    arguments.output.mkdir(parents=True, exist_ok=False)
    configuration = json.loads((arguments.trial_directory / "configuration.json").read_text())
    with tempfile.TemporaryDirectory(prefix="dodgeball-removal-audit-") as temporary:
        source = Path(temporary)
        with tarfile.open(arguments.input_archive) as archive:
            archive.extractall(source, filter="data")
        for relative, digest in json.loads((source / "input-files.json").read_text()).items():
            if file_digest(source / relative) != digest:
                raise ValueError(f"Captured audit input changed: {relative}")
        sys.path.insert(0, str(source / "sim"))
        for seed in (7000, 7100):
            for arm in configuration["arms"]:
                result = audit_trial(
                    {**arm, "seed": seed, "seconds": 4.0, "input_directory": str(source)}
                )
                reference = json.loads(
                    (arguments.trial_directory / f"{seed}_{arm['arm']}.json").read_text()
                )
                for field in ("launch_state", "throws", "trace", "episode"):
                    if result["trial"][field] != reference[field]:
                        raise ValueError(
                            f"Read-only instrumentation changed {seed}/{arm['arm']}/{field}"
                        )
                write_json(arguments.output / f"{seed}_{arm['arm']}.json", result)
                print(
                    json.dumps(
                        {
                            "seed": seed,
                            "arm": arm["arm"],
                            "inactive_contacts": len(result["inactive_ball_robot_contacts"]),
                            "inactive_visible_captures": len(
                                result["inactive_ball_visible_captures"]
                            ),
                        }
                    ),
                    flush=True,
                )


if __name__ == "__main__":
    main()
