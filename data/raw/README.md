# Real data: NBS 70-city housing price index

This directory contains the data used by the analysis. The previous synthetic
`listings.csv` scaffold has been removed.

## Source

- Publisher: 国家统计局 (National Bureau of Statistics of China)
- Release: `YYYY年M月份70个大中城市商品住宅销售价格变动情况`
- Landing page: <https://www.stats.gov.cn/sj/zxfb/>
- Latest release: see `meta.json` (`latest_release_url`)
- Update cadence: monthly, usually around the 15th–20th of the following month

The NBS index is a **price-change index**, not a transaction price:

- `mom_index`: previous month = 100; `100.3` means +0.3% MoM.
- `yoy_index`: same month last year = 100; `99.3` means -0.7% YoY.
- `ytd_index`: same period last year = 100; may be missing for January releases.

## Files

| File | Meaning |
| --- | --- |
| `nbs_housing_index.csv` | Tidy dataset: one row per month/market/city |
| `releases.csv` | Monthly release title, source URL, and fetch time |
| `meta.json` | Latest month, coverage, row count, source URL, SHA-256 |

`nbs_housing_index.csv` columns:

| Column | Meaning |
| --- | --- |
| `month` | `YYYY-MM` |
| `market` | `new` (new commodity housing) or `second_hand` |
| `city` | NBS city name, whitespace normalised |
| `mom_index` | MoM index, previous month = 100 |
| `yoy_index` | YoY index, same month last year = 100 |
| `ytd_index` | YTD average index, same period last year = 100; nullable |
| `source_url` | Exact monthly release page |

## Update

```bash
python -m src.update --months 2
python -m src.pipeline
```

Rebuild the full history:

```bash
python -m src.update --backfill 48 --force
```

The updater searches NBS's public search API for the exact monthly title,
downloads the release page, parses the two main HTML tables, validates
70 cities per market, and only then writes the files. If NBS changes the page
layout, the update fails instead of silently writing bad data.

## Attribution and license

The data is published by the National Bureau of Statistics of China. This
repository uses it for learning and reproducible analysis; the code is MIT
licensed, while the data remains subject to the publisher's terms. Always cite
NBS and the exact release page when reusing the data.
