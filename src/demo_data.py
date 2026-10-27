"""生成示例数据（不是真实行情！）。

用途有两个：
  1. 让刚 clone 下来的人能一条命令跑通整条流程；
  2. 给单元测试提供固定的输入。

真实数据请放到 data/raw/listings.csv，覆盖掉这里生成的示例文件。
示例数据故意掺了脏东西：缺失、重复、"85万"这种带单位的字符串、
按"元"填的价格、离谱的面积——就是为了让清洗逻辑有活干。
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from . import config

COLUMNS = [
    "listing_id", "district", "community", "area_m2", "total_price_wan",
    "unit_price", "floor", "total_floors", "rooms", "orientation",
    "build_year", "listed_date",
]


def make_demo_data(rows: int = 800, seed: int = 20260101) -> pd.DataFrame:
    """生成一份带脏数据的挂牌表。"""
    rng = np.random.default_rng(seed)

    districts = list(config.DEMO_PROFILE)
    weights = np.array([config.DEMO_PROFILE[d][1] for d in districts], dtype=float)
    weights = weights / weights.sum()

    records = []
    for index in range(rows):
        district = str(rng.choice(districts, p=weights))
        base_price = config.DEMO_PROFILE[district][0]

        area = float(np.clip(rng.lognormal(mean=np.log(85.0), sigma=0.32), 28.0, 220.0))

        # 年份：2010 年后的房子多一些（真实市场也是这样）
        build_year = int(rng.choice(
            np.arange(1995, 2025),
            p=_year_weights(),
        ))
        age = config.REFERENCE_YEAR - build_year

        # 小户型单价略高、老房子单价略低，再加 8% 的随机波动
        area_factor = 1.0 + (90.0 - area) / 90.0 * 0.05
        age_factor = max(0.72, 1.0 - age * 0.004)
        noise = 1.0 + rng.normal(0.0, 0.08)
        unit_price = base_price * area_factor * age_factor * noise

        total_price = unit_price * area / 10000.0  # 万元

        if area < 60:
            rooms = 1
        elif area < 90:
            rooms = 2
        elif area < 130:
            rooms = 3
        else:
            rooms = 4
        if rng.random() < 0.1:  # 少量"两室改三室"这类情况
            rooms = max(1, rooms + int(rng.choice([-1, 1])))

        records.append({
            "listing_id": f"CC{index + 1:05d}",
            "district": district,
            "community": f"{district[:2]}{rng.integers(1, 60):02d}号院",
            "area_m2": round(area, 1),
            "total_price_wan": round(total_price, 1),
            "unit_price": round(unit_price),
            "floor": str(rng.choice(["低楼层", "中楼层", "高楼层"], p=[0.28, 0.42, 0.30])),
            "total_floors": int(rng.integers(6, 33)),
            "rooms": rooms,
            "orientation": str(rng.choice(
                ["南", "南北", "东南", "西南", "东", "西", "北"],
                p=[0.30, 0.28, 0.12, 0.10, 0.08, 0.07, 0.05],
            )),
            "build_year": build_year,
            "listed_date": (
                pd.Timestamp("2026-01-01") + pd.Timedelta(days=int(rng.integers(0, 270)))
            ).date().isoformat(),
        })

    frame = pd.DataFrame(records, columns=COLUMNS)
    return _make_dirty(frame, rng)


def _year_weights() -> np.ndarray:
    """1995-2024 每年的抽样权重：越新的房子越多。"""
    years = np.arange(1995, 2025)
    weights = np.exp((years - 1995) / 12.0)
    return weights / weights.sum()


def _make_dirty(frame: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """往干净数据里掺脏东西，模拟真实挂牌数据。

    注意：整个表先转成 object 类型，否则往 float 列里塞 "85万" 这种字符串
    会被 pandas 3 直接拒绝（pandas 2 会悄悄变成 object，更坑）。
    每一行只"弄脏"一次，避免一行的价格既带"万"又按元算。
    """
    dirty = frame.copy().astype(object)
    n = len(dirty)
    used = np.zeros(n, dtype=bool)

    def pick(probability: float) -> np.ndarray:
        """挑一批还没被弄脏的行。"""
        mask = (rng.random(n) < probability) & ~used
        used[mask] = True
        return mask

    # 1) 区名少写"区"（中介系统里常见）
    mask = pick(0.05)
    dirty.loc[mask, "district"] = dirty.loc[mask, "district"].str.replace("区", "", regex=False)

    # 2) 价格写成 "85.5万"
    mask = pick(0.05)
    dirty.loc[mask, "total_price_wan"] = dirty.loc[mask, "total_price_wan"].map(lambda v: f"{v}万")

    # 3) 价格按"元"填（导入时单位没统一）
    mask = pick(0.04)
    dirty.loc[mask, "total_price_wan"] = (dirty.loc[mask, "total_price_wan"].astype(float) * 10000).round(0)

    # 4) 面积带单位
    mask = pick(0.05)
    dirty.loc[mask, "area_m2"] = dirty.loc[mask, "area_m2"].map(lambda v: f"{v}㎡")

    # 5) 总价缺失
    mask = pick(0.02)
    dirty.loc[mask, "total_price_wan"] = ""

    # 6) 单价缺失或为 0
    mask = pick(0.03)
    dirty.loc[mask, "unit_price"] = 0

    # 7) 离谱的面积和价格（录入错误）
    mask = pick(0.01)
    dirty.loc[mask, "area_m2"] = 9999
    mask = pick(0.01)
    dirty.loc[mask, "total_price_wan"] = 99999

    # 8) 日期格式不统一
    mask = pick(0.05)
    dirty.loc[mask, "listed_date"] = dirty.loc[mask, "listed_date"].astype(str).str.replace("-", "/")

    # 9) 重复挂牌：同一个 listing_id 出现两次（换了价格重发）
    duplicates = dirty.sample(frac=0.05, random_state=7)
    dirty = pd.concat([dirty, duplicates], ignore_index=True)

    return dirty.sample(frac=1.0, random_state=11).reset_index(drop=True)


def main() -> None:
    frame = make_demo_data()
    config.RAW_CSV.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(config.RAW_CSV, index=False, encoding="utf-8-sig")
    print(f"已生成示例数据：{config.RAW_CSV}（{len(frame)} 行）")
    print("提醒：这是示例数据，不是真实行情；换真实数据直接覆盖这个文件即可。")


if __name__ == "__main__":
    main()
