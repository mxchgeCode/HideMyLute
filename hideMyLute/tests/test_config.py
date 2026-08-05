"""Тесты модуля конфигурации."""

from __future__ import annotations

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
        assert config_ru.t("status_ready_join") == "Готов к соединению"

    def test_translation_en(self, config_en: AppConfig) -> None:
        """Английская локализация: корректный перевод."""
        assert config_en.t("app_title") == "hideMyLute"
        assert config_en.t("tab_join") == "Join"
        assert config_en.t("tab_split") == "Split"
        assert config_en.t("join_btn") == "Join"
        assert config_en.t("split_btn") == "Split"
        assert config_en.t("status_ready_join") == "Ready to join"

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

    def test_set_language(self, config_ru: AppConfig) -> None:
        """set_language() меняет язык и переводы обновляются."""
        config_ru.set_language("en")
        assert config_ru.language == "en"
        assert config_ru.t("tab_join") == "Join"
        assert config_ru.t("status_ready_join") == "Ready to join"

        config_ru.set_language("ru")
        assert config_ru.language == "ru"
        assert config_ru.t("tab_join") == "Соединение"

    def test_config_fields(self, config_ru: AppConfig) -> None:
        """Проверка значений полей конфигурации."""
        assert config_ru.language == "ru"
        assert config_ru.logging_enabled is False
        assert config_ru.log_file is None

    def test_appconfig_is_frozen(self) -> None:
        """AppConfig — frozen dataclass: прямое присваивание запрещено.

        Язык меняется только через set_language() (object.__setattr__).
        """
        from dataclasses import FrozenInstanceError

        config = AppConfig()
        with pytest.raises(FrozenInstanceError):
            # noinspection PySetattr
            config.language = "en"

    def test_translations_class_used(self) -> None:
        """AppConfig.t() делегирует в Translations."""
        from hideMyLute.config import Translations

        config = AppConfig(language="ru")
        tr = config.translations
        assert isinstance(tr, Translations)
        assert tr.t("join_btn") == "Соединить"

    def test_ru_en_translation_keys_are_identical(self) -> None:
        """Наборы ключей переводов ru и en совпадают (MIN-07)."""
        from hideMyLute.config import TRANSLATIONS

        ru_keys = set(TRANSLATIONS["ru"].keys())
        en_keys = set(TRANSLATIONS["en"].keys())
        assert ru_keys == en_keys

    def test_msg_keys_referenced_by_exceptions_exist(self) -> None:
        """Все msg_key, используемые исключениями, есть в переводах."""
        from hideMyLute.config import TRANSLATIONS

        keys = set(TRANSLATIONS["ru"].keys())

        assert "error_password_empty" in keys
        assert "error_password_short" in keys
        assert "error_password_too_long" in keys
        assert "error_salt_size" in keys
        assert "error_key_size" in keys
        assert "error_data_too_short" in keys
        assert "error_derive_failed" in keys
        assert "error_encrypt_failed" in keys
        assert "error_wrong_password" in keys
        assert "error_container_hash_mismatch" in keys
        assert "error_operation_cancelled" in keys
        # И все ошибки футера/файлов
        for key in (
            "error_file_not_found",
            "error_carrier_not_found",
            "error_container_not_found",
            "error_same_file",
            "error_output_exists",
            "error_join_failed",
            "error_extract_failed",
            "error_copy_failed",
            "error_append_failed",
            "error_size_mismatch",
            "error_hash_mismatch",
            "error_footer_too_small",
            "error_footer_version",
            "error_footer_too_large",
            "error_footer_parse",
            "error_footer_fields",
            "error_empty_path",
            "error_no_footer",
        ):
            assert key in keys, f"missing translation key: {key}"


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
