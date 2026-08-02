"""Конфигурация приложения hideMyLute — dataclass + переводы.

Предоставляет единый конфигурационный объект, внедряемый
через конструкторы (Dependency Injection) во все компоненты.
Язык может быть изменён в рантайме через set_language().
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar

# Константы, не подлежащие изменению в рантайме
MAGIC_BYTES: bytes = b'HMLF'
"""Сигнатура футера: 4 байта в начале футера для идентификации формата."""

FOOTER_VERSION: int = 2
"""Версия формата футера (для будущей обратной совместимости).

v2 (текущая): magic-поле заголовка — случайные байты (не содержит
детектируемой сигнатуры), метаданные включают ``container_hash_sha256``
и ``container_name``, отсутствует ``timestamp``.
"""

FOOTER_VERSION_V1: int = 1
"""Версия формата футера v1 (legacy): фиксированный magic b'HMLF'."""

FOOTER_HEADER_SIZE: int = 12
"""Размер заголовка футера в байтах:
4 (magic/случайные байты) + 2 (version) + 2 (flags) + 4 (footer_len)."""

MIN_FOOTER_PAYLOAD_LEN: int = 60
"""Минимальный размер payload футера: salt(32) + nonce(12) + GCM tag(16).

Используется для отбраковки случайных файлов при поиске футера.
"""

MAX_FOOTER_PAYLOAD_LEN: int = 1024 * 1024
"""Максимальный размер payload футера (1 МБ).

Защита от чтения гигантских нерелевантных блоков из случайного файла.
"""

PBKDF2_ITERATIONS: int = 600_000
"""Количество итераций PBKDF2-HMAC-SHA256 согласно OWASP 2023."""

PBKDF2_SALT_SIZE: int = 32
"""Размер соли для PBKDF2 в байтах."""

AES_KEY_SIZE: int = 32
"""Размер ключа AES-256 в байтах."""

AES_NONCE_SIZE: int = 12
"""Размер nonce для AES-256-GCM (рекомендация NIST: 96 бит)."""

AES_GCM_TAG_SIZE: int = 16
"""Размер тега аутентификации AES-GCM в байтах."""

CHUNK_SIZE: int = 1024 * 1024
"""Размер буфера для потокового копирования файлов (1 МБ)."""

# Минимальная и рекомендуемая длина пароля.
# Безопасность инструмента целиком держится на пароле: минимум 12
# символов (OWASP) блокирует слабые пароли на уровне операции.
MIN_PASSWORD_LENGTH: int = 12
"""Минимальная длина пароля, при которой разрешена операция."""

MAX_PASSWORD_LENGTH: int = 1024
"""Максимальная длина пароля.

