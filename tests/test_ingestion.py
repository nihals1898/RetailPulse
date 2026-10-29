from __future__ import annotations

import csv
from pathlib import Path

from retailpulse.ingestion.framework import EXPECTED_SCHEMAS, ingest


def test_ingestion_records_contract_counts_and_preserves_sources(
    clean_data_dir: Path, tmp_path: Path
) -> None:
    original_files = {path.name: path.read_bytes() for path in clean_data_dir.glob("*.csv")}
    report_dir = tmp_path / "reports"

    result = ingest(
        clean_data_dir,
        report_dir,
        tmp_path / "quarantine",
        tmp_path / "logs" / "ingestion.log",
    )

    assert result["status"] == "success"
    assert result["summary_rows"] == len(EXPECTED_SCHEMAS)
    with (report_dir / "ingestion_summary.csv").open(newline="", encoding="utf-8") as handle:
        rows = {row["dataset"]: row for row in csv.DictReader(handle)}
    assert set(rows) == set(EXPECTED_SCHEMAS)
    assert all(row["status"] == "success" for row in rows.values())
    assert {path.name: path.read_bytes() for path in clean_data_dir.glob("*.csv")} == original_files


def test_ingestion_quarantines_malformed_rows_and_marks_partial(
    clean_data_dir: Path, tmp_path: Path
) -> None:
    customers_path = clean_data_dir / "customers.csv"
    with customers_path.open("a", encoding="utf-8") as handle:
        handle.write("too,few,columns\n")

    quarantine_dir = tmp_path / "quarantine"
    report_dir = tmp_path / "reports"
    result = ingest(
        clean_data_dir,
        report_dir,
        quarantine_dir,
        tmp_path / "logs" / "ingestion.log",
    )

    assert result["status"] == "failed"
    assert result["partial_files"] == 1
    with (report_dir / "ingestion_summary.csv").open(newline="", encoding="utf-8") as handle:
        customers = next(row for row in csv.DictReader(handle) if row["dataset"] == "customers")
    assert customers["status"] == "partial"
    assert customers["row_count"] == "9"
    assert customers["valid_rows"] == "8"
    assert customers["quarantined_rows"] == "1"
    assert list((quarantine_dir / "rows").glob("customers_malformed_*.csv"))


def test_ingestion_quarantines_schema_mismatch_as_a_file(
    clean_data_dir: Path, tmp_path: Path
) -> None:
    customers_path = clean_data_dir / "customers.csv"
    content = customers_path.read_text(encoding="utf-8")
    customers_path.write_text(content.replace("email,", "email_extra,", 1), encoding="utf-8")

    quarantine_dir = tmp_path / "quarantine"
    report_dir = tmp_path / "reports"
    result = ingest(
        clean_data_dir,
        report_dir,
        quarantine_dir,
        tmp_path / "logs" / "ingestion.log",
    )

    assert result["status"] == "failed"
    assert list((quarantine_dir / "files").glob("customers_*.csv"))
    with (report_dir / "ingestion_summary.csv").open(newline="", encoding="utf-8") as handle:
        customers = next(row for row in csv.DictReader(handle) if row["dataset"] == "customers")
    assert customers["status"] == "failed"
