"""Render encounter and final-horizon states from verified first-seed replays."""

from __future__ import annotations

import argparse
import importlib
import json
import math
import sys
import tarfile
import tempfile
from itertools import pairwise
from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import mujoco
import numpy as np
from evaluate import evaluate_trial, file_digest, write_json


def add_ground_line(scene: Any, start: list[float], end: list[float], color: list[float]) -> None:
    extension: Any = mujoco
    geometry = scene.geoms[scene.ngeom]
    extension.mjv_initGeom(
        geometry,
        extension.mjtGeom.mjGEOM_LINE,
        np.zeros(3),
        np.zeros(3),
        np.eye(3).ravel(),
        np.asarray(color, dtype=np.float32),
    )
    extension.mjv_connector(
        geometry, extension.mjtGeom.mjGEOM_LINE, 3.0, np.asarray(start), np.asarray(end)
    )
    scene.ngeom += 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-archive", type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--trial-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--arms", nargs=3, default=["nominal", "outage_0_continuous", "outage_320_continuous"]
    )
    arguments = parser.parse_args()
    if file_digest(arguments.input_archive) != arguments.input_sha256:
        raise ValueError("Simulation input digest mismatch")
    configuration = json.loads((arguments.trial_directory / "configuration.json").read_text())
    arms = arguments.arms
    first_seed = configuration["seeds"][0]
    references = [
        json.loads((arguments.trial_directory / f"{first_seed}_{arm}.json").read_text())
        for arm in arms
    ]
    contact_times = [
        reference["throws"][0]["resolved_at"]
        for reference in references
        if reference["throws"][0]["result"] == "hits"
    ]
    contact_time = (
        min(contact_times)
        if contact_times
        else min(reference["throws"][0]["resolved_at"] for reference in references)
    )
    # Select the last common recorded control state before actual contact,
    # rather than choosing arbitrary video times or an especially good pose.
    encounter_time = max(
        sample["time"] for sample in references[1]["trace"] if sample["time"] < contact_time
    )
    times = (encounter_time, references[0]["trace"][-1]["time"])
    arguments.output.mkdir(parents=True, exist_ok=False)
    records = []
    with tempfile.TemporaryDirectory(prefix="dodgeball-event-stills-") as temporary:
        source = Path(temporary)
        with tarfile.open(arguments.input_archive) as archive:
            archive.extractall(source, filter="data")
        for relative, digest in json.loads((source / "input-files.json").read_text()).items():
            if file_digest(source / relative) != digest:
                raise ValueError(f"Simulation input changed: {relative}")
        sys.path.insert(0, str(source / "sim"))
        simulator = importlib.import_module("sim")
        controller = importlib.import_module("controller")
        weights = source / "weights/released"
        manifest = controller.verify_weights(weights)
        for arm, reference in zip(arms, references, strict=True):
            declared = next(item for item in configuration["arms"] if item["arm"] == arm)
            result = evaluate_trial(
                {
                    **declared,
                    "seed": first_seed,
                    "seconds": 4.0,
                    "input_directory": str(source),
                    "record_states": True,
                }
            )
            for field in ("launch_state", "throws", "trace", "episode"):
                if result[field] != reference[field]:
                    raise ValueError(f"Still replay differs from retained evidence: {arm}/{field}")
            world = simulator.World(
                argparse.Namespace(
                    seed=first_seed,
                    device="cpu",
                    threads=1,
                    weights_dir=str(weights),
                    camera_pitch=manifest["camera"]["pitch_deg"],
                    dynamics="sonic",
                    delay_ms=0,
                    camera_hz=25.0,
                    clean_depth=False,
                    depth="normal",
                    no_throws=True,
                    seconds=4.0,
                    lead=1.0,
                ),
                manifest,
            )
            extension: Any = mujoco
            camera = extension.MjvCamera()
            camera.lookat[:] = [0.5, 0.0, 0.65]
            camera.distance = 4.4
            camera.azimuth = 100
            camera.elevation = -24
            # Appearance only; evaluate_trial above uses the unchanged model.
            floor = world.model.geom("floor").id
            world.model.geom_matid[floor] = -1
            world.model.geom_rgba[floor] = [0.88, 0.90, 0.91, 1.0]
            world.model.geom_rgba[world.ball_geom] = [0.92, 0.12, 0.08, 1.0]
            world.model.vis.global_.offwidth = 2560
            world.model.vis.global_.offheight = 1440
            with mujoco.Renderer(world.model, height=1440, width=2560) as renderer:
                for row, simulated_time in enumerate(times):
                    frame = next(
                        frame
                        for frame in result["state_frames"]
                        if math.isclose(frame["time"], simulated_time, abs_tol=1e-9)
                    )
                    world.data.qpos[:] = frame["qpos"]
                    if simulated_time >= result["throws"][0]["resolved_at"]:
                        world.data.qpos[world.ball_q : world.ball_q + 3] = [0.0, 0.0, -20.0]
                    extension.mj_forward(world.model, world.data)
                    renderer.update_scene(world.data, camera=camera)
                    angles = np.linspace(0, 2 * np.pi, 81)
                    for first, second in pairwise(angles):
                        add_ground_line(
                            renderer.scene,
                            [float(np.cos(first)), float(np.sin(first)), 0.015],
                            [float(np.cos(second)), float(np.sin(second)), 0.015],
                            [0.05, 0.35, 0.40, 1.0],
                        )
                    previous = [0.0, 0.0, 0.025]
                    for sample in result["trace"]:
                        if sample["time"] > simulated_time + 1e-9:
                            break
                        position = [*sample["pelvis_position_m"][:2], 0.025]
                        if np.linalg.norm(np.asarray(position) - np.asarray(previous)) > 0.001:
                            add_ground_line(
                                renderer.scene, previous, position, [0.65, 0.22, 0.01, 1.0]
                            )
                        previous = position
                    filename = f"{arm}_{row}.png"
                    plt.imsave(arguments.output / filename, renderer.render())
                    records.append(
                        {
                            "arm": arm,
                            "row": row,
                            "time": simulated_time,
                            "file": filename,
                            "sha256": file_digest(arguments.output / filename),
                        }
                    )
            write_json(arguments.output / f"{arm}.json", reference)
    write_json(
        arguments.output / "verification.json",
        {
            "seed": first_seed,
            "selection": "first declared seed; last common control state before earliest contact (or earliest native throw resolution if all dodge), and declared final horizon",
            "encounter_event": "contact" if contact_times else "throw resolution",
            "contact_time": contact_time,
            "encounter_time": encounter_time,
            "final_time": times[1],
            "render_pixels": [2560, 1440],
            "exact_replay_match": True,
            "visual_overlays": "1 m radius around initial pelvis position; orange measured pelvis ground trace; red active ball; appearance changes only",
            "frames": records,
        },
    )


if __name__ == "__main__":
    main()
