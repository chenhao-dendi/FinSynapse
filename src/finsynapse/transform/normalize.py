from __future__ import annotations

from pathlib import Path

import pandas as pd

from finsynapse import config as _cfg

CANONICAL_COLUMNS = ["date", "indicator", "value", "source"]


def collect_bronze(bronze_dir: Path | None = None) -> pd.DataFrame:
    """Walk every bronze parquet, concat into one long-format frame.

    Bronze files written by providers all share the schema produced by
    `Provider.fetch`: date, indicator, value, source_symbol. We re-tag the
    source column with the provider name (parent folder of the parquet)
    so silver consumers can attribute origin without parsing source_symbol.
    """
    bronze = Path(bronze_dir or _cfg.settings.bronze_dir)
    frames: list[pd.DataFrame] = []
    for parquet in sorted(bronze.rglob("*.parquet")):
        provider_name = parquet.parent.name
        df = pd.read_parquet(parquet)
        df["source"] = provider_name
        frames.append(df[["date", "indicator", "value", "source"]])

    if not frames:
        return pd.DataFrame(columns=CANONICAL_COLUMNS)

    combined = pd.concat(frames, ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"]).dt.date
    # Same (date, indicator) may appear from multiple bronze fetches; keep
    # the latest non-null. For ties we keep the row from the lexically last
    # source — deterministic, easy to override later if a priority is needed.
    combined = (
        combined.sort_values(["date", "indicator", "source"])
        .drop_duplicates(subset=["date", "indicator"], keep="last")
        .reset_index(drop=True)
    )
    return combined[CANONICAL_COLUMNS]


def write_silver_macro(df: pd.DataFrame) -> Path:
    silver = _cfg.settings.silver_dir
    silver.mkdir(parents=True, exist_ok=True)
    path = silver / "macro_daily.parquet"
    df.to_parquet(path, index=False)
    return path
