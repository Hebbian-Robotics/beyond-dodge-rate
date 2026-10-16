"""Render the first declared extension seed; reruns are illustrative, not new samples."""

from __future__ import annotations

import argparse
import importlib
import json
import math
import subprocess
import sys
import tarfile
import tempfile
from itertools import pairwise
from pathlib import Path
from typing import Any

import mujoco
import numpy as np
from evaluate import evaluate_trial, file_digest, write_json
from PIL import Image, ImageDraw, ImageFont
from render_stills import add_ground_line


def render_trial(
    request: dict[str, Any],
    output_path: Path,
    presentation: bool = False,
    pause_frame_indices: frozenset[int] = frozenset(),
) -> dict[str, Any]:
    result = evaluate_trial({**request, "record_states": True})
    simulator = importlib.import_module("sim")
    controller_module = importlib.import_module("controller")
    weights_directory = Path(request["input_directory"]) / "weights/released"
    manifest = controller_module.verify_weights(weights_directory)
    arguments = argparse.Namespace(
        seed=request["seed"],
        device="cpu",
        threads=1,
        weights_dir=str(weights_directory),
        camera_pitch=manifest["camera"]["pitch_deg"],
        dynamics="sonic",
        delay_ms=0,
        camera_hz=25.0,
        clean_depth=False,
        depth="normal",
        no_throws=True,
        seconds=request["seconds"],
        lead=1.0,
    )
    world = simulator.World(arguments, manifest)
    # The installed MuJoCo stubs omit these compiled-extension entry points.
    mujoco_extension: Any = mujoco
    camera = mujoco_extension.MjvCamera()
    camera.lookat[:] = [0.5, 0.0, 0.65]
    camera.distance = 4.4
    camera.azimuth = 100
    camera.elevation = -24
    render_width = 960
    render_height = 720
    world.model.vis.global_.offwidth = render_width
    world.model.vis.global_.offheight = render_height
    encoder = subprocess.Popen(
        [
            "ffmpeg",
            "-y",
            "-loglevel",
            "error",
            "-f",
            "rawvideo",
            "-pixel_format",
            "rgb24",
            "-video_size",
            f"{render_width}x{render_height}",
            "-framerate",
            "25",
            "-i",
            "-",
            "-an",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(output_path),
        ],
        stdin=subprocess.PIPE,
    )
    last_ball_pose: Any = None
    last_ball_time = 0.0
    outcome = result["throws"][0]
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
    try:
        with mujoco.Renderer(world.model, height=render_height, width=render_width) as renderer:
            if encoder.stdin is None:
                raise RuntimeError("Video encoder has no frame input")
            for frame_index, frame in enumerate(result["state_frames"][1::2]):
                world.data.qpos[:] = np.asarray(frame["qpos"])
                retained_marker = False
                if presentation:
                    ball_pose = world.data.qpos[world.ball_q : world.ball_q + 7]
                    if outcome["time"] <= frame["time"] < outcome["resolved_at"]:
                        last_ball_pose = ball_pose.copy()
                        last_ball_time = frame["time"]
                    elif last_ball_pose is not None and frame["time"] - last_ball_time <= 1.0:
                        # Presentation-only marker: never step physics with this pose.
                        ball_pose[:] = last_ball_pose
                        retained_marker = True
                    else:
                        # Native removal can leave the inactive free body moving
                        # outside the arena; it is not part of the measured throw.
                        ball_pose[:3] = [0.0, 0.0, -20.0]
                    world.model.geom_rgba[world.ball_geom] = (
                        [1.0, 0.55, 0.05, 1.0] if retained_marker else [0.9, 0.12, 0.08, 1.0]
                    )
                mujoco_extension.mj_forward(world.model, world.data)
                renderer.update_scene(world.data, camera=camera)
                if presentation:
                    for first_angle, second_angle in pairwise(np.linspace(0, 2 * np.pi, 81)):
                        add_ground_line(
                            renderer.scene,
                            [float(np.cos(first_angle)), float(np.sin(first_angle)), 0.015],
                            [float(np.cos(second_angle)), float(np.sin(second_angle)), 0.015],
                            [0.05, 0.35, 0.40, 1.0],
                        )
                    previous_position = [0.0, 0.0, 0.025]
                    for sample in result["trace"]:
                        if sample["time"] > frame["time"] + 1e-9:
                            break
                        current_position = [*sample["pelvis_position_m"][:2], 0.025]
                        if (
                            np.linalg.norm(
                                np.asarray(current_position) - np.asarray(previous_position)
                            )
                            > 0.001
                        ):
                            add_ground_line(
                                renderer.scene,
                                previous_position,
                                current_position,
                                [0.65, 0.22, 0.01, 1.0],
                            )
                        previous_position = current_position
                rendered_frame = renderer.render()
                repeats = 1
                if presentation:
                    image = Image.fromarray(rendered_frame)
                    drawing = ImageDraw.Draw(image)
                    if world.data.qpos[world.ball_q + 2] > -10:
                        scene_camera = renderer.scene.camera[0]
                        forward = np.asarray(scene_camera.forward)
                        upward = np.asarray(scene_camera.up)
                        rightward = np.cross(forward, upward)
                        offset = world.data.qpos[world.ball_q : world.ball_q + 3] - np.asarray(
                            scene_camera.pos
                        )
                        distance = float(np.dot(offset, forward))
                        if distance > 0:
                            focal_length = (
                                render_height
                                * scene_camera.frustum_near
                                / (scene_camera.frustum_top - scene_camera.frustum_bottom)
                            )
                            horizontal = (
                                render_width / 2
                                + focal_length * float(np.dot(offset, rightward)) / distance
                            )
                            vertical = (
                                render_height / 2
                                - focal_length * float(np.dot(offset, upward)) / distance
                            )
                            color = (255, 193, 99) if retained_marker else (255, 245, 110)
                            drawing.ellipse(
                                (horizontal - 26, vertical - 26, horizontal + 26, vertical + 26),
                                outline=color,
                                width=6,
                            )
                    drawing.rectangle((0, 572, render_width, render_height), fill=(18, 28, 38))
                    resolved = frame["time"] + 1e-9 >= outcome["resolved_at"]
                    status = (
                        {"hits": "CONTACT", "misses": "DODGED", "aborted": "ABORTED"}[
                            outcome["result"]
                        ]
                        if resolved
                        else "Ball in flight"
                        if frame["time"] >= 1.0
                        else "Before launch"
                    )
                    displacement = float(np.linalg.norm(world.data.xpos[world.root][:2]))
                    applied_captures = [
                        event
                        for event in result["capture_events"]
                        if event["time"] < frame["time"] - 1e-9
                    ]
                    camera_status = "FRESH"
                    if applied_captures and applied_captures[-1]["frozen"]:
                        camera_status = (
                            "BLANK" if request.get("fault_frame_mode") == "zero" else "STALE"
                        )
                    drawing.text(
                        (24, 582),
                        f"Sim t={frame['time']:.2f}s | {status} | Depth {camera_status}",
                        font=font,
                        fill="white",
                    )
                    drawing.text(
                        (24, 628),
                        f"Pelvis radius {displacement:.2f}m | limit 1.00m",
                        font=font,
                        fill="white",
                    )
                    note = (
                        "Orange ball: retained last position (visual aid)"
                        if retained_marker
                        else "Teal: 1m boundary; orange: pelvis trajectory"
                    )
                    drawing.text(
                        (24, 674),
                        note,
                        font=font,
                        fill=(255, 193, 99) if retained_marker else "white",
                    )
                    rendered_frame = np.asarray(image)
                    repeats = 52 if frame_index in pause_frame_indices else 2
                for _ in range(repeats):
                    encoder.stdin.write(rendered_frame.tobytes())
            encoder.stdin.close()
        if encoder.wait() != 0:
            raise RuntimeError("Video encoding failed")
    finally:
        if encoder.poll() is None:
            encoder.kill()
            encoder.wait()
    result.pop("state_frames")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-archive", type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--trial-directory", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--presentation", action="store_true")
    parser.add_argument(
        "--arms", nargs=3, default=["nominal", "outage_0_continuous", "outage_320_continuous"]
    )
    arguments = parser.parse_args()
    if file_digest(arguments.input_archive) != arguments.input_sha256:
        raise ValueError("Simulation input digest mismatch")
    configuration = json.loads((arguments.trial_directory / "configuration.json").read_text())
    first_seed = configuration["seeds"][0]
    selected_arms = arguments.arms
    arguments.output.mkdir(parents=True, exist_ok=False)
    references = [
        json.loads((arguments.trial_directory / f"{first_seed}_{arm}.json").read_text())
        for arm in selected_arms
    ]
    # Hold all panels on the first display frame at/after each measured throw
    # resolution, plus the final horizon. Shared indices keep arms synchronized.
    pause_frame_indices = frozenset(
        [
            math.ceil(reference["throws"][0]["resolved_at"] * 25 - 1e-8) - 1
            for reference in references
        ]
        + [round(configuration["episode_seconds"] * 25) - 1]
        + [
            round(
                (1.0 + arm.get("fault_onset_offset_seconds", 0.0) + arm["fault_duration_seconds"])
                * 25
            )
            - 1
            for arm in configuration["arms"]
            if arm["arm"] in selected_arms and arm.get("fault_duration_seconds") is not None
        ]
    )
    pause_times = [(index + 1) / 25 for index in sorted(pause_frame_indices)]
    verification = []
    with tempfile.TemporaryDirectory(prefix="dodgeball-outage-render-") as temporary_directory:
        source_directory = Path(temporary_directory)
        with tarfile.open(arguments.input_archive) as archive:
            archive.extractall(source_directory, filter="data")
        for relative_path, expected_digest in json.loads(
            (source_directory / "input-files.json").read_text()
        ).items():
            if file_digest(source_directory / relative_path) != expected_digest:
                raise ValueError(f"Simulation input changed: {relative_path}")
        sys.path.insert(0, str(source_directory / "sim"))
        for arm_name in selected_arms:
            arm = next(arm for arm in configuration["arms"] if arm["arm"] == arm_name)
            result = render_trial(
                {
                    **arm,
                    "seed": first_seed,
                    "seconds": configuration["episode_seconds"],
                    "input_directory": str(source_directory),
                },
                arguments.output / f"{arm_name}.mp4",
                presentation=arguments.presentation,
                pause_frame_indices=pause_frame_indices,
            )
            reference = json.loads(
                (arguments.trial_directory / f"{first_seed}_{arm_name}.json").read_text()
            )
            for field in ("launch_state", "throws", "trace", "episode"):
                if result[field] != reference[field]:
                    raise ValueError(
                        f"Illustrative rerun differs from retained evidence: {arm_name}/{field}"
                    )
            write_json(arguments.output / f"{arm_name}.json", result)
            verification.append({"arm": arm_name, "exact_rerun_match": True})
    arm_labels = {
        "nominal": "Healthy vision",
        "outage_0_continuous": "Freeze at launch",
        "outage_320_continuous": "Freeze after 320 ms",
        "outage_160_continuous": "Stale depth after 160 ms",
        "zero_160_continuous": "Blank depth after 160 ms",
        "stale_continuous": "Vision stays stale",
        "stale_recover_2000": "Fresh vision at 2 seconds",
        "stale_recover_3000": "Fresh vision at 3 seconds",
    }
    labels = [arm_labels[arm] for arm in selected_arms]
    filter_parts = [
        f"[{index}:v]drawtext=text='{label}':fontcolor=white:fontsize=36:box=1:boxcolor=black@0.7:x=24:y=24[v{index}]"
        for index, label in enumerate(labels)
    ]
    filter_parts.append("[v0][v1][v2]hstack=inputs=3[v]")
    command = ["ffmpeg", "-y", "-loglevel", "error"]
    for arm_name in selected_arms:
        command.extend(["-i", str(arguments.output / f"{arm_name}.mp4")])
    command.extend(
        [
            "-filter_complex",
            ";".join(filter_parts),
            "-map",
            "[v]",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            str(arguments.output / "comparison.mp4"),
        ]
    )
    subprocess.run(command, check=True)
    write_json(
        arguments.output / "verification.json",
        {
            "seed": first_seed,
            "selection": "first declared seed, not outcome selected",
            "role": "illustrative exact reruns, not additional independent samples",
            "arms": verification,
            "video_sha256": file_digest(arguments.output / "comparison.mp4"),
            "panel_pixels": [960, 720],
            "comparison_pixels": [2880, 720],
            "visual_overlays": "teal 1 m boundary; orange measured pelvis ground trajectory; highlighted active ball; retained orange ball marker is display-only",
            "presentation": {
                "enabled": arguments.presentation,
                "speed": 0.5 if arguments.presentation else 1.0,
                "pause_simulation_times_seconds": pause_times if arguments.presentation else [],
                "pause_selection": "first display frame at or after each selected arm resolves its throw, each declared restoration, and final horizon",
                "retained_ball_marker_seconds": 1.0 if arguments.presentation else 0.0,
                "marker_semantics": "last observed position; no continued physics or rebound",
            },
        },
    )


if __name__ == "__main__":
    main()
