"""Load the cleaned processed CSVs into a SQLite database.

Applies sql/schema.sql (tables, keys, indexes), inserts cleaned data with
foreign keys enabled, and leaves rfm_segments empty for segmentation.py to fill.

Run:  python src/load_db.py
"""
from __future__ import annotations

import sqlite3
import pandas as pd

from config import load_config, ensure_dirs, DATA_PROCESSED, DB_PATH, SQL_DIR

LOAD_ORDER = ["customers", "merchants", "campaigns", "transactions", "campaign_interactions"]


def load() -> None:
    ensure_dirs()
    if DB_PATH.exists():
        DB_PATH.unlink()

    schema = (SQL_DIR / "schema.sql").read_text(encoding="utf-8")
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(schema)
        conn.execute("PRAGMA foreign_keys = ON;")

        for name in LOAD_ORDER:
            df = pd.read_csv(DATA_PROCESSED / f"{name}.csv")
            # pandas writes NaN as NULL only if we convert to object None
            df = df.where(pd.notna(df), None)
            df.to_sql(name, conn, if_exists="append", index=False)
            print(f"  loaded {name:24s} {len(df):>7,} rows")

        # integrity check
        problems = conn.execute("PRAGMA foreign_key_check;").fetchall()
        if problems:
            raise RuntimeError(f"Foreign key violations after load: {problems[:5]}")
        conn.commit()
        print(f"\nSQLite database written to {DB_PATH} (foreign keys OK)")
    finally:
        conn.close()


if __name__ == "__main__":
    load_config()  # validate config is readable
    load()
