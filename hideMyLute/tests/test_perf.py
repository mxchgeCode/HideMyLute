"""Нагрузочные/производительные тесты (marker slow).

Запуск: ``pytest --run-slow``.
"""

from __future__ import annotations

import os
import time
from pathlib import Path

import pytest

from hideMyLute.crypto import derive_key
from hideMyLute.steganography import join_files, split_file

pytestmark = pytest.mark.slow

_PASSWORD = "password123456"


def test_derive_key_within_budget() -> None:
    """PBKDF2 (600k итераций) укладывается в бюджет времени.

    Защищает от неожиданного замедления деривации ключа на слабых машинах.
    """
    start = time.monotonic()
    derive_key(_PASSWORD)
    elapsed = time.monotonic() - start
    assert elapsed < 2.0, f"derive_key слишком медленная: {elapsed:.2f}с"


def test_large_file_roundtrip(tmp_path) -> None:
    """Roundtrip join→split для файлов по 8 МБ."""
    carrier = tmp_path / "carrier.jpg"
    container = tmp_path / "container.bin"
    output = tmp_path / "out.jpg"
    out_dir = tmp_path / "out"

    size = 8 * 1024 * 1024
    carrier.write_bytes(os.urandom(size))
    container.write_bytes(os.urandom(size))

    join_files(carrier, container, output, _PASSWORD)
    assert output.stat().st_size > 2 * size

    container_out, metadata = split_file(output, out_dir, _PASSWORD)
    assert metadata["carrier_size"] == size
    assert metadata["container_size"] == size
    assert Path(container_out).stat().st_size == size
