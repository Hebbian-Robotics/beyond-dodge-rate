"""Check static website links, asset hashes, and the reported comparison counts."""

from __future__ import annotations

import hashlib
import json
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote, urlsplit


class SiteLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.targets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name in {"src", "href", "poster"} and value:
                self.targets.append(value)


def main() -> None:
    repository = Path(__file__).resolve().parent.parent
    site = repository / "site"
    parser = SiteLinks()
    parser.feed((site / "index.html").read_text())
    for target in parser.targets:
        url = urlsplit(target)
        if url.scheme or not url.path:
            continue
        relative = Path(unquote(url.path))
        if relative.is_absolute() or ".." in relative.parts or not (site / relative).is_file():
            raise ValueError(f"Missing or nonportable website asset: {url.path}")
    manifest = json.loads((repository / "results/publication-files.json").read_text())
    for relative, expected in manifest.items():
        if hashlib.sha256((repository / relative).read_bytes()).hexdigest() != expected:
            raise ValueError(f"Publication file changed: {relative}")
    results = json.loads((repository / "results/summary.json").read_text())
    if results["total_trials"] != 2496 or results["seeds_per_policy"] != 192:
        raise ValueError("Unexpected scientific trial coverage")
    if [row["policy"] for row in results["conditions"]] != ["π₁"] * 3 + ["π₂"] * 3:
        raise ValueError("Publication policy symbols differ from the declared checkpoint mapping")
    expected_counts = [(192, 192), (191, 70), (182, 171), (162, 161), (165, 158), (101, 100)]
    measured_counts = [(row["dodged"], row["success"]) for row in results["conditions"]]
    if measured_counts != expected_counts:
        raise ValueError("Headline comparison differs from the verified study")
    recovery = json.loads((repository / "results/demo-recovery.json").read_text())
    recovery_counts = [
        (
            row["policy"],
            row["seed_count"],
            row["stale_successes"],
            row["recovered_successes"],
            row["stale_dodges"],
            row["recovered_dodges"],
        )
        for row in recovery["policies"]
    ]
    if recovery_counts != [("π₁", 64, 32, 61, 64, 64), ("π₂", 64, 53, 51, 54, 54)]:
        raise ValueError("Demo recovery counts differ from the verified held-out cohort")
    print(f"Checked {len(parser.targets)} site links and {len(manifest)} publication file hashes.")


if __name__ == "__main__":
    main()
