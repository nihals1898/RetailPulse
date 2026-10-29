from __future__ import annotations

from pathlib import Path

import pytest

from retailpulse.generation import GenerationConfig, generate


@pytest.fixture
def clean_data_dir(tmp_path: Path) -> Path:
    input_dir = tmp_path / "raw"
    generate(
        GenerationConfig(
            customers=8,
            products=4,
            stores=2,
            orders=6,
            order_items=12,
            payments=6,
            inventory=8,
            returns=2,
            seed=17,
            defect_rate=0,
            output_dir=input_dir,
        )
    )
    return input_dir
