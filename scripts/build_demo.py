"""Build the demo with consistent typography and a results table from recorded counts."""

from __future__ import annotations

import argparse
import json
import math
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from evaluate import file_digest
from PIL import Image, ImageDraw, ImageFont

FRAME_SIZE = (1920, 1080)
INK = "#111111"
MUTED = "#555555"
RULE = "#d9d9d9"
SURFACE = "#f2f2f2"
FONT_DIRECTORY = Path("/usr/share/fonts/truetype/dejavu")


@dataclass(frozen=True)
class PolicyComparison:
    policy: str
    stale_successes: int
    blank_successes: int
    seed_count: int
    difference: float
    interval: tuple[float, float]


def draw_text(
    drawing: ImageDraw.ImageDraw,
    position: tuple[int, int],
    text: str,
    size: int,
    *,
    bold: bool = False,
    color: str = INK,
    width: int = 1680,
    centered: bool = False,
) -> None:
    font_path = FONT_DIRECTORY / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf")
    font = ImageFont.truetype(str(font_path), size)
    bounds = drawing.textbbox((0, 0), text, font=font)
    if bounds[2] - bounds[0] > width:
        raise ValueError(f"Demo text exceeds its allotted width: {text}")
    drawing.text(position, text, font=font, fill=color, anchor="mt" if centered else "lt")


def load_comparisons(repository: Path) -> list[PolicyComparison]:
    results = json.loads((repository / "results/summary.json").read_text())
    seed_count = results["seeds_per_policy"]
    comparisons = []
    for contrast in results["blank_minus_stale"]:
        policy = contrast["policy"]
        rows = {row["input"]: row for row in results["conditions"] if row["policy"] == policy}
        stale_successes = rows["Stale"]["success"]
        blank_successes = rows["Blank"]["success"]
        difference = (blank_successes - stale_successes) / seed_count
        interval = tuple(contrast["paired_bootstrap_95"])
        if not (
            0 <= stale_successes <= seed_count
            and 0 <= blank_successes <= seed_count
            and math.isclose(difference, contrast["difference"], abs_tol=1e-12)
            and len(interval) == 2
            and interval[0] <= difference <= interval[1]
        ):
            raise ValueError(f"Inconsistent demo comparison: {policy}")
        comparisons.append(
            PolicyComparison(
                policy,
                stale_successes,
                blank_successes,
                seed_count,
                difference,
                (interval[0], interval[1]),
            )
        )
    if len(comparisons) != 2:
        raise ValueError("The demo requires both evaluated policies")
    return comparisons


def make_intro(path: Path) -> None:
    image = Image.new("RGB", FRAME_SIZE, "white")
    drawing = ImageDraw.Draw(image)
    draw_text(drawing, (960, 280), "Beyond Dodge Rate", 94, bold=True, centered=True)
    draw_text(
        drawing, (960, 430), "Camera failures in simulated humanoid dodgeball", 46, centered=True
    )
    draw_text(drawing, (960, 640), "Kingston Kuan and Brandon Ong", 36, centered=True)
    draw_text(drawing, (960, 705), "Hebbian Robotics", 34, color=MUTED, centered=True)
    add_wordmark(image, (960, 855), 390)
    image.save(path)


