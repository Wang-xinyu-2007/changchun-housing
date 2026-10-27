"""数据清洗：把一份"脏"的挂牌表变成能分析的表。

这个文件是整个项目最值得看的部分。真实数据一定是脏的，
面试官问得最多的也是"你清洗时遇到最大的问题是什么"。

清洗分六步，每一步都记进 stats，最后连成一份"脏数据报告"：
    1. 统一区名         "朝阳" -> "朝阳区"
    2. 解析金额         "85万" / "850000" / "85" -> 85.0（万元）
    3. 数值化           面积 "89.5㎡" -> 89.5
    4. 去重             同一个 listing_id 只留第一条
    5. 业务规则过滤     面积/总价/单价超出常识范围的行
    6. 派生字段         单价缺失时用总价/面积补，再算房龄
"""

from __future__ import annotations

import pandas as pd

from . import config

NAN = float("nan")


# ---------------------------------------------------------------------------
# 单字段解析（每一步都能单独测）
# ---------------------------------------------------------------------------

def normalize_district(value: object) -> str:
    """把区名统一成 DISTRICTS 里的标准写法。认不出来就原样返回。"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return config.UNKNOWN_DISTRICT

    text = str(value).strip().replace(" ", "")
    if not text:
        return config.UNKNOWN_DISTRICT
    if text in config.DISTRICT_ALIASES:
        return config.DISTRICT_ALIASES[text]
    if text in config.DISTRICTS:
        return text
    # 少写了一个"区"的情况
    if text + "区" in config.DISTRICTS:
        return text + "区"
    return text


def parse_price_wan(value: object) -> float:
    """把各种写法的挂牌价统一成「万元」。

    '85'      -> 85.0        （本来就按万元填的）
    '85.5万'  -> 85.5
    '850000'  -> 85.0        （按元填的，大于 1 万的当作元）
    '85,0000' -> 85.0
    ''/None   -> NaN         （缺失，交给后面决定丢还是补）
    """
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return NAN

    text = str(value).strip().replace(",", "").replace("，", "")
    if not text or text in {"-", "--", "暂无", "nan", "None"}:
        return NAN

    text = text.replace("万元", "万").replace("W", "万").replace("w", "万")
    if text.endswith("万"):
        text = text[:-1].strip()

    number = pd.to_numeric(text, errors="coerce")
    if pd.isna(number):
        return NAN

    # 大于 1 万的数字，几乎不可能是"万元"，按"元"处理
    return float(number) / 10000.0 if float(number) > 10000.0 else float(number)


def parse_area(value: object) -> float:
    """'89.5㎡' / '89.5平米' / '89.5' -> 89.5；解析不了返回 NaN。"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return NAN

    text = str(value).strip()
    for unit in ("平方米", "平米", "平方", "㎡", "m2", "M2", "m²"):
        text = text.replace(unit, "")
    text = text.strip().replace(",", "")

    number = pd.to_numeric(text, errors="coerce")
    return float(number) if pd.notna(number) else NAN


def parse_number(value: object) -> float:
    """房龄、楼层数这类普通数字。"""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return NAN
    number = pd.to_numeric(str(value).strip(), errors="coerce")
    return float(number) if pd.notna(number) else NAN


# ---------------------------------------------------------------------------
# 主流程
# ---------------------------------------------------------------------------

def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """清洗整张表，返回 (干净的表, 清洗统计)。"""
    stats: dict[str, object] = {"原始行数": len(df)}

    work = df.copy()

    # 1. 字符串字段统一去空格
    for column in ("district", "community", "floor", "orientation", "listed_date"):
        if column in work.columns:
            work[column] = work[column].astype("string").str.strip()

    # 2. 区名归一
    work["district"] = work["district"].map(normalize_district)

    # 3. 数值字段解析
    work["area_m2"] = work["area_m2"].map(parse_area)
    work["total_price_wan"] = work["total_price_wan"].map(parse_price_wan)
    work["unit_price"] = work["unit_price"].map(parse_number)
    if "build_year" in work.columns:
        work["build_year"] = work["build_year"].map(parse_number)
    if "rooms" in work.columns:
        work["rooms"] = work["rooms"].map(parse_number)

    # 4. 去重：同一个房源可能被重复挂牌（中介换价格重发）
    before = len(work)
    work = work.drop_duplicates(subset="listing_id", keep="first")
    stats["重复删除"] = before - len(work)

    # 5. 必填字段缺失：直接丢
    before = len(work)
    work = work.dropna(subset=["listing_id", "district", "area_m2", "total_price_wan"])
    stats["必填缺失删除"] = before - len(work)

    # 6. 业务规则过滤：面积、总价、单价超出常识范围
    before = len(work)
    area_ok = work["area_m2"].between(config.AREA_MIN, config.AREA_MAX)
    price_ok = work["total_price_wan"].between(config.TOTAL_PRICE_MIN, config.TOTAL_PRICE_MAX)
    work = work[area_ok & price_ok]
    stats["面积/总价异常删除"] = before - len(work)

    # 7. 单价：优先用原有的，缺失或明显不对就用总价/面积重算
    calculated = work["total_price_wan"] * 10000.0 / work["area_m2"]
    unit_ok = work["unit_price"].between(config.UNIT_PRICE_MIN, config.UNIT_PRICE_MAX)
    stats["单价重新计算"] = int((~unit_ok).sum())
    work["unit_price"] = work["unit_price"].where(unit_ok, calculated)

    # 单价重算后仍不合理的（总价和面积本身矛盾），再删一次
    before = len(work)
    work = work[work["unit_price"].between(config.UNIT_PRICE_MIN, config.UNIT_PRICE_MAX)]
    stats["单价异常删除"] = before - len(work)

    # 8. 派生字段
    work["房龄"] = (config.REFERENCE_YEAR - work["build_year"]).clip(lower=0)
    work["单价万元"] = work["unit_price"] / 10000.0

    work = work.sort_values(["district", "unit_price"], ascending=[True, False]).reset_index(drop=True)

    stats["最终行数"] = len(work)
    stats["保留比例"] = f"{len(work) / max(stats['原始行数'], 1):.1%}"
    return work, stats


def describe_missing(df: pd.DataFrame) -> pd.DataFrame:
    """每个字段缺了多少，按缺失比例排序。报告里会用到。"""
    missing = df.isna().sum()
    result = pd.DataFrame({
        "字段": missing.index,
        "缺失数": missing.to_numpy(),
        "缺失比例": (missing / max(len(df), 1)).to_numpy(),
    })
    return result.sort_values("缺失数", ascending=False).reset_index(drop=True)
