"""Тесты модуля конфигурации."""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from hideMyLute.config import AppConfig
from hideMyLute.exceptions import HideMyLuteError


class TestAppConfig:
    """Тесты класса AppConfig."""

    @pytest.fixture
    def config_ru(self) -> AppConfig:
        """Создаёт конфигурацию на русском языке."""
        return AppConfig(
            language="ru",
            logging_enabled=False,
            log_file=None,
        )

    @pytest.fixture
    def config_en(self) -> AppConfig:
        """Создаёт конфигурацию на английском языке."""
        return AppConfig(
            language="en",
            logging_enabled=True,
            log_file=Path("/tmp/test.log"),
        )

    def test_translation_ru(self, config_ru: AppConfig) -> None:
        """Русская локализация: корректный перевод."""
        assert config_ru.t("app_title") == "hideMyLute"
        assert config_ru.t("tab_join") == "Соединение"
        assert config_ru.t("tab_split") == "Разделение"
        assert config_ru.t("join_btn") == "Соединить"
        assert config_ru.t("split_btn") == "Разделить"
        assert config_ru.t("status_ready") == "Готов"

    def test_translation_en(self, config_en: AppConfig) -> None:
        """Английская локализация: корректный перевод."""
        assert config_en.t("app_title") == "hideMyLute"
        assert config_en.t("tab_join") == "Join"
        assert config_en.t("tab_split") == "Split"
        assert config_en.t("join_btn") == "Join"
        assert config_en.t("split_btn") == "Split"
        assert config_en.t("status_ready") == "Ready"

    def test_translation_fallback_for_missing_language(
        self,
    ) -> None:
        """Неизвестный язык: fallback на английский."""
        config = AppConfig(
            language="fr",
            logging_enabled=False,
            log_file=None,
        )
        assert config.t("tab_join") == "Join"

    def test_translation_with_formatting(
        self, config_ru: AppConfig
    ) -> None:
        """Форматирование строк с параметрами."""
        msg = config_ru.t(
            "error_file_not_found", path="test.bin"
        )
        assert "test.bin" in msg

    def test_empty_key_returns_key_itself(
        self, config_ru: AppConfig
    ) -> None:
        """Неизвестный ключ: возвращается сам ключ."""
        assert config_ru.t("nonexistent_key") == "nonexistent_key"

    def test_config_is_frozen(self, config_ru: AppConfig) -> None:
        """Frozen dataclass: изменение поля вызывает исключение."""
        with pytest.raises(dataclasses.FrozenInstanceError):
            config_ru.logging_enabled = True  # type: ignore[misc]

    def test_config_fields(self, config_ru: AppConfig) -> None:
        """Проверка значений полей конфигурации."""
        assert config_ru.language == "ru"
        assert config_ru.logging_enabled is False
        assert config_ru.log_file is None


class TestExceptions:
    """Тесты иерархии исключений."""

    def test_hide_my_lute_error_is_base(self) -> None:
        """HideMyLuteError — базовый класс всех исключений."""
        from hideMyLute.exceptions import (
            CryptoError,
            FileOperationError,
            FooterError,
            ValidationError,
        )

        assert issubclass(CryptoError, HideMyLuteError)
        assert issubclass(FooterError, HideMyLuteError)
        assert issubclass(FileOperationError, HideMyLuteError)
        assert issubclass(ValidationError, HideMyLuteError)

    def test_exception_can_be_caught_by_base(self) -> None:
        """Специфичное исключение ловится базовым классом."""
        from hideMyLute.exceptions import CryptoError

        try:
            raise CryptoError("test")
        except HideMyLuteError as exc:
            assert str(exc) == "test"
