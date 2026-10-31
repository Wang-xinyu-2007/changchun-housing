"""Validation and analysis helpers for the NBS housing index dataset."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import config
from .nbs import month_before

REQUIRED_COLUMNS = (
    "month",
    "market",
    "city",
    "mom_index",
    "yoy_index",
    "ytd_index",
    "source_url",
)


def load_dataset(path: str | Path = config.RAW_CSV) -> pd.DataFrame:
    """Load the committed tidy CSV and normalise dtypes."""
    frame = pd.read_csv(
        path,
        dtype={"month": str, "market": str, "city": str, "source_url": str},
    )
    frame["month"] = frame["month"].str.strip()
    frame["city"] = frame["city"].str.strip()
    frame["market"] = frame["market"].str.strip()
    for column in ("mom_index", "yoy_index", "ytd_index"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    return frame.sort_values(["month", "market", "city"]).reset_index(drop=True)


def validate_dataset(
    frame: pd.DataFrame,
    expected_cities: int = config.EXPECTED_CITIES,
) -> None:
    """Raise a useful error instead of silently analysing a broken dataset."""
    if frame.empty:
        raise ValueError("dataset is empty")

    missing = [column for column in REQUIRED_COLUMNS if column not in frame.columns]
    if missing:
        raise ValueError(f"missing columns: {missing}")

    if frame.duplicated(["month", "market", "city"]).any():
        duplicates = frame[
            frame.duplicated(["month", "market", "city"], keep=False)
        ].head(10)
        raise ValueError(f"duplicate month/market/city rows:\n{duplicates}")

    if not frame["month"].astype(str).str.match(r"^\d{4}-\d{2}$").all():
        raise ValueError("month must use YYYY-MM")

    if set(frame["market"].unique()) - set(config.MARKETS):
        raise ValueError(f"unexpected markets: {sorted(set(frame['market']) - set(config.MARKETS))}")

    if frame[["month", "market", "city"]].isna().any().any():
        raise ValueError("month, market, and city must not be null")

    if frame["mom_index"].isna().any() or frame["yoy_index"].isna().any():
        raise ValueError("mom_index and yoy_index must be present for every row")

    for column in ("mom_index", "yoy_index", "ytd_index"):
        values = frame[column].dropna()
        if ((values < 50) | (values > 200)).any():
            raise ValueError(f"{column} outside the plausible 50-200 range")

    counts = frame.groupby(["month", "market"])["city"].nunique()
    bad_counts = counts[counts != expected_cities]
    if not bad_counts.empty:
        preview = ", ".join(f"{month}/{market}={count}" for (month, market), count in bad_counts.items())
        raise ValueError(
            f"expected {expected_cities} cities per month/market; got {preview}"
        )

    focus_months = set(frame.loc[frame["city"] == config.FOCUS_CITY, "month"])
    if focus_months != set(frame["month"]):
        raise ValueError(f"{config.FOCUS_CITY} is missing from some months")


def latest_month(frame: pd.DataFrame) -> str:
    return str(frame["month"].max())


def cumulative_index(frame: pd.DataFrame) -> pd.DataFrame:
    """Chain MoM indices into a cumulative index, base 100 at each series' first month.

    NBS defines the MoM index as previous month = 100. A value of 100.3 means
    +0.3% month over month. Chaining those factors gives a level series without
    claiming that the index equals a transaction price.
    """
    result = frame.copy()
    result = result.sort_values(["city", "market", "month"])

    def chain(values: pd.Series) -> pd.Series:
        factors = values / 100.0
        cumulative = factors.cumprod()
        return 100.0 * cumulative / cumulative.iloc[0]

    result["cumulative_index"] = result.groupby(
        ["city", "market"], sort=False
    )["mom_index"].transform(chain)
    return result


def _market_rows(frame: pd.DataFrame, market: str, city: str | None = None) -> pd.DataFrame:
    rows = frame[frame["market"] == market]
    if city is not None:
        rows = rows[rows["city"] == city]
    return rows.sort_values("month")


def _streak(frame: pd.DataFrame, city: str, market: str, threshold: float = 100.0) -> dict[str, object]:
    rows = _market_rows(frame, market, city)
    below = rows["yoy_index"] < threshold
    if below.empty or not bool(below.iloc[-1]):
        return {"months": 0, "start": None}
    count = 0
    for is_below in reversed(below.tolist()):
        if not is_below:
            break
        count += 1
    start = str(rows["month"].iloc[-count])
    return {"months": count, "start": start}


def build_facts(frame: pd.DataFrame) -> dict[str, object]:
    """Compute the numbers and comparisons used by the report."""
    month = latest_month(frame)
    latest = frame[frame["month"] == month].copy()
    latest["mom_pct"] = latest["mom_index"] - 100.0
    latest["yoy_pct"] = latest["yoy_index"] - 100.0
    latest["ytd_pct"] = latest["ytd_index"] - 100.0
    latest["yoy_rank"] = (
        latest.groupby("market")["yoy_index"].rank(ascending=False, method="min").astype("Int64")
    )
    latest["city_count"] = latest.groupby("market")["city"].transform("count").astype(int)

    focus = {}
    for market in config.MARKETS:
        row = latest[(latest["city"] == config.FOCUS_CITY) & (latest["market"] == market)]
        if row.empty:
            raise ValueError(f"missing {config.FOCUS_CITY}/{market} in {month}")
        record = row.iloc[0]
        focus[market] = {
            "month": month,
            "mom_index": float(record["mom_index"]),
            "yoy_index": float(record["yoy_index"]),
            "ytd_index": float(record["ytd_index"]) if pd.notna(record["ytd_index"]) else None,
            "mom_pct": float(record["mom_pct"]),
            "yoy_pct": float(record["yoy_pct"]),
            "ytd_pct": float(record["ytd_pct"]) if pd.notna(record["ytd_pct"]) else None,
            "yoy_rank": int(record["yoy_rank"]),
            "city_count": int(record["city_count"]),
        }

    medium = latest.groupby("market")[["mom_index", "yoy_index", "ytd_index"]].median()
    national_median = {
        market: {column: float(medium.loc[market, column]) for column in medium.columns}
        for market in config.MARKETS
        if market in medium.index
    }

    peers: list[dict[str, object]] = []
    for city in config.PEER_CITIES:
        city_rows = latest[latest["city"] == city]
        if city_rows.empty:
            continue
        record: dict[str, object] = {"city": city}
        for market in config.MARKETS:
            row = city_rows[city_rows["market"] == market]
            if row.empty:
                continue
            item = row.iloc[0]
            record[f"{market}_mom"] = float(item["mom_index"])
            record[f"{market}_yoy"] = float(item["yoy_index"])
            record[f"{market}_ytd"] = float(item["ytd_index"])
        peers.append(record)

    cumulative = cumulative_index(frame)
    cumulative_focus = cumulative[cumulative["city"] == config.FOCUS_CITY]
    base_month = str(cumulative_focus["month"].min())
    cumulative_latest = {}
    for market in config.MARKETS:
        rows = cumulative_focus[cumulative_focus["market"] == market]
        if rows.empty:
            continue
        latest_row = rows.iloc[-1]
        cumulative_latest[market] = {
            "base_month": base_month,
            "cumulative_index": float(latest_row["cumulative_index"]),
            "change_pct": float(latest_row["cumulative_index"] - 100.0),
        }

    twelve_months_ago = month_before(month, 12)
    twelve_month = {}
    for market in config.MARKETS:
        rows = _market_rows(frame, market, config.FOCUS_CITY)
        previous = rows[rows["month"] == twelve_months_ago]
        twelve_month[market] = (
            None
            if previous.empty
            else {
                "month": twelve_months_ago,
                "yoy_index": float(previous.iloc[0]["yoy_index"]),
            }
        )

    return {
        "month": month,
        "focus": focus,
        "national_median": national_median,
        "peers": peers,
        "cumulative": cumulative_latest,
        "streak": {
            market: _streak(frame, config.FOCUS_CITY, market) for market in config.MARKETS
        },
        "twelve_month": twelve_month,
        "spread_yoy": float(focus["new"]["yoy_index"] - focus["second_hand"]["yoy_index"]),
        "spread_mom": float(focus["new"]["mom_index"] - focus["second_hand"]["mom_index"]),
        "data_start": str(frame["month"].min()),
        "data_end": month,
        "months_covered": int(frame["month"].nunique()),
    }
