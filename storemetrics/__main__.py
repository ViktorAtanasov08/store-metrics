"""Run with python -m storemetrics. No third-party packages are needed."""
import argparse
import contextlib
import sqlite3
import sys

from .database import connect
from .importer import ImportProblem, import_sales
from .reporting import html_report, plain_report, totals, validate_month


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="Import EUR sales CSVs and calculate a simple gross-profit report.")
    parser.add_argument("--db", default="data/metrics.db", help="SQLite database path (default: data/metrics.db)")
    commands = parser.add_subparsers(dest="command", required=True)
    load = commands.add_parser("import", help="Validate and atomically import a CSV")
    load.add_argument("csv", help="UTF-8 sales CSV")
    report = commands.add_parser("report", help="Print totals and optionally write an HTML dashboard")
    report.add_argument("--month", help="Optional YYYY-MM filter")
    report.add_argument("--html", help="Write a self-contained HTML file at this path")
    args = parser.parse_args(argv)
    try:
        if args.command == "report":
            validate_month(args.month)
        with contextlib.closing(connect(args.db)) as connection:
            if args.command == "import":
                inserted, skipped = import_sales(connection, args.csv)
                print(f"Imported {inserted} orders; skipped {skipped} identical existing orders.")
            else:
                print(plain_report(totals(connection, args.month), args.month or "All imported sales"))
                if args.html:
                    html_report(connection, args.html, args.month)
                    print(f"HTML report written to {args.html}")
    except (ImportProblem, OSError, sqlite3.Error, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
