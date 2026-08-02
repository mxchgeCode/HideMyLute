"""Фоновый воркер для выполнения длительных операций без зависания UI.

Использует threading.Thread для выноса операций соединения/разделения
из основного потока GUI. Результаты и ошибки передаются через callback'и,
выполняемые в основном потоке через root.after().

Потокобезопасность:
- состояние воркера защищено threading.Lock;
- каждая операция получает уникальный токен; при завершении токен
  сверяется с текущим, что исключает затирание ссылки на более новый
  поток (гонка между завершением старой и стартом новой операции);
- отмена реализована через threading.Event, передаваемый целевой
  функции в kwargs (параметр ``cancel_event``), что позволяет длительным
  операциям прерваться и выполнить очистку частичных файлов.
"""

from __future__ import annotations

import inspect
import threading
import traceback
from collections.abc import Callable
from typing import Any

from .exceptions import HideMyLuteError


def _accepts_cancel_event(target: Callable[..., Any]) -> bool:
    """True, если целевая функция принимает kwarg ``cancel_event``.

    Позволяет внедрять событие отмены только в функции, которые
    объявили его параметром (или **kwargs) — остальные вызываются
    без изменений.
    """
    try:
        signature = inspect.signature(target)
    except (TypeError, ValueError):
        return True
    for param in signature.parameters.values():
        if param.kind == inspect.Parameter.VAR_KEYWORD:
            return True
    return "cancel_event" in signature.parameters


class BackgroundWorker:
    """Выполняет функцию в фоновом потоке с обратными вызовами.

    Attributes:
        _thread: Активный поток (None, если не запущен).
        _lock: Защищает состояние воркера.
        _token: Номер текущей операции (для защиты от гонок).
        _cancel_event: Событие отмены текущей операции.
    """

    def __init__(self) -> None:
        """Инициализирует воркер."""
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._token: int = 0
        self._cancel_event = threading.Event()

    @property
    def is_running(self) -> bool:
        """True, если операция выполняется в данный момент."""
        with self._lock:
            return self._thread is not None and self._thread.is_alive()

    def run(
        self,
        target: Callable[..., Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[Any], None],
        on_finish: Callable[[], None] | None = None,
        root=None,
        args: tuple[Any, ...] | None = None,
        kwargs: dict[str, Any] | None = None,
    ) -> None:
        """Запускает операцию в фоновом потоке.

        Args:
            target: Функция для выполнения в фоне. Может принимать
                    необязательный kwarg ``cancel_event``.
            on_success: Вызывается в основном потоке при успехе,
                        получает результат target.
            on_error: Вызывается в основном потоке при ошибке,
                      получает HideMyLuteError (с msg_key) или str.
            on_finish: Вызывается в основном потоке в любом случае
                       после on_success/on_error.
            root: Корневой виджет tkinter для root.after().
            args: Кортеж позиционных аргументов для target.
            kwargs: Словарь именованных аргументов для target.
        """
        if self.is_running:
            on_error("Операция уже выполняется")
            return

        with self._lock:
            self._token += 1
            token = self._token
            self._cancel_event.clear()
            _args = args or ()
            _kwargs = dict(kwargs or {})
            if _accepts_cancel_event(target):
                _kwargs.setdefault("cancel_event", self._cancel_event)
            self._thread = threading.Thread(
                target=self._wrapper,
                daemon=True,
                args=(
                    token,
                    target,
                    _args,
                    _kwargs,
                    on_success,
                    on_error,
                    on_finish,
                    root,
                ),
            )
        self._thread.start()

    def _wrapper(
        self,
        token: int,
        target: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
        on_success: Callable[[Any], None],
        on_error: Callable[[Any], None],
        on_finish: Callable[[], None] | None,
        root,
    ) -> None:
        """Выполняет target и диспетчеризует callbacks."""
        try:
            result = target(*args, **kwargs)
            if not self._cancel_event.is_set() and root:
                root.after(0, on_success, result)
            elif not self._cancel_event.is_set():
                on_success(result)
        except HideMyLuteError as exc:
            self._report_error(on_error, exc, root)
        except Exception as exc:
            msg = (
                f"Неожиданная ошибка: {exc}\n\n"
                f"{traceback.format_exc()}"
            )
            self._report_error(on_error, msg, root)
        finally:
            with self._lock:
                # Сбрасываем поток только для текущей операции
                if self._token == token:
                    self._thread = None
            if not self._cancel_event.is_set() and on_finish:
                if root:
                    root.after(0, on_finish)
                else:
                    on_finish()

    def cancel(self) -> None:
        """Запрашивает отмену текущей операции.

        Устанавливает событие отмены, которое проверяется длительной
        операцией; callbacks по завершении подавляются.
        """
        self._cancel_event.set()

    def _report_error(
        self,
        on_error: Callable[[Any], None],
        message: Any,
        root=None,
    ) -> None:
        """Сообщает об ошибке через callback в основном потоке."""
        if self._cancel_event.is_set():
            return
        if root:
            root.after(0, on_error, message)
        else:
            on_error(message)
