#!/usr/bin/env python3
"""Mutation testing runner for FinSynapse.

Runs mutmut on critical transform + eval modules to verify
that the test suite can detect injected bugs.

Usage:
    uv run python scripts/run_mutation.py                # full run
    uv run python scripts/run_mutation.py --quick        # quick 30s sample
    uv run python scripts/run_mutation.py --module finsynapse.transform.percentile
"""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

CRITICAL_MODULES = [
    "src/finsynapse/transform/percentile.py",
    "src/finsynapse/transform/temperature.py",
    "src/finsynapse/eval/metrics.py",
    "src/finsynapse/eval/suite.py",
    "src/finsynapse/eval/champion.py",
]


def _run_mutmut(targets: list[str], quick: bool = False) -> int:
    for target in targets:
        path = REPO_ROOT / target
        if not path.exists():
            print(f"SKIP: {target} not found")
            continue

        print(f"\n{'=' * 60}")
        print(f"  mutmut: {target}")
        print(f"{'=' * 60}")

        args = ["uv", "run", "mutmut", "run", "--paths-to-mutate", str(path)]
        if quick:
            args.append("--tests-dir")
            args.append("tests")

        try:
            result = subprocess.run(
                args,
                cwd=REPO_ROOT,
                timeout=300 if not quick else 60,
                capture_output=True,
                text=True,
            )
            # Print last 30 lines of output
            lines = result.stdout.splitlines()[-30:]
            for line in lines:
                print(line)
            if result.stderr:
                print(result.stderr[-500:])

            # Show results summary
            results = subprocess.run(
                ["uv", "run", "mutmut", "results"],
                cwd=REPO_ROOT,
                timeout=30,
                capture_output=True,
                text=True,
            )
            summary = results.stdout.splitlines()[-15:]
            for line in summary:
                print(line)

        except subprocess.TimeoutExpired:
            print(f"  TIMEOUT: {target} took too long")
        except Exception as e:
            print(f"  ERROR: {e}")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run mutation testing on critical modules")
    parser.add_argument("--quick", action="store_true", help="Quick mode: fewer mutations, shorter timeout")
    parser.add_argument("--module", type=str, help="Run on a single module path")
    args = parser.parse_args()

    targets = [args.module] if args.module else CRITICAL_MODULES

    print("Mutation Testing — FinSynapse Critical Modules")
    print(f"Targets: {len(targets)}")
    print()

    return _run_mutmut(targets, quick=args.quick)


if __name__ == "__main__":
    sys.exit(main())
