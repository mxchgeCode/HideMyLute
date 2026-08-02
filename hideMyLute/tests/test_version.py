"""Тесты системы версионирования hideMyLute.

Версия формируется по схеме MAJOR.MINOR.PATCH, где PATCH равен
количеству изменений с предыдущего минорного релиза.
"""

from __future__ import annotations

import re
from pathlib import Path

import hideMyLute
from hideMyLute import _version

_SEMVER_RE = re.compile(r"^\d+\.\d+\.\d+$")


class TestVersionFormat:
    """Проверки формата и согласованности версии."""

    def test_version_string_matches_semver(self) -> None:
        """__version__ соответствует схеме MAJOR.MINOR.PATCH."""
        assert _SEMVER_RE.match(hideMyLute.__version__)

    def test_package_version_equals_module_version(self) -> None:
        """__init__ и _version используют один источник версии."""
        assert hideMyLute.__version__ == _version.VERSION_STRING

    def test_version_string_built_from_tuple(self) -> None:
        """VERSION_STRING собирается из кортежа VERSION."""
        assert _version.VERSION_STRING == ".".join(
            str(part) for part in _version.VERSION
        )

    def test_version_tuple_matches_components(self) -> None:
        """VERSION согласован с компонентами VERSION_MAJOR/MINOR/PATCH."""
        assert _version.VERSION == (
            _version.VERSION_MAJOR,
            _version.VERSION_MINOR,
            _version.VERSION_PATCH,
        )

    def test_version_components_are_non_negative(self) -> None:
        """Компоненты версии — неотрицательные целые."""
        for part in _version.VERSION:
            assert isinstance(part, int)
            assert part >= 0

    def test_version_is_public(self) -> None:
        """__version__ доступен через __all__ пакета."""
        assert "__version__" in hideMyLute.__all__


class TestVersionHistory:
    """Проверки соответствия версии журналу изменений."""

    def test_version_documented_in_changelog(self) -> None:
        """Актуальная версия упомянута в CHANGELOG.md."""
        changelog_path = (
            Path(__file__).resolve().parents[2] / "CHANGELOG.md"
        )
        assert changelog_path.exists()
        assert hideMyLute.__version__ in changelog_path.read_text(
            encoding="utf-8"
        )
