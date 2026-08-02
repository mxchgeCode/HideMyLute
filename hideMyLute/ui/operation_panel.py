"""Общий базовый класс панели операции.

Содержит общую логику вкладок «Соединение» и «Разделение»:
- состояние операции (processing / completed / error);
- обработку и перевод ошибок;
- жизненный цикл прогресс-бара и кнопки действия;
- запуск фоновой операции через BackgroundWorker.

Дочерние классы обязаны:
- создать ``self._progress_bar`` (CTkProgressBar, indeterminate) и
  ``self._action_btn`` (CTkButton) в ``_build_ui``;
- реализовать ``refresh_status()``;
- реализовать метод запуска операции, вызывающий ``_run_operation``.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import customtkinter as ctk

from ..config import AppConfig
from ..exceptions import HideMyLuteError
from ..worker import BackgroundWorker


class OperationPanel(ctk.CTkFrame):
    """Панель операции с общим жизненным циклом фоновой работы."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        config: AppConfig,
        worker: BackgroundWorker,
        on_status: Any,
        **kwargs: Any,
    ) -> None:
        """Инициализирует панель.

        Args:
            parent: Родительский виджет.
            config: Конфигурация приложения (DI).
            worker: Фоновый воркер (DI).
            on_status: Callback для строки статуса.
        """
        super().__init__(parent, **kwargs)
        self._config = config
        self._worker = worker
        self._on_status = on_status

        self._completed_path: Path | None = None
        self._error: str | HideMyLuteError | None = None
        self._processing: bool = False

    # --- Общие хелперы ошибок ---

    def _format_error(self, error: str | HideMyLuteError) -> str:
        """Возвращает переведённое сообщение об ошибке целиком."""
        return (
            f"{self._config.t('error_title')}: "
            f"{self._translate_error(error)}"
        )

    def _translate_error(self, error: str | HideMyLuteError) -> str:
        """Возвращает переведённое сообщение об ошибке."""
        if isinstance(error, HideMyLuteError) and error.msg_key:
            return self._config.t(error.msg_key, **error.msg_kwargs)
        return str(error)

    # --- Общие обработчики изменений полей ---

    def _on_file_changed(self, *args: Any) -> None:
        """Сбрасывает состояние завершённой операции при смене файла."""
        self._completed_path = None
        self._error = None
        self.refresh_status()

    def _on_password_changed(self, *args: Any) -> None:
        """Сбрасывает состояние завершённой операции при смене пароля."""
        if getattr(self, "_clearing_passwords", False):
            return
        self._completed_path = None
        self._error = None
        self.refresh_status()

    def _clear_password_fields(self) -> None:
        """Очищает поля пароля после успешной операции.

        Сокращает время жизни секрета в памяти UI (SIG-05). Очистка
        выполняется с подавлением trace-callbacks, чтобы не перезаписать
        статус успешного завершения.
        """
        if getattr(self, "_clearing_passwords", False):
            return
        self._clearing_passwords = True
        try:
            if hasattr(self, "_password"):
                self._password.password_var.set("")
            if hasattr(self, "_confirm_var"):
                self._confirm_var.set("")
            updater = getattr(self, "_update_strength_label", None)
            if updater is not None:
                updater()
        finally:
            self._clearing_passwords = False

    # --- Жизненный цикл фоновой операции ---

    def _begin_processing(self) -> None:
        """Переводит панель в состояние «обработка»."""
        self._processing = True
        self._completed_path = None
        self._error = None
        self._progress_bar.pack(fill="x", padx=10, pady=(0, 5))
        self._progress_bar.start()
        self._on_status(self._config.t("status_processing"))
        if hasattr(self, "_action_btn"):
            self._action_btn.configure(state="disabled")

    def _end_processing(self) -> None:
        """Возвращает панель в исходное состояние по завершении."""
        self._processing = False
        self._progress_bar.stop()
        self._progress_bar.pack_forget()
        if hasattr(self, "_action_btn"):
            self._action_btn.configure(state="normal")

    def _run_operation(
        self,
        target: Any,
        args: tuple[Any, ...],
        on_success: Any,
        on_error: Any,
    ) -> None:
        """Запускает операцию в фоне через воркер.

        Args:
            target: Функция операции (join_files / split_file).
            args: Позиционные аргументы для target.
            on_success: Callback при успехе.
            on_error: Callback при ошибке.
        """
        self._worker.run(
            target=target,
            args=args,
            on_success=on_success,
            on_error=on_error,
            on_finish=self._end_processing,
            root=self.winfo_toplevel(),
        )
