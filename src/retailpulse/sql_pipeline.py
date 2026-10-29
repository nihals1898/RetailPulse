"""Load CSVs into local SQLite and execute the project's SQL transformation files."""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sqlite3
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from retailpulse.ingestion.framework import EXPECTED_SCHEMAS, ingest
from retailpulse.quality.engine import validate

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BATCH_SIZE = 5_000

BRONZE_EXPORTS = {f"bronze_{name}": f"{name}.csv" for name in EXPECTED_SCHEMAS}
SILVER_EXPORTS = {f"silver_{name}": f"{name}.csv" for name in EXPECTED_SCHEMAS}
GOLD_EXPORTS = {
    "gold_monthly_sales": "sales_monthly.csv",
    "gold_customer_summary": "customer_summary.csv",
    "gold_product_summary": "product_summary.csv",
    "gold_store_summary": "store_summary.csv",
    "gold_inventory_summary": "inventory_summary.csv",
    "gold_returns_summary": "returns_summary.csv",
    "gold_low_sales_products": "low_sales_products.csv",
}
POWER_BI_MODEL_QUERIES = {
    "dim_customer": "SELECT * FROM dim_customer",
    "dim_product": "SELECT * FROM dim_product",
    "dim_store": "SELECT * FROM dim_store",
    # Omit the unused key-0/blank-date row so Power BI can mark this as a date table.
    "dim_date": "SELECT * FROM dim_date WHERE date_key <> 0",
    "fact_sales": "SELECT * FROM fact_sales",
    "fact_returns": "SELECT * FROM fact_returns",
    "fact_inventory": "SELECT * FROM fact_inventory",
}
MONITORING_FIELDS = [
    "pipeline_run_id",
    "run_start_timestamp",
    "run_end_timestamp",
    "duration_seconds",
    "run_status",
    "input_dir",
    "source_files_seen",
    "latest_source_file",
    "latest_source_modified_at_utc",
    "source_freshness_age_seconds",
    "ingestion_run_id",
    "ingestion_rows_total",
    "quality_status",
    "quality_rules_evaluated",
    "quality_rules_passed",
    "quality_rules_failed",
    "quality_failed_rows_across_rules",
    "quality_violation_details_written",
    "foreign_key_violations",
    "bronze_export_rows",
    "silver_export_rows",
    "gold_export_rows",
    "power_bi_model_export_rows",
    "error_type",
    "error_message",
]


def _reference_date(input_dir: Path, override: date | None) -> date:
    if override is not None:
        return override
    summary_path = input_dir / "generation_summary.json"
    if summary_path.exists():
        summary = json.loads(summary_path.read_text(encoding="utf-8"))
        return date.fromisoformat(summary["as_of_date"])
    return date(2025, 12, 31)


def _load_csv(
    connection: sqlite3.Connection,
    dataset: str,
    source: Path,
    ingestion_metadata: dict[str, str],
) -> int:
    expected_fields = EXPECTED_SCHEMAS[dataset]
    with source.open("r", newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle, strict=True)
        actual_fields = reader.fieldnames or []
        if len(actual_fields) != len(expected_fields) or set(actual_fields) != set(expected_fields):
            raise ValueError(f"{source.name} has a schema mismatch; run the Phase 3 ingestion check.")
        columns_sql = ", ".join(f'"{name}"' for name in expected_fields)
        placeholders = ", ".join("?" for _ in expected_fields)
        insert_sql = f"INSERT INTO stg_{dataset} ({columns_sql}) VALUES ({placeholders})"
        bronze_fields = [
            *expected_fields,
            "source_file",
            "source_system",
            "ingestion_timestamp",
            "ingestion_run_id",
            "source_row_number",
            "source_file_size_bytes",
        ]
        bronze_columns_sql = ", ".join(f'"{name}"' for name in bronze_fields)
        bronze_placeholders = ", ".join("?" for _ in bronze_fields)
        bronze_insert_sql = f"INSERT INTO bronze_{dataset} ({bronze_columns_sql}) VALUES ({bronze_placeholders})"
        batch: list[tuple[Any, ...]] = []
        bronze_batch: list[tuple[Any, ...]] = []
        row_count = 0
        for row in reader:
            if None in row or any(value is None for value in row.values()):
                raise ValueError(f"{source.name} contains a structurally malformed record; run Phase 3 ingestion.")
            row_count += 1
            source_values = tuple(row.get(column, "") or "" for column in expected_fields)
            batch.append(source_values)
            bronze_batch.append((
                *source_values,
                source.name,
                "retailpulse_synthetic_csv",
                ingestion_metadata["ingestion_timestamp"],
                ingestion_metadata["ingestion_run_id"],
                row_count,
                int(ingestion_metadata["file_size_bytes"]),
            ))
            if len(batch) >= BATCH_SIZE:
                connection.executemany(insert_sql, batch)
                connection.executemany(bronze_insert_sql, bronze_batch)
                batch.clear()
                bronze_batch.clear()
        if batch:
            connection.executemany(insert_sql, batch)
            connection.executemany(bronze_insert_sql, bronze_batch)
    expected_rows = int(ingestion_metadata["row_count"])
    if row_count != expected_rows:
        raise ValueError(f"{source.name} row count changed after ingestion: expected {expected_rows}, found {row_count}.")
    return row_count


