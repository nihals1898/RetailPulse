"""Measure end-to-end SQL pipeline runtime on local CSV inputs."""

from __future__ import annotations

import argparse
import json
import os
import platform
import sqlite3
import statistics
import sys
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter

from retailpulse.sql_pipeline import run_sql


def _directory_size(path: Path) -> int:
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def run_benchmark(input_dir: Path, runs: int, output_dir: Path) -> dict[str, object]:
    input_dir = input_dir.resolve()
    output_dir = output_dir.resolve()
    input_files = sorted(input_dir.glob("*.csv"))
    if not input_files:
        raise FileNotFoundError(f"No source CSV files found in {input_dir}")

    output_dir.mkdir(parents=True, exist_ok=False)
    input_bytes = sum(path.stat().st_size for path in input_files)
    run_results = []
    for run_number in range(1, runs + 1):
        run_dir = output_dir / f"run_{run_number:02d}" / "processed"
        database_path = run_dir / "retailpulse.db"
        started = perf_counter()
        summary = run_sql(input_dir, database_path)
        wall_seconds = round(perf_counter() - started, 3)
        run_results.append({
            "run_number": run_number,
            "duration_seconds": wall_seconds,
            "pipeline_duration_seconds": summary["duration_seconds"],
            "run_status": summary["run_status"],
            "quality_status": summary["quality_status"],
            "input_rows": summary["ingestion_rows_total"],
            "silver_rows": summary["silver_export_rows"],
            "gold_rows": summary["gold_export_rows"],
            "power_bi_model_rows": summary["power_bi_model_export_rows"],
            "database_bytes": database_path.stat().st_size,
            "processed_output_bytes": _directory_size(run_dir),
        })

    durations = [float(result["duration_seconds"]) for result in run_results]
    result = {
        "benchmark_timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "measurement": "end-to-end local SQL pipeline; each run writes to a fresh isolated directory",
        "input_directory": str(input_dir),
        "input_file_count": len(input_files),
        "input_files": [path.name for path in input_files],
        "input_bytes": input_bytes,
        "runs": runs,
        "duration_seconds": {
            "per_run": durations,
            "median": round(statistics.median(durations), 3),
            "minimum": min(durations),
            "maximum": max(durations),
        },
        "environment": {
            "python_version": sys.version.split()[0],
            "python_implementation": platform.python_implementation(),
            "platform": platform.platform(),
            "processor": platform.processor() or "unknown",
            "logical_cpu_count": os.cpu_count(),
            "sqlite_version": sqlite3.sqlite_version,
        },
        "run_results": run_results,
        "output_directory": str(output_dir),
        "notes": [
            "Source files are read in place and never modified.",
            "Each benchmark run uses a fresh SQLite database and isolated outputs.",
            "Later runs may benefit from operating-system file cache; treat the median as a local reference, not a universal guarantee.",
            "Data-quality failures in intentionally dirty sample data do not mean the pipeline execution failed.",
        ],
    }
    report_path = output_dir / "benchmark_report.json"
    report_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--output-dir", type=Path, default=None)
    args = parser.parse_args()
    if args.runs < 1:
        parser.error("--runs must be at least 1")
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    output_dir = args.output_dir or Path("work/performance") / timestamp
    report = run_benchmark(args.input_dir, args.runs, output_dir)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
