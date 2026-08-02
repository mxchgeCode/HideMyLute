"""Панель вкладки «Разделение»."""

from __future__ import annotations

from pathlib import Path
from tkinter import messagebox
from typing import Any

import customtkinter as ctk

from ..config import MIN_PASSWORD_LENGTH, AppConfig
from ..steganography import split_file
from ..worker import BackgroundWorker
from .widgets import FileSelector, PasswordField


class SplitPanel(ctk.CTkFrame):
    """Панель для разделения собранного файла на носитель и контейнер."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        config: AppConfig,
        worker: BackgroundWorker,
        on_status: Any,
        progress_show: Any,
        progress_hide: Any,
        **kwargs: Any,
    ) -> None:
        """Инициализирует панель разделения.

        Args:
            parent: Родительский виджет.
            config: Конфигурация приложения (DI).
            worker: Фоновый воркер (DI).
            on_status: Callback для строки статуса.
            progress_show: Callback показа прогресс-оверлея.
            progress_hide: Callback скрытия прогресс-оверлея.
        """
        super().__init__(parent, **kwargs)
        self._config = config
        self._worker = worker
        self._on_status = on_status
        self._progress_show = progress_show
        self._progress_hide = progress_hide

        self._build_ui()

    def _build_ui(self) -> None:
        """Строит интерфейс панели."""
        t = self._config.t

        # Выбор собранного файла
        self._combined = FileSelector(
            self,
            label=t("combined_file"),
            browse_text=t("browse"),
        )
        self._combined.pack(fill="x", padx=10, pady=(5, 0))

        # Пароль
        self._password = PasswordField(
            self,
            label=t("password"),
        )
        self._password.pack(fill="x", padx=10)

        # Кнопка разделения
        self._split_btn = ctk.CTkButton(
            self,
            text=t("split_btn"),
            height=38,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._on_split,
        )
        self._split_btn.pack(pady=15)

    def _on_split(self) -> None:
        """Обработчик нажатия кнопки «Разделить»."""
        t = self._config.t

        combined = self._combined.path_or_none
        password = self._password.password_var.get()

        if not combined:
            self._on_status(t("status_not_ready"))
            messagebox.showerror(
                t("error_title"),
                t("error_file_not_found", path="собранный файл"),
            )
            return
        if not password:
            self._on_status(t("status_not_ready"))
            messagebox.showerror(
                t("error_title"), t("error_password_empty")
            )
            return
        if len(password) < MIN_PASSWORD_LENGTH:
            self._on_status(t("status_not_ready"))
            messagebox.showerror(
                t("error_title"), t("error_password_short")
            )
            return

        output_dir = combined.parent

        self._split_btn.configure(state="disabled")
        self._progress_show(t("progress_split"))
        self._on_status(t("status_processing"))

        self._worker.run(
            target=split_file,
            args=(str(combined), str(output_dir), password),
            on_success=self._on_split_success,
            on_error=self._on_split_error,
            on_finish=self._on_split_finish,
            root=self.winfo_toplevel(),
        )

    def _on_split_success(self, result: tuple[Path, dict]) -> None:
        """Callback при успешном разделении."""
        del result  # метаданные не отображаются в UI
        self._on_status(self._config.t("status_completed_split"))

    def _on_split_error(self, error_msg: str) -> None:
        """Callback при ошибке разделения."""
        messagebox.showerror(self._config.t("error_title"), error_msg)
        self._on_status(self._config.t("status_not_ready"))

    def _on_split_finish(self) -> None:
        """Callback по завершении (всегда)."""
        self._progress_hide()
        self._split_btn.configure(state="normal")
