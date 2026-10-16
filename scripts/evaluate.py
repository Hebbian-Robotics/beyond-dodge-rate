"""Paired first-throw sensor-freeze/fallback experiment on a frozen native simulator."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import math
import sys
import tarfile
import tempfile
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

import numpy as np
import onnxruntime as ort


def file_digest(path: Path) -> str:
    with path.open("rb") as source:
        return hashlib.file_digest(source, "sha256").hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + "\n")


def validate_replayed_throw(throw: dict[str, Any]) -> None:
    """Require a finite recorded trajectory for the explicit common-throw control."""
    for name in ("start", "velocity"):
        values = throw[name]
        if len(values) != 3 or not all(math.isfinite(value) for value in values):
            raise ValueError("Replayed throws require finite three-dimensional vectors")
    if not math.isfinite(throw["flight"]) or throw["flight"] <= 0:
        raise ValueError("Replayed throws require a finite positive flight time")
    if not math.isclose(throw["time"], 1.0, abs_tol=1e-9) or not isinstance(throw["target"], str):
        raise ValueError("Common throws must use a recorded target and one-second launch")


def evaluate_trial(request: dict[str, Any]) -> dict[str, Any]:
    """Use upstream dynamics, camera, PD loop, collision and fall definitions unchanged."""
    input_directory = Path(request["input_directory"])
    sys.path.insert(0, str(input_directory / "sim"))
    simulator = importlib.import_module("sim")
    controller_module = importlib.import_module("controller")
    weights_directory = input_directory / "weights" / "released"
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
    controller = world.controller
    original_capture = world.capture_depth
    original_act = controller.act
    frozen_depth: Any = None
    held_action: Any = None
    intervention_time: float | None = None
    plain_session: Any = None
    fault_onset = 1.0 + request.get("fault_onset_offset_seconds", 0.0)
    fault_duration = request.get("fault_duration_seconds")
    capture_events: list[dict[str, Any]] = []
    if request["response"] == "plain":
        options = ort.SessionOptions()
        options.intra_op_num_threads = 1
        options.inter_op_num_threads = 1
        plain_session = ort.InferenceSession(
            str(weights_directory / "sonic_plain.onnx"),
            sess_options=options,
            providers=["CPUExecutionProvider"],
        )

    def capture_depth() -> Any:
        nonlocal frozen_depth
        # Always draw the native noise stream, even when the frame is discarded.
        current_depth = original_capture()
        fault_active = (
            request["fault"]
            and world.data.time + 1e-9 >= fault_onset
            and (fault_duration is None or world.data.time + 1e-9 < fault_onset + fault_duration)
        )
        capture_events.append({"time": float(world.data.time), "frozen": fault_active})
        if fault_active:
            if request.get("fault_frame_mode", "freeze") == "zero":
                return np.zeros_like(current_depth)
            if frozen_depth is None:
                frozen_depth = world.previous_capture_before_fault.copy()
            return frozen_depth.copy()
        world.previous_capture_before_fault = current_depth.copy()
        return current_depth

    def act(gyro: Any, joint_positions: Any, joint_velocities: Any, rotation: Any) -> Any:
        nonlocal held_action, intervention_time
        # Upstream act owns history order and appends the previously applied action.
        action = original_act(gyro, joint_positions, joint_velocities, rotation)
        should_intervene = (
            request["response"] != "continue"
            and world.data.time + 1e-9 >= 1.0 + request["response_delay_seconds"]
        )
        if should_intervene:
            if intervention_time is None:
                intervention_time = float(world.data.time)
                held_action = previous_applied_action.copy()
            if request["response"] == "hold":
                action = held_action.copy()
            elif request["response"] == "default":
                # Zero normalized residual retains powered native PD at DEFAULT.
                action = np.zeros(29, dtype=np.float32)
            elif request["response"] == "plain":
                policy = np.concatenate(
                    [np.stack(controller.history[name]).reshape(-1) for name in controller.history]
                )[None]
                plain_outputs = plain_session.run(
                    None,
                    {
                        "tokenizer": controller_module.reference(rotation)[None],
                        "policy": policy,
                    },
                )
                plain_actions = plain_outputs[0]
                if not isinstance(plain_actions, np.ndarray):
                    raise TypeError("Plain policy must return a dense action array")
                action = plain_actions[0]
            else:
                raise ValueError("Unknown response")
            controller.previous_action = action.copy()
        if not np.isfinite(action).all():
            raise ValueError("Nonfinite applied action")
        return action

    world.previous_capture_before_fault = world.previous_capture.copy()
    world.capture_depth = capture_depth
    controller.act = act
    previous_applied_action = controller.previous_action.copy()
    trace: list[dict[str, Any]] = []
    state_frames: list[dict[str, Any]] = []
    launch_state: dict[str, Any] | None = None
    while True:
        # One throw only; identical pre-fault state and random draw for every arm.
        if launch_state is None and world.data.time + 1e-9 >= 1.0:
            launch_state = {"qpos": world.data.qpos.tolist(), "qvel": world.data.qvel.tolist()}
            if request.get("throw", True):
                world.launch()
                if "replayed_throw" in request:
                    # Consume the native random draws first; change only the ball's launch state.
                    throw = request["replayed_throw"]
                    validate_replayed_throw(throw)
                    world.data.qpos[world.ball_q : world.ball_q + 7] = [*throw["start"], 1, 0, 0, 0]
                    world.data.qvel[world.ball_v : world.ball_v + 6] = [*throw["velocity"], 0, 0, 0]
                    for name in ("target", "start", "velocity", "flight"):
                        world.current_throw[name] = throw[name]
                    simulator.mujoco.mj_forward(world.model, world.data)
        finished = world.step(auto=False)
        if request.get("record_states", False):
            state_frames.append({"time": float(world.data.time), "qpos": world.data.qpos.tolist()})
        previous_applied_action = controller.previous_action.copy()
        trace.append(
            {
                "time": float(world.data.time),
                "pelvis_position_m": world.data.xpos[world.root].tolist(),
                "upright_cosine": float(world.data.xmat[world.root].reshape(3, 3)[2, 2]),
            }
        )
        if finished:
            break
    episode = world.episode_result()
    launched = episode["launches"] == 1
    resolved = episode["hits"] + episode["misses"] == 1
    survived = episode["falls"] == 0
    return {
        "seed": request["seed"],
        "arm": request["arm"],
        "fault": request["fault"],
        "response": request["response"],
        "response_delay_seconds": request["response_delay_seconds"],
        "intervention_time": intervention_time,
        "fault_onset_seconds": fault_onset,
        "fault_duration_seconds": fault_duration,
        "fault_frame_mode": request.get("fault_frame_mode", "freeze"),
        "capture_events": capture_events,
        "state_frames": state_frames,
        "launch_state": launch_state,
        "episode": episode,
        "throws": world.records,
        "trace": trace,
        "launched": launched,
        "resolved": resolved,
        "hit": episode["hits"] > 0,
        "fall": not survived,
        "dodge": launched and episode["misses"] == 1,
        "contained_05": episode["station_max"] <= 0.5,
        "contained_10": episode["station_max"] <= 1.0,
        "joint_success_05": launched
        and episode["misses"] == 1
        and survived
        and episode["station_max"] <= 0.5,
        "joint_success_10": launched
        and episode["misses"] == 1
        and survived
        and episode["station_max"] <= 1.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-archive", type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if file_digest(arguments.input_archive) != arguments.input_sha256:
        raise ValueError("Input archive does not match expected digest")
    configuration = json.loads(arguments.config.read_text())
    arguments.output.mkdir(parents=True, exist_ok=False)
    write_json(arguments.output / "configuration.json", configuration)
    started = time.perf_counter()
    with tempfile.TemporaryDirectory(prefix="dodgeball-assurance-input-") as directory:
        input_directory = Path(directory)
        with tarfile.open(arguments.input_archive) as archive:
            archive.extractall(input_directory, filter="data")
        frozen_files = json.loads((input_directory / "input-files.json").read_text())
        for relative_path, expected_digest in frozen_files.items():
            if file_digest(input_directory / relative_path) != expected_digest:
                raise ValueError(f"Input mismatch: {relative_path}")
        requests = [
            {
                **arm,
                "seed": seed,
                "input_directory": str(input_directory),
                "seconds": configuration["episode_seconds"],
            }
            for seed in configuration["seeds"]
            for arm in configuration["arms"]
        ]
        if "replayed_throws" in configuration:
            schedule = configuration["replayed_throws"]
            if set(schedule) != {str(seed) for seed in configuration["seeds"]}:
                raise ValueError("Common-throw schedule must cover exactly the declared seeds")
            for request in requests:
                throw = schedule[str(request["seed"])]
                validate_replayed_throw(throw)
                request["replayed_throw"] = throw
        with ProcessPoolExecutor(max_workers=configuration["workers"]) as executor:
            for completed_count, result in enumerate(executor.map(evaluate_trial, requests), 1):
                write_json(arguments.output / f"{result['seed']}_{result['arm']}.json", result)
                print(
                    json.dumps(
                        {
                            "completed": completed_count,
                            "total": len(requests),
                            "seed": result["seed"],
                            "arm": result["arm"],
                            "fall": result["fall"],
                            "dodge": result["dodge"],
                        }
                    ),
                    flush=True,
                )
    write_json(
        arguments.output / "execution.json",
        {
            "wall_seconds": time.perf_counter() - started,
            "input_sha256": arguments.input_sha256,
            "python": sys.version,
            "numpy": np.__version__,
            "onnxruntime": ort.__version__,
            "trials": len(requests),
            "benchmark_equivalent": False,
        },
    )


if __name__ == "__main__":
    main()
