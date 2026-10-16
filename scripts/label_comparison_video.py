"""Add policy symbols to the existing presentation header of a verified replay."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
from pathlib import Path

from evaluate import file_digest, write_json
from PIL import Image, ImageDraw, ImageFont


def video_stream(path: Path) -> dict[str, str | int]:
    completed = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,nb_frames,r_frame_rate",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(completed.stdout)["streams"][0]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--input-sha256", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--policy", choices=("π₁", "π₂"), required=True)
    parser.add_argument("--labels", nargs=3, required=True)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise FileExistsError("Choose a new output; preserve the source replay")
    if file_digest(arguments.input) != arguments.input_sha256:
        raise ValueError("Replay source hash differs from the declared input")
    source_stream = video_stream(arguments.input)
    if (source_stream["width"], source_stream["height"]) != (2880, 720):
        raise ValueError("Expected the existing three-panel replay presentation")
    header_height = 72
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 36)
    header = Image.new("RGB", (2880, header_height), "#13202c")
    drawing = ImageDraw.Draw(header)
    for panel_index, label in enumerate(arguments.labels):
        text = f"{arguments.policy} · {label}"
        bounds = drawing.textbbox((0, 0), text, font=font)
        if bounds[2] - bounds[0] > 912:
            raise ValueError("Policy header exceeds its panel width")
        drawing.text((960 * panel_index + 24, 18), text, font=font, fill="white")
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="policy-replay-header-") as temporary:
        header_path = Path(temporary) / "header.png"
        header.save(header_path)
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-i",
                str(arguments.input),
                "-loop",
                "1",
                "-i",
                str(header_path),
                "-filter_complex",
                "[0:v][1:v]overlay=0:0:shortest=1",
                "-an",
                "-c:v",
                "libx264",
                "-threads",
                "4",
                "-crf",
                "18",
                "-pix_fmt",
                "yuv420p",
                "-movflags",
                "+faststart",
                str(arguments.output),
            ],
            check=True,
        )
    if video_stream(arguments.output) != source_stream:
        raise ValueError("Replay dimensions, frame count or frame rate changed")
    write_json(
        arguments.output.with_suffix(".json"),
        {
            "source_sha256": arguments.input_sha256,
            "output_sha256": file_digest(arguments.output),
            "policy": arguments.policy,
            "condition_labels": arguments.labels,
            "video_stream": source_stream,
            "changed_region": {"x": 0, "y": 0, "width": 2880, "height": header_height},
            "scope": "Presentation header only; recorded motion, condition timing, event holds and measured annotations retained. Video is re-encoded.",
        },
    )


if __name__ == "__main__":
    main()
