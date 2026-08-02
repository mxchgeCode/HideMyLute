"""Конфигурация приложения hideMyLute — frozen dataclass + переводы.

Предоставляет единый иммутабельный объект конфигурации, внедряемый
через конструкторы (Dependency Injection) во все компоненты.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

# Константы, не подлежащие изменению в рантайме
MAGIC_BYTES: bytes = b'HMLF'
"""Сигнатура футера: 4 байта в начале футера для идентификации формата."""

FOOTER_VERSION: int = 1
"""Версия формата футера (для будущей обратной совместимости)."""

FOOTER_HEADER_SIZE: int = 12
"""Размер заголовка футера в байтах: 4 (magic) + 2 (version) + 2 (flags) + 4 (footer_len)."""

PBKDF2_ITERATIONS: int = 600_000
"""Количество итераций PBKDF2-HMAC-SHA256 согласно OWASP 2023."""

PBKDF2_SALT_SIZE: int = 32
"""Размер соли для PBKDF2 в байтах."""

AES_KEY_SIZE: int = 32
"""Размер ключа AES-256 в байтах."""

AES_NONCE_SIZE: int = 12
"""Размер nonce для AES-256-GCM (рекомендация NIST: 96 бит)."""

CHUNK_SIZE: int = 1024 * 1024
"""Размер буфера для потокового копирования файлов (1 МБ)."""


# Словари переводов UI
TRANSLATIONS: dict[str, dict[str, str]] = {
    "ru": {
        "app_title": "hideMyLute",
        "tab_join": "Соединение",
        "tab_split": "Разделение",
        "carrier_file": "Файл-носитель:",
        "container_file": "Файл-контейнер:",
        "combined_file": "Собранный файл:",
        "output_file": "Выходной файл:",
        "password": "Пароль:",
        "password_confirm": "Подтверждение:",
        "browse": "Обзор...",
        "join_btn": "Соединить",
        "split_btn": "Разделить",
        "progress_join": "Соединение...",
        "progress_split": "Разделение...",
        "success_join": "Файлы успешно соединены.",
        "success_split": "Контейнер успешно извлечён.",
        "error_title": "Ошибка",
        "error_wrong_password": "Неверный пароль или файл повреждён.",
        "error_no_footer": "В файле не найден футер hideMyLute.",
        "error_passwords_mismatch": "Пароли не совпадают.",
        "error_file_not_found": "Файл не найден: {path}",
        "error_empty_path": "Путь к файлу не может быть пустым.",
        "carrier_original_size": "Исходный размер носителя:",
        "container_size": "Размер контейнера:",
        "status_ready": "Готов",
        "status_processing": "Обработка...",
    },
    "en": {
        "app_title": "hideMyLute",
        "tab_join": "Join",
        "tab_split": "Split",
        "carrier_file": "Carrier file:",
        "container_file": "Container file:",
        "combined_file": "Combined file:",
        "output_file": "Output file:",
        "password": "Password:",
        "password_confirm": "Confirmation:",
        "browse": "Browse...",
        "join_btn": "Join",
        "split_btn": "Split",
        "progress_join": "Joining...",
        "progress_split": "Splitting...",
        "success_join": "Files joined successfully.",
        "success_split": "Container extracted successfully.",
        "error_title": "Error",
        "error_wrong_password": (
            "Wrong password or file is corrupted."
        ),
        "error_no_footer": "hideMyLute footer not found in file.",
        "error_passwords_mismatch": "Passwords do not match.",
        "error_file_not_found": "File not found: {path}",
        "error_empty_path": "File path cannot be empty.",
        "carrier_original_size": "Original carrier size:",
        "container_size": "Container size:",
        "status_ready": "Ready",
        "status_processing": "Processing...",
    },
}


@dataclass(frozen=True)
class AppConfig:
    """Иммутабельная конфигурация приложения.

    Внедряется через конструкторы компонентов (Dependency Injection).
    Все поля обязательны — конфигурация создаётся один раз при старте.

    Attributes:
        language: Код языка интерфейса ('ru' или 'en').
        logging_enabled: Включить логирование в файл.
        log_file: Путь к файлу лога (если logging_enabled True).
    """

    language: str
    logging_enabled: bool
    log_file: Path | None

    # Переводы на лету не меняются — это константы класса
    _TRANSLATIONS: ClassVar[dict[str, dict[str, str]]] = TRANSLATIONS

    def t(self, key: str, **kwargs: str) -> str:
        """Возвращает переведённую строку по ключу.

        Args:
            key: Ключ строки в словаре переводов.
            **kwargs: Параметры для форматирования строки.

        Returns:
            Переведённая строка с подставленными параметрами.
        """
        lang_dict = self._TRANSLATIONS.get(
            self.language,
            self._TRANSLATIONS["en"],
        )
        template = lang_dict.get(key, key)
        if kwargs:
            return template.format(**kwargs)
        return template
