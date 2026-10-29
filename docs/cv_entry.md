# Phase 20 — CV entry

## Independent project

**RetailPulse — Retail Data Engineering & Analytics Platform** | Oct 2026

- Built a local Python/SQL pipeline for eight synthetic retail datasets (96,520 source rows), with contract checks, quarantine, 106 data-quality rules, SQLite star-schema modeling, and Bronze/Silver/Gold exports; the recorded run had zero foreign-key violations.
- Designed the Power BI model (four dimensions, three facts), authored KPI measures, and built three report pages: Sales Overview, Products & Returns, and Inventory.
- Added pytest coverage (13 passed in the latest recorded run), pipeline run/freshness monitoring, and a repeatable SQL benchmark (4.050-second median across three runs on the recorded Windows 11 sample); verified Spark summary parity across 461 products with zero mismatches and demonstrated a Delta Lake insert/update/time-travel merge.

## Shorter version

**RetailPulse — Independent Data Engineering Project:** Developed a local Python,
SQL, SQLite, PySpark, Delta Lake, and Power BI learning project over a reproducible
96.5K-row synthetic retail dataset. Implemented ingestion, data-quality
reporting, dimensional modeling, medallion exports, monitoring, and tests; the
recorded benchmark median was 4.050 seconds on one Windows 11 environment.

## Evidence and wording notes

- Present this under **Projects** or **Independent Projects**, not as employment
  or client work.
- The 40 failed quality rules and 16,553 summed rule-level failures are expected
  for deliberately defective synthetic input. The project distinguishes a
  successful pipeline run from a failed source-quality outcome.
- The 4.050-second result is the median of three runs on one local environment;
  do not describe it as a production-scale or cross-machine performance claim.
- The last recorded automated test run passed 13 tests; no hosted CI run is
  claimed. Azure and Databricks resources remain design-only.
- The user-built Power BI report is saved locally; its PBIX is excluded from Git
  because its CSV source paths expose the Windows account name. Save screenshots
  in the portfolio if the report is listed publicly.
- Update the date and metrics if the project changes before using these bullets.
