"""Local CSV discovery, contract checks, run reporting, and structural quarantine."""

from __future__ import annotations

import argparse
import csv
import json
import logging
import shutil
import sys
import time as time_module
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from retailpulse.generation import (
    CUSTOMER_FIELDS,
    INVENTORY_FIELDS,
    ORDER_FIELDS,
    ORDER_ITEM_FIELDS,
    PAYMENT_FIELDS,
    PRODUCT_FIELDS,
    RETURN_FIELDS,
    STORE_FIELDS,
)

EXPECTED_SCHEMAS: dict[str, list[str]] = {
    "customers": CUSTOMER_FIELDS,
    "products": PRODUCT_FIELDS,
    "stores": STORE_FIELDS,
    "orders": ORDER_FIELDS,
    "order_items": ORDER_ITEM_FIELDS,
    "payments": PAYMENT_FIELDS,
    "inventory": INVENTORY_FIELDS,
    "returns": RETURN_FIELDS,
}

SUMMARY_FIELDS = [
    "dataset", "source_file", "ingestion_timestamp", "row_count", "status", "error_count",
    "file_size_bytes", "valid_rows", "quarantined_rows", "error_message",
]
ERROR_FIELDS = [
    "ingestion_timestamp", "dataset", "source_file", "line_number", "error", "raw_values",
]


def _utc_timestamp() -> tuple[str, str]:
    now = datetime.now(timezone.utc)
    return now.isoformat(timespec="microseconds"), now.strftime("%Y%m%dT%H%M%S%fZ")


