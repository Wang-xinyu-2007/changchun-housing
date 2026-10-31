"""One command: real CSV -> validation -> SQLite -> SQL -> figures -> report."""

from __future__ import annotations

import json
import re
import sys

from . import analysis, config, report, store


def _load_meta() -> dict[str, object]:
    if config.META_JSON.exists():
        return json.loads(config.META_JSON.read_text(encoding="utf-8"))
    return {}


def _update_readme_snapshot(facts: dict[str, object]) -> None:
    """Keep the short latest-results block in README.md in sync with reports."""
    readme_path = config.ROOT / "README.md"
    if not readme_path.exists():
        return
    text = readme_path.read_text(encoding="utf-8")
    pattern = re.compile(
        re.escape(report.README_START) + r".*?" + re.escape(report.README_END),
        re.DOTALL,
    )
    if not pattern.search(text):
        return
    updated = pattern.sub(lambda _: report.build_readme_snapshot(facts), text)
    if updated != text:
        readme_path.write_text(updated, encoding="utf-8")


def main() -> int:
    if not config.RAW_CSV.exists():
        print(f"找不到数据文件：{config.RAW_CSV}", file=sys.stderr)
        print("先运行 `python -m src.update --backfill 48` 抓取真实数据。", file=sys.stderr)
        return 2

    frame = analysis.load_dataset(config.RAW_CSV)
    try:
        analysis.validate_dataset(frame)
    except ValueError as error:
        print(f"数据校验失败：{error}", file=sys.stderr)
        return 1

    facts = analysis.build_facts(frame)
    meta = _load_meta()
    store.write_sqlite(frame, config.DB_PATH)
    queries = store.load_queries(config.SQL_FILE)
    results = store.run_queries(config.DB_PATH, queries)

    figures = {
        "yoy": report.plot_yoy_trend(frame, config.FIGURE_DIR),
        "cumulative": report.plot_cumulative(frame, config.FIGURE_DIR),
        "peers": report.plot_peer_comparison(facts, config.FIGURE_DIR),
    }
    text = report.build_report(frame, facts, results, meta, figures)
    config.REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    config.REPORT_PATH.write_text(text, encoding="utf-8")
    _update_readme_snapshot(facts)

    print(f"数据月份    {facts['data_start']} → {facts['data_end']}（{facts['months_covered']} 个月）")
    print(f"最新快照    新房 {facts['focus']['new']['yoy_index']:.1f} / 二手房 {facts['focus']['second_hand']['yoy_index']:.1f}")
    print(f"数据库      {config.DB_PATH}")
    print(f"查询        {len(results)} 条")
    print(f"报告        {config.REPORT_PATH}")
    print(f"图表        {', '.join(path.name for path in figures.values())}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
