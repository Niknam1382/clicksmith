"""One-time setup: replace the OWNER/clicksmith placeholder with your real GitHub repo.

Every badge, workflow, and doc link in this project points at the placeholder
"OWNER/clicksmith" so the project works out of the box in CI even before you've chosen a
name. Run this once, right after you create the GitHub repository:

    python scripts/set_repo.py your-username your-repo-name

It rewrites every tracked text file in place (README, pyproject.toml, the GitHub Actions
workflows, the Inno Setup script, docs, ...) and leaves a short summary of what changed.
Safe to re-run - it only ever replaces the current placeholder or a previous owner/repo you
already set with this script, never arbitrary text.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PLACEHOLDER = "OWNER/clicksmith"
BINARY_SUFFIXES = {".png", ".ico", ".jpg", ".jpeg", ".zip", ".exe"}


def tracked_files() -> list[Path]:
    """Every file git is tracking (respects .gitignore); falls back to a manual walk."""
    try:
        result = subprocess.run(
            ["git", "ls-files"], cwd=ROOT, capture_output=True, text=True, check=True
        )
        return [ROOT / line for line in result.stdout.splitlines() if line]
    except (OSError, subprocess.CalledProcessError):
        return [p for p in ROOT.rglob("*") if p.is_file() and ".git" not in p.parts]


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        print(f"Usage: python {Path(__file__).name} <owner> <repo>", file=sys.stderr)
        return 2
    owner, repo = sys.argv[1], sys.argv[2]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", owner) or not re.fullmatch(
        r"[A-Za-z0-9._-]+", repo
    ):
        print("error: owner/repo contain characters GitHub wouldn't accept", file=sys.stderr)
        return 2
    replacement = f"{owner}/{repo}"
    if replacement == PLACEHOLDER:
        print("Nothing to do: that's already the placeholder value.")
        return 0

    changed = []
    for path in tracked_files():
        if path == Path(__file__) or path.suffix.lower() in BINARY_SUFFIXES:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        if PLACEHOLDER not in text:
            continue
        path.write_text(text.replace(PLACEHOLDER, replacement), encoding="utf-8")
        changed.append(path.relative_to(ROOT))

    if not changed:
        print(f"No occurrences of '{PLACEHOLDER}' found - already customised?")
        return 0
    print(f"Replaced '{PLACEHOLDER}' -> '{replacement}' in {len(changed)} file(s):")
    for path in changed:
        print(f"  {path}")
    print("\nDone. Review the diff (`git diff`), then commit.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
