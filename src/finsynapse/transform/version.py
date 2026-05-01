"""Algorithm version management.

Every temperature output carries an `algo_version` column tracking which
version of the algorithm produced it. This enables:
- Champion/challenger comparison: was v2.1 better than v2.0?
- Drift detection: did a weights config change cause abrupt temperature shifts?
- Reproducibility: given bronze data + version × weights snapshot → rebuild exact output.

Bump ALGO_VERSION whenever the algorithm semantics change (new indicators alone
don't require a bump — weights.yaml covers that; adding dispersion weighting,
changing the combination formula, or adding multi-timeframe columns does).
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pandas as pd

from finsynapse import config as _cfg

ALGO_VERSION = "2.1"

WEIGHTS_SNAPSHOT_DIR_NAME = "weights_snapshots"


def stamp_version(df: pd.DataFrame) -> pd.DataFrame:
    """Add `algo_version` column to temperature output."""
    if df.empty:
        return df
    return df.assign(algo_version=ALGO_VERSION)


def snapshot_weights(source_path: str = "config/weights.yaml") -> Path | None:
    """Copy weights.yaml into silver/weights_snapshots/YYYY-MM-DD.yaml.

    Called by write_silver_temperature to ensure every temperature output
    has a corresponding weights config for reproducibility.
    Returns the snapshot path, or None if source missing.
    """
    src = Path(source_path)
    if not src.exists():
        return None

    from datetime import date

    snap_dir = _cfg.settings.silver_dir / WEIGHTS_SNAPSHOT_DIR_NAME
    snap_dir.mkdir(parents=True, exist_ok=True)
    dest = snap_dir / f"{date.today().isoformat()}.yaml"
    if not dest.exists() or src.stat().st_mtime > dest.stat().st_mtime:
        shutil.copyfile(src, dest)
    return dest


def list_weights_snapshots() -> list[Path]:
    """Return all weights snapshots sorted by date (newest first)."""
    snap_dir = _cfg.settings.silver_dir / WEIGHTS_SNAPSHOT_DIR_NAME
    if not snap_dir.exists():
        return []
    return sorted(snap_dir.glob("*.yaml"), reverse=True)


def compare_snapshots(prev: Path | None, curr: Path | None) -> dict:
    """Diff two weights snapshots. Returns dict of changes."""
    import yaml

    if prev is None or not prev.exists():
        return {"status": "first_snapshot"}
    if curr is None or not curr.exists():
        return {"status": "no_current"}
    p_data = yaml.safe_load(prev.read_text())
    c_data = yaml.safe_load(curr.read_text())
    diff: dict[str, list] = {"changed": [], "added": [], "removed": []}

    p_blocks = p_data.get("indicator_weights", {})
    c_blocks = c_data.get("indicator_weights", {})
    all_blocks = set(p_blocks) | set(c_blocks)
    for block in sorted(all_blocks):
        p_block = p_blocks.get(block, {})
        c_block = c_blocks.get(block, {})
        all_indicators = set(p_block) | set(c_block)
        for ind in sorted(all_indicators):
            p_spec = p_block.get(ind, {})
            c_spec = c_block.get(ind, {})
            if p_spec == c_spec:
                continue
            if not p_spec:
                diff["added"].append(f"{block}.{ind}: {c_spec}")
            elif not c_spec:
                diff["removed"].append(f"{block}.{ind}")
            else:
                diff["changed"].append(f"{block}.{ind}: {p_spec} -> {c_spec}")
    return {"status": "diff", **{k: v for k, v in diff.items() if v}}


def drift_check(
    today: pd.DataFrame,
    yesterday: pd.DataFrame,
    threshold: float = 15.0,
) -> list[dict]:
    """Detect large day-over-day temperature changes.

    Returns list of {market, today_temp, yesterday_temp, delta, alert} for
    any market exceeding `threshold` degrees.
    """
    if today.empty or yesterday.empty:
        return []

    alerts = []
    today_latest = today.sort_values("date").groupby("market").tail(1).set_index("market")
    yesterday_latest = yesterday.sort_values("date").groupby("market").tail(1).set_index("market")

    for market in ["us", "cn", "hk"]:
        if market not in today_latest.index or market not in yesterday_latest.index:
            continue
        t_today = float(today_latest.loc[market, "overall"])
        t_yesterday = float(yesterday_latest.loc[market, "overall"])
        delta = t_today - t_yesterday
        if abs(delta) >= threshold:
            zone_today = "hot" if t_today >= 70 else ("cold" if t_today < 30 else "mid")
            zone_yesterday = "hot" if t_yesterday >= 70 else ("cold" if t_yesterday < 30 else "mid")
            alerts.append(
                {
                    "market": market,
                    "today_temp": round(t_today, 1),
                    "yesterday_temp": round(t_yesterday, 1),
                    "delta": round(delta, 1),
                    "alert": "zone_crossing" if zone_today != zone_yesterday else "large_move",
                    "algo_version": ALGO_VERSION,
                }
            )
    return alerts
