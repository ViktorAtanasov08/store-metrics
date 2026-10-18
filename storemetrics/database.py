"""SQLite setup. Currency amounts are integer euro cents, never floats."""
from pathlib import Path
import sqlite3

SCHEMA = """
CREATE TABLE IF NOT EXISTS sales (
    order_id TEXT PRIMARY KEY,
    order_date TEXT NOT NULL,
    product TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity BETWEEN 1 AND 10000),
    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents >= 0),
    unit_cost_cents INTEGER NOT NULL CHECK (unit_cost_cents >= 0),
    refund_cents INTEGER NOT NULL CHECK (
        refund_cents >= 0 AND refund_cents <= quantity * unit_price_cents),
    currency TEXT NOT NULL CHECK (currency = 'EUR')
);
CREATE INDEX IF NOT EXISTS sales_order_date ON sales(order_date);
"""


def connect(path: str | Path) -> sqlite3.Connection:
    location = Path(path)
    location.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(location)
    connection.row_factory = sqlite3.Row
    connection.executescript(SCHEMA)
    return connection
