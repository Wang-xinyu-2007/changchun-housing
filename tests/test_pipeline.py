"""Integration tests against the committed real dataset and SQL files."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from src import analysis, config, store


class CommittedDatasetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.frame = analysis.load_dataset(config.RAW_CSV)
        analysis.validate_dataset(cls.frame)

    def test_dataset_has_a_long_history(self) -> None:
        self.assertGreaterEqual(self.frame["month"].nunique(), 36)
        self.assertGreaterEqual(analysis.latest_month(self.frame), "2026-09")

    def test_every_month_has_all_70_cities_and_both_markets(self) -> None:
        counts = self.frame.groupby(["month", "market"])["city"].nunique()
        self.assertTrue((counts == 70).all(), counts[counts != 70])

    def test_changchun_is_present_every_month(self) -> None:
        focus = self.frame[self.frame["city"] == "长春"]
        self.assertEqual(set(focus["market"]), {"new", "second_hand"})
        self.assertEqual(focus["month"].nunique(), self.frame["month"].nunique())


class SqlTests(unittest.TestCase):
    def test_queries_are_executable_and_named(self) -> None:
        queries = store.load_queries(config.SQL_FILE)
        self.assertEqual(len(queries), 5)
        self.assertIn("长春最新快照", {query["name"] for query in queries})

        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "housing.db"
            store.write_sqlite(analysis.load_dataset(config.RAW_CSV), db_path)
            results = store.run_queries(db_path, queries)
            self.assertEqual(len(results), 5)
            snapshot = results["长春最新快照"]
            self.assertEqual(len(snapshot), 2)
            self.assertIn("market", snapshot.columns)
