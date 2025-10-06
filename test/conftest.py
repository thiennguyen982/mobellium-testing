# conftest.py

import pytest
import csv
from pathlib import Path
from log_processor.processor import LogProcessor


@pytest.fixture
def sample_log_dir(tmp_path: Path):
    log_dir = tmp_path
    log_file = log_dir / "2025-01-01.log.csv"

    sample_data = [
        ["2025-01-01 00:15:00", "user1", "app1"] + list(range(1, 10)),
        ["2025-01-01 00:45:00", "user1", "app1"] + list(range(1, 10)),
        ["2025-01-01 01:15:00", "user2", "app2"] + list(range(1, 10)),
    ]
    with log_file.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(sample_data)

    return log_dir


@pytest.fixture
def processor(sample_log_dir: Path):
    return LogProcessor(logs_dir=str(sample_log_dir))
