"""Load Olist Brazilian E-Commerce CSV data into Postgres in FK-safe order.

Expected CSV layout (default ./data/):
  olist_orders_dataset.csv                  -> public.orders
  olist_customers_dataset.csv               -> public.customers
  olist_sellers_dataset.csv                 -> public.sellers
  olist_products_dataset.csv                -> public.products
  olist_product_category_name_translation.csv -> public.product_category_name_translation
  olist_order_items_dataset.csv             -> public.order_items   (FK -> orders)
  olist_order_payments_dataset.csv          -> public.order_payments (FK -> orders)
  olist_order_reviews_dataset.csv           -> public.order_reviews   (FK -> orders)
  olist_geolocation_dataset.csv             -> public.geolocation   (blocked by policy)

Usage:
    python scripts/load_data.py [--data-dir ./data] [--reset] [--no-geolocation]

Requires MCP_DATABASE_URL in environment/.env (defaults to the docker-compose
user/password: postgresql://olist_owner:olist_owner_password@localhost:5432/olist).
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv optional fallback
    load_dotenv = None

import psycopg2
from psycopg2.extras import RealDictCursor

DEFAULT_DATABASE_URL = (
    "postgresql://olist_owner:olist_owner_password@localhost:5432/olist"
)

# (table_name, csv_filename, copy_columns, column_map, upsert) in FK-safe load order.
# column_map maps CSV header names -> table column names (for CSVs with typos).
# upsert loads via staging + INSERT ... ON CONFLICT DO NOTHING (for CSVs with duplicate PKs).
LOAD_ORDER: list[tuple[str, str, list[str] | None, dict[str, str] | None, bool]] = [
    ("public.orders", "olist_orders_dataset.csv", None, None, False),
    ("public.customers", "olist_customers_dataset.csv", None, None, False),
    ("public.sellers", "olist_sellers_dataset.csv", None, None, False),
    (
        "public.products",
        "olist_products_dataset.csv",
        None,
        {
            "product_name_lenght": "product_name_length",
            "product_description_lenght": "product_description_length",
        },
        False,
    ),
    (
        "public.product_category_name_translation",
        "product_category_name_translation.csv",
        None,
        None,
        False,
    ),
    ("public.order_items", "olist_order_items_dataset.csv", None, None, False),
    ("public.order_payments", "olist_order_payments_dataset.csv", None, None, False),
    ("public.order_reviews", "olist_order_reviews_dataset.csv", None, None, True),
    ("public.geolocation", "olist_geolocation_dataset.csv", None, None, False),
]


def get_database_url() -> str:
    env_path = Path(__file__).resolve().parent.parent / ".env"
    if load_dotenv is not None and env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
    return os.getenv("MCP_DATABASE_URL", DEFAULT_DATABASE_URL)


def _copy_csv(
    cur,
    table: str,
    csv_path: Path,
    columns: list[str] | None,
    column_map: dict[str, str] | None,
    upsert: bool = False,
) -> int:
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        if header is None:
            raise ValueError(f"CSV {csv_path} has no header row")

        if not column_map and not upsert:
            # Direct COPY: CSV header names match table column names.
            col_list = columns or header
            col_sql = ", ".join(f'"{c}"' for c in col_list)
            fh.seek(0)
            sql = f'COPY {table} ({col_sql}) FROM STDIN WITH (FORMAT csv, HEADER true)'
            cur.copy_expert(sql, fh)
            cur.execute(f"SELECT COUNT(*) AS c FROM {table}")
            return cur.fetchone()["c"]

    # Column-map or upsert path: stage into a temp table with the target's
    # column types, then INSERT into the target (types match, no cast needed).
    import tempfile

    rows = []
    with open(csv_path, "r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader, None)
        rows = list(reader)

    effective_header = [column_map.get(h, h) for h in header] if column_map else header

    short = table.split(".")[-1]
    staging = f"_stg_{short}"
    cur.execute(f'DROP TABLE IF EXISTS {staging}')

    # Staging table mirrors target column types so COPY performs type conversion.
    cur.execute(f'CREATE TEMP TABLE {staging} AS SELECT * FROM {table} WHERE 1=0')

    # Write CSV with effective (possibly renamed) headers to a temp file for COPY.
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="", suffix=".csv", delete=False
    ) as tf:
        writer = csv.writer(tf)
        writer.writerow(effective_header)
        writer.writerows(rows)
        temp_path = tf.name

    try:
        with open(temp_path, "r", encoding="utf-8", newline="") as tf:
            col_sql = ", ".join(f'"{c}"' for c in effective_header)
            sql = f'COPY {staging} ({col_sql}) FROM STDIN WITH (FORMAT csv, HEADER true)'
            cur.copy_expert(sql, tf)

        src_cols = ", ".join(f'"{c}"' for c in effective_header)
        dst_cols = ", ".join(f'"{c}"' for c in effective_header)
        if upsert:
            cur.execute(
                f'INSERT INTO {table} ({dst_cols}) SELECT {src_cols} FROM {staging} ON CONFLICT DO NOTHING'
            )
        else:
            cur.execute(
                f'INSERT INTO {table} ({dst_cols}) SELECT {src_cols} FROM {staging}'
            )

        cur.execute(f"SELECT COUNT(*) AS c FROM {table}")
        return cur.fetchone()["c"]
    finally:
        os.unlink(temp_path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data-dir",
        default="data",
        help="Directory containing Olist CSV files (default: ./data)",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="TRUNCATE all target tables (CASCADE) before loading",
    )
    parser.add_argument(
        "--no-geolocation",
        action="store_true",
        help="Skip loading the geolocation table (blocked by default policy)",
    )
    args = parser.parse_args()

    data_dir = Path(args.data_dir)
    if not data_dir.is_dir():
        print(f"ERROR: data directory not found: {data_dir.resolve()}", file=sys.stderr)
        return 1

    database_url = get_database_url()
    print(f"Connecting to {database_url.split('@')[-1]}")

    conn = psycopg2.connect(database_url)
    conn.autocommit = False
    try:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            if args.reset:
                tables = ", ".join(t for t, _, _, _, _ in LOAD_ORDER)
                cur.execute(f"TRUNCATE {tables} RESTART IDENTITY CASCADE")
                print("Truncated target tables.")

            order = LOAD_ORDER
            if args.no_geolocation:
                order = [row for row in order if row[0] != "public.geolocation"]

            loaded: list[tuple[str, int]] = []
            skipped: list[str] = []

            for table, csv_name, columns, column_map, upsert in order:
                csv_path = data_dir / csv_name
                if not csv_path.exists():
                    print(f"  SKIP {table}: {csv_name} not found in {data_dir}")
                    skipped.append(table)
                    continue
                count = _copy_csv(cur, table, csv_path, columns, column_map, upsert)
                loaded.append((table, count))
                print(f"  LOAD {table}: {count} rows from {csv_name}")

            conn.commit()

        print("\nSummary:")
        for table, count in loaded:
            print(f"  {table}: {count} rows")
        if skipped:
            print(f"  Skipped: {', '.join(skipped)}")
        print("Done.")
        return 0
    except Exception as exc:  # noqa: BLE001
        conn.rollback()
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
