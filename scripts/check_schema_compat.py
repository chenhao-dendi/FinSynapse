#!/usr/bin/env python3
"""Check JSON Schema compatibility between old and new schemas.

Detects whether a schema change is a minor bump (additive) or
major bump (breaking: field deletion, type change).

Usage:
    uv run python scripts/check_schema_compat.py [--old schemas/api/v1/] [--new schemas/api/v2/]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OLD = REPO_ROOT / "schemas" / "api" / "v1"
DEFAULT_NEW = REPO_ROOT / "schemas" / "api" / "v2"


def _collect_fields(schema: dict, prefix: str = "") -> tuple[dict[str, str], dict[str, str]]:
    """Walk a JSON Schema and collect all fields (path -> type).

    Returns (required_fields, all_fields) where required_fields only includes
    those listed in `required` arrays, and all_fields includes every property.
    """
    required: dict[str, str] = {}
    all_fields: dict[str, str] = {}

    def add_field(path, prop_type, is_required):
        if isinstance(prop_type, list):
            prop_type = "|".join(str(t) for t in prop_type)
        all_fields[path] = str(prop_type)
        if is_required:
            required[path] = str(prop_type)

    def walk(node, current_path, parent_required):
        if not isinstance(node, dict):
            return
        req_list = set(node.get("required", []))
        for field_name, prop in node.get("properties", {}).items():
            full_path = f"{current_path}.{field_name}" if current_path else field_name
            is_req = field_name in req_list
            prop_type = prop.get("type", "unknown")
            add_field(full_path, prop_type, is_req)

            ref = prop.get("$ref", "")
            if ref and ref.startswith("#/"):
                ref_node = schema
                for part in ref.split("/")[1:]:
                    ref_node = ref_node.get(part, {})
                walk(ref_node, full_path, is_req)
            elif isinstance(prop, dict):
                walk(prop, full_path, is_req)

    walk(schema, "", False)
    return required, all_fields


def _load_schema(path: Path) -> dict:
    with open(path) as f:
        return json.load(f)


def check_compat(old_dir: Path, new_dir: Path) -> tuple[int, list[str]]:
    issues: list[str] = []
    major_break = False

    if not old_dir.exists():
        return 0, [f"INFO: No old schemas at {old_dir} — this is the first version."]

    old_files = sorted(old_dir.glob("*.schema.json"))
    new_files = sorted(new_dir.glob("*.schema.json"))

    new_names = {f.name for f in new_files}

    for old_file in old_files:
        if old_file.name not in new_names:
            issues.append(f"WARN: {old_file.name} removed in new version")
            major_break = True
            continue

        new_file = new_dir / old_file.name
        old = _load_schema(old_file)
        new = _load_schema(new_file)

        old_req, old_all = _collect_fields(old)
        new_req, new_all = _collect_fields(new)

        # Check for deleted fields (any field in old not in new)
        for path, otype in old_all.items():
            if path not in new_all:
                if path in old_req:
                    issues.append(f"BREAKING: {old_file.name} — required field '{path}' (type={otype}) removed")
                else:
                    issues.append(f"BREAKING: {old_file.name} — field '{path}' (type={otype}) removed")
                major_break = True

        # Check for type changes in existing fields
        for path, ntype in new_all.items():
            if path in old_all and old_all[path] != ntype:
                if path in old_req or path in new_req:
                    level = "BREAKING"
                    major_break = True
                else:
                    level = "WARN"
                issues.append(
                    f"{level}: {old_file.name} — field '{path}' "
                    f"type changed from {old_all[path]} to {ntype}"
                )

        # Check for new required fields (minor — additive)
        for path in new_req:
            if path not in old_req:
                issues.append(f"MINOR: {old_file.name} — new required field '{path}' (type={new_req[path]})")

    # Check for new schema files (minor)
    for new_file in new_files:
        if new_file.name not in {f.name for f in old_files}:
            issues.append(f"MINOR: new schema file '{new_file.name}' added")

    return 1 if major_break else 0, issues


def main() -> int:
    parser = argparse.ArgumentParser(description="Check JSON Schema compatibility")
    parser.add_argument("--old", type=Path, default=DEFAULT_OLD)
    parser.add_argument("--new", type=Path, default=DEFAULT_NEW)
    args = parser.parse_args()

    exit_code, issues = check_compat(args.old, args.new)
    for issue in issues:
        print(issue)

    if exit_code == 1:
        print("\nMAJOR version bump required.")
    else:
        print("\nMinor version bump (backward-compatible).")

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
