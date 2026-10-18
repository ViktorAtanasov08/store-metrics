"""Validate the whole file, then import all its rows in one transaction."""
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path
import re
import sqlite3

FIELDS = ("order_id", "order_date", "product", "quantity", "unit_price", "unit_cost", "refund", "currency")
MONEY_PATTERN = re.compile(r"[0-9]+(?:\.[0-9]{1,2})?")
MAX_CENTS = 100_000_000  # 1,000,000 EUR per unit or refund, sufficient for the demo.


class ImportProblem(ValueError):
    """A user-correctable CSV or duplicate-order problem."""


def cents(value: str, field: str) -> int:
    if len(value) > 20 or MONEY_PATTERN.fullmatch(value) is None:
        raise ImportProblem(f"{field} must be a non-negative amount with at most two decimal places")
    try:
        result = int(Decimal(value) * 100)
    except (InvalidOperation, ValueError, OverflowError) as error:
        raise ImportProblem(f"Invalid {field}") from error
    if result > MAX_CENTS:
        raise ImportProblem(f"{field} exceeds the demo limit of 1,000,000 EUR")
    return result


def parse_row(raw: dict, line: int) -> tuple:
    if None in raw or any(raw.get(field) is None for field in FIELDS):
        raise ImportProblem(f"Row {line}: wrong number of columns")
    row = {field: raw[field].strip() for field in FIELDS}
    try:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,64}", row["order_id"]):
            raise ImportProblem("order_id must contain 1–64 letters, digits, underscores or hyphens")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", row["order_date"]):
            raise ImportProblem("order_date must use YYYY-MM-DD")
        try:
            date.fromisoformat(row["order_date"])
        except ValueError as error:
            raise ImportProblem("order_date is not a real calendar date") from error
        if not 1 <= len(row["product"]) <= 120 or any(ord(c) < 32 for c in row["product"]):
            raise ImportProblem("product must contain 1–120 characters without control characters")
        if not re.fullmatch(r"[0-9]{1,5}", row["quantity"]):
            raise ImportProblem("quantity must be a whole number from 1 to 10000")
        quantity = int(row["quantity"])
        if not 1 <= quantity <= 10000:
            raise ImportProblem("quantity must be a whole number from 1 to 10000")
        price = cents(row["unit_price"], "unit_price")
        cost = cents(row["unit_cost"], "unit_cost")
        refund = cents(row["refund"], "refund")
        if refund > price * quantity:
            raise ImportProblem("refund cannot exceed this order's gross revenue")
        if row["currency"] != "EUR":
            raise ImportProblem("only EUR is supported; mixed currencies must not be added together")
        return (row["order_id"], row["order_date"], row["product"], quantity,
                price, cost, refund, row["currency"])
    except ImportProblem as error:
        raise ImportProblem(f"Row {line}: {error}") from error


def read_sales(path: str | Path) -> list[tuple]:
    source = Path(path)
    if source.stat().st_size > 10 * 1024 * 1024:
        raise ImportProblem("CSV exceeds the demo limit of 10 MiB")
    rows = []
    seen = set()
    try:
        with source.open(encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream, strict=True)
            if reader.fieldnames is None or len(reader.fieldnames) != len(FIELDS) or set(reader.fieldnames) != set(FIELDS):
                raise ImportProblem("CSV headers must be exactly: " + ",".join(FIELDS))
            for line, raw in enumerate(reader, start=2):
                if len(rows) >= 50_000:
                    raise ImportProblem("CSV exceeds the demo limit of 50000 rows")
                row = parse_row(raw, line)
                if row[0] in seen:
                    raise ImportProblem(f"Row {line}: duplicate order_id within this file: {row[0]}")
                seen.add(row[0])
                rows.append(row)
    except (UnicodeError, csv.Error) as error:
        raise ImportProblem(f"Cannot read UTF-8 CSV: {error}") from error
    if not rows:
        raise ImportProblem("CSV must contain at least one sale")
    return rows


def import_sales(connection: sqlite3.Connection, path: str | Path) -> tuple[int, int]:
    rows = read_sales(path)
    inserted = 0
    skipped = 0
    # Validation and duplicate conflicts must never leave a half-imported file.
    with connection:
        for row in rows:
            existing = connection.execute("SELECT * FROM sales WHERE order_id = ?", (row[0],)).fetchone()
            if existing is not None:
                if tuple(existing) != row:
                    raise ImportProblem(f"Order {row[0]} already exists with different data; nothing from this file was imported")
                skipped += 1
                continue
            connection.execute("INSERT INTO sales VALUES (?, ?, ?, ?, ?, ?, ?, ?)", row)
            inserted += 1
    return inserted, skipped