def _load_ingestion_metadata(report_dir: Path) -> tuple[str, dict[str, dict[str, str]]]:
    summary_path = report_dir / "ingestion_summary.csv"
    run_path = report_dir / "run_summary.json"
    if not summary_path.is_file() or not run_path.is_file():
        raise FileNotFoundError("Run the Phase 3 ingestion step before building medallion layers.")
    run = json.loads(run_path.read_text(encoding="utf-8"))
    metadata = {}
    with summary_path.open("r", newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            dataset = Path(row["source_file"]).stem
            if dataset in EXPECTED_SCHEMAS:
                if row["status"] != "success":
                    raise ValueError(f"Ingestion status for {dataset} is {row['status']}; cannot build Bronze.")
                metadata[dataset] = {
                    "ingestion_timestamp": row["ingestion_timestamp"],
                    "row_count": row["row_count"],
                    "file_size_bytes": row["file_size_bytes"],
                    "ingestion_run_id": run["run_id"],
                }
    missing = sorted(set(EXPECTED_SCHEMAS) - set(metadata))
    if missing:
        raise ValueError(f"Ingestion summary is missing successful datasets: {', '.join(missing)}")
    return run["run_id"], metadata


def _export_query(connection: sqlite3.Connection, query: str, path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    cursor = connection.execute(query)
    fields = [column[0] for column in cursor.description or []]
    row_count = 0
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(fields)
        while rows := cursor.fetchmany(BATCH_SIZE):
            writer.writerows(rows)
            row_count += len(rows)
    return row_count


def _export_table(connection: sqlite3.Connection, table: str, path: Path) -> int:
    return _export_query(connection, f'SELECT * FROM "{table}"', path)


def _export_layer(
    connection: sqlite3.Connection,
    layer_dir: Path,
    table_files: dict[str, str],
) -> dict[str, int]:
    return {
        file_name: _export_table(connection, table, layer_dir / file_name)
        for table, file_name in table_files.items()
    }


def _table_counts(connection: sqlite3.Connection) -> dict[str, int]:
    tables = [
        row[0]
        for row in connection.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND "
            "(name LIKE 'stg_%' OR name LIKE 'clean_%' OR name LIKE 'analytics_%' "
            "OR name LIKE 'dim_%' OR name LIKE 'fact_%' OR name LIKE 'bronze_%' "
            "OR name LIKE 'silver_%' OR name LIKE 'gold_%') ORDER BY name"
        )
    ]
    return {table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0] for table in tables}


