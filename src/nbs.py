"""Fetch and parse the NBS 70-city housing price index releases.

NBS publishes one page per month with two main tables:

* table 1: new commodity housing price indices;
* table 2: second-hand housing price indices.

Each table is laid out as two records per row: city, MoM, YoY, YTD average,
then another city and three values. The parser normalises the city names
(which contain ideographic spaces) and returns tidy rows.
"""

from __future__ import annotations

import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from bs4 import BeautifulSoup

from . import config


class NbsError(RuntimeError):
    """Raised when a release cannot be fetched or parsed."""


@dataclass(frozen=True)
class Release:
    month: str
    title: str
    url: str
    timestamp: int | None = None


@dataclass(frozen=True)
class ParsedRelease:
    month: str
    source_url: str
    rows: list[dict[str, object]]

    @property
    def city_count(self) -> int:
        return len({row["city"] for row in self.rows})


def _headers() -> dict[str, str]:
    return {
        "User-Agent": (
            "Mozilla/5.0 (compatible; changchun-housing/1.0; "
            "+https://github.com/Wang-xinyu-2007/changchun-housing)"
        ),
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.7",
    }


def _request(
    url: str,
    data: bytes | None = None,
    timeout: int = 60,
    retries: int = 3,
    extra_headers: dict[str, str] | None = None,
) -> bytes:
    last_error: Exception | None = None
    for attempt in range(retries):
        headers = _headers()
        if extra_headers:
            headers.update(extra_headers)
        request = urllib.request.Request(url, data=data, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return response.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as error:
            last_error = error
            status = getattr(error, "code", None)
            if attempt == retries - 1 or (status is not None and status not in (429, 500, 502, 503, 504)):
                break
            time.sleep(1.5 * (attempt + 1))
    raise NbsError(f"request failed for {url}: {last_error}") from last_error


def month_title(month: str) -> str:
    year_text, month_text = month.split("-")
    return config.NBS_RELEASE_TITLE.format(year=int(year_text), month=int(month_text))


def month_before(month: str, count: int = 1) -> str:
    current = datetime.strptime(f"{month}-01", "%Y-%m-%d").date()
    for _ in range(count):
        current = (current.replace(day=1) - timedelta(days=1)).replace(day=1)
    return current.strftime("%Y-%m")


def expected_latest_month(today: date | None = None) -> str:
    today = today or date.today()
    return month_before(today.strftime("%Y-%m"), 1)


def month_range(start: str, end: str) -> list[str]:
    if start > end:
        raise ValueError(f"start month {start} is after end month {end}")
    months: list[str] = []
    current = start
    while current <= end:
        months.append(current)
        current = _next_month(current)
    return months


def last_n_months(count: int, end: str | None = None) -> list[str]:
    if count <= 0:
        raise ValueError("count must be positive")
    end = end or expected_latest_month()
    current = end
    months = [current]
    for _ in range(count - 1):
        current = month_before(current)
        months.append(current)
    return sorted(months)


def _next_month(month: str) -> str:
    year, number = map(int, month.split("-"))
    if number == 12:
        return f"{year + 1:04d}-01"
    return f"{year:04d}-{number + 1:02d}"


def _clean_text(value: str) -> str:
    return "".join(value.split())


def _clean_html_title(value: str) -> str:
    return re.sub(r"<[^>]+>", "", html.unescape(value or "")).strip()


def _parse_index(value: str) -> float | None:
    cleaned = value.strip().replace("—", "").replace("－", "").replace("-", "")
    if not cleaned or cleaned in {"…", "..."}:
        return None
    try:
        return float(cleaned)
    except ValueError:
        return None


def search_release(month: str) -> Release | None:
    """Search NBS for the exact monthly release, returning the first exact match."""
    title = month_title(month)
    payload = urllib.parse.urlencode(
        {
            "siteCode": config.NBS_SITE_CODE,
            "tab": "",
            "qt": title,
            "page": "1",
            "pageSize": "20",
            "ie": "utf-8",
        }
    ).encode()
    raw = _request(
        config.NBS_SEARCH_URL,
        data=payload,
        extra_headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Referer": config.NBS_SEARCH_REFERER,
        },
    )

    try:
        response = json.loads(raw.decode("utf-8"))
    except json.JSONDecodeError as error:
        raise NbsError("NBS search returned invalid JSON") from error

    for document in response.get("resultDocs", []):
        data = document.get("data", {})
        result_title = _clean_html_title(data.get("titleO", ""))
        url = (data.get("url") or "").strip()
        if result_title == title and url:
            return Release(
                month=month,
                title=result_title,
                url=url,
                timestamp=document.get("timestamp"),
            )
    return None


def fetch_release_page(url: str) -> str:
    raw = _request(url)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError:
        return raw.decode("gb18030", "replace")


def _looks_like_city_table(table) -> bool:
    rows = table.find_all("tr")
    if not rows:
        return False
    first_cells = [_clean_text(cell.get_text(" ", strip=True)) for cell in rows[0].find_all(["td", "th"])]
    return "城市" in first_cells


def _iter_city_values(table) -> Iterable[tuple[str, float | None, float | None, float | None]]:
    for row in table.find_all("tr"):
        cells = [_clean_text(cell.get_text(" ", strip=True)) for cell in row.find_all(["td", "th"])]
        if len(cells) == 8:
            offsets, value_count = (0, 4), 3
        elif len(cells) == 6:
            offsets, value_count = (0, 3), 2
        elif len(cells) == 4:
            offsets, value_count = (0,), 3
        elif len(cells) == 3:
            offsets, value_count = (0,), 2
        else:
            continue

        for offset in offsets:
            city = cells[offset]
            if not city or city == "城市" or cells[offset + 1].startswith("上月"):
                continue
            mom = _parse_index(cells[offset + 1])
            yoy = _parse_index(cells[offset + 2]) if value_count >= 2 else None
            ytd = _parse_index(cells[offset + 3]) if value_count >= 3 else None
            if mom is None and yoy is None:
                continue
            yield city, mom, yoy, ytd


def parse_release_page(html_text: str, month: str, source_url: str) -> ParsedRelease:
    """Parse the two main NBS tables into tidy rows."""
    soup = BeautifulSoup(html_text, "lxml")
    city_tables = [table for table in soup.find_all("table") if _looks_like_city_table(table)]
    if len(city_tables) < 2:
        raise NbsError(
            f"{month}: expected at least 2 city tables, found {len(city_tables)}"
        )

    rows: list[dict[str, object]] = []
    for market, table in zip(config.MARKETS, city_tables[:2], strict=False):
        cities: set[str] = set()
        for city, mom, yoy, ytd in _iter_city_values(table):
            if city in cities:
                raise NbsError(f"{month}/{market}: duplicate city row for {city}")
            cities.add(city)
            rows.append(
                {
                    "month": month,
                    "market": market,
                    "city": city,
                    "mom_index": mom,
                    "yoy_index": yoy,
                    "ytd_index": ytd,
                    "source_url": source_url,
                }
            )

    if not rows:
        raise NbsError(f"{month}: parsed no city rows")
    if config.FOCUS_CITY not in {row["city"] for row in rows}:
        raise NbsError(f"{month}: focus city {config.FOCUS_CITY!r} not found")
    return ParsedRelease(month=month, source_url=source_url, rows=rows)
