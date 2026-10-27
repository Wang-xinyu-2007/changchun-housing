"""出报告：把 SQL 的结果和几张图拼成一份 Markdown。

图片用 matplotlib 画，中文字体做了一轮兜底（Windows/macOS/Linux 各找一个），
找不到中文字体也不影响流程，只是中文会显示成方块。
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from . import config

# ---------------------------------------------------------------------------
# Markdown 小工具（不依赖 tabulate）
# ---------------------------------------------------------------------------

def md_table(df: pd.DataFrame, float_format: str = ",.1f") -> str:
    """把 DataFrame 转成 Markdown 表格。

    用 itertuples 而不是 iterrows：后者会把一整行统一转成 float，
    整数列 1 就变成 "1.0" 了（pandas 里非常经典的坑）。
    """
    if df.empty:
        return "_（没有数据）_"

    columns = [str(c) for c in df.columns]
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join("---" for _ in columns) + " |",
    ]
    for row in df.itertuples(index=False, name=None):
        cells = []
        for value in row:
            if isinstance(value, float):
                cells.append(format(value, float_format))
            else:
                cells.append(str(value))
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 画图
# ---------------------------------------------------------------------------

def _setup_matplotlib():
    """初始化 matplotlib，并尽量找一个能显示中文的字体。"""
    import matplotlib

    matplotlib.use("Agg")  # 不弹窗口，直接出图（服务器上必须）
    import matplotlib.pyplot as plt

    for name in ("Microsoft YaHei", "SimHei", "PingFang SC",
                 "Noto Sans CJK SC", "WenQuanYi Zen Hei"):
        try:
            matplotlib.font_manager.findfont(name, fallback_to_default=False)
        except Exception:
            continue
        matplotlib.rcParams["font.sans-serif"] = [name]
        break

    matplotlib.rcParams["axes.unicode_minus"] = False
    return plt


def plot_district_price(df: pd.DataFrame, label_col: str, value_col: str, out_dir: Path) -> Path | None:
    """各区均价横向条形图。"""
    if df.empty:
        return None
    plt = _setup_matplotlib()
    data = df.sort_values(value_col, ascending=True)

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.barh(data[label_col], data[value_col], color="#2f81f7")
    ax.set_xlabel("平均单价（元/平方米）")
    ax.set_title("长春各区二手房挂牌均价")
    for y, value in enumerate(data[value_col]):
        ax.text(value, y, f" {value:,.0f}", va="center", fontsize=9)
    ax.margins(x=0.12)
    fig.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "district_price.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def plot_area_band(df: pd.DataFrame, label_col: str, value_col: str, out_dir: Path) -> Path | None:
    """面积段与均价的关系。"""
    if df.empty:
        return None
    plt = _setup_matplotlib()

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.bar(df[label_col], df[value_col], color="#3fb950")
    ax.set_ylabel("平均单价（元/平方米）")
    ax.set_title("不同面积段的挂牌均价")
    for x, value in enumerate(df[value_col]):
        ax.text(x, value, f"{value:,.0f}", ha="center", va="bottom", fontsize=9)
    ax.margins(y=0.12)
    fig.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "area_band_price.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


def plot_price_hist(df: pd.DataFrame, out_dir: Path) -> Path | None:
    """单价分布直方图——看数据结构比看均值重要得多。"""
    if df.empty:
        return None
    plt = _setup_matplotlib()

    fig, ax = plt.subplots(figsize=(8, 4.5))
    ax.hist(df["unit_price"], bins=30, color="#d29922", edgecolor="white")
    ax.set_xlabel("单价（元/平方米）")
    ax.set_ylabel("房源数")
    ax.set_title("挂牌单价的分布")
    fig.tight_layout()

    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / "price_hist.png"
    fig.savefig(path, dpi=140)
    plt.close(fig)
    return path


# ---------------------------------------------------------------------------
# 报告正文
# ---------------------------------------------------------------------------

def build_report(
    clean_df: pd.DataFrame,
    stats: dict,
    results: dict[str, pd.DataFrame],
    missing: pd.DataFrame,
    source_note: str,
    figures: dict[str, Path | None],
    hist_figure: Path | None = None,
) -> str:
    """拼出 reports/report.md 的全文。"""
    lines: list[str] = []
    add = lines.append

    add("# 长春二手房挂牌数据分析")
    add("")
    add(f"> 数据来源：{source_note}")
    add(">")
    add("> 这份报告由 `python -m src.pipeline` 自动生成，改 SQL 或换数据后重跑即可。")
    add("")

    add("## 1. 数据概况")
    add("")
    add(f"- 清洗后房源：**{len(clean_df)}** 套")
    add(f"- 覆盖区：**{clean_df['district'].nunique()}** 个")
    add(f"- 单价中位数：**{clean_df['unit_price'].median():,.0f}** 元/平方米")
    add(f"- 总价中位数：**{clean_df['total_price_wan'].median():,.1f}** 万元")
    add("")

    add("### 清洗过程")
    add("")
    add("| 步骤 | 行数变化 |")
    add("| --- | --- |")
    for key in ("原始行数", "重复删除", "必填缺失删除", "面积/总价异常删除",
                "单价异常删除", "最终行数", "保留比例"):
        if key in stats:
            add(f"| {key} | {stats[key]} |")
    add("")
    add(f"（其中 {stats.get('单价重新计算', 0)} 行单价缺失或明显不对，用「总价 ÷ 面积」重算）")
    add("")

    if hist_figure is not None:
        add(f"![单价分布]({hist_figure.relative_to(config.REPORT_PATH.parent).as_posix()})")
        add("")
        add("> 看分布比看均值重要：多数分析会在这里发现「双峰」或「长尾」，")
        add("> 那才是值得写进结论的东西。")
        add("")

    add("### 字段缺失情况（清洗前）")
    add("")
    add(md_table(missing[missing["缺失数"] > 0].head(8), float_format=",.3f"))
    add("")

    # ---- 每个 SQL 问题一段 ----
    add("## 2. 五个问题")
    add("")
    for index, (name, table) in enumerate(results.items(), start=1):
        add(f"### Q{index}. {name}")
        add("")
        if name in figures and figures[name] is not None:
            relative = figures[name].relative_to(config.REPORT_PATH.parent).as_posix()
            add(f"![{name}]({relative})")
            add("")
        add(md_table(table.head(12)))
        add("")

    add("## 3. 结论")
    add("")
    add("> 这一节要你自己写。套路是：一句结论 + 一个数字 + 一个可能的解释。")
    add(">")
    add("> 例：*净月区均价最高（11,300 元/㎡），比最低的宽城区高 40%，")
    add("> 可能和学区、新房供给结构有关，需要分房龄再看一遍。*")
    add("")
    add("- TODO: 结论 1")
    add("- TODO: 结论 2")
    add("- TODO: 结论 3")
    add("")

    add("## 4. 取舍与局限")
    add("")
    add("- 挂牌价 ≠ 成交价：真实成交通常低于挂牌 5%~10%，这份数据只能看「卖家想要多少」。")
    add("- 只用了挂牌时点的截面数据，没有时间序列，无法判断涨跌。")
    add("- 学区、地铁、装修这些真正影响价格的因素没有进模型。")
    add("- 异常值用固定区间过滤，可能误伤真实的极端房源（比如别墅）。")
    add("")

    return "\n".join(lines)
