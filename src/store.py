"""SQLite storage and SQL question runner.

The data is small enough for pandas, but the project intentionally keeps the
questions in SQL so the analysis layer can be inspected and reused by any BI
or database tool.
"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

import pandas as pd


def write_sqlite(df: pd.DataFrame, db_path: Path, table: str = "housing_index") -> Path:
    """Replace the SQLite database with the current tidy dataset."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if db_path.exists():
        db_path.unlink()

    connection = sqlite3.connect(db_path)
    try:
        df.to_sql(table, connection, index=False)
        connection.execute(f"CREATE INDEX idx_{table}_month ON {table}(month)")
        connection.execute(f"CREATE INDEX idx_{table}_city ON {table}(city)")
        connection.execute(f"CREATE INDEX idx_{table}_market ON {table}(market)")
        connection.commit()
    finally:
        connection.close()
    return db_path


def load_queries(sql_path: Path) -> list[dict[str, str]]:
    """Parse `sql/questions.sql` into named queries.

    Format:
        -- name: 长春最新快照
        -- 说明: ...
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
    """Run every named query and return the result frames."""
    results: dict[str, pd.DataFrame] = {}
    connection = sqlite3.connect(db_path)
    try:
        for query in queries:
            results[query["name"]] = pd.read_sql_query(query["sql"], connection)
    finally:
        connection.close()
    return results
