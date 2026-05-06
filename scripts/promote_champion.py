#!/usr/bin/env python3
"""Promote a challenger to champion.

Only entry point allowed to write eval/champion.json.
Must be run on main branch.

Usage:
    uv run python scripts/promote_champion.py \
        --latest /tmp/latest.json \
        --commit-sha abc1234 \
        --pr "https://github.com/..." \
        --reason "Improved CN 3m MRS from 0.39 to 0.45"
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CHAMPION_PATH = REPO_ROOT / "eval" / "champion.json"
CHAMPION_MD_PATH = REPO_ROOT / "eval" / "CHAMPION.md"


def _current_branch() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
        ).strip()
    except Exception:
        return "unknown"


def _read_md_table() -> list[str]:
    if not CHAMPION_MD_PATH.exists():
        return []
    return CHAMPION_MD_PATH.read_text().splitlines()


def _append_champion_md(
    seq: int,
    commit_sha: str,
    pr: str,
    reason: str,
    latest: dict,
) -> None:
    metrics = latest.get("metrics", {})
    dir_rate = metrics.get("pivot_directional_rate", "N/A")
    strict = metrics.get("pivot_strict_rate", "N/A")
    mrs_3m_us = metrics.get("mean_reversion_strength.3m.us", "N/A")

    key_delta = f"dir_rate={dir_rate}, strict={strict}, mrs_3m_us={mrs_3m_us}"

    line = f"| {seq} | {date.today().isoformat()} | `{commit_sha}` | {pr} | {reason} | {key_delta} |"

    lines = _read_md_table()
    if not lines:
        CHAMPION_MD_PATH.write_text(
            f"# Champion Promotion History\n\n> `maturity: Lv2`\n\n"
            f"| # | Date | Commit | PR | Reason | Key Delta |\n"
            f"|---|---|---|---|---|---|\n"
            f"{line}\n"
        )
        return

    sep_idx = None
    for i, l in enumerate(lines):
        if l.strip().startswith("|---"):
            sep_idx = i
            break

    if sep_idx is None:
        lines.append(line)
        CHAMPION_MD_PATH.write_text("\n".join(lines) + "\n")
        return

    lines.insert(sep_idx + 2, line)
    CHAMPION_MD_PATH.write_text("\n".join(lines) + "\n")


def _count_existing() -> int:
    if not CHAMPION_MD_PATH.exists():
        return 0
    import re
    content = CHAMPION_MD_PATH.read_text()
    count = 0
    for line in content.splitlines():
        m = re.match(r"^\|\s*(\d+)\s*\|", line)
        if m:
            count = max(count, int(m.group(1)))
    return count


def main() -> int:
    parser = argparse.ArgumentParser(description="Promote challenger to champion")
    parser.add_argument("--latest", type=Path, required=True, help="Path to latest.json from suite run")
    parser.add_argument("--commit-sha", type=str, required=True, help="Commit SHA of the change being promoted")
    parser.add_argument("--pr", type=str, required=True, help="PR URL or number")
    parser.add_argument("--reason", type=str, required=True, help="Reason for promotion")
    parser.add_argument(
        "--force", action="store_true", help="Allow promotion on non-main branch (for testing)"
    )
    args = parser.parse_args()

    branch = _current_branch()
    if branch != "main" and not args.force:
        print(f"ERROR: must be on main branch to promote champion (current: {branch})", file=sys.stderr)
        print("Use --force to override (for testing only)", file=sys.stderr)
        return 1

    if not args.latest.exists():
        print(f"ERROR: latest.json not found: {args.latest}", file=sys.stderr)
        return 1

    latest_data = json.loads(args.latest.read_text())

    CHAMPION_PATH.write_text(json.dumps(latest_data, indent=2, ensure_ascii=False))
    print(f"[champion] written -> {CHAMPION_PATH}")

    seq = _count_existing() + 1
    _append_champion_md(seq, args.commit_sha, args.pr, args.reason, latest_data)
    print(f"[history] appended entry #{seq} -> {CHAMPION_MD_PATH}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
