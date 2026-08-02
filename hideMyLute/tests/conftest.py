"""Общие настройки pytest для hideMyLute.

Медленные (нагрузочные) тесты помечены маркером ``slow`` и пропускаются
по умолчанию; запуск: ``pytest --run-slow``.
"""

from __future__ import annotations

import pytest


def pytest_addoption(parser: pytest.Parser) -> None:
    """Добавляет опцию --run-slow."""
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="Запускать медленные нагрузочные тесты (marker slow)",
    )


def pytest_collection_modifyitems(
    config: pytest.Config, items: list[pytest.Item]
) -> None:
    """Пропускает slow-тесты, если не передана опция --run-slow."""
    if config.getoption("--run-slow"):
        return
    skip_slow = pytest.mark.skip(reason="slow test, используйте --run-slow")
    for item in items:
        if "slow" in item.keywords:
            item.add_marker(skip_slow)
