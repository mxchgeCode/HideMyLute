"""Пользовательские исключения для hideMyLute."""

from __future__ import annotations

from typing import Any


class HideMyLuteError(Exception):
    """Базовое исключение приложения.

    Attributes:
        msg_key: Ключ для перевода сообщения через AppConfig.t().
        msg_kwargs: Аргументы для форматирования перевода.
    """

    def __init__(
        self,
        message: str = "",
        msg_key: str | None = None,
        **msg_kwargs: Any,
    ) -> None:
        super().__init__(message)
        self.msg_key = msg_key
        self.msg_kwargs = msg_kwargs


class CryptoError(HideMyLuteError):
    """Ошибка криптографических операций: шифрование/дешифрование.

    Возникает при неверном пароле, повреждении данных,
    неверном формате зашифрованного блока.
    """


class FooterError(HideMyLuteError):
    """Ошибка чтения/записи/валидации футера.

    Возникает при отсутствии футера, неверной сигнатуре magic bytes,
    несовпадении версии формата, битом футере.
    """


class FileOperationError(HideMyLuteError):
    """Ошибка файловых операций.

    Возникает при невозможности открыть/прочитать/записать/удалить файл,
    недостаточности прав, нехватке дискового пространства.
    """


class ValidationError(HideMyLuteError):
    """Ошибка валидации входных параметров.

    Возникает при пустых путях, несуществующих файлах,
    недопустимых значениях конфигурации.
    """