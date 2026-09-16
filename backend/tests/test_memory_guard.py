"""Unit tests for the memory check that protects the real-model tests."""

from pathlib import Path

import pytest

from tests.memory_guard import REQUIRED_MEMORY_MB, available_memory_mb, low_memory_message

MEMINFO = """MemTotal:       11874524 kB
MemFree:          812344 kB
MemAvailable:    3145728 kB
Buffers:          120000 kB
"""


def test_reads_mem_available_in_megabytes(tmp_path: Path) -> None:
    meminfo = tmp_path / "meminfo"
    meminfo.write_text(MEMINFO, encoding="utf-8")

    # MemAvailable, not MemFree: 3145728 kB are 3072 MB.
    assert available_memory_mb(meminfo) == 3072


def test_missing_file_or_field_means_unknown(tmp_path: Path) -> None:
    without_field = tmp_path / "meminfo"
    without_field.write_text("MemTotal:       11874524 kB\n", encoding="utf-8")

    assert available_memory_mb(tmp_path / "does-not-exist") is None
    assert available_memory_mb(without_field) is None


def test_the_real_file_can_be_read_on_linux() -> None:
    if not Path("/proc/meminfo").exists():
        pytest.skip("no /proc/meminfo on this system")

    assert available_memory_mb() > 0


@pytest.mark.parametrize(
    ("available_mb", "stops"),
    [(REQUIRED_MEMORY_MB - 1, True), (REQUIRED_MEMORY_MB, False), (8000, False), (None, False)],
    ids=["below-threshold", "exactly-the-threshold", "plenty", "unknown"],
)
def test_stops_only_when_memory_is_known_to_be_too_low(available_mb: int | None, stops: bool) -> None:
    message = low_memory_message(available_mb)

    assert (message is not None) == stops
    if stops:
        assert f"{available_mb} MB" in message
        assert str(REQUIRED_MEMORY_MB) in message
