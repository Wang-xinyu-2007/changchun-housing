"""单元测试：python -m unittest discover -s tests -v

测试的重点不是"函数能跑"，而是**边界**：
"85万" 和 850000 是不是同一个意思、区名少写一个"区"会不会漏、
重复挂牌会不会算两次。这些才是面试时会问到的地方。
"""

import sys
import unittest
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src import clean, config, demo_data, report, store  # noqa: E402


class TestParsePrice(unittest.TestCase):
    def test_plain_number(self):
        self.assertEqual(clean.parse_price_wan("85"), 85.0)
        self.assertEqual(clean.parse_price_wan(85.5), 85.5)

    def test_with_unit(self):
        self.assertEqual(clean.parse_price_wan("85.5万"), 85.5)
        self.assertEqual(clean.parse_price_wan("85万元"), 85.0)

    def test_yuan_is_converted(self):
        # 大于 1 万的数字几乎不可能是"万元"，按"元"处理
        self.assertEqual(clean.parse_price_wan("850000"), 85.0)
        self.assertEqual(clean.parse_price_wan("85,0000"), 85.0)

    def test_missing(self):
        for value in ("", None, "   ", "暂无", "-"):
            self.assertTrue(pd.isna(clean.parse_price_wan(value)), msg=repr(value))


class TestParseArea(unittest.TestCase):
    def test_units_are_stripped(self):
        self.assertEqual(clean.parse_area("89.5㎡"), 89.5)
        self.assertEqual(clean.parse_area("120平米"), 120.0)
        self.assertEqual(clean.parse_area("76.2平方米"), 76.2)

    def test_missing(self):
        self.assertTrue(pd.isna(clean.parse_area("")))
        self.assertTrue(pd.isna(clean.parse_area("暂无")))


class TestDistrict(unittest.TestCase):
    def test_short_name(self):
        self.assertEqual(clean.normalize_district("朝阳"), "朝阳区")

    def test_whitespace(self):
        self.assertEqual(clean.normalize_district(" 宽城区 "), "宽城区")

    def test_alias(self):
        self.assertEqual(clean.normalize_district("净月开发区"), "净月区")

    def test_missing(self):
        self.assertEqual(clean.normalize_district(""), config.UNKNOWN_DISTRICT)
        self.assertEqual(clean.normalize_district(None), config.UNKNOWN_DISTRICT)


class TestCleanPipeline(unittest.TestCase):
    """用一小份人造数据把清洗规则走一遍。"""

    def setUp(self):
        self.raw = pd.DataFrame({
            "listing_id": ["A1", "A2", "A3", "A3", "A4", "A5", "A6"],
            "district": ["朝阳", "朝阳区", "宽城", "宽城", "绿园区", "南关区", "二道区"],
            "community": ["甲院", "乙院", "丙院", "丙院", "丁院", "戊院", "己院"],
            "area_m2": ["89.5㎡", "120", "60", "60", "9999", "75", ""],
            "total_price_wan": ["85万", "120", "850000", "850000", "99999", "60", "70"],
            "unit_price": [9500, 10000, 0, 0, 5000, 8000, 9000],
            "floor": ["中楼层"] * 7,
            "total_floors": [18] * 7,
            "rooms": [2, 3, 2, 2, 2, 2, 2],
            "orientation": ["南北"] * 7,
            "build_year": [2015, 2010, 2005, 2005, 2000, 2018, 2012],
            "listed_date": ["2026-01-01"] * 7,
        })
        self.clean_df, self.stats = clean.clean(self.raw)

    def test_duplicate_removed(self):
        self.assertEqual(self.stats["重复删除"], 1)
        self.assertEqual(self.clean_df["listing_id"].duplicated().sum(), 0)

    def test_price_with_unit_and_yuan_agree(self):
        row = self.clean_df[self.clean_df["listing_id"] == "A2"].iloc[0]
        self.assertAlmostEqual(row["total_price_wan"], 120.0)
        # A3 的 "850000" 应按元处理成 85 万，而不是 85 万×10000
        row = self.clean_df[self.clean_df["listing_id"] == "A3"].iloc[0]
        self.assertAlmostEqual(row["total_price_wan"], 85.0)

    def test_outliers_removed(self):
        self.assertNotIn("A4", set(self.clean_df["listing_id"]))   # 面积 9999 + 总价 99999
        self.assertIn("A5", set(self.clean_df["listing_id"]))      # 75㎡ / 60 万，是正常房源

    def test_missing_required_dropped(self):
        self.assertNotIn("A6", set(self.clean_df["listing_id"]))   # 面积缺失

    def test_unit_price_recalculated(self):
        # A3 原本单价是 0，应该用 总价/面积 补出来
        row = self.clean_df[self.clean_df["listing_id"] == "A3"].iloc[0]
        self.assertAlmostEqual(row["unit_price"], 85 * 10000 / 60, places=2)

    def test_all_values_in_range(self):
        self.assertTrue(self.clean_df["area_m2"].between(config.AREA_MIN, config.AREA_MAX).all())
        self.assertTrue(self.clean_df["unit_price"].between(
            config.UNIT_PRICE_MIN, config.UNIT_PRICE_MAX).all())

    def test_age_is_non_negative(self):
        self.assertTrue((self.clean_df["房龄"] >= 0).all())


class TestDemoData(unittest.TestCase):
    def test_shape_and_dirt(self):
        frame = demo_data.make_demo_data(rows=100, seed=1)
        self.assertGreater(len(frame), 100)          # 掺了重复行
        self.assertEqual(list(frame.columns), demo_data.COLUMNS)
        # 至少有一样脏东西存在（否则清洗逻辑就测不到了）
        has_unit_price_text = frame["total_price_wan"].astype(str).str.contains("万").any()
        self.assertTrue(has_unit_price_text)

    def test_is_deterministic(self):
        first = demo_data.make_demo_data(rows=50, seed=42)
        second = demo_data.make_demo_data(rows=50, seed=42)
        pd.testing.assert_frame_equal(first, second)


class TestSql(unittest.TestCase):
    def setUp(self):
        frame, _ = clean.clean(demo_data.make_demo_data(rows=200, seed=3))
        self.db = Path(__file__).resolve().parent / "_test.db"
        store.write_sqlite(frame, self.db)
        self.queries = store.load_queries(config.SQL_FILE)

    def tearDown(self):
        self.db.unlink(missing_ok=True)

    def test_queries_are_loaded(self):
        self.assertEqual(len(self.queries), 5)
        self.assertTrue(all(q["sql"] for q in self.queries))

    def test_every_query_returns_rows(self):
        results = store.run_queries(self.db, self.queries)
        self.assertEqual(len(results), 5)
        for name, table in results.items():
            self.assertGreater(len(table), 0, msg=name)


class TestReport(unittest.TestCase):
    def test_markdown_table(self):
        frame = pd.DataFrame({"a": [1, 2], "b": [1.5, 2.5]})
        text = report.md_table(frame)
        self.assertIn("| a | b |", text)
        self.assertIn("| 1 | 1.5 |", text)

    def test_empty_table(self):
        self.assertIn("没有数据", report.md_table(pd.DataFrame()))


if __name__ == "__main__":
    unittest.main()
