import sqlite3
import csv
from datetime import datetime
from .logger import logger

DB_FILE = "foodwise.db"

def get_conn():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_conn()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL, category TEXT NOT NULL,
            quantity REAL NOT NULL, unit TEXT, price REAL NOT NULL, expiry_date TEXT, added_date TEXT NOT NULL
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS purchases (
            id INTEGER PRIMARY KEY AUTOINCREMENT, item_name TEXT NOT NULL, category TEXT,
            quantity REAL NOT NULL, price REAL NOT NULL, purchase_date TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()
    logger.info("Database initialized.")

def export_to_csv(filename="report.csv"):
    conn = get_conn()
    items = conn.execute("SELECT * FROM items").fetchall()
    conn.close()
    with open(filename, mode='w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(["ID", "Name", "Category", "Quantity", "Unit", "Price", "Expiry", "Added"])
        for row in items:
            writer.writerow([row["id"], row["name"], row["category"], row["quantity"], row["unit"], row["price"], row["expiry_date"], row["added_date"]])
    logger.info(f"Data exported to {filename}")
    return filename

def get_monthly_report():
    conn = get_conn()
    c = conn.cursor()

    month = datetime.now().strftime("%Y-%m")

    total_spend = c.execute("""
        SELECT COALESCE(SUM(quantity * price), 0)
        FROM purchases
        WHERE substr(purchase_date, 1, 7) = ?
    """, (month,)).fetchone()[0]

    by_cat = c.execute("""
        SELECT category, SUM(quantity * price) AS s
        FROM purchases
        WHERE substr(purchase_date, 1, 7) = ?
        GROUP BY category
    """, (month,)).fetchall()

    conn.close()
    return {"total": total_spend, "by_cat": by_cat}

def get_frequent_items():
    conn = get_conn()
    rows = conn.execute("SELECT item_name, COUNT(*) as n FROM purchases GROUP BY LOWER(item_name) ORDER BY n DESC LIMIT 5").fetchall()
    conn.close()
    return rows