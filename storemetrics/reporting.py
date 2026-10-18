"""SQL summaries and a self-contained HTML report."""
from dataclasses import dataclass
from html import escape
from pathlib import Path
import re
import sqlite3


@dataclass(frozen=True)
class Totals:
    orders: int
    units: int
    gross: int
    costs: int
    refunds: int

    @property
    def net(self) -> int:
        return self.gross - self.refunds

    @property
    def profit(self) -> int:
        return self.net - self.costs


def money(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    value = abs(cents)
    return f"{sign}{value // 100:,}.{value % 100:02d}"


def validate_month(month: str | None) -> None:
    if month is not None and (re.fullmatch(r"[0-9]{4}-(0[1-9]|1[0-2])", month) is None
                              or month.startswith("0000")):
        raise ValueError("month must be a real YYYY-MM value, for example 2026-07")


def period(month: str | None) -> tuple[str, tuple]:
    validate_month(month)
    return (" WHERE substr(order_date, 1, 7) = ?", (month,)) if month else ("", ())


def totals(connection: sqlite3.Connection, month: str | None = None) -> Totals:
    where, values = period(month)
    row = connection.execute("""
        SELECT COUNT(*), COALESCE(SUM(quantity), 0),
        COALESCE(SUM(quantity * unit_price_cents), 0),
        COALESCE(SUM(quantity * unit_cost_cents), 0), COALESCE(SUM(refund_cents), 0)
        FROM sales""" + where, values).fetchone()
    return Totals(*row)


def monthly(connection: sqlite3.Connection, month: str | None = None) -> list[tuple]:
    where, values = period(month)
    return [tuple(row) for row in connection.execute("""
        SELECT substr(order_date, 1, 7) AS month, COUNT(*),
            SUM(quantity * unit_price_cents), SUM(quantity * unit_cost_cents), SUM(refund_cents)
        FROM sales""" + where + " GROUP BY month ORDER BY month", values)]


def plain_report(result: Totals, label: str) -> str:
    return "\n".join([
        f"StoreMetrics | {label} | EUR",
        f"Orders: {result.orders} | Units: {result.units}",
        f"Gross revenue: {money(result.gross)}",
        f"Refunds:       {money(result.refunds)}",
        f"Net revenue:   {money(result.net)}",
        f"Product costs: {money(result.costs)}",
        f"Gross profit:  {money(result.profit)}",
        "Gross profit excludes advertising, shipping, fees and tax.",
    ])


def html_report(connection: sqlite3.Connection, output: str | Path,
                month: str | None = None) -> None:
    result = totals(connection, month)
    label = month or "All imported sales"
    cards = "".join(f'<article><span>{name}</span><strong>€{money(value)}</strong></article>'
                    for name, value in [("Gross revenue", result.gross), ("Refunds", result.refunds),
                                        ("Product costs", result.costs), ("Gross profit", result.profit)])
    month_rows = "".join(
        f"<tr><td>{escape(m)}</td><td>{count}</td><td>€{money(gross)}</td>"
        f"<td>€{money(refunds)}</td><td>€{money(cost)}</td><td>€{money(gross-refunds-cost)}</td></tr>"
        for m, count, gross, cost, refunds in monthly(connection, month))
    where, values = period(month)
    recent = connection.execute("SELECT * FROM sales" + where +
                                " ORDER BY order_date DESC, order_id DESC LIMIT 20", values)
    order_rows = "".join(
        f"<tr><td>{escape(row['order_id'])}</td><td>{escape(row['order_date'])}</td>"
        f"<td>{escape(row['product'])}</td><td>{row['quantity']}</td>"
        f"<td>€{money(row['quantity'] * row['unit_price_cents'] - row['refund_cents'])}</td></tr>"
        for row in recent)
    document = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>StoreMetrics · {escape(label)}</title><style>
:root{{font-family:system-ui,-apple-system,sans-serif;color:#182e35;background:#f4f5f0}}*{{box-sizing:border-box}}
body{{max-width:1150px;margin:auto;padding:30px 24px}}header{{border-bottom:1px solid #ccd5d3;padding-bottom:24px;display:flex;justify-content:space-between;gap:20px}}
.brand{{font-size:23px;font-weight:800}}.edition,.eyebrow{{font-size:11px;letter-spacing:.15em;text-transform:uppercase;color:#566c6c}}
.eyebrow{{margin-top:45px}}h1{{font-size:clamp(36px,5vw,62px);letter-spacing:-.045em;line-height:1.1;max-width:700px;margin:22px 0}}
.intro{{color:#566c6c;line-height:1.7}}.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:15px;margin:30px 0}}
article,.panel{{border:1px solid #d1dcd7;border-radius:15px;background:#fffef9;padding:24px}}article:last-child{{background:#183f3c;color:#fff}}
article span{{display:block;font-size:12px;margin-bottom:16px}}article strong{{font-size:clamp(21px,2.7vw,34px);letter-spacing:-.04em}}
.panel{{margin:22px 0;overflow-x:auto}}h2{{font-size:20px;margin-top:0}}table{{width:100%;border-collapse:collapse;text-align:left;font-size:14px}}
th,td{{padding:15px 10px;border-bottom:1px solid #e1e7e1}}th{{font-size:11px;text-transform:uppercase;letter-spacing:.06em}}
footer{{padding:20px 0;color:#566c6c;font-size:12px;line-height:1.8}}.empty{{color:#566c6c}}
@media(max-width:800px){{.cards{{grid-template-columns:repeat(2,1fr)}}header{{flex-direction:column}}}}
@media(max-width:420px){{.cards{{grid-template-columns:1fr}}}}
</style></head><body>
<header><span class="brand">StoreMetrics</span><span class="edition">01 / sales reporting prototype</span></header>
<p class="eyebrow">{escape(label)} · EUR</p><h1>Know what your<br>sales leave behind.</h1>
<p class="intro">{result.orders} imported orders · {result.units} units · net revenue €{money(result.net)}<br>
One currency. Explicit costs. A clearer view of gross profit.</p>
<section class="cards" aria-label="Sales totals">{cards}</section>
<section class="panel"><h2>Monthly breakdown</h2><table><thead><tr><th>Month</th><th>Orders</th><th>Gross revenue</th><th>Refunds</th><th>Product costs</th><th>Gross profit</th></tr></thead>
<tbody>{month_rows or '<tr><td colspan="6" class="empty">No sales in this period.</td></tr>'}</tbody></table></section>
<section class="panel"><h2>Latest orders <small>(up to 20)</small></h2><table><thead><tr><th>Order</th><th>Date</th><th>Product</th><th>Units</th><th>Net revenue</th></tr></thead>
<tbody>{order_rows or '<tr><td colspan="5" class="empty">No orders to display.</td></tr>'}</tbody></table></section>
<footer>Gross profit = gross revenue − refunds − product costs. Product costs remain charged after refunds.<br>
Advertising, shipping, payment fees and tax are excluded. This learning prototype is not a complete accounting report.<br>
Generated locally from imported CSV data. The included sample uses fictional orders.</footer></body></html>"""
    destination = Path(output)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(document, encoding="utf-8")