def _make_logger(log_file: Path) -> logging.Logger:
    log_file.parent.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("retailpulse.ingestion")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()
    formatter = logging.Formatter("%(asctime)sZ %(levelname)s %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
    formatter.converter = time_module.gmtime
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    logger.addHandler(stream_handler)
    return logger


def _write_csv(path: Path, fields: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _quarantine_file(source: Path, quarantine_dir: Path, run_id: str, reason: list[str]) -> Path:
    files_dir = quarantine_dir / "files"
    files_dir.mkdir(parents=True, exist_ok=True)
    destination = files_dir / f"{source.stem}_{run_id}{source.suffix}"
    shutil.copy2(source, destination)
    reason_path = destination.with_suffix(destination.suffix + ".reason.json")
    reason_path.write_text(
        json.dumps({"source_file": source.name, "reasons": reason}, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination


def _inspect_csv(
    path: Path,
    dataset: str,
    expected_fields: list[str] | None,
    ingestion_timestamp: str,
    run_id: str,
    quarantine_dir: Path,
    error_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    try:
        file_size = path.stat().st_size
    except OSError as error:
        file_size = 0
        messages = [f"Could not inspect file metadata: {error}"]
    else:
        messages = []
    row_count = 0
    valid_rows = 0
    malformed_rows: list[dict[str, Any]] = []
    header: list[str] | None = None
    parser_error = False

    try:
        with path.open("r", newline="", encoding="utf-8-sig") as handle:
            reader = csv.reader(handle, strict=True)
            try:
                header = next(reader)
            except StopIteration:
                messages.append("CSV file is empty; a header row is required.")
            if header is not None:
                duplicate_headers = sorted({name for name in header if header.count(name) > 1})
                if duplicate_headers:
                    messages.append(f"Duplicate header names: {', '.join(duplicate_headers)}")
                if not header or any(not name.strip() for name in header):
                    messages.append("Header contains an empty column name.")
                if expected_fields is not None:
                    missing = sorted(set(expected_fields) - set(header))
                    extra = sorted(set(header) - set(expected_fields))
                    if missing:
                        messages.append(f"Missing required columns: {', '.join(missing)}")
                    if extra:
                        messages.append(f"Unexpected columns: {', '.join(extra)}")
                try:
                    for values in reader:
                        row_count += 1
                        if len(values) != len(header):
                            message = f"Field count {len(values)} does not match header count {len(header)}."
                            malformed_rows.append({
                                "ingestion_timestamp": ingestion_timestamp,
                                "dataset": dataset,
                                "source_file": path.name,
                                "line_number": reader.line_num,
                                "error": message,
                                "raw_values": json.dumps(values, ensure_ascii=False),
                            })
                        else:
                            valid_rows += 1
                except csv.Error as error:
                    parser_error = True
                    messages.append(f"CSV parsing error near line {reader.line_num}: {error}")
    except (OSError, UnicodeError) as error:
        parser_error = True
        messages.append(f"Could not read file: {error}")

    schema_errors = bool(messages) or header is None
    malformed_count = len(malformed_rows)
    if malformed_count:
        error_rows.extend(malformed_rows)
        messages.append(f"{malformed_count} row(s) have an unexpected field count.")

    quarantined_rows = malformed_count
    status = "success"
    if schema_errors or parser_error:
        status = "failed"
        try:
            _quarantine_file(path, quarantine_dir, run_id, messages)
            quarantined_rows = row_count
        except OSError as error:
            messages.append(f"Failed to copy file to quarantine: {error}")
            quarantined_rows = 0
    elif malformed_count:
        status = "partial"
        rows_dir = quarantine_dir / "rows"
        row_path = rows_dir / f"{path.stem}_malformed_{run_id}.csv"
        try:
            _write_csv(row_path, ERROR_FIELDS, malformed_rows)
        except OSError as error:
            messages.append(f"Failed to write malformed rows to quarantine: {error}")
            status = "failed"
            quarantined_rows = 0

    for message in messages:
        error_rows.append({
            "ingestion_timestamp": ingestion_timestamp,
            "dataset": dataset,
            "source_file": path.name,
            "line_number": "",
            "error": message,
            "raw_values": "",
        })

    return {
        "dataset": dataset,
        "source_file": path.name,
        "ingestion_timestamp": ingestion_timestamp,
        "row_count": row_count,
        "status": status,
        "error_count": len(messages) + malformed_count,
        "file_size_bytes": file_size,
        "valid_rows": valid_rows if status != "failed" else 0,
        "quarantined_rows": quarantined_rows,
        "error_message": " | ".join(messages),
    }


def ingest(
    input_dir: Path = Path("data/raw"),
    report_dir: Path = Path("data/processed/ingestion"),
    quarantine_dir: Path = Path("data/quarantine/ingestion"),
    log_file: Path = Path("logs/ingestion.log"),
) -> dict[str, Any]:
    """Discover expected CSVs, validate contracts, quarantine structural failures, and report."""
    ingestion_timestamp, run_id = _utc_timestamp()
    logger = _make_logger(log_file)
    input_dir = input_dir.resolve()
    report_dir.mkdir(parents=True, exist_ok=True)
    quarantine_dir.mkdir(parents=True, exist_ok=True)
    summary_rows: list[dict[str, Any]] = []
    error_rows: list[dict[str, Any]] = []

    discovered = {file.name: file for file in input_dir.glob("*.csv")} if input_dir.is_dir() else {}
    discovered_count = len(discovered)
    if not input_dir.is_dir():
        logger.error("Input directory does not exist: %s", input_dir)

    for dataset, expected_fields in EXPECTED_SCHEMAS.items():
        file_name = f"{dataset}.csv"
        source = discovered.pop(file_name, None)
        if source is None:
            message = "Expected source file is missing."
            logger.error("%s: %s", file_name, message)
            summary_rows.append({
                "dataset": dataset,
                "source_file": file_name,
                "ingestion_timestamp": ingestion_timestamp,
                "row_count": 0,
                "status": "missing",
                "error_count": 1,
                "file_size_bytes": 0,
                "valid_rows": 0,
                "quarantined_rows": 0,
                "error_message": message,
            })
            error_rows.append({
                "ingestion_timestamp": ingestion_timestamp,
                "dataset": dataset,
                "source_file": file_name,
                "line_number": "",
                "error": message,
                "raw_values": "",
            })
            continue
        result = _inspect_csv(
            source, dataset, expected_fields, ingestion_timestamp, run_id,
            quarantine_dir, error_rows,
        )
        summary_rows.append(result)
        logger.log(
            logging.INFO if result["status"] == "success" else logging.WARNING,
            "%s status=%s rows=%s errors=%s bytes=%s",
            source.name, result["status"], result["row_count"],
            result["error_count"], result["file_size_bytes"],
        )

    for source in sorted(discovered.values()):
        message = "Unexpected CSV filename; expected one of the registered dataset names."
        try:
            _quarantine_file(source, quarantine_dir, run_id, [message])
            file_size = source.stat().st_size
            status = "failed"
            quarantine_error = ""
        except OSError as error:
            file_size = 0
            status = "failed"
            quarantine_error = f" Could not quarantine file: {error}"
        logger.error("Unexpected file %s; copied to quarantine when possible.", source.name)
        summary_rows.append({
            "dataset": "unknown",
            "source_file": source.name,
            "ingestion_timestamp": ingestion_timestamp,
            "row_count": 0,
            "status": status,
            "error_count": 1,
            "file_size_bytes": file_size,
            "valid_rows": 0,
            "quarantined_rows": 0,
            "error_message": message + quarantine_error,
        })
        error_rows.append({
            "ingestion_timestamp": ingestion_timestamp,
            "dataset": "unknown",
            "source_file": source.name,
            "line_number": "",
            "error": message + quarantine_error,
            "raw_values": "",
        })

    _write_csv(report_dir / "ingestion_summary.csv", SUMMARY_FIELDS, summary_rows)
    _write_csv(report_dir / "ingestion_errors.csv", ERROR_FIELDS, error_rows)
    failed_count = sum(row["status"] in {"failed", "missing"} for row in summary_rows)
    partial_count = sum(row["status"] == "partial" for row in summary_rows)
    run_summary = {
        "ingestion_timestamp": ingestion_timestamp,
        "run_id": run_id,
        "input_dir": str(input_dir),
        "datasets_discovered": discovered_count,
        "summary_rows": len(summary_rows),
        "failed_or_missing_files": failed_count,
        "partial_files": partial_count,
        "status": "failed" if failed_count or partial_count else "success",
    }
    (report_dir / "run_summary.json").write_text(
        json.dumps(run_summary, indent=2) + "\n", encoding="utf-8"
    )
    logger.info("Ingestion run %s completed with status=%s", run_id, run_summary["status"])
    return run_summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Ingest and validate RetailPulse source CSV files.")
    parser.add_argument("--input-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--report-dir", type=Path, default=Path("data/processed/ingestion"))
    parser.add_argument("--quarantine-dir", type=Path, default=Path("data/quarantine/ingestion"))
    parser.add_argument("--log-file", type=Path, default=Path("logs/ingestion.log"))
    return parser


def main() -> None:
    args = build_parser().parse_args()
    try:
        summary = ingest(args.input_dir, args.report_dir, args.quarantine_dir, args.log_file)
    except OSError as error:
        print(f"Ingestion could not complete: {error}", file=sys.stderr)
        raise SystemExit(1) from error
    print(json.dumps(summary, indent=2))
    if summary["status"] != "success":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
