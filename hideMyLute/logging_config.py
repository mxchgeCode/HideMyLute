"""Настройка логирования для hideMyLute.

Поддерживает полное отключение логирования (флаг logging_enabled=False)
для исключения любых следов работы программы на диске.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Формат: время, уровень, имя модуля
LOG_FORMAT = (
    "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
)
LOG_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def setup_logging(
    enabled: bool = False,
    log_file: Path | None = None,
    level: int = logging.WARNING,
) -> None:
    """Настраивает логирование приложения.

    При enabled=False никакие сообщения не выводятся ни в консоль,
    ни в файл — для режима «без следов».

    Args:
        enabled: Включить логирование. По умолчанию False.
        log_file: Путь к файлу лога. Если None, используется
                  stdout (только при enabled=True).
        level: Минимальный уровень логирования.
    """
    root_logger = logging.getLogger("hideMyLute")

    if not enabled:
        # Полное отключение — добавляем NullHandler
        root_logger.addHandler(logging.NullHandler())
        root_logger.propagate = False
        return

    root_logger.setLevel(level)
    formatter = logging.Formatter(LOG_FORMAT, LOG_DATE_FORMAT)

    if log_file is not None:
        file_handler = logging.FileHandler(
            str(log_file), encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    else:
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(formatter)
        root_logger.addHandler(stream_handler)

    root_logger.propagate = False


def get_logger(name: str) -> logging.Logger:
    """Возвращает логгер для указанного модуля.

    Args:
        name: Имя логгера (обычно __name__ модуля).

    Returns:
        Настроенный экземпляр logging.Logger.
    """
    return logging.getLogger(f"hideMyLute.{name}")
