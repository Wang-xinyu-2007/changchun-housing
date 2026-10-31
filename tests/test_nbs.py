"""Tests for the NBS release search and HTML parser (no network required)."""

from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from src import config
from src.nbs import (
    NbsError,
    last_n_months,
    month_before,
    month_title,
    parse_release_page,
    search_release,
)


class NbsParserTests(unittest.TestCase):
    def test_parse_fixture_extracts_both_markets(self) -> None:
        html = config.FIXTURE_HTML.read_text(encoding="utf-8")
        parsed = parse_release_page(html, "2026-09", "https://example.test/release")
        self.assertEqual(parsed.city_count, 4)
        self.assertEqual(len(parsed.rows), 8)
        changchun = [row for row in parsed.rows if row["city"] == "长春"]
        self.assertEqual({row["market"] for row in changchun}, {"new", "second_hand"})
        new = next(row for row in changchun if row["market"] == "new")
        self.assertEqual(new["mom_index"], 100.3)
        self.assertEqual(new["yoy_index"], 99.3)
        self.assertEqual(new["ytd_index"], 98.4)

    def test_parse_six_cell_layout_without_ytd(self) -> None:
        html = """
        <table>
          <tr><td>城市</td><td>环比</td><td>同比</td><td>城市</td><td>环比</td><td>同比</td></tr>
          <tr><td>上月=100</td><td>上年同月=100</td><td>上月=100</td><td>上年同月=100</td></tr>
          <tr><td>长春</td><td>100.2</td><td>98.6</td><td>沈阳</td><td>99.8</td><td>97.2</td></tr>
        </table>
        <table>
          <tr><td>城市</td><td>环比</td><td>同比</td><td>城市</td><td>环比</td><td>同比</td></tr>
          <tr><td>上月=100</td><td>上年同月=100</td><td>上月=100</td><td>上年同月=100</td></tr>
          <tr><td>长春</td><td>99.5</td><td>94.8</td><td>沈阳</td><td>99.3</td><td>94.2</td></tr>
        </table>
        """
        parsed = parse_release_page(html, "2024-01", "https://example.test/january")
        self.assertEqual(parsed.city_count, 2)
        new = next(row for row in parsed.rows if row["city"] == "长春" and row["market"] == "new")
        self.assertIsNone(new["ytd_index"])

    def test_missing_tables_raise(self) -> None:
        with self.assertRaises(NbsError):
            parse_release_page("<html><body>no tables</body></html>", "2026-09", "x")

    def test_missing_focus_city_raises(self) -> None:
        html = config.FIXTURE_HTML.read_text(encoding="utf-8").replace("长　　春", "哈尔滨")
        with self.assertRaises(NbsError):
            parse_release_page(html, "2026-09", "x")


class NbsSearchTests(unittest.TestCase):
    def test_search_selects_exact_title(self) -> None:
        title = month_title("2026-09")
        payload = json.dumps(
            {
                "resultDocs": [
                    {"data": {"titleO": "2026年9月房价综述", "url": "https://example.test/wrong"}},
                    {"data": {"titleO": title, "url": "https://example.test/right"}},
                ]
            }
        ).encode()
        with patch("src.nbs._request", return_value=payload):
            release = search_release("2026-09")
        self.assertIsNotNone(release)
        self.assertEqual(release.url, "https://example.test/right")
        self.assertEqual(release.month, "2026-09")

    def test_search_returns_none_when_missing(self) -> None:
        with patch("src.nbs._request", return_value=b'{"resultDocs": []}'):
            self.assertIsNone(search_release("2026-09"))


class MonthHelpersTests(unittest.TestCase):
    def test_month_before_crosses_year(self) -> None:
        self.assertEqual(month_before("2024-01"), "2023-12")
        self.assertEqual(month_before("2024-01", 13), "2022-12")

    def test_last_n_months(self) -> None:
        self.assertEqual(last_n_months(3, "2026-09"), ["2026-07", "2026-08", "2026-09"])

    def test_month_title(self) -> None:
        self.assertEqual(
            month_title("2026-09"),
            "2026年9月份70个大中城市商品住宅销售价格变动情况",
        )
