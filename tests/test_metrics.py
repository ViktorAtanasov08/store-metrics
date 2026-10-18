import contextlib
import csv
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from storemetrics.database import connect
from storemetrics.importer import FIELDS, ImportProblem, import_sales
from storemetrics.reporting import Totals, html_report, money, monthly, totals

ROOT = Path(__file__).resolve().parents[1]
SAMPLE = ROOT / "samples/sales.csv"


class MetricsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        self.connection = connect(self.folder / "test.db")
        self.addCleanup(self.connection.close)

    def row(self, **changes):
        return {**dict(zip(FIELDS, ["NEW-1", "2026-07-02", "Journal", "2", "20.00", "8.00", "0.00", "EUR"])), **changes}

    def csv(self, rows, headers=FIELDS):
        path = self.folder / "import.csv"
        with path.open("w", encoding="utf-8-sig", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=headers)
            writer.writeheader()
            writer.writerows(rows)
        return path

    def test_sample_totals_and_sql_monthly_grouping(self):
        self.assertEqual(import_sales(self.connection, SAMPLE), (6, 0))
        result = totals(self.connection)
        self.assertEqual(result, Totals(6, 10, 21000, 8000, 2500))
        self.assertEqual(result.net, 18500)
        self.assertEqual(result.profit, 10500)
        self.assertEqual(monthly(self.connection), [
            ("2026-07", 3, 11500, 4300, 500), ("2026-08", 3, 9500, 3700, 2000)])

    def test_month_filter_and_empty_period(self):
        import_sales(self.connection, SAMPLE)
        self.assertEqual(totals(self.connection, "2026-07").profit, 6700)
        self.assertEqual(totals(self.connection, "2026-08").profit, 3800)
        self.assertEqual(totals(self.connection, "2025-01"), Totals(0, 0, 0, 0, 0))

    def test_reimport_is_idempotent(self):
        import_sales(self.connection, SAMPLE)
        self.assertEqual(import_sales(self.connection, SAMPLE), (0, 6))
        self.assertEqual(totals(self.connection).orders, 6)

    def test_conflicting_duplicate_rolls_back_prior_insert(self):
        import_sales(self.connection, SAMPLE)
        path = self.csv([self.row(), self.row(order_id="DEMO-001", unit_price="99.00")])
        with self.assertRaisesRegex(ImportProblem, "already exists with different data"):
            import_sales(self.connection, path)
        self.assertEqual(totals(self.connection).orders, 6)
        self.assertIsNone(self.connection.execute("SELECT 1 FROM sales WHERE order_id = ?", ("NEW-1",)).fetchone())

    def test_invalid_later_row_does_not_import_earlier_row(self):
        path = self.csv([self.row(), self.row(order_id="NEW-2", quantity="0")])
        with self.assertRaisesRegex(ImportProblem, "Row 3"):
            import_sales(self.connection, path)
        self.assertEqual(totals(self.connection).orders, 0)

    def test_duplicate_inside_file_is_rejected(self):
        with self.assertRaisesRegex(ImportProblem, "duplicate order_id within this file"):
            import_sales(self.connection, self.csv([self.row(), self.row()]))
        self.assertEqual(totals(self.connection).orders, 0)

    def test_invalid_values_are_rejected(self):
        invalid = [
            {"order_id": ""}, {"order_id": "bad id"}, {"order_id": "x" * 65},
            {"order_date": "2026-02-30"}, {"order_date": "20260702"},
            {"product": " "}, {"product": "x" * 121}, {"product": "bad\nname"},
            {"quantity": "0"}, {"quantity": "-1"}, {"quantity": "1.5"}, {"quantity": "10001"},
            {"unit_price": "NaN"}, {"unit_price": "Infinity"}, {"unit_price": "1.001"},
            {"unit_price": "-1"}, {"unit_price": "1,20"}, {"unit_price": "1000000.01"},
            {"unit_cost": "-0.01"}, {"refund": "40.01"}, {"refund": "-1"}, {"currency": "USD"},
        ]
        for changes in invalid:
            with self.subTest(changes=changes):
                with self.assertRaises(ImportProblem):
                    import_sales(self.connection, self.csv([self.row(**changes)]))
                self.assertEqual(totals(self.connection).orders, 0)

    def test_zero_price_and_loss_are_allowed(self):
        import_sales(self.connection, self.csv([self.row(quantity="1", unit_price="0.00", unit_cost="2.00")]))
        self.assertEqual(totals(self.connection).profit, -200)
        self.assertEqual(money(-200), "-2.00")

    def test_full_refund_keeps_product_cost(self):
        import_sales(self.connection, self.csv([self.row(refund="40.00")]))
        self.assertEqual(totals(self.connection).net, 0)
        self.assertEqual(totals(self.connection).profit, -1600)

    def test_cents_are_exact_and_normalized_duplicates_skip(self):
        path = self.csv([self.row(unit_price="0.10", unit_cost="0.03", quantity="3")])
        import_sales(self.connection, path)
        self.assertEqual(totals(self.connection).profit, 21)
        self.assertEqual(import_sales(self.connection, self.csv([
            self.row(unit_price="0.1", unit_cost="0.03", quantity="3")])), (0, 1))

    def test_headers_empty_file_and_column_count(self):
        path = self.folder / "bad.csv"
        for text in ["", ",".join(FIELDS) + "\n", "order_id,product\nA,Test\n",
                     ",".join(FIELDS) + "\nA,2026-07-01,Product,1,2,1,0,EUR,extra\n",
                     ",".join(FIELDS) + "\nA,2026-07-01,Product,1\n",
                     ",".join(FIELDS[:-1] + ("refund",)) + "\n"]:
            with self.subTest(text=text):
                path.write_text(text, encoding="utf-8")
                with self.assertRaises(ImportProblem):
                    import_sales(self.connection, path)

    def test_utf8_bom_and_whitespace(self):
        import_sales(self.connection, self.csv([self.row(product="  Спортна бутилка  ", unit_price=" 20.00 ")]))
        row = self.connection.execute("SELECT product,unit_price_cents FROM sales").fetchone()
        self.assertEqual(tuple(row), ("Спортна бутилка", 2000))

    def test_month_validation_rejects_invalid_and_sql_like_input(self):
        for month in ["2026-13", "2026-00", "2026-7", "2026-01' OR 1=1--", "0000-01"]:
            with self.subTest(month=month), self.assertRaises(ValueError):
                totals(self.connection, month)

    def test_html_escapes_product_names_and_filters_orders(self):
        import_sales(self.connection, self.csv([self.row(product='<script>alert("x")</script>')]))
        report = self.folder / "report.html"
        html_report(self.connection, report, "2026-07")
        text = report.read_text(encoding="utf-8")
        self.assertIn("&lt;script&gt;", text)
        self.assertNotIn("<script>", text)
        self.assertIn("€24.00", text)
        html_report(self.connection, report, "2026-08")
        self.assertNotIn("NEW-1", report.read_text(encoding="utf-8"))

    def test_database_persists_after_connection_closes(self):
        path = self.folder / "persist.db"
        with contextlib.closing(connect(path)) as first:
            import_sales(first, SAMPLE)
        with contextlib.closing(connect(path)) as second:
            self.assertEqual(totals(second).profit, 10500)

    def test_cli_success_and_error_exit_codes(self):
        base = [sys.executable, "-m", "storemetrics", "--db", str(self.folder / "cli.db")]
        imported = subprocess.run(base + ["import", str(SAMPLE)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(imported.returncode, 0, imported.stderr)
        self.assertIn("Imported 6", imported.stdout)
        output = self.folder / "cli.html"
        report = subprocess.run(base + ["report", "--html", str(output)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(report.returncode, 0, report.stderr)
        self.assertIn("105.00", report.stdout)
        self.assertTrue(output.exists())
        invalid = subprocess.run(base + ["report", "--month", "invalid"], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(invalid.returncode, 1)
        self.assertIn("Error:", invalid.stderr)
        missing = subprocess.run(base + ["import", str(self.folder / "missing.csv")], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(missing.returncode, 1)
        self.assertNotIn("Traceback", missing.stderr)


if __name__ == "__main__":
    unittest.main()