def add_wordmark(image: Image.Image, center: tuple[int, int], width: int) -> None:
    repository = Path(__file__).resolve().parent.parent
    with Image.open(repository / "site/assets/hebbian-wordmark.png") as source:
        wordmark = source.convert("RGBA")
    height = round(wordmark.height * width / wordmark.width)
    wordmark = wordmark.resize((width, height), Image.Resampling.LANCZOS)
    image.paste(wordmark, (center[0] - width // 2, center[1] - height // 2), wordmark)


def make_outro(path: Path) -> None:
    image = Image.new("RGB", FRAME_SIZE, "white")
    drawing = ImageDraw.Draw(image)
    draw_text(drawing, (960, 250), "Beyond Dodge Rate", 80, bold=True, centered=True)
    draw_text(drawing, (960, 410), "Evaluate what happens after the dodge.", 46, centered=True)
    draw_text(drawing, (960, 580), "Kingston Kuan and Brandon Ong", 34, centered=True)
    draw_text(drawing, (960, 645), "Hebbian Robotics", 32, color=MUTED, centered=True)
    add_wordmark(image, (960, 820), 460)
    image.save(path)


def make_experiment_explanation(path: Path) -> None:
    image = Image.new("RGB", FRAME_SIZE, "white")
    drawing = ImageDraw.Draw(image)
    draw_text(drawing, (960, 85), "A dodge is only part of success", 64, bold=True, centered=True)
    for center, label, detail in (
        (330, "Avoid contact", "The ball misses the robot"),
        (960, "Stay upright", "The robot does not fall"),
        (1590, "Stay in the area", "Pelvis stays within 1 m"),
    ):
        draw_text(drawing, (center, 300), label, 43, bold=True, centered=True, width=600)
        draw_text(drawing, (center, 390), detail, 31, centered=True, width=600)
    draw_text(drawing, (960, 535), "Check all three over a four-second trial.", 42, centered=True)
    drawing.line((120, 665, 1800, 665), fill=RULE, width=2)
    draw_text(drawing, (120, 720), "Replay the same throw with different camera inputs.", 38)
    draw_text(
        drawing, (120, 805), "π₁: released checkpoint    π₂: separately trained checkpoint", 33
    )
    draw_text(
        drawing,
        (120, 870),
        "Same PPO method, architecture, objective and recorded settings.",
        30,
        color=MUTED,
    )
    draw_text(
        drawing,
        (120, 960),
        "Compare camera conditions within each policy; these are not policy rankings.",
        29,
        color=MUTED,
    )
    image.save(path)


def make_comparison_background(
    path: Path, title: str, context: str, conditions: tuple[str, str, str], takeaway: str
) -> None:
    image = Image.new("RGB", FRAME_SIZE, "white")
    drawing = ImageDraw.Draw(image)
    draw_text(drawing, (960, 48), title, 58, bold=True, centered=True)
    draw_text(drawing, (960, 140), context, 29, color=MUTED, centered=True)
    for center, label in zip((320, 960, 1600), conditions, strict=True):
        draw_text(drawing, (center, 215), label, 32, bold=True, centered=True, width=620)
    draw_text(drawing, (960, 835), takeaway, 39, bold=True, centered=True)
    draw_text(
        drawing,
        (960, 930),
        "Illustrative replay; this example is not average performance.",
        29,
        color=MUTED,
        centered=True,
    )
    draw_text(
        drawing,
        (960, 990),
        "Teal: 1 m boundary    Orange: pelvis path    Pauses mark key events",
        28,
        color=MUTED,
        centered=True,
    )
    image.save(path)


def make_recovery_results(path: Path, repository: Path) -> None:
    report = json.loads((repository / "results/demo-recovery.json").read_text())
    image = Image.new("RGB", FRAME_SIZE, "white")
    drawing = ImageDraw.Draw(image)
    draw_text(
        drawing, (960, 75), "Fresh images after the dodge can matter", 60, bold=True, centered=True
    )
    draw_text(
        drawing,
        (960, 175),
        "64 matched test seeds per condition and policy",
        34,
        color=MUTED,
        centered=True,
    )
    drawing.rectangle((120, 280, 1800, 390), fill=SURFACE)
    for center, label in [
        (250, "Policy"),
        (650, "Keep stale"),
        (1090, "Restore at 2 s"),
        (1570, "Change (pp)"),
    ]:
        draw_text(drawing, (center, 320), label, 34, bold=True, centered=True, width=430)
    for index, comparison in enumerate(report["policies"]):
        count = comparison["seed_count"]
        difference = (comparison["recovered_successes"] - comparison["stale_successes"]) / count
        if not math.isclose(difference, comparison["difference"], abs_tol=1e-12):
            raise ValueError("Recovery counts differ from the paired contrast")
        top = 430 + index * 175
        draw_text(drawing, (250, top), comparison["policy"], 48, bold=True, centered=True)
        draw_text(
            drawing, (650, top), f"{comparison['stale_successes']} / {count}", 52, centered=True
        )
        draw_text(
            drawing,
            (1090, top),
            f"{comparison['recovered_successes']} / {count}",
            52,
            centered=True,
        )
        draw_text(drawing, (1570, top), f"{difference * 100:+.1f}", 52, bold=True, centered=True)
        lower, upper = comparison["paired_bootstrap_95"]
        draw_text(
            drawing,
            (1570, top + 75),
            f"95% CI: {lower * 100:+.1f} to {upper * 100:+.1f}",
            25,
            color=MUTED,
            centered=True,
            width=450,
        )
        drawing.line((120, top + 145, 1800, top + 145), fill=RULE, width=2)
    draw_text(drawing, (120, 815), "π₁ dodges all 64 throws in both conditions.", 38)
    draw_text(drawing, (120, 885), "Restoring vision improves area compliance, not dodge rate.", 36)
    draw_text(
        drawing,
        (120, 970),
        "Overall success: dodge, stay upright, stay within 1 m for four seconds.",
        29,
        color=MUTED,
    )
    draw_text(
        drawing,
        (120, 1020),
        "Change: restored minus stale, in percentage points; paired bootstrap intervals.",
        26,
        color=MUTED,
    )
    image.save(path)


def make_results_table(path: Path, comparisons: list[PolicyComparison]) -> None:
    image = Image.new("RGB", FRAME_SIZE, "white")
    drawing = ImageDraw.Draw(image)
    draw_text(drawing, (120, 95), "Stale versus blank images: overall success", 58, bold=True)
    draw_text(
        drawing,
        (120, 200),
        f"Overall success across {comparisons[0].seed_count} test seeds per condition",
        34,
        color=MUTED,
    )
    column_edges = (120, 500, 900, 1300, 1800)
    column_centers = (310, 700, 1100, 1550)
    drawing.rectangle((120, 300, 1800, 410), fill=SURFACE)
    draw_text(drawing, (150, 337), "Policy", 34, bold=True, width=320)
    draw_text(drawing, (700, 337), "Repeat last image", 32, bold=True, centered=True, width=380)
    draw_text(drawing, (1100, 337), "Blank image", 32, bold=True, centered=True, width=380)
    draw_text(drawing, (1550, 320), "Change", 32, bold=True, centered=True, width=480)
    draw_text(drawing, (1550, 365), "percentage points", 26, centered=True, width=480)
    for row_index, comparison in enumerate(comparisons):
        row_top = 410 + row_index * 166
        row_center = row_top + 50
        draw_text(drawing, (150, row_center), comparison.policy, 38, bold=True, width=320)
        for column, successes in ((1, comparison.stale_successes), (2, comparison.blank_successes)):
            draw_text(
                drawing,
                (column_centers[column], row_center),
                f"{successes} / {comparison.seed_count}",
                49,
                centered=True,
                width=column_edges[column + 1] - column_edges[column] - 40,
            )
        draw_text(
            drawing,
            (1550, row_top + 29),
            f"{comparison.difference * 100:+.1f}",
            53,
            bold=True,
            color=INK,
            centered=True,
            width=480,
        )
        lower, upper = comparison.interval
        draw_text(
            drawing,
            (1550, row_top + 104),
            f"95% CI: {lower * 100:+.1f} to {upper * 100:+.1f}",
            26,
            color=MUTED,
            centered=True,
            width=480,
        )
        drawing.line((120, row_top + 166, 1800, row_top + 166), fill=RULE, width=2)
    draw_text(drawing, (120, 800), "Blank input improves area compliance for both models.", 34)
    draw_text(drawing, (120, 855), "For π₂, lost dodges outweigh that benefit.", 34)
    draw_text(
        drawing, (120, 930), "Success: dodge, stay upright, stay within 1 m for four seconds", 28
    )
    draw_text(
        drawing,
        (120, 985),
        "Change is blank minus repeated images. Intervals use a paired bootstrap.",
        28,
        color=MUTED,
    )
    image.save(path)


def encode_segment(
    output: Path,
    background: Path,
    duration: int,
    source: Path | None = None,
    outcomes: tuple[str, str, str] | None = None,
) -> None:
    command = [
        "ffmpeg",
        "-y",
        "-loglevel",
        "error",
        "-loop",
        "1",
        "-framerate",
        "25",
        "-i",
        str(background),
    ]
    if source is not None:
        if outcomes is None:
            raise ValueError("A replay needs endpoint outcome labels")
        outcome_image = Image.new("RGBA", FRAME_SIZE, (0, 0, 0, 0))
        outcome_drawing = ImageDraw.Draw(outcome_image)
        for center, label in zip((320, 960, 1600), outcomes, strict=True):
            draw_text(
                outcome_drawing, (center, 755), label, 32, bold=True, centered=True, width=620
            )
        outcome_path = background.with_name(background.stem + "-outcomes.png")
        outcome_image.save(outcome_path)
        command += [
            "-i",
            str(source),
            "-loop",
            "1",
            "-framerate",
            "25",
            "-i",
            str(outcome_path),
            "-filter_complex",
            "[1:v]crop=2880:648:0:72,scale=1920:432[comparison];"
            "[0:v][comparison]overlay=0:285:shortest=1[scene];"
            "[scene][2:v]overlay=0:0:enable='gte(t,12)':shortest=1[video]",
            "-map",
            "[video]",
        ]
    subprocess.run(
        [
            *command,
            "-t",
            str(duration),
            "-an",
            "-c:v",
            "libx264",
            "-threads",
            "4",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            str(output),
        ],
        check=True,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    if arguments.output.exists():
        raise FileExistsError("Use a fresh output path to preserve the existing demo")
    repository = Path(__file__).resolve().parent.parent
    source_videos = (
        ("timing", "152a0a1b50d85b29f1cc442dbd2353f8d947c2b78f3e2bbe77ff75e7cf69a030"),
        ("team", "074bb7f40d94704ff047ffdc565d8a8c49f7cd6cf0c60a1e81fd47b1c3ce4917"),
        ("recovery", "0dfca4182b37127db5f656ad540230642e2b472ffe6264013474d830935ba7c0"),
    )
    for prefix, expected in source_videos:
        if file_digest(repository / f"site/assets/{prefix}-comparison.mp4") != expected:
            raise ValueError(f"Source comparison changed: {prefix}")
    comparisons = load_comparisons(repository)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="dodgeball-demo-") as temporary:
        directory = Path(temporary)
        make_intro(directory / "intro.png")
        encode_segment(directory / "intro.mp4", directory / "intro.png", 4)
        make_experiment_explanation(directory / "policies.png")
        encode_segment(directory / "policies.mp4", directory / "policies.png", 7)
        for prefix, title, context, conditions, takeaway, outcomes in (
            (
                "timing",
                "When does the camera freeze?",
                "π₁ · Seed 3000",
                ("Healthy camera", "Freeze at launch", "Freeze after 320 ms"),
                "Avoiding the ball does not guarantee staying in the area.",
                ("Dodged", "Contact", "Dodged; left the area"),
            ),
            (
                "recovery",
                "What happens when fresh images return?",
                "π₁ · Seed 9000 · Three-second restoration is exploratory",
                ("Keep stale images", "Restore at 2 seconds", "Restore at 3 seconds"),
                "All three dodge; only restoration at 2 s keeps this trial in the area.",
                ("Dodged; left the area", "Dodged; stayed in the area", "Dodged; left the area"),
            ),
            (
                "team",
                "Repeat the last image or send a blank?",
                "π₂ · Seed 7300 · Failure starts 160 ms after launch",
                ("Healthy camera", "Repeat last image", "Blank image"),
                "Blank images cause contact in this π₂ example.",
                ("Dodged", "Dodged", "Contact"),
            ),
        ):
            make_comparison_background(
                directory / f"{prefix}.png", title, context, conditions, takeaway
            )
            encode_segment(
                directory / f"{prefix}.mp4",
                directory / f"{prefix}.png",
                14,
                repository / f"site/assets/{prefix}-comparison.mp4",
                outcomes,
            )
        make_results_table(directory / "closing.png", comparisons)
        encode_segment(directory / "closing.mp4", directory / "closing.png", 10)
        make_recovery_results(directory / "recovery-results.png", repository)
        encode_segment(directory / "recovery-results.mp4", directory / "recovery-results.png", 10)
        make_outro(directory / "outro.png")
        encode_segment(directory / "outro.mp4", directory / "outro.png", 4)
        sources = [
            directory / name
            for name in (
                "intro.mp4",
                "policies.mp4",
                "timing.mp4",
                "recovery.mp4",
                "team.mp4",
                "recovery-results.mp4",
                "closing.mp4",
                "outro.mp4",
            )
        ]
        concat = directory / "segments.txt"
        concat.write_text("\n".join(f"file '{path}'" for path in sources) + "\n")
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-loglevel",
                "error",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(arguments.output),
            ],
            check=True,
        )
    print(file_digest(arguments.output))


if __name__ == "__main__":
    main()
