r"""Champion-challenger gate CLI.

Usage:
    uv run python -m finsynapse.eval.gate \
        --champion eval/champion.json \
        --challenger /tmp/latest.json

Exit codes:
    0  all rules pass (or only warn failures with no block failures)
    1  at least one block rule fails
    2  only warn rules fail
    3  usage error
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from finsynapse.eval.champion import diff


def _main() -> int:
    parser = argparse.ArgumentParser(description="Run champion-challenger gate check")
    parser.add_argument("--champion", type=Path, required=True, help="Path to champion.json")
    parser.add_argument("--challenger", type=Path, required=True, help="Path to challenger latest.json")
    args = parser.parse_args()

    if not args.champion.exists():
        print(f"ERROR: champion file not found: {args.champion}", file=sys.stderr)
        return 3
    if not args.challenger.exists():
        print(f"ERROR: challenger file not found: {args.challenger}", file=sys.stderr)
        return 3

    champion = json.loads(args.champion.read_text())
    challenger = json.loads(args.challenger.read_text())

    report = diff(champion, challenger)
    print(report.format_text())

    return report.exit_code


if __name__ == "__main__":
    sys.exit(_main())
