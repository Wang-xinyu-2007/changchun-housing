"""一条命令跑完整条流水线：读数据 → 清洗 → 入库 → 跑 SQL → 出报告。"""

from __future__ import annotations

import sys

import pandas as pd

from . import clean, config, report, store


def main() -> int:
    # 1. 读原始数据（全部按字符串读，让 clean 决定怎么解析）
    if not config.RAW_CSV.exists():
        print(f"找不到数据文件：{config.RAW_CSV}", file=sys.stderr)
        print("先跑一次 `python -m src.demo_data` 生成示例数据，", file=sys.stderr)
        print("或者把你的真实数据放到这个路径。", file=sys.stderr)
        return 2

    raw = pd.read_csv(config.RAW_CSV, dtype=str, keep_default_na=False)
    missing = clean.describe_missing(raw.replace("", pd.NA))

    # 2. 清洗
    clean_df, stats = clean.clean(raw)

    # 3. 入库
    store.write_sqlite(clean_df, config.DB_PATH)

    # 4. 跑 SQL
    queries = store.load_queries(config.SQL_FILE)
    results = store.run_queries(config.DB_PATH, queries)

    # 5. 出图（matplotlib 没装的话跳过，不影响报告生成）
    figures: dict[str, object] = {}
    hist_figure = None
    try:
        first = results.get("各区均价与房源数")
        if first is not None:
            figures["各区均价与房源数"] = report.plot_district_price(
                first, "区域", "均价", config.FIGURE_DIR)
        second = results.get("面积段与均价")
        if second is not None:
            figures["面积段与均价"] = report.plot_area_band(
                second, "面积段", "均价", config.FIGURE_DIR)
        hist_figure = report.plot_price_hist(clean_df, config.FIGURE_DIR)
    except ImportError as exc:
        print(f"提示：没有画图（{exc}），报告只包含表格。", file=sys.stderr)

    # 6. 写报告
    source_note = (
        "示例数据（`python -m src.demo_data` 生成），**不是真实行情**"
        if "示例" not in str(config.RAW_CSV) else "示例数据"
    )
    text = report.build_report(
        clean_df=clean_df,
        stats=stats,
        results=results,
        missing=missing,
        source_note=source_note,
        figures=figures,
        hist_figure=hist_figure,
    )
    config.REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.REPORT_PATH.write_text(text, encoding="utf-8")

    # 7. 终端摘要
    print(f"原始行数    {stats['原始行数']}")
    print(f"清洗后行数  {stats['最终行数']}（保留 {stats['保留比例']}）")
    print(f"数据库      {config.DB_PATH}")
    print(f"查询        {len(results)} 条")
    print(f"报告        {config.REPORT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
