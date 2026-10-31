# 长春房价指数：国家统计局 70 城真实数据

把**国家统计局每月发布的 70 个大中城市商品住宅销售价格指数**抓下来、校验、入库、用 SQL 提问，再自动生成图表和报告。

这不是一个“用示例数据跑通流程”的脚手架：仓库里的 `data/raw/nbs_housing_index.csv` 是真实发布数据，覆盖 **2022-10 至 2026-09**、**48 个月、70 个城市、2 个市场**，并且可以通过 GitHub Actions 每月自动更新。

> **重要口径**：NBS 指数是价格**变动**指数，不是成交均价。环比“上月 = 100”，同比“上年同月 = 100”，年内累计“上年同期 = 100”。它不能直接换算成某个小区的每平米单价。

![Tests](https://github.com/Wang-xinyu-2007/changchun-housing/actions/workflows/tests.yml/badge.svg)
![Update](https://github.com/Wang-xinyu-2007/changchun-housing/actions/workflows/update-data.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.10%2B-blue)
![Data](https://img.shields.io/badge/data-NBS%2070--city%20index-orange)

---

<!-- LATEST_SNAPSHOT_START -->
## 最新结果（2026-09）

| 市场 | 环比 | 同比 | 年内累计 | 同比排名 |
| --- | --- | --- | --- | --- |
| 新房 | +0.3% | -0.7% | -1.6% | 9 / 70 |
| 二手房 | -0.4% | -3.6% | -3.9% | 17 / 70 |

- 同月 70 城新房同比中位数为 **96.6**，二手房为 **95.0**。
- 新房同比比二手房高 **+2.9 个指数点**，环比高 **+0.7 个指数点**。
- 以 2022-10 为 100，到 2026-09 新房累计指数 **89.8**，二手房 **80.4**。
- 二手房：在本数据覆盖期内连续 48 个月同比下降（数据自 2022-10 起）。
<!-- LATEST_SNAPSHOT_END -->

完整报告：[`reports/report.md`](reports/report.md)  
SQL 问题：[`sql/questions.sql`](sql/questions.sql)  
数据说明：[`data/raw/README.md`](data/raw/README.md)

---

## 为什么这个项目值得看

它把一条真实数据的完整链路跑通了，而不是只展示一个分析结论：

1. **真实来源**：通过 NBS 公开搜索接口定位每月发布页，解析官方 HTML 表格，保存来源 URL 和抓取元数据。
2. **可更新**：`python -m src.update --months 2` 检查最新发布；GitHub Actions 每月 20/25 日自动运行。
3. **可验证**：校验 70 个城市、2 个市场、月份/市场/城市唯一性、指数范围；NBS 改版时更新会失败，而不是静默写入错误数据。
4. **可复现**：`python -m src.pipeline` 从已提交 CSV 重建 SQLite、SQL 结果、3 张图和整份报告。
5. **有边界**：报告明确说明指数不是成交价、城市级不是小区级、没有成交量，不能做因果解释。

---

## 快速开始

```bash
git clone https://github.com/Wang-xinyu-2007/changchun-housing.git
cd changchun-housing

python -m pip install -r requirements.txt

# 用已提交的真实数据重建数据库、SQL、图表和报告
python -m src.pipeline

# 跑测试（不依赖网络）
python -m unittest discover -s tests -v
```

想抓取最新发布：

```bash
python -m src.update --months 2
python -m src.pipeline
```

第一次构建/重建完整历史：

```bash
python -m src.update --backfill 48 --force
```

`src.update` 会：
- 搜索每月精确标题；
- 下载发布页；
- 解析“新房 / 二手房”两张主表；
- 校验 70 个城市；
- 合并去重后写入 `data/raw/`；
- 更新 `meta.json` 和 `releases.csv`。

如果某个月还没发布、或 NBS 页面结构变化，它会跳过或报错，不会写入不完整的月份。

---

## 每个月自动更新

[`.github/workflows/update-data.yml`](.github/workflows/update-data.yml) 在每月 **20 日和 25 日**（北京时间上午）运行：

```text
checkout → 安装依赖 → src.update --months 2
→ src.pipeline → 单元测试
→ 有变化则提交 data/ 和 reports/
```

也可以在 Actions 页面手动触发 `update-data`。NBS 通常在每月 15–20 日发布上一个月数据；25 日再检查一次，给延迟发布留余量。

---

## 数据与指标

| 字段 | 含义 |
| --- | --- |
| `month` | `YYYY-MM` |
| `market` | `new`（新房）/ `second_hand`（二手房） |
| `city` | NBS 城市名（已去掉全角空格） |
| `mom_index` | 环比，上月 = 100 |
| `yoy_index` | 同比，上年同月 = 100 |
| `ytd_index` | 年内累计，上年同期 = 100；1 月发布可能为空 |
| `source_url` | 该月 NBS 发布页 |

`data/raw/nbs_housing_index.csv` 是 tidy 长表，一行 = 一个月 × 一个市场 × 一个城市。`data/raw/releases.csv` 保存每月标题、URL 和抓取时间；`meta.json` 保存最新月份、覆盖范围、行数、来源 URL 和 CSV SHA-256。

---

## 分析内容

报告回答这些问题：

1. 长春新房/二手房最新环比、同比、年内累计是多少？
2. 长春在 70 个城市中同比排第几？
3. 长春和沈阳、哈尔滨、大连、北京、上海、广州、深圳、杭州、成都相比如何？
4. 新房和二手房的走势分化有多大？是单月现象还是持续趋势？
5. 自 2022-10 以来，两个市场累计涨跌了多少？

SQL 覆盖：最新快照、近 12 个月走势、全国排名（窗口函数 `RANK`）、同类城市对比、新房/二手房同比价差。

报告和图表全部由 `src.pipeline` 生成：

- `reports/figures/changchun_yoy.png`：长春新房/二手房同比走势
- `reports/figures/changchun_cumulative.png`：以 2022-10 为 100 的累计指数
- `reports/figures/peer_comparison.png`：最新月份与同类城市的同比对比

---

## 项目结构

```text
src/
  config.py     # 路径、数据源、城市/市场常量
  nbs.py        # NBS 搜索、下载、HTML 表格解析
  update.py     # 增量更新 + 回填 + 校验 + 元数据
  analysis.py   # 数据校验、累计指数、排名、连续下跌、报告指标
  store.py      # SQLite 写入与 SQL 查询
  report.py     # 图表 + Markdown 报告
  pipeline.py   # 一键重建
sql/questions.sql
data/raw/       # 真实 CSV、releases.csv、meta.json、数据说明
reports/        # 提交的报告和图表
tests/          # 20 个离线单元/集成测试 + HTML fixture
```

---

## 测试

```bash
python -m unittest discover -s tests -v
```

- **20 个测试**，不访问网络；
- 解析器使用最小 HTML fixture，覆盖 8 列双城市、6 列无 YTD（1 月）两种版式；
- 搜索接口使用 mock，验证精确标题匹配；
- 校验器覆盖重复行、异常指数、城市数量；
- 集成测试检查真实 CSV 的 70 城完整性，并把 5 条 SQL 真正跑一遍。

CI 还会在干净环境里重新执行 `src.pipeline`，确认报告可重建。

---

## 已知局限

- **城市级，不是小区级**：没有区县、面积段、楼层、装修、学区，不能回答“长春哪个区最贵”。
- **指数不是价格**：只能看变动方向和幅度，不能直接换算成元/平方米。
- **没有成交量**：不能判断“有价无市”还是“以价换量”，也不能单独解释原因。
- **发布与修订**：NBS 可能修订历史值；仓库保存的是抓取时点的发布值。
- **搜索接口不是正式 API**：通过 NBS 公开搜索页使用的查询接口定位发布页；如果接口或页面改版，更新会失败并保留旧数据。
- **1 月缺少年内累计**：NBS 1 月表没有“1 月平均”列，报告中显示为 `—`。

要解释“为什么”，还需要成交量、收入、人口、土地供给、政策等数据；单看价格指数不够。

---

## 数据来源与许可

- 数据：国家统计局，[70 个大中城市商品住宅销售价格变动情况](https://www.stats.gov.cn/sj/zxfb/)；每月发布页链接保存在 `data/raw/releases.csv`。
- 代码：MIT。数据版权归国家统计局，仓库仅用于学习、研究与可复现分析；转载数据请注明来源和具体发布页。

> 这是一个个人数据分析项目，不构成投资建议。
