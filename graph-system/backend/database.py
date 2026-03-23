"""
database.py - SQLite database setup and schema
Handles all table creation and data ingestion from the Excel dataset
"""

import sqlite3
import pandas as pd
import os
import json
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "graph.db"
DATA_DIR = Path(__file__).parent.parent / "data"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    """Initialize SQLite schema."""
    os.makedirs(DATA_DIR, exist_ok=True)
    conn = get_connection()
    cur = conn.cursor()

    cur.executescript("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id TEXT PRIMARY KEY,
            customer_name TEXT,
            city TEXT,
            country TEXT,
            region TEXT
        );

        CREATE TABLE IF NOT EXISTS products (
            material_id TEXT PRIMARY KEY,
            material_desc TEXT,
            material_group TEXT,
            unit TEXT
        );

        CREATE TABLE IF NOT EXISTS addresses (
            address_id TEXT PRIMARY KEY,
            street TEXT,
            city TEXT,
            postal_code TEXT,
            country TEXT
        );

        CREATE TABLE IF NOT EXISTS sales_orders (
            sales_order_id TEXT PRIMARY KEY,
            customer_id TEXT,
            order_date TEXT,
            net_value REAL,
            currency TEXT,
            status TEXT,
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );

        CREATE TABLE IF NOT EXISTS sales_order_items (
            item_id TEXT PRIMARY KEY,
            sales_order_id TEXT,
            material_id TEXT,
            quantity REAL,
            unit TEXT,
            net_price REAL,
            FOREIGN KEY (sales_order_id) REFERENCES sales_orders(sales_order_id),
            FOREIGN KEY (material_id) REFERENCES products(material_id)
        );

        CREATE TABLE IF NOT EXISTS deliveries (
            delivery_id TEXT PRIMARY KEY,
            sales_order_id TEXT,
            customer_id TEXT,
            delivery_date TEXT,
            plant TEXT,
            shipping_point TEXT,
            status TEXT,
            FOREIGN KEY (sales_order_id) REFERENCES sales_orders(sales_order_id),
            FOREIGN KEY (customer_id) REFERENCES customers(customer_id)
        );

        CREATE TABLE IF NOT EXISTS billing_documents (
            billing_id TEXT PRIMARY KEY,
            sales_order_id TEXT,
            delivery_id TEXT,
            billing_date TEXT,
            net_value REAL,
            currency TEXT,
            billing_type TEXT,
            FOREIGN KEY (sales_order_id) REFERENCES sales_orders(sales_order_id),
            FOREIGN KEY (delivery_id) REFERENCES deliveries(delivery_id)
        );

        CREATE TABLE IF NOT EXISTS payments (
            payment_id TEXT PRIMARY KEY,
            billing_id TEXT,
            payment_date TEXT,
            amount REAL,
            currency TEXT,
            payment_method TEXT,
            FOREIGN KEY (billing_id) REFERENCES billing_documents(billing_id)
        );

        CREATE TABLE IF NOT EXISTS journal_entries (
            journal_id TEXT PRIMARY KEY,
            billing_id TEXT,
            posting_date TEXT,
            amount REAL,
            currency TEXT,
            account TEXT,
            FOREIGN KEY (billing_id) REFERENCES billing_documents(billing_id)
        );
    """)

    conn.commit()
    conn.close()
    print("✅ Database schema initialized.")


def load_excel_dataset(filepath: str):
    """
    Load and ingest the Excel dataset.
    Tries to detect sheets and map them to the correct tables.
    """
    print(f"Loading dataset from: {filepath}")
    xl = pd.ExcelFile(filepath)
    sheets = xl.sheet_names
    print(f"Found sheets: {sheets}")

    conn = get_connection()

    sheet_map = {
        "customer": "customers",
        "product": "products",
        "material": "products",
        "address": "addresses",
        "sales_order": "sales_orders",
        "order": "sales_orders",
        "delivery": "deliveries",
        "billing": "billing_documents",
        "invoice": "billing_documents",
        "payment": "payments",
        "journal": "journal_entries",
    }

    for sheet in sheets:
        df = xl.parse(sheet)
        df.columns = [c.strip().lower().replace(" ", "_").replace("-", "_") for c in df.columns]

        matched_table = None
        for key, table in sheet_map.items():
            if key in sheet.lower():
                matched_table = table
                break

        if matched_table:
            try:
                df.to_sql(matched_table, conn, if_exists="replace", index=False)
                print(f"  ✅ Loaded sheet '{sheet}' → table '{matched_table}' ({len(df)} rows)")
            except Exception as e:
                print(f"  ⚠️  Could not load sheet '{sheet}': {e}")
        else:
            # Store as raw table using sheet name
            safe_name = sheet.lower().replace(" ", "_").replace("-", "_")
            df.to_sql(safe_name, conn, if_exists="replace", index=False)
            print(f"  📋 Stored sheet '{sheet}' as raw table '{safe_name}' ({len(df)} rows)")

    conn.commit()
    conn.close()
    print("✅ Dataset loaded successfully.")


def get_schema_info():
    """Return full schema as a string for LLM context."""
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cur.fetchall()]

    schema_parts = []
    for table in tables:
        cur.execute(f"PRAGMA table_info({table})")
        cols = cur.fetchall()
        col_defs = ", ".join([f"{c[1]} ({c[2]})" for c in cols])

        # Get row count
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        count = cur.fetchone()[0]

        # Sample rows
        cur.execute(f"SELECT * FROM {table} LIMIT 3")
        samples = cur.fetchall()
        sample_strs = [str(dict(r)) for r in samples] if samples else []

        schema_parts.append(
            f"Table: {table} ({count} rows)\n"
            f"  Columns: {col_defs}\n"
            f"  Sample: {'; '.join(sample_strs[:2])}"
        )

    conn.close()
    return "\n\n".join(schema_parts)


def get_tables():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cur.fetchall()]
    conn.close()
    return tables


def execute_query(sql: str):
    """Execute a SELECT query and return results as list of dicts."""
    conn = get_connection()
    try:
        cur = conn.cursor()
        cur.execute(sql)
        rows = cur.fetchall()
        results = [dict(r) for r in rows]
        return results, None
    except Exception as e:
        return None, str(e)
    finally:
        conn.close()
