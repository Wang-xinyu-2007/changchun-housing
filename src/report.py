"""Build the Markdown report and the figures from real NBS index data."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import analysis, config

CITY_EN = {
    "长春": "Changchun",
    "沈阳": "Shenyang",
    "哈尔滨": "Harbin",
    "大连": "Dalian",
    "北京": "Beijing",
    "上海": "Shanghai",
    "广州": "Guangzhou",
    "深圳": "Shenzhen",
    "杭州": "Hangzhou",
    "成都": "Chengdu",
}
PLOT_LABELS = {"new": "New homes", "second_hand": "Second-hand"}
README_START = "<!-- LATEST_SNAPSHOT_START -->"
README_END = "<!-- LATEST_SNAPSHOT_END -->"


def md_table(df: pd.DataFrame, float_format: str = ",.1f") -> str:
    """Convert a DataFrame to a Markdown table without extra dependencies."""
    if df.empty:
        return "_（没有数据）_"

    columns = [str(column) for column in df.columns]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in df.itertuples(index=False, name=None):
        cells = []
        for value in row:
            if pd.isna(value):
                cells.append("—")
            elif isinstance(value, float):
                cells.append(format(value, float_format))
            elif value is None:
                cells.append("—")
            else:
                cells.append(str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


def _setup_matplotlib():
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    matplotlib.rcParams["axes.unicode_minus"] = False
    return plt


def _focus_frame(frame: pd.DataFrame) -> pd.DataFrame:
    return frame[frame["city"] == config.FOCUS_CITY].sort_values(["market", "month"])


def plot_yoy_trend(frame: pd.DataFrame, out_dir: Path) -> Path:
    plt = _setup_matplotlib()
    focus = _focus_frame(frame)
    pivot = focus.pivot(index="month", columns="market", values="yoy_index").sort_index()
    x = pd.to_datetime(pivot.index + "-01")

    fig, ax = plt.subplots(figsize=(9, 4.6))
    for market in config.MARKETS:
        if market in pivot.columns:
            ax.plot(
                x,
                pivot[market],
                marker="o",
                markersize=2.5,
                linewidth=1.8,
                label=PLOT_LABELS[market],
                color=config.MARKET_COLORS[market],
            )
    ax.axhline(100, color="#8b949e", linestyle="--", linewidth=1, label="No change (100)")
    ax.set_title("Changchun housing price index: year-over-year (previous year = 100)")
    ax.set_ylabel("Index")
    ax.grid(alpha=0.2)
    ax.legend(frameon=False, fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "changchun_yoy.png"
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_cumulative(frame: pd.DataFrame, out_dir: Path) -> Path:
    plt = _setup_matplotlib()
    cumulative = analysis.cumulative_index(frame)
    focus = cumulative[cumulative["city"] == config.FOCUS_CITY]
    pivot = focus.pivot(index="month", columns="market", values="cumulative_index").sort_index()
    x = pd.to_datetime(pivot.index + "-01")
    base = pivot.index.min()

    fig, ax = plt.subplots(figsize=(9, 4.6))
    for market in config.MARKETS:
        if market in pivot.columns:
            ax.plot(
                x,
                pivot[market],
                marker="o",
                markersize=2.5,
                linewidth=1.8,
                label=PLOT_LABELS[market],
                color=config.MARKET_COLORS[market],
            )
    ax.axhline(100, color="#8b949e", linestyle="--", linewidth=1, label=f"Base ({base}) = 100")
    ax.set_title(f"Changchun cumulative index (base {base} = 100)")
    ax.set_ylabel("Cumulative index")
    ax.grid(alpha=0.2)
    ax.legend(frameon=False, fontsize=8)
    fig.autofmt_xdate()
    fig.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "changchun_cumulative.png"
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path


def plot_peer_comparison(facts: dict[str, object], out_dir: Path) -> Path:
    plt = _setup_matplotlib()
    peers = pd.DataFrame(facts["peers"])
    if peers.empty:
        raise ValueError("no peer-city data to plot")

    peers = peers.set_index("city").reindex([city for city in config.PEER_CITIES if city in peers["city"].values])
    labels = [CITY_EN.get(city, city) for city in peers.index]
    y = range(len(peers))

    fig, ax = plt.subplots(figsize=(9, 5.0))
    all_values: list[float] = []
    for offset, market in zip((-0.12, 0.12), config.MARKETS, strict=False):
        column = f"{market}_yoy"
        if column not in peers.columns:
            continue
        values = peers[column].astype(float).tolist()
        all_values.extend(values)
        positions = [position + offset for position in y]
        ax.scatter(
            values,
            positions,
            s=38,
            label=PLOT_LABELS[market],
            color=config.MARKET_COLORS[market],
            zorder=3,
        )
        for value, position in zip(values, positions, strict=False):
            ax.annotate(
                f"{value:.1f}",
                (value, position),
                xytext=(4, 0),
                textcoords="offset points",
                va="center",
                fontsize=7,
                color="#57606a",
            )
    ax.axvline(100, color="#8b949e", linestyle="--", linewidth=1)
    ax.set_yticks(list(y), labels)
    ax.set_xlabel("Year-over-year index (previous year = 100)")
    ax.set_title(f"Latest year-over-year index: Changchun vs peers ({facts['month']})")
    if all_values:
        ax.set_xlim(min(all_values) - 0.8, max(all_values) + 1.2)
    ax.grid(axis="x", alpha=0.2)
    ax.legend(frameon=False, fontsize=8, loc="lower right")
    fig.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "peer_comparison.png"
    fig.savefig(path, dpi=160, bbox_inches="tight")
    plt.close(fig)
    return path


def _pct(index: float | None) -> str:
    if index is None or pd.isna(index):
        return "—"
    return f"{index - 100.0:+.1f}%"


def _streak_text(streak: dict[str, object]) -> str:
    months = int(streak["months"])
    if months == 0:
        return "最新月未处于同比下跌区间"
    return f"在本数据覆盖期内连续 {months} 个月同比下降（数据自 {streak['start']} 起）"


def _snapshot_table(facts: dict[str, object]) -> pd.DataFrame:
    rows = []
    for market in config.MARKETS:
        item = facts["focus"][market]
        rows.append(
            {
                "市场": config.MARKET_LABELS[market],
                "环比": _pct(item["mom_index"]),
                "同比": _pct(item["yoy_index"]),
                "年内累计": _pct(item["ytd_index"]),
                "同比排名": f"{item['yoy_rank']} / {item['city_count']}",
            }
        )
    return pd.DataFrame(rows)


def _peer_table(facts: dict[str, object]) -> pd.DataFrame:
    rows = []
    for item in facts["peers"]:
        rows.append(
            {
                "城市": item["city"],
                "新房同比": _pct(item["new_yoy"]),
                "二手房同比": _pct(item["second_hand_yoy"]),
                "新房环比": _pct(item["new_mom"]),
                "二手房环比": _pct(item["second_hand_mom"]),
            }
        )
    return pd.DataFrame(rows)


def build_readme_snapshot(facts: dict[str, object]) -> str:
    """Generate the auto-updating snapshot block for README.md."""
    median = facts["national_median"]
    cumulative = facts["cumulative"]
    lines = [
        README_START,
        f"## 最新结果（{facts['month']}）",
        "",
        md_table(_snapshot_table(facts)),
        "",
        (
            f"- 同月 70 城新房同比中位数为 **{median['new']['yoy_index']:.1f}**，"
            f"二手房为 **{median['second_hand']['yoy_index']:.1f}**。"
        ),
        (
            f"- 新房同比比二手房高 **{facts['spread_yoy']:+.1f} 个指数点**，"
            f"环比高 **{facts['spread_mom']:+.1f} 个指数点**。"
        ),
        (
            f"- 以 {cumulative['new']['base_month']} 为 100，到 {facts['month']} "
            f"新房累计指数 **{cumulative['new']['cumulative_index']:.1f}**，"
            f"二手房 **{cumulative['second_hand']['cumulative_index']:.1f}**。"
        ),
        f"- 二手房：{_streak_text(facts['streak']['second_hand'])}。",
        README_END,
    ]
    return "\n".join(lines)


def build_report(
    frame: pd.DataFrame,
    facts: dict[str, object],
    results: dict[str, pd.DataFrame],
    meta: dict[str, object],
    figures: dict[str, Path],
) -> str:
    """Compose the Chinese Markdown report from computed facts."""
    lines: list[str] = []
    add = lines.append

    latest = facts["focus"]
    new = latest["new"]
    second = latest["second_hand"]
    median = facts["national_median"]
    strength = "强于" if new["yoy_index"] > second["yoy_index"] else "弱于"
    yoy_spread = facts["spread_yoy"]
    mom_spread = facts["spread_mom"]
    source_url = str(meta.get("latest_release_url", ""))
    fetched_at = str(meta.get("fetched_at", "—"))
    fetched_date = fetched_at[:10] if fetched_at != "—" else "—"

    add("# 长春房价指数：国家统计局 70 城数据")
    add("")
    add(f"> 数据来源：{config.NBS_SOURCE_NAME}，[最新发布页]({source_url})")
    add(">")
    add(
        f"> 覆盖 **{facts['data_start']} 至 {facts['data_end']}**，"
        f"**{facts['months_covered']}** 个月、70 个城市、2 个市场；"
        f"最近更新：{fetched_date}"
    )
    add(">")
    add(
        "> 指数口径：环比为「上月 = 100」，同比为「上年同月 = 100」，"
        "年内累计为「上年同期 = 100」。**它不是成交均价，也不代表单个小区或户型。**"
    )
    add("")

    add("## 1. 最新快照")
    add("")
    add(f"**{facts['month']}，长春：**")
    add("")
    add(md_table(_snapshot_table(facts)))
    add("")
    add(
        f"新房环比 **{_pct(new['mom_index'])}**、同比 **{_pct(new['yoy_index'])}**；"
        f"二手房环比 **{_pct(second['mom_index'])}**、同比 **{_pct(second['yoy_index'])}**。"
    )
    add("")
    add(
        f"同月 70 城中位数：新房同比 {median['new']['yoy_index']:.1f}、"
        f"二手房同比 {median['second_hand']['yoy_index']:.1f}。"
    )
    add("")
    add(
        f"新房同比比二手房高 **{yoy_spread:+.1f} 个指数点**，"
        f"环比差为 **{mom_spread:+.1f} 个指数点**；"
        f"短期和同比层面，新房都{strength}二手房。"
    )
    add("")

    add("## 2. 长春新房与二手房走势")
    add("")
    add(f"![长春新房与二手房同比指数]({figures['yoy'].relative_to(config.REPORT_PATH.parent).as_posix()})")
    add("")
    add(
        f"从 {facts['data_start']} 到 {facts['month']}，新房和二手房的同比走势见上图；"
        "100 是「与上年同月持平」的分界线。"
    )
    add("")
    if facts["twelve_month"]["new"] is not None:
        previous_new = facts["twelve_month"]["new"]["yoy_index"]
        previous_second = facts["twelve_month"]["second_hand"]["yoy_index"]
        add(
            f"与 12 个月前（{facts['twelve_month']['new']['month']}）相比，"
            f"新房同比从 {previous_new:.1f} 变为 {new['yoy_index']:.1f}，"
            f"二手房同比从 {previous_second:.1f} 变为 {second['yoy_index']:.1f}。"
        )
        add("")
    add(f"![长春累计指数]({figures['cumulative'].relative_to(config.REPORT_PATH.parent).as_posix()})")
    add("")
    cumulative = facts["cumulative"]
    add(
        f"把每月的环比指数连乘起来（基期 {cumulative['new']['base_month']} = 100），"
        f"到 {facts['month']} 新房累计指数为 **{cumulative['new']['cumulative_index']:.1f}**，"
        f"二手房为 **{cumulative['second_hand']['cumulative_index']:.1f}**。"
    )
    add("")
    add(
        "累计指数用来描述「相对基期涨跌了多少」，仍然是指数口径，"
        "不能直接换算成某个小区的成交价。"
    )
    add("")

    add("## 3. 全国与同类城市对比")
    add("")
    add(f"![长春与同类城市同比对比]({figures['peers'].relative_to(config.REPORT_PATH.parent).as_posix()})")
    add("")
    add(md_table(_peer_table(facts)))
    add("")
    add(
        f"在 70 个城市中，长春新房同比排名 **{new['yoy_rank']}/{new['city_count']}**，"
        f"二手房同比排名 **{second['yoy_rank']}/{second['city_count']}**。"
        "排名只描述当前截面，不代表长期趋势。"
    )
    add("")

    add("## 4. 数据里的结论")
    add("")
    add(
        f"1. **最新一个月：新房环比 {_pct(new['mom_index'])}，"
        f"二手房环比 {_pct(second['mom_index'])}。** "
        f"新房环比比二手房高 {mom_spread:+.1f} 个指数点。"
    )
    add(
        f"2. **同比层面二手房调整更深：** 新房同比 {_pct(new['yoy_index'])}，"
        f"二手房同比 {_pct(second['yoy_index'])}，相差 {yoy_spread:+.1f} 个指数点。"
    )
    add(
        f"3. **长春新房同比在 70 城中排第 {new['yoy_rank']}，"
        f"二手房排第 {second['yoy_rank']}。** "
        f"全国中位数分别为 {median['new']['yoy_index']:.1f} 和 "
        f"{median['second_hand']['yoy_index']:.1f}。"
    )
    add(
        f"4. **二手房：{_streak_text(facts['streak']['second_hand'])}。** "
        "这说明二手房同比在最近一段时间持续低于 100，而不是单月波动。"
    )
    add(
        f"5. **自 {cumulative['new']['base_month']} 以来，"
        f"新房累计 {cumulative['new']['change_pct']:+.1f}%，"
        f"二手房累计 {cumulative['second_hand']['change_pct']:+.1f}%。** "
        "这说明两个市场的走势分化是累积形成的，不只发生在最新一个月。"
    )
    add("")
    add(
        "> 这些结论是**指数层面的描述**，不是因果解释。要解释为什么，需要成交量、"
        "收入、人口、土地供给、政策等数据；单看价格指数无法回答。"
    )
    add("")

    add("## 5. SQL 问题")
    add("")
    for index, (name, table) in enumerate(results.items(), start=1):
        add(f"### Q{index}. {name}")
        add("")
        add(md_table(table))
        add("")

    add("## 6. 方法与局限")
    add("")
    add(
        "- **数据口径**：国家统计局 70 城商品住宅销售价格指数；环比/同比/年内累计均以 100 为基准。"
    )
    add(
        "- **城市级，不是小区级**：没有区县、面积段、楼层、装修、学区等维度；"
        "不能回答「长春哪个区最贵」。"
    )
    add(
        "- **指数不是成交价**：它衡量的是价格变动，不是绝对价格；不能直接换算成每平米单价。"
    )
    add(
        "- **没有成交量**：价格指数不能说明「有价无市」还是「以价换量」，也不能单独解释原因。"
    )
    add(
        "- **发布与修订**：NBS 按月发布，历史数据可能修订；本仓库保存的是抓取时点的发布值。"
    )
    add(
        "- **抓取方式**：通过 NBS 公开搜索接口定位每月发布页，再解析 HTML 表格；"
        "如果 NBS 改版，`src.update` 会失败而不是静默写入错误数据。"
    )
    add("")

    add("## 7. 更新与复现")
    add("")
    add("```bash")
    add("python -m pip install -r requirements.txt")
    add("python -m src.update --months 2      # 抓取最新发布（已有月份会跳过）")
    add("python -m src.pipeline               # 校验 → SQLite → SQL → 图表 → 报告")
    add("python -m unittest discover -s tests -v")
    add("```")
    add("")
    add(
        "GitHub Actions 在每月 20 日和 25 日自动检查新发布；有变化时提交数据、"
        "图表和本报告。也可以手动触发 `update-data` workflow。"
    )
    add("")

    add("## 8. 数据来源与许可")
    add("")
    add(
        f"- 数据：{config.NBS_SOURCE_NAME}，"
        f"[发布页]({config.NBS_INDEX_PAGE})；最新一期：[链接]({source_url})。"
    )
    add("- 代码：MIT；数据版权归国家统计局，仓库仅用于学习、研究与可复现分析。")
    add("")
    return "\n".join(lines)
