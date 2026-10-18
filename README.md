# StoreMetrics

[![Verify imports and reports](https://github.com/ViktorAtanasov08/store-metrics/actions/workflows/checks.yml/badge.svg)](https://github.com/ViktorAtanasov08/store-metrics/actions/workflows/checks.yml)

**In progress — initial reporting milestone.** A Python / SQLite learning project that imports sales CSVs, calculates gross profit and creates a self-contained HTML dashboard.

## What works

- Validate and import a UTF-8 CSV into a persistent SQLite database.
- Calculate gross revenue, refunds, net revenue, product costs and gross profit using SQL.
- Show all-time totals, monthly breakdowns and an optional month filter.
- Write a responsive HTML report with totals and the latest 20 orders.
- Reimport identical orders without double counting; refuse conflicting duplicates.
- Roll back the entire import if any row is invalid or conflicts with an existing order.
- Store money as integer euro cents, avoiding binary floating-point arithmetic.

## Try it

Install **Python 3.12 or newer**. No external packages, account or API keys are required. From this repository folder:

```sh
python -m storemetrics import samples/sales.csv
python -m storemetrics report --html reports/overview.html
python -m storemetrics report --month 2026-07
```

Open `reports/overview.html` in your browser. On systems where Python is named `python3`, use that command instead. The default database is `data/metrics.db`; restarting the command preserves imported data. Both generated folders are ignored by Git.

To choose a separate database, put the global `--db` option **before** the subcommand:

```sh
python -m storemetrics --db data/practice.db import samples/sales.csv
python -m storemetrics --db data/practice.db report
```

The fictional sample produces:

| Metric | All sales | July 2026 |
| --- | ---: | ---: |
| Orders | 6 | 3 |
| Units | 10 | 6 |
| Gross revenue | €210.00 | €115.00 |
| Refunds | €25.00 | €5.00 |
| Net revenue | €185.00 | €110.00 |
| Product costs | €80.00 | €43.00 |
| Gross profit | **€105.00** | **€67.00** |

## CSV contract

```csv
order_id,order_date,product,quantity,unit_price,unit_cost,refund,currency
EXAMPLE-001,2026-07-01,Training journal,2,20.00,8.00,0.00,EUR
```

All eight headers are required exactly once; their order may vary. One row represents **one whole order of one product**, not an order line. `order_id` must be unique. Multi-product orders are a future milestone.

- `order_id`: 1–64 ASCII letters, digits, underscores or hyphens.
- `order_date`: a real date in `YYYY-MM-DD` format; this is also the reporting date for its refund.
- `product`: 1–120 characters, without control characters.
- `quantity`: a whole number from 1 to 10000.
- `unit_price` and `unit_cost`: per-unit EUR amounts, non-negative, with at most two decimal places and a decimal point.
- `refund`: the total EUR refund for the order, between zero and that order's gross revenue.
- `currency`: exactly `EUR`. Currency conversion is not implemented.

Files are limited to 10 MiB and 50000 rows. Empty imports, missing/extra fields, repeated order IDs within one file and malformed values fail with a readable error and a nonzero exit code.

## Calculation rules and limits

```text
Gross revenue = quantity × unit price
Product costs = quantity × unit cost
Net revenue = gross revenue − refunds
Gross profit = net revenue − product costs
```

Product costs remain charged after a refund; the app does not assume returned stock is recoverable. A refunded order can therefore have negative gross profit. Refunds are assigned to the original order month, since the CSV has no refund-event date.

**Gross profit is not net business profit.** Advertising, shipping, payment fees, tax, inventory recovery and operating costs are excluded. This prototype does not connect to Shopify, read real customer accounts, accept uploads on a public server or provide a complete accounting system. It is a local command-line workflow plus a generated HTML report.

## Code map

| Path | Responsibility |
| --- | --- |
| `storemetrics/__main__.py` | Command-line interface and readable errors |
| `storemetrics/importer.py` | CSV contract, validation, duplicate rules and atomic import |
| `storemetrics/database.py` | SQLite connection, table and constraints |
| `storemetrics/reporting.py` | SQL totals, monthly grouping and escaped HTML output |
| `samples/sales.csv` | Six fictional orders with partial and full refunds |
| `tests/test_metrics.py` | Calculation, persistence, import, reporting and CLI checks |

## Verification

```sh
python -m unittest discover -s tests -v
```

GitHub Actions runs the same checks and the documented sample commands. Tests cover exact cents, month filters, refunds and losses, persistent data, repeated imports, conflicting duplicates, atomic rollback, invalid CSV values, HTML escaping and CLI exit codes. Browser layout is not covered by these automated checks.

## Next milestones

- [ ] Explain the import → SQLite → SQL summary flow together.
- [ ] Add shipping and payment fees with a documented cost model.
- [ ] Support multiple order lines and separately dated refund events.
- [ ] Add date ranges and product-level summaries.
- [ ] Capture screenshots from a verified running browser session.

## Learning notes

The initial scaffold was prepared with AI assistance. It is an unfinished learning project to run, understand and extend together. See [the first walkthrough](docs/day-01.md).

References: Python documentation for [CSV](https://docs.python.org/3/library/csv.html), [SQLite](https://docs.python.org/3/library/sqlite3.html), [Decimal](https://docs.python.org/3/library/decimal.html) and [unittest](https://docs.python.org/3/library/unittest.html).
