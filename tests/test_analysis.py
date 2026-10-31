"""Tests for validation and derived metrics."""

from __future__ import annotations

import unittest

import pandas as pd

from src import analysis


def sample_frame() -> pd.DataFrame:
    rows = []
    for month in ("2026-08", "2026-09"):
        for city, new_mom, new_yoy, old_mom, old_yoy in (
            ("长春", 100.2, 99.1, 99.7, 96.2),
            ("沈阳", 100.1, 99.8, 99.8, 95.5),
            ("北京", 99.8, 98.5, 99.9, 94.0),
        ):
            for market, mom, yoy in (("new", new_mom, new_yoy), ("second_hand", old_mom, old_yoy)):
                rows.append(
                    {
                        "month": month,
                        "market": market,
                        "city": city,
                        "mom_index": mom,
                        "yoy_index": yoy,
                        "ytd_index": 98.0,
                        "source_url": "https://example.test",
                    }
                )
    return pd.DataFrame(rows)


class ValidationTests(unittest.TestCase):
    def test_sample_is_valid_with_small_city_count(self) -> None:
        analysis.validate_dataset(sample_frame(), expected_cities=3)

    def test_duplicate_rows_are_rejected(self) -> None:
        frame = sample_frame()
        duplicated = pd.concat([frame, frame.iloc[[0]]], ignore_index=True)
        with self.assertRaisesRegex(ValueError, "duplicate"):
            analysis.validate_dataset(duplicated, expected_cities=3)

    def test_impossible_index_is_rejected(self) -> None:
        frame = sample_frame()
        frame.loc[0, "mom_index"] = 250
        with self.assertRaisesRegex(ValueError, "plausible"):
            analysis.validate_dataset(frame, expected_cities=3)


class MetricTests(unittest.TestCase):
    def test_cumulative_index_starts_at_100(self) -> None:
        frame = analysis.cumulative_index(sample_frame())
        first = frame[(frame["city"] == "长春") & (frame["market"] == "new")].sort_values("month").iloc[0]
        last = frame[(frame["city"] == "长春") & (frame["market"] == "new")].sort_values("month").iloc[-1]
        self.assertAlmostEqual(first["cumulative_index"], 100.0)
        self.assertAlmostEqual(last["cumulative_index"], 100.2)

    def test_build_facts_ranks_focus_city(self) -> None:
        facts = analysis.build_facts(sample_frame())
        self.assertEqual(facts["month"], "2026-09")
        self.assertEqual(facts["focus"]["new"]["yoy_index"], 99.1)
        self.assertEqual(facts["focus"]["new"]["yoy_rank"], 2)
        self.assertEqual(facts["focus"]["second_hand"]["yoy_rank"], 1)
        self.assertEqual(facts["streak"]["new"]["months"], 2)
        self.assertEqual(facts["streak"]["second_hand"]["months"], 2)

    def test_peer_rows_only_include_present_cities(self) -> None:
        facts = analysis.build_facts(sample_frame())
        self.assertEqual({row["city"] for row in facts["peers"]}, {"长春", "沈阳", "北京"})

    def test_twelve_month_lookup_is_none_when_history_is_short(self) -> None:
        facts = analysis.build_facts(sample_frame())
        self.assertIsNone(facts["twelve_month"]["new"])
