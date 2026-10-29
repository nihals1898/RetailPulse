from __future__ import annotations

import csv
from pathlib import Path

import pytest

from retailpulse.quality.engine import validate


def test_clean_synthetic_fixture_passes_quality_rules(clean_data_dir: Path, tmp_path: Path) -> None:
    result = validate(clean_data_dir, tmp_path / "quality")

    assert result["run_status"] == "completed"
    assert result["quality_status"] == "passed"
    assert result["rules_evaluated"] > 0
    assert result["rules_failed"] == 0
    assert result["violation_details_written"] == 0


def test_quality_reports_business_rule_failures_with_bounded_examples(
    clean_data_dir: Path, tmp_path: Path
) -> None:
    orders_path = clean_data_dir / "orders.csv"
    with orders_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
        fields = list(rows[0])
    rows[0]["order_total"] = "0.00"
    with orders_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    output_dir = tmp_path / "quality"
    result = validate(clean_data_dir, output_dir, detail_cap_per_rule=1)

    assert result["quality_status"] == "failed"
    with (output_dir / "quality_report.csv").open(newline="", encoding="utf-8") as handle:
        report = {row["rule"]: row for row in csv.DictReader(handle) if row["dataset"] == "orders"}
    assert report["order_total_reconciles_lines"]["failed_rows"] == "1"
    assert report["order_total_reconciles_lines"]["status"] == "failed"
    with (output_dir / "quality_violations.csv").open(newline="", encoding="utf-8") as handle:
        violations = list(csv.DictReader(handle))
    assert len(violations) == 1
    assert violations[0]["rule"] == "order_total_reconciles_lines"


def test_quality_rejects_returns_above_purchased_quantity(
    clean_data_dir: Path, tmp_path: Path
) -> None:
    returns_path = clean_data_dir / "returns.csv"
    with returns_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
        fields = list(rows[0])
    rows[0]["return_quantity"] = "999"
    with returns_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    output_dir = tmp_path / "quality"
    result = validate(clean_data_dir, output_dir)

    assert result["quality_status"] == "failed"
    with (output_dir / "quality_report.csv").open(newline="", encoding="utf-8") as handle:
        report = {
            row["rule"]: row
            for row in csv.DictReader(handle)
            if row["dataset"] == "returns"
        }
    assert report["return_quantity_within_purchase"]["failed_rows"] == "1"


def test_quality_requires_all_input_files(clean_data_dir: Path, tmp_path: Path) -> None:
    (clean_data_dir / "returns.csv").unlink()

    with pytest.raises(FileNotFoundError, match="Required input is missing"):
        validate(clean_data_dir, tmp_path / "quality")
