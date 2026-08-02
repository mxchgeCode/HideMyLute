"""Фоновый воркер для выполнения длительных операций без зависания UI.

Использует threading.Thread для выноса операций соединения/разделения
из основного потока GUI.

Потокобезопасность:
- состояние воркера защищено threading.Lock;
- каждая операция получает уникальный токен; при завершении токен
  сверяется с текущим, что исключает затирание ссылки на более новый
  поток (гонка между завершением старой и стартом новой операции);
- отмена реализована через threading.Event, передаваемый целевой
  функции в kwargs (параметр ``cancel_event``), что позволяет длительным
  операциям прерваться и выполнить очистку частичных файлов.

Доставка callbacks в главный поток:
- фоновый поток НИКОГДА не вызывает Tk-методы (в Python 3.14
  ``root.after`` из неглавного потока поднимает RuntimeError);
- вместо этого события кладутся в queue.Queue, а главный поток
  опрашивает очередь через периодический root.after()-поллер;
- при root=None callbacks вызываются непосредственно из фонового потока
  (для CLI/тестов).
"""

from __future__ import annotations

import inspect
import queue
import threading
import traceback
from collections.abc import Callable
from typing import Any

from .exceptions import HideMyLuteError
from .logging_config import get_logger

logger = get_logger("worker")

_POLL_INTERVAL_MS = 50


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
        _queue: Очередь событий (success/error/finish) для главного потока.
        _callbacks: Callback'и текущей операции (on_success/on_error/on_finish).
    """

    def __init__(self) -> None:
        """Инициализирует воркер."""
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._token: int = 0
        self._cancel_event = threading.Event()
        self._queue: queue.Queue = queue.Queue()
        self._callbacks: tuple[Any, Any, Any] = (None, None, None)

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
            on_success: Вызывается при успехе, получает результат target.
            on_error: Вызывается при ошибке, получает HideMyLuteError
                      (с msg_key) или str.
            on_finish: Вызывается в любом случае после on_success/on_error.
            root: Корневой виджет tkinter (необязательно). Если задан,
                  callbacks доставляются через очередь и опрашиваются
                  главным потоком.
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
            self._queue = queue.Queue()
            self._use_queue = root is not None
            self._callbacks = (on_success, on_error, on_finish)
            _args = args or ()
            _kwargs = dict(kwargs or {})
            if _accepts_cancel_event(target):
                _kwargs.setdefault("cancel_event", self._cancel_event)
            self._thread = threading.Thread(
                target=self._wrapper,
                daemon=True,
                args=(token, target, _args, _kwargs),
            )

        if root is not None:
            # Поллер запускается из главного потока (run вызывается из UI)
            root.after(_POLL_INTERVAL_MS, self._poll, root)
        self._thread.start()

    def _wrapper(
        self,
        token: int,
        target: Callable[..., Any],
        args: tuple[Any, ...],
        kwargs: dict[str, Any],
    ) -> None:
        """Выполняет target и кладёт события в очередь (или вызывает напрямую)."""
        try:
            result = target(*args, **kwargs)
            if not self._cancel_event.is_set():
                self._emit("success", result)
        except HideMyLuteError as exc:
            logger.error("operation error: %s", exc.msg_key or type(exc).__name__)
            if not self._cancel_event.is_set():
                self._emit("error", exc)
        except Exception as exc:
            logger.exception("unexpected operation error")
            if not self._cancel_event.is_set():
                msg = (
                    f"Неожиданная ошибка: {exc}\n\n"
                    f"{traceback.format_exc()}"
                )
                self._emit("error", msg)
        finally:
            # finish ставится в очередь ДО обнуления _thread, иначе поллер
            # может остановиться раньше времени и потерять событие
            if not self._cancel_event.is_set():
                self._emit("finish", None)
            with self._lock:
                # Сбрасываем поток только для текущей операции
                if self._token == token:
                    self._thread = None

    def _emit(self, kind: str, payload: Any) -> None:
        """Помещает событие в очередь или вызывает callback напрямую."""
        on_success, on_error, on_finish = self._callbacks
        if self._use_queue:
            self._queue.put((kind, payload))
            return
        # root=None: прямой вызов (CLI/тесты)
        if kind == "success" and on_success is not None:
            on_success(payload)
        elif kind == "error" and on_error is not None:
            on_error(payload)
        elif kind == "finish" and on_finish is not None:
            on_finish()

    def _poll(self, root) -> None:
        """Опрашивает очередь событий и диспетчеризует callbacks.

        Вызывается главным потоком через root.after; перепланирует себя,
        пока операция не завершится и очередь не опустеет.
        """
        try:
            while True:
                kind, payload = self._queue.get_nowait()
                on_success, on_error, on_finish = self._callbacks
                if kind == "success" and on_success is not None:
                    on_success(payload)
                elif kind == "error" and on_error is not None:
                    on_error(payload)
                elif kind == "finish" and on_finish is not None:
                    on_finish()
        except queue.Empty:
            pass

        # Продолжаем опрос, пока операция активна или остались события
        if self._thread is not None or not self._queue.empty():
            root.after(_POLL_INTERVAL_MS, self._poll, root)

    def cancel(self) -> None:
        """Запрашивает отмену текущей операции.

        Устанавливает событие отмены, которое проверяется длительной
        операцией; callbacks по завершении подавляются.
        """
        self._cancel_event.set()
