"""Фоновый воркер для выполнения длительных операций без зависания UI.

Использует threading.Thread для выноса операций соединения/разделения
из основного потока GUI. Результаты и ошибки передаются через callback'и,
выполняемые в основном потоке через root.after().
"""

from __future__ import annotations

import threading
import traceback
from collections.abc import Callable
from typing import Any

from .exceptions import HideMyLuteError


class BackgroundWorker:
    """Выполняет функцию в фоновом потоке с обратными вызовами.

    Attributes:
        _thread: Активный поток (None, если не запущен).
        _cancelled: Флаг отмены операции.
    """

    def __init__(self) -> None:
        """Инициализирует воркер."""
        self._thread: threading.Thread | None = None
        self._cancelled: bool = False

    @property
    def is_running(self) -> bool:
        """True, если операция выполняется в данный момент."""
        return self._thread is not None and self._thread.is_alive()

    def run(
        self,
        target: Callable[..., Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[str], None],
        on_finish: Callable[[], None] | None = None,
        root=None,
        args: tuple[Any, ...] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> None:
        """Запускает операцию в фоновом потоке.

        Args:
            target: Функция для выполнения в фоне.
            on_success: Вызывается в основном потоке при успехе,
                        получает результат target.
            on_error: Вызывается в основном потоке при ошибке,
                      получает строку с сообщением.
            on_finish: Вызывается в основном потоке в любом случае
                       после on_success/on_error.
            root: Корневой виджет tkinter для root.after().
            args: Кортеж позиционных аргументов для target.
            kwargs: Словарь именованных аргументов для target.
        """
        if self.is_running:
            on_error("Операция уже выполняется")
            return

        self._cancelled = False
        _args = args or ()
        _kwargs = kwargs or {}

        def _wrapper() -> None:
            try:
                result = target(*_args, **_kwargs)
                if not self._cancelled and root:
                    root.after(0, on_success, result)
                elif not self._cancelled:
                    on_success(result)
            except HideMyLuteError as exc:
                self._report_error(on_error, str(exc), root)
            except Exception as exc:
                msg = (
                    f"Неожиданная ошибка: {exc}\n\n"
                    f"{traceback.format_exc()}"
                )
                self._report_error(on_error, msg, root)
            finally:
                self._thread = None
                if not self._cancelled and on_finish:
                    if root:
                        root.after(0, on_finish)
                    else:
                        on_finish()

        self._thread = threading.Thread(
            target=_wrapper, daemon=True
        )
        self._thread.start()

    def cancel(self) -> None:
        """Запрашивает отмену текущей операции.

        Операция не прерывается мгновенно — устанавливается флаг,
        который подавляет callback'и по завершении.
        """
        self._cancelled = True

    def _report_error(
        self,
        on_error: Callable[[str], None],
        message: str,
        root=None,
    ) -> None:
        """Сообщает об ошибке через callback в основном потоке."""
        if self._cancelled:
            return
        if root:
            root.after(0, on_error, message)
        else:
            on_error(message)