def _run_sql(
    input_dir: Path = Path("data/raw"),
    database_path: Path = Path("data/processed/retailpulse.db"),
    sql_dir: Path = Path("sql"),
    as_of_date: date | None = None,
) -> dict[str, Any]:
    input_dir = input_dir.resolve()
    database_path = database_path.resolve()
    database_path.parent.mkdir(parents=True, exist_ok=True)
    sql_dir = sql_dir.resolve()
    reference_date = _reference_date(input_dir, as_of_date)
    processed_dir = database_path.parent
    ingestion_dir = processed_dir / "ingestion"
    quality_dir = processed_dir / "quality"
    quarantine_dir = processed_dir.parent / "quarantine" / "ingestion"
    log_file = processed_dir.parent.parent / "logs" / "ingestion.log"
    ingestion_run = ingest(input_dir, ingestion_dir, quarantine_dir, log_file)
    if ingestion_run["status"] != "success":
        raise ValueError("Ingestion found missing, unexpected, or malformed source files; see its report.")
    quality_summary = validate(input_dir, quality_dir, reference_date)
    ingestion_run_id, ingestion_metadata = _load_ingestion_metadata(ingestion_dir)

    connection = sqlite3.connect(database_path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        staging_sql = (sql_dir / "staging" / "01_create_staging.sql").read_text(encoding="utf-8")
        clean_sql = (sql_dir / "transformations" / "01_clean_tables.sql").read_text(encoding="utf-8")
        analytics_sql = (sql_dir / "analytics" / "01_business_summaries.sql").read_text(encoding="utf-8")
        model_sql = (sql_dir / "model" / "01_star_schema.sql").read_text(encoding="utf-8")
        bronze_sql = (sql_dir / "medallion" / "01_create_bronze.sql").read_text(encoding="utf-8")
        silver_gold_sql = (sql_dir / "medallion" / "02_create_silver_gold.sql").read_text(encoding="utf-8")
        connection.executescript(staging_sql)
        connection.executescript(bronze_sql)
        load_counts = {}
        for dataset in EXPECTED_SCHEMAS:
            load_counts[f"stg_{dataset}"] = _load_csv(
                connection, dataset, input_dir / f"{dataset}.csv", ingestion_metadata[dataset]
            )
        connection.execute("DROP TABLE IF EXISTS pipeline_config")
        connection.execute(
            "CREATE TABLE pipeline_config (as_of_date TEXT NOT NULL, source_dir TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO pipeline_config (as_of_date, source_dir) VALUES (?, ?)",
            (reference_date.isoformat(), str(input_dir)),
        )
        connection.commit()
        connection.executescript(clean_sql)
        connection.executescript(analytics_sql)
        connection.executescript(model_sql)
        connection.executescript(silver_gold_sql)
        foreign_key_violations = connection.execute("PRAGMA foreign_key_check").fetchall()
        if foreign_key_violations:
            raise sqlite3.IntegrityError(
                f"Star-schema build has {len(foreign_key_violations)} foreign-key violation(s)."
            )
        counts = _table_counts(connection)
        bronze_dir = processed_dir / "bronze"
        silver_dir = processed_dir / "silver"
        gold_dir = processed_dir / "gold"
        export_counts = {
            "bronze": _export_layer(connection, bronze_dir, BRONZE_EXPORTS),
            "silver": _export_layer(connection, silver_dir, SILVER_EXPORTS),
            "gold": _export_layer(connection, gold_dir, GOLD_EXPORTS),
        }
        power_bi_dir = processed_dir / "powerbi_model"
        power_bi_export_counts = {
            f"{table}.csv": _export_query(
                connection, query, power_bi_dir / f"{table}.csv"
            )
            for table, query in POWER_BI_MODEL_QUERIES.items()
        }
        shutil.copy2(quality_dir / "quality_report.csv", silver_dir / "quality_rule_results.csv")
        shutil.copy2(quality_dir / "quality_violations.csv", silver_dir / "quality_violation_examples.csv")
        run_summary = {
            "run_timestamp": datetime.now(timezone.utc).isoformat(timespec="microseconds"),
            "sqlite_version": sqlite3.sqlite_version,
            "database_path": str(database_path.resolve()),
            "source_dir": str(input_dir),
            "as_of_date": reference_date.isoformat(),
            "foreign_key_violations": len(foreign_key_violations),
            "ingestion_run_id": ingestion_run_id,
            "quality_status": quality_summary["quality_status"],
            "quality_rules_evaluated": quality_summary["rules_evaluated"],
            "quality_rules_passed": quality_summary["rules_passed"],
            "quality_rules_failed": quality_summary["rules_failed"],
            "quality_failed_rows_across_rules": quality_summary[
                "failed_row_counts_across_rules"
            ],
            "quality_violation_details_written": quality_summary[
                "violation_details_written"
            ],
            "staging_rows_loaded": load_counts,
            "table_row_counts": counts,
            "medallion_export_row_counts": export_counts,
            "medallion_export_directories": {
                "bronze": str(bronze_dir.resolve()),
                "silver": str(silver_dir.resolve()),
                "gold": str(gold_dir.resolve()),
            },
            "power_bi_model_export_row_counts": power_bi_export_counts,
            "power_bi_model_export_directory": str(power_bi_dir.resolve()),
        }
        summary_path = database_path.with_name("sql_run_summary.json")
        summary_path.write_text(json.dumps(run_summary, indent=2) + "\n", encoding="utf-8")
        return run_summary
    finally:
        connection.close()


def _source_freshness(input_dir: Path) -> dict[str, Any]:
    source_files = list(input_dir.glob("*.csv")) if input_dir.is_dir() else []
    latest_path: Path | None = None
    latest_modified: datetime | None = None
    for path in source_files:
        try:
            modified = datetime.fromtimestamp(path.stat().st_mtime, timezone.utc)
        except OSError:
            continue
        if latest_modified is None or modified > latest_modified:
            latest_path = path
            latest_modified = modified
    age_seconds = (
        max(0.0, (datetime.now(timezone.utc) - latest_modified).total_seconds())
        if latest_modified is not None
        else None
    )
    return {
        "source_files_seen": len(source_files),
        "latest_source_file": latest_path.name if latest_path else "",
        "latest_source_modified_at_utc": (
            latest_modified.isoformat(timespec="microseconds") if latest_modified else ""
        ),
        "source_freshness_age_seconds": (
            round(age_seconds, 3) if age_seconds is not None else ""
        ),
    }


def _append_monitoring_record(path: Path, record: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not path.exists() or path.stat().st_size == 0
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=MONITORING_FIELDS, extrasaction="ignore")
        if write_header:
            writer.writeheader()
        writer.writerow(record)


def _summary_monitor_metrics(summary: dict[str, Any]) -> dict[str, Any]:
    staging_rows = summary.get("staging_rows_loaded", {})
    export_counts = summary.get("medallion_export_row_counts", {})
    return {
        "ingestion_run_id": summary.get("ingestion_run_id", ""),
        "ingestion_rows_total": sum(int(value) for value in staging_rows.values()),
        "quality_status": summary.get("quality_status", ""),
        "quality_rules_evaluated": summary.get("quality_rules_evaluated", ""),
        "quality_rules_passed": summary.get("quality_rules_passed", ""),
        "quality_rules_failed": summary.get("quality_rules_failed", ""),
        "quality_failed_rows_across_rules": summary.get(
            "quality_failed_rows_across_rules", ""
        ),
        "quality_violation_details_written": summary.get(
            "quality_violation_details_written", ""
        ),
        "foreign_key_violations": summary.get("foreign_key_violations", ""),
        "bronze_export_rows": sum(export_counts.get("bronze", {}).values()),
        "silver_export_rows": sum(export_counts.get("silver", {}).values()),
        "gold_export_rows": sum(export_counts.get("gold", {}).values()),
        "power_bi_model_export_rows": sum(
            summary.get("power_bi_model_export_row_counts", {}).values()
        ),
    }


def run_sql(
    input_dir: Path = Path("data/raw"),
    database_path: Path = Path("data/processed/retailpulse.db"),
    sql_dir: Path = Path("sql"),
    as_of_date: date | None = None,
) -> dict[str, Any]:
    input_dir = input_dir.resolve()
    database_path = database_path.resolve()
    monitoring_path = database_path.parent / "monitoring" / "pipeline_runs.csv"
    run_start = datetime.now(timezone.utc)
    start_clock = perf_counter()
    pipeline_run_id = f"sql_{run_start.strftime('%Y%m%dT%H%M%S%fZ')}"
    freshness = _source_freshness(input_dir)

    try:
        summary = _run_sql(input_dir, database_path, sql_dir, as_of_date)
    except Exception as error:
        run_end = datetime.now(timezone.utc)
        record = {
            "pipeline_run_id": pipeline_run_id,
            "run_start_timestamp": run_start.isoformat(timespec="microseconds"),
            "run_end_timestamp": run_end.isoformat(timespec="microseconds"),
            "duration_seconds": round(perf_counter() - start_clock, 3),
            "run_status": "failed",
            "input_dir": str(input_dir),
            **freshness,
            "error_type": type(error).__name__,
            "error_message": str(error),
        }
        try:
            _append_monitoring_record(monitoring_path, record)
        except OSError:
            pass
        raise

    run_end = datetime.now(timezone.utc)
    duration_seconds = round(perf_counter() - start_clock, 3)
    summary.update({
        "pipeline_run_id": pipeline_run_id,
        "run_start_timestamp": run_start.isoformat(timespec="microseconds"),
        "run_end_timestamp": run_end.isoformat(timespec="microseconds"),
        "duration_seconds": duration_seconds,
        "run_status": "success",
        "source_files_seen": freshness["source_files_seen"],
        "latest_source_file": freshness["latest_source_file"],
        "latest_source_modified_at_utc": freshness["latest_source_modified_at_utc"],
        "source_freshness_age_seconds": freshness["source_freshness_age_seconds"],
        "monitoring_log_path": str(monitoring_path.resolve()),
    })
    summary.update(_summary_monitor_metrics(summary))
    summary_path = database_path.with_name("sql_run_summary.json")
    summary_path.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    record = {
        "pipeline_run_id": pipeline_run_id,
        "run_start_timestamp": summary["run_start_timestamp"],
        "run_end_timestamp": summary["run_end_timestamp"],
        "duration_seconds": duration_seconds,
        "run_status": "success",
        "input_dir": str(input_dir),
        **freshness,
        **_summary_monitor_metrics(summary),
    }
    _append_monitoring_record(monitoring_path, record)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run RetailPulse ingestion, quality, SQLite, and medallion layers.")
    parser.add_argument("--input-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--database", type=Path, default=Path("data/processed/retailpulse.db"))
    parser.add_argument("--sql-dir", type=Path, default=PROJECT_ROOT / "sql")
    parser.add_argument("--as-of-date", type=date.fromisoformat, default=None)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        summary = run_sql(args.input_dir, args.database, args.sql_dir, args.as_of_date)
    except (OSError, ValueError, sqlite3.Error, json.JSONDecodeError) as error:
        print(f"SQL pipeline could not complete: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
