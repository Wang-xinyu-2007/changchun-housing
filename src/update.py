"""Update the real NBS housing-index dataset.

Examples:
    python -m src.update --months 2          # check the latest one or two months
    python -m src.update --backfill 48       # rebuild 48 months of history
    python -m src.update --start 2022-10 --end 2026-09 --force
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

import pandas as pd

from . import analysis, config
from .nbs import (
    NbsError,
    expected_latest_month,
    fetch_release_page,
    last_n_months,
    month_range,
    parse_release_page,
    search_release,
)


def _empty_frame() -> pd.DataFrame:
    return pd.DataFrame(
        columns=[
            "month",
            "market",
            "city",
            "mom_index",
            "yoy_index",
            "ytd_index",
            "source_url",
        ]
    )


def _read_existing(path: Path) -> pd.DataFrame:
    if not path.exists():
        return _empty_frame()
    return pd.read_csv(path, dtype={"month": str, "market": str, "city": str, "source_url": str})


def _read_releases(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["month", "title", "url", "fetched_at"])
    return pd.read_csv(path, dtype=str)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_dataset(frame: pd.DataFrame, release_rows: list[dict[str, str]]) -> None:
    config.RAW_CSV.parent.mkdir(parents=True, exist_ok=True)
    frame = frame.sort_values(["month", "market", "city"]).reset_index(drop=True)
    frame.to_csv(config.RAW_CSV, index=False, encoding="utf-8", float_format="%.3f")

    releases = _read_releases(config.RELEASES_CSV)
    if release_rows:
        releases = pd.concat(
            [releases, pd.DataFrame(release_rows)],
            ignore_index=True,
        )
        releases = releases.drop_duplicates("month", keep="last").sort_values("month")
        releases.to_csv(config.RELEASES_CSV, index=False, encoding="utf-8")

    latest_release = max(release_rows, key=lambda row: row["month"]) if release_rows else {}
    meta = {
        "source": config.NBS_SOURCE_NAME,
        "source_page": config.NBS_INDEX_PAGE,
        "latest_month": str(frame["month"].max()),
        "data_start": str(frame["month"].min()),
        "months_covered": int(frame["month"].nunique()),
        "rows": len(frame),
        "cities": int(frame["city"].nunique()),
        "markets": sorted(frame["market"].unique().tolist()),
        "latest_release_url": latest_release.get("url", ""),
        "fetched_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "dataset_sha256": _sha256(config.RAW_CSV),
    }
    config.META_JSON.write_text(
        json.dumps(meta, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def update(months: list[str], force: bool, delay: float) -> int:
    existing = _read_existing(config.RAW_CSV)
    existing_months = set(existing["month"].astype(str)) if not existing.empty else set()
    new_frames: list[pd.DataFrame] = []
    release_rows: list[dict[str, str]] = []

    for month in months:
        if month in existing_months and not force:
            print(f"{month}: already present, skipping")
            continue

        print(f"{month}: searching NBS release")
        release = search_release(month)
        if release is None:
            print(f"{month}: release not found yet, skipping")
            continue

        print(f"{month}: parsing {release.url}")
        html = fetch_release_page(release.url)
        parsed = parse_release_page(html, month, release.url)
        if parsed.city_count != config.EXPECTED_CITIES:
            raise NbsError(
                f"{month}: expected {config.EXPECTED_CITIES} cities, got {parsed.city_count}"
            )

        frame = pd.DataFrame(parsed.rows)
        new_frames.append(frame)
        release_rows.append(
            {
                "month": month,
                "title": release.title,
                "url": release.url,
                "fetched_at": datetime.now(UTC).replace(microsecond=0).isoformat(),
            }
        )
        print(f"{month}: parsed {len(frame)} rows / {parsed.city_count} cities")
        time.sleep(delay)

    if not new_frames:
        print("no new data; dataset unchanged")
        return 0

    new_frame = pd.concat(new_frames, ignore_index=True)
    if not existing.empty:
        existing = existing[~existing["month"].astype(str).isin(new_frame["month"].unique())]
        combined = pd.concat([existing, new_frame], ignore_index=True)
    else:
        combined = new_frame

    combined = combined.sort_values(["month", "market", "city"]).reset_index(drop=True)
    analysis.validate_dataset(combined)
    _write_dataset(combined, release_rows)

    print(
        f"wrote {config.RAW_CSV} ({len(combined)} rows, "
        f"{combined['month'].nunique()} months, latest {combined['month'].max()})"
    )
    return 0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--months", type=int, default=1, help="try the latest N months")
    parser.add_argument("--backfill", type=int, help="rebuild the latest N months")
    parser.add_argument("--start", type=str, help="start month YYYY-MM")
    parser.add_argument("--end", type=str, help="end month YYYY-MM (default: previous month)")
    parser.add_argument("--force", action="store_true", help="refetch months already present")
    parser.add_argument("--delay", type=float, default=0.5, help="seconds between page requests")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    end = args.end or expected_latest_month()
    try:
        if args.start:
            if not args.end:
                end = expected_latest_month()
            months = month_range(args.start, end)
        elif args.backfill:
            months = last_n_months(args.backfill, end)
        else:
            months = last_n_months(args.months, end)
    except ValueError as error:
        print(f"bad month range: {error}", file=sys.stderr)
        return 2

    try:
        return update(months, force=args.force, delay=args.delay)
    except NbsError as error:
        print(f"update failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
