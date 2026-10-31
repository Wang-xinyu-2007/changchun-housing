"""Configuration: paths, official data source, and analysis constants."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

RAW_CSV = ROOT / "data" / "raw" / "nbs_housing_index.csv"
RELEASES_CSV = ROOT / "data" / "raw" / "releases.csv"
META_JSON = ROOT / "data" / "raw" / "meta.json"
DB_PATH = ROOT / "data" / "processed" / "housing.db"
REPORT_PATH = ROOT / "reports" / "report.md"
FIGURE_DIR = ROOT / "reports" / "figures"
SQL_FILE = ROOT / "sql" / "questions.sql"
FIXTURE_HTML = ROOT / "tests" / "fixtures" / "nbs_release_sample.html"

NBS_SEARCH_URL = "https://api.so-gov.cn/query/s"
NBS_SITE_CODE = "bm36000002"
NBS_SEARCH_REFERER = "https://www.stats.gov.cn/search/s"
NBS_RELEASE_TITLE = "{year}年{month}月份70个大中城市商品住宅销售价格变动情况"
NBS_SOURCE_NAME = "国家统计局：70 个大中城市商品住宅销售价格指数"
NBS_INDEX_PAGE = "https://www.stats.gov.cn/sj/zxfb/"
NBS_DATA_NOTE = (
    "国家统计局每月发布的 70 个大中城市商品住宅销售价格指数；"
    "指数以上月/上年同月/上年同期为 100，不是成交均价。"
)

EXPECTED_CITIES = 70
FOCUS_CITY = "长春"
PEER_CITIES = (
    "长春",
    "沈阳",
    "哈尔滨",
    "大连",
    "北京",
    "上海",
    "广州",
    "深圳",
    "杭州",
    "成都",
)
MARKETS = ("new", "second_hand")
MARKET_LABELS = {"new": "新房", "second_hand": "二手房"}
MARKET_COLORS = {"new": "#2f81f7", "second_hand": "#d29922"}

DEFAULT_BACKFILL_MONTHS = 48
DEFAULT_START_MONTH = "2022-10"
