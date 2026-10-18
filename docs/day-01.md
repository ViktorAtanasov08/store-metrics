# First walkthrough: where does the profit come from?

1. Run the three README commands. Open the HTML report.
2. Calculate `DEMO-001` by hand: two journals at €20, costing €8 each. Gross profit is €24.
3. Calculate `DEMO-004`: a €20 order, refunded in full, with €8 product cost. Gross profit is −€8. Explain why.
4. Trace `main` → `import_sales` → `parse_row` → SQLite. Why validate the file before writing rows?
5. Read the `with connection` transaction. What happens if row two conflicts after row one has been inserted?
6. Run the same import again. Why are the totals unchanged?
7. Find the `SUM` expressions in `reporting.py`. Explain the difference between gross revenue, net revenue and gross profit.
8. Explain why 10 cents are stored as `10`, not as a floating-point euro amount.
9. Compare July's €67 gross profit with August's €38. These totals say nothing about advertising or shipping costs yet.

## Your first change

Create `samples/my-sales.csv` with three fictional orders. Predict the totals, then import into a separate database and check your result. Keep real customer details out of a public repository.

```sh
git clone https://github.com/ViktorAtanasov08/store-metrics.git
cd store-metrics
git switch -c learn/my-sales-example
python -m storemetrics --db data/my-sales.db import samples/my-sales.csv
python -m storemetrics --db data/my-sales.db report
python -m unittest discover -s tests -v
git add samples/my-sales.csv
git commit -m "Add a sales example with hand-checked totals"
git push -u origin learn/my-sales-example
```

Open a pull request describing your expected totals and what you learned. The goal is to understand and extend the AI-assisted scaffold yourself.
