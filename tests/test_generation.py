from __future__ import annotations

import csv
from dataclasses import replace
from datetime import date
from pathlib import Path

import pytest

from retailpulse.generation import GenerationConfig, generate
from retailpulse.ingestion.framework import EXPECTED_SCHEMAS


def test_generation_is_seeded_and_writes_expected_schemas(tmp_path: Path) -> None:
    first_dir = tmp_path / "first"
    second_dir = tmp_path / "second"
    config = GenerationConfig(
        customers=8,
        products=4,
        stores=2,
        orders=6,
        order_items=12,
        payments=6,
        inventory=8,
        returns=2,
        seed=17,
        as_of_date=date(2025, 12, 31),
        defect_rate=0,
    )

    first_summary = generate(replace(config, output_dir=first_dir))
    second_summary = generate(replace(config, output_dir=second_dir))

    assert first_summary["row_counts"] == second_summary["row_counts"]
    assert first_summary["injected_defects_by_rule"] == second_summary["injected_defects_by_rule"]
    assert first_summary["injected_defects_by_rule"]
    for dataset, expected_fields in EXPECTED_SCHEMAS.items():
        first_file = first_dir / f"{dataset}.csv"
        second_file = second_dir / f"{dataset}.csv"
        assert first_file.read_bytes() == second_file.read_bytes()
        with first_file.open(newline="", encoding="utf-8") as handle:
            assert next(csv.reader(handle)) == expected_fields


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"customers": -1}, "Row counts cannot be negative"),
        ({"defect_rate": 0.5}, "defect-rate must be between"),
        ({"orders": 2, "order_items": 1}, "at least the order count"),
    ],
)
def test_generation_rejects_invalid_configuration(
    overrides: dict[str, object], message: str, tmp_path: Path
) -> None:
    config = GenerationConfig(output_dir=tmp_path, **overrides)

    with pytest.raises(ValueError, match=message):
        config.validate()
