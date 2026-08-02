"""Тесты настройки логирования (logging_config)."""

from __future__ import annotations

import logging
import tempfile
from pathlib import Path

from hideMyLute.config import AppConfig
from hideMyLute.logging_config import setup_logging


class TestSetupLogging:
    """Тесты функции setup_logging."""

    def _logger_handlers(self):
        return logging.getLogger("hideMyLute").handlers

    def test_disabled_uses_null_handler(self) -> None:
        """При enabled=False логгер не пишет (только NullHandler)."""
        setup_logging(enabled=False)
        logger = logging.getLogger("hideMyLute")
        assert all(
            isinstance(h, logging.NullHandler) for h in logger.handlers
        )
        assert logger.propagate is False

    def test_disabled_default_config(self) -> None:
        """AppConfig по умолчанию (logging_enabled=False) не логирует.

        Регрессионный тест CRT-01: ранее объект AppConfig передавался
        как аргумент enabled и логирование включалось.
        """
        config = AppConfig()  # logging_enabled=False, log_file=None
        setup_logging(
            enabled=config.logging_enabled,
            log_file=config.log_file,
        )
        logger = logging.getLogger("hideMyLute")
        assert all(
            isinstance(h, logging.NullHandler) for h in logger.handlers
        )

    def test_enabled_with_file_writes_to_file(self) -> None:
        """При enabled=True и log_file записи попадают в файл."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".log"
        ) as fh:
            log_path = Path(fh.name)
        log_path.unlink(missing_ok=True)

        try:
            setup_logging(
                enabled=True,
                log_file=log_path,
                level=logging.INFO,
            )
            logger = logging.getLogger("hideMyLute.test_file")
            logger.info("hello from test")
            for handler in logging.getLogger("hideMyLute").handlers:
                handler.flush()

            assert log_path.exists()
            content = log_path.read_text(encoding="utf-8")
            assert "hello from test" in content
        finally:
            # Закрываем FileHandler (setup_logging сбрасывает хэндлеры),
            # иначе Windows не даст удалить открытый файл
            setup_logging(enabled=False)
            log_path.unlink(missing_ok=True)

    def test_enabled_without_file_uses_stream_handler(self) -> None:
        """Без log_file создаётся StreamHandler."""
        setup_logging(enabled=True, log_file=None)
        logger = logging.getLogger("hideMyLute")
        assert any(
            isinstance(h, logging.StreamHandler)
            and not isinstance(h, logging.NullHandler)
            for h in logger.handlers
        )

    def test_repeated_calls_do_not_accumulate_handlers(self) -> None:
        """Повторные вызовы setup_logging не дублируют хэндлеры."""
        setup_logging(enabled=True, log_file=None)
        count_after_first = len(
            logging.getLogger("hideMyLute").handlers
        )
        setup_logging(enabled=True, log_file=None)
        count_after_second = len(
            logging.getLogger("hideMyLute").handlers
        )
        assert count_after_second == count_after_first

    def test_switch_from_enabled_to_disabled(self) -> None:
        """Переключение enabled→disabled убирает рабочие хэндлеры."""
        setup_logging(enabled=True, log_file=None)
        setup_logging(enabled=False)
        logger = logging.getLogger("hideMyLute")
        assert all(
            isinstance(h, logging.NullHandler) for h in logger.handlers
        )
