from __future__ import annotations

import csv
import sqlite3
from pathlib import Path

import pytest

from retailpulse.sql_pipeline import run_sql

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_sql_pipeline_builds_layers_star_schema_and_business_outputs(
    clean_data_dir: Path, tmp_path: Path
) -> None:
    database_path = tmp_path / "processed" / "retailpulse.db"
    result = run_sql(clean_data_dir, database_path, PROJECT_ROOT / "sql")

    assert result["quality_status"] == "passed"
    assert result["foreign_key_violations"] == 0
    assert result["staging_rows_loaded"]["stg_orders"] == 6
    assert result["table_row_counts"]["dim_customer"] == 8
    assert result["table_row_counts"]["fact_sales"] == 12
    assert result["medallion_export_row_counts"]["bronze"]["orders.csv"] == 6
    assert result["power_bi_model_export_row_counts"]["dim_customer.csv"] == 8
    assert result["power_bi_model_export_row_counts"]["fact_sales.csv"] == 12
    assert result["power_bi_model_export_row_counts"]["fact_returns.csv"] == 2
    assert result["power_bi_model_export_row_counts"]["fact_inventory.csv"] == 8
    assert result["run_status"] == "success"
    assert result["duration_seconds"] >= 0
    assert result["source_files_seen"] == 8
    assert result["latest_source_file"]
    assert result["latest_source_modified_at_utc"]
    assert result["source_freshness_age_seconds"] >= 0
    assert result["quality_rules_evaluated"] > 0
    assert result["quality_rules_passed"] == result["quality_rules_evaluated"]
    assert result["quality_rules_failed"] == 0
    assert result["ingestion_rows_total"] == 48

    date_export = tmp_path / "processed" / "powerbi_model" / "dim_date.csv"
    with date_export.open(newline="", encoding="utf-8") as handle:
        date_rows = list(csv.DictReader(handle))
    assert date_rows
    assert all(row["date_key"] != "0" and row["date_value"] for row in date_rows)

    connection = sqlite3.connect(database_path)
    try:
        fact_revenue = connection.execute(
            "SELECT ROUND(SUM(net_sales_amount), 2) FROM fact_sales "
            "WHERE order_status = 'completed'"
        ).fetchone()[0]
        summary_revenue = connection.execute(
            "SELECT ROUND(SUM(gross_revenue), 2) FROM analytics_product_summary"
        ).fetchone()[0]
        assert summary_revenue == fact_revenue
        assert connection.execute("PRAGMA foreign_key_check").fetchall() == []
        for table, column in (
            ("fact_sales", "order_date_key"),
            ("fact_returns", "order_date_key"),
            ("fact_returns", "return_date_key"),
            ("fact_inventory", "snapshot_date_key"),
        ):
            assert connection.execute(
                f"SELECT COUNT(*) FROM {table} WHERE {column} = 0"
            ).fetchone()[0] == 0
    finally:
        connection.close()

    product_summary = tmp_path / "processed" / "gold" / "product_summary.csv"
    with product_summary.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert len(rows) == 4
    assert {row["product_id"] for row in rows}

    monitoring_log = tmp_path / "processed" / "monitoring" / "pipeline_runs.csv"
    with monitoring_log.open(newline="", encoding="utf-8") as handle:
        monitor_rows = list(csv.DictReader(handle))
    assert len(monitor_rows) == 1
    assert monitor_rows[0]["run_status"] == "success"
    assert monitor_rows[0]["quality_status"] == "passed"


def test_sql_pipeline_records_failed_runs(
    clean_data_dir: Path, tmp_path: Path
) -> None:
    database_path = tmp_path / "processed" / "retailpulse.db"

    with pytest.raises(FileNotFoundError):
        run_sql(clean_data_dir, database_path, tmp_path / "missing-sql")

    monitoring_log = tmp_path / "processed" / "monitoring" / "pipeline_runs.csv"
    with monitoring_log.open(newline="", encoding="utf-8") as handle:
        monitor_rows = list(csv.DictReader(handle))
    assert len(monitor_rows) == 1
    assert monitor_rows[0]["run_status"] == "failed"
    assert monitor_rows[0]["error_type"] == "FileNotFoundError"
    assert monitor_rows[0]["source_files_seen"] == "8"