Защита от DoS через PBKDF2 на гигантских входных данных.
"""

RECOMMENDED_PASSWORD_LENGTH: int = 14

# Словари переводов UI
TRANSLATIONS: dict[str, dict[str, str]] = {
    "ru": {
        "app_title": "hideMyLute",
        "tab_join": "Соединение",
        "tab_split": "Разделение",
        "carrier_file": "Файл-носитель:",
        "container_file": "Файл-контейнер:",
        "combined_file": "Собранный файл:",
        "password": "Пароль:",
        "password_confirm": "Подтверждение:",
        "browse": "Обзор...",
        "join_btn": "Соединить",
        "split_btn": "Разделить",
        "progress_join": "Соединение...",
        "progress_split": "Разделение...",
        "error_title": "Ошибка",
        "error_wrong_password": "Неверный пароль или файл повреждён.",
        "error_no_footer": "В файле не найден футер hideMyLute.",
        "error_passwords_mismatch": "Пароли не совпадают.",
        "error_file_not_found": "Файл не найден: {path}",
        "error_carrier_not_found": "Файл-носитель не найден: {path}",
        "error_container_not_found": "Файл-контейнер не найден: {path}",
        "error_same_file": "Файл-носитель и контейнер не могут быть одним файлом.",
        "error_output_exists": "Выходной файл уже существует: {path}",
        "error_join_failed": "Ошибка при соединении файлов: {error}",
        "error_extract_failed": "Ошибка при извлечении контейнера: {error}",
        "error_copy_failed": "Ошибка копирования {src} → {dst}: {error}",
        "error_append_failed": "Ошибка дописывания {src} → {dst}: {error}",
        "error_size_mismatch": (
            "Размер файла ({size}) не соответствует ожидаемому ({expected}). "
            "Файл мог быть изменён."
        ),
        "error_hash_mismatch": (
            "Хеш носителя не совпадает. Файл-носитель был изменён после сборки."
        ),
        "error_container_hash_mismatch": (
            "Хеш контейнера не совпадает. Контейнер был изменён после сборки."
        ),
        "error_password_too_long": (
            "Пароль слишком длинный (максимум {max_len} символов)."
        ),
        "error_operation_cancelled": "Операция отменена.",
        "error_footer_too_small": "Файл слишком мал для содержания футера.",
        "error_footer_version": (
            "Несовместимая версия футера: {version} (ожидается {expected})."
        ),
        "error_footer_too_large": (
            "Заявленный размер футера превышает размер файла."
        ),
        "error_footer_parse": "Не удалось распарсить метаданные футера.",
        "error_footer_fields": (
            "В метаданных футера отсутствуют поля: {fields}"
        ),
        "error_empty_path": "Путь к файлу не может быть пустым.",
        "error_password_empty": "Пароль не может быть пустым.",
        "error_password_short": (
            "Пароль должен быть не менее 4 символов."
        ),
        "password_strength_weak": "Слабый",
        "password_strength_ok": "Приемлемый",
        "password_strength_strong": "Надёжный",
        "status_ready_join": "Готов к соединению",
        "status_ready_split": "Готов к разделению",
        "status_not_ready": "Заполните все поля",
        "status_processing": "Обработка...",
        "status_completed_join": "Готово: файл сохранён",
        "status_completed_split": "Готово: контейнер извлечён",
        "password_mismatch": "Пароли не совпадают",
        "language_label": "Язык:",
    },
    "en": {
        "app_title": "hideMyLute",
        "tab_join": "Join",
        "tab_split": "Split",
        "carrier_file": "Carrier file:",
        "container_file": "Container file:",
        "combined_file": "Combined file:",
        "password": "Password:",
        "password_confirm": "Confirmation:",
        "browse": "Browse...",
        "join_btn": "Join",
        "split_btn": "Split",
        "progress_join": "Joining...",
        "progress_split": "Splitting...",
        "error_title": "Error",
        "error_wrong_password": (
            "Wrong password or file is corrupted."
        ),
        "error_no_footer": "hideMyLute footer not found in file.",
        "error_passwords_mismatch": "Passwords do not match.",
        "error_file_not_found": "File not found: {path}",
        "error_carrier_not_found": "Carrier file not found: {path}",
        "error_container_not_found": "Container file not found: {path}",
        "error_same_file": "Carrier and container cannot be the same file.",
        "error_output_exists": "Output file already exists: {path}",
        "error_join_failed": "Error while joining files: {error}",
        "error_extract_failed": "Error while extracting container: {error}",
        "error_copy_failed": "Error copying {src} → {dst}: {error}",
        "error_append_failed": "Error appending {src} → {dst}: {error}",
        "error_size_mismatch": (
            "File size ({size}) does not match expected ({expected}). "
            "The file may have been modified."
        ),
        "error_hash_mismatch": (
            "Carrier hash mismatch. The carrier file was modified after assembly."
        ),
        "error_container_hash_mismatch": (
            "Container hash mismatch. The container was modified after assembly."
        ),
        "error_password_too_long": (
            "Password is too long (maximum {max_len} characters)."
        ),
        "error_operation_cancelled": "Operation cancelled.",
        "error_footer_too_small": "File is too small to contain a footer.",
        "error_footer_version": (
            "Incompatible footer version: {version} (expected {expected})."
        ),
        "error_footer_too_large": "Declared footer size exceeds file size.",
        "error_footer_parse": "Failed to parse footer metadata.",
        "error_footer_fields": "Footer metadata is missing fields: {fields}",
        "error_empty_path": "File path cannot be empty.",
        "error_password_empty": "Password cannot be empty.",
        "error_password_short": (
            "Password must be at least 4 characters."
        ),
        "password_strength_weak": "Weak",
        "password_strength_ok": "Acceptable",
        "password_strength_strong": "Strong",
        "status_ready_join": "Ready to join",
        "status_ready_split": "Ready to split",
        "status_not_ready": "Fill all fields",
        "status_processing": "Processing...",
        "status_completed_join": "Done: file saved",
        "status_completed_split": "Done: container extracted",
        "password_mismatch": "Passwords do not match",
        "language_label": "Language:",
    },
}


@dataclass
class AppConfig:
    """Конфигурация приложения.

    Внедряется через конструкторы компонентов (Dependency Injection).
    Все поля имеют разумные умолчания для production-запуска,
    но могут быть переопределены при создании.
    Язык может быть изменён в рантайме через set_language().

    Attributes:
        language: Код языка интерфейса ('ru' или 'en').
        logging_enabled: Включить логирование в файл.
        log_file: Путь к файлу лога (если logging_enabled True).
    """

    language: str = "ru"
    logging_enabled: bool = False
    log_file: Path | None = None

    # Переводы на лету не меняются — это константы класса
    _TRANSLATIONS: ClassVar[dict[str, dict[str, str]]] = TRANSLATIONS

    def set_language(self, language: str) -> None:
        """Устанавливает язык интерфейса.

        Args:
            language: Код языка ('ru' или 'en').
        """
        object.__setattr__(self, "language", language)

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
