"""Opt-in update check against the GitHub Releases API (no telemetry, nothing is downloaded)."""

from __future__ import annotations

import json
import re
import urllib.request
from dataclasses import dataclass

from .. import REPO, __version__


@dataclass(frozen=True)
class ReleaseInfo:
    tag: str
    url: str
    notes: str


def parse_version(text: str) -> tuple[int, ...]:
    """"v1.2.3-rc1" -> (1, 2, 3); anything unparsable -> (0,)."""
    core = text.strip().split("-")[0].split("+")[0]
    numbers = re.findall(r"\d+", core)
    return tuple(int(n) for n in numbers[:4]) or (0,)


def is_newer(latest: str, current: str) -> bool:
    a, b = parse_version(latest), parse_version(current)
    width = max(len(a), len(b))
    return a + (0,) * (width - len(a)) > b + (0,) * (width - len(b))


def fetch_latest(repo: str = REPO, timeout: float = 6.0) -> ReleaseInfo:
    """Return the latest published release. Raises OSError / ValueError on failure."""
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/releases/latest",
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"Clicksmith/{__version__}",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        data = json.load(response)
    return ReleaseInfo(
        tag=str(data["tag_name"]),
        url=str(data["html_url"]),
        notes=str(data.get("body") or "")[:600],
    )
