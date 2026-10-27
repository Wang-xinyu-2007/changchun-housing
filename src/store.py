"""存储层：清洗结果写进 SQLite，然后直接用 SQL 问问题。

为什么用 SQL 而不是 pandas 一口气算完？
因为真实工作里，分析师的 80% 时间在 SQL 上，而且 SQL 写得好，
换工具（Excel/BI/数据库）也照样能用。这个项目刻意把「问什么」
和「怎么算」分开：问题写在 sql/questions.sql，代码只负责执行。
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pandas as pd


def write_sqlite(df: pd.DataFrame, db_path: Path, table: str = "listings") -> Path:
    """整表写入 SQLite（每次覆盖，保证可复现）。"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    # 注意：`with sqlite3.connect(...)` 只负责提交事务，不会关闭连接。
    # Windows 上不关连接，文件就会被锁住，删都删不掉。
    conn = sqlite3.connect(db_path)
    try:
        df.to_sql(table, conn, index=False)
        conn.execute(f"CREATE INDEX idx_{table}_district ON {table}(district)")
        conn.commit()
    finally:
        conn.close()
    return db_path


def load_queries(sql_path: Path) -> list[dict[str, str]]:
    """解析 sql/questions.sql。

    文件格式（一条查询一段）：

        -- name: 各区均价
        -- 说明: 用来看哪个区最贵
        SELECT ...;
    """
    text = sql_path.read_text(encoding="utf-8")
    blocks = re.split(r"^--\s*name:\s*", text, flags=re.MULTILINE)[1:]

    queries: list[dict[str, str]] = []
    for block in blocks:
        lines = block.splitlines()
        name = lines[0].strip()
        body = "\n".join(line for line in lines[1:] if not line.strip().startswith("--"))
        if body.strip():
            queries.append({"name": name, "sql": body.strip()})
    return queries


def run_queries(db_path: Path, queries: list[dict[str, str]]) -> dict[str, pd.DataFrame]:
    """依次执行所有查询，返回 {名字: 结果表}。"""
    results: dict[str, pd.DataFrame] = {}
    conn = sqlite3.connect(db_path)
    try:
        for query in queries:
            results[query["name"]] = pd.read_sql_query(query["sql"], conn)
    finally:
        conn.close()
    return results
