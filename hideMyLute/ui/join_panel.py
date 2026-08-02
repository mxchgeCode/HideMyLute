"""Панель вкладки «Соединение»."""

from __future__ import annotations

from pathlib import Path
from tkinter import messagebox
from typing import Any

import customtkinter as ctk

from ..config import (
    MIN_PASSWORD_LENGTH,
    RECOMMENDED_PASSWORD_LENGTH,
    AppConfig,
)
from ..steganography import generate_output_path, join_files
from ..worker import BackgroundWorker
from .widgets import FileSelector, PasswordField


class JoinPanel(ctk.CTkFrame):
    """Панель для соединения файла-носителя и контейнера."""

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
        """Инициализирует панель соединения.

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

        # Выбор файла-носителя
        self._carrier = FileSelector(
            self,
            label=t("carrier_file"),
            browse_text=t("browse"),
        )
        self._carrier.pack(fill="x", padx=10, pady=(5, 0))

        # Выбор файла-контейнера
        self._container = FileSelector(
            self,
            label=t("container_file"),
            browse_text=t("browse"),
        )
        self._container.pack(fill="x", padx=10)

        # Блок пароля — единая рамка
        self._pwd_frame = ctk.CTkFrame(self)
        self._pwd_frame.pack(fill="x", padx=10, pady=(5, 0))

        # Пароль
        self._password = PasswordField(
            self._pwd_frame,
            label=t("password"),
            trace_callback=self._on_password_changed,
        )
        self._password.pack(fill="x", padx=5)

        # Индикатор силы пароля
        self._strength_label = ctk.CTkLabel(
            self._pwd_frame,
            text="",
            font=ctk.CTkFont(size=11),
            anchor="w",
        )
        self._strength_label.pack(fill="x", padx=5, pady=(0, 2))

        # Подтверждение
        self._confirm_label = ctk.CTkLabel(
            self._pwd_frame,
            text=t("password_confirm"),
            anchor="w",
        )
        self._confirm_label.pack(fill="x", padx=5, pady=(8, 2))

        self._confirm_var = ctk.StringVar()
        self._confirm_entry = ctk.CTkEntry(
            self._pwd_frame,
            textvariable=self._confirm_var,
            show="•",
        )
        self._confirm_entry.pack(
            fill="x", padx=5, pady=(0, 10)
        )

        # Кнопка
        self._join_btn = ctk.CTkButton(
            self,
            text=t("join_btn"),
            height=38,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._on_join,
        )
        self._join_btn.pack(pady=15)

    def _on_password_changed(self, *args: Any) -> None:
        """Обновляет индикатор силы пароля."""
        pwd = self._password.password_var.get()
        length = len(pwd)

        if not length:
            self._strength_label.configure(text="", text_color=None)
            return

        if length < MIN_PASSWORD_LENGTH:
            self._strength_label.configure(
                text=self._config.t("password_strength_weak"),
                text_color="red",
            )
        elif length < RECOMMENDED_PASSWORD_LENGTH:
            self._strength_label.configure(
                text=self._config.t("password_strength_ok"),
                text_color="orange",
            )
        else:
            self._strength_label.configure(
                text=self._config.t("password_strength_strong"),
                text_color="green",
            )

    def _on_join(self) -> None:
        """Обработчик нажатия кнопки «Соединить»."""
        t = self._config.t

        carrier = self._carrier.path_or_none
        container = self._container.path_or_none
        password = self._password.password_var.get()
        confirm = self._confirm_var.get()

        if not carrier:
            self._on_status(t("status_not_ready"))
            messagebox.showerror(
                t("error_title"),
                t("error_file_not_found", path="носитель"),
            )
            return
        if not container:
            self._on_status(t("status_not_ready"))
            messagebox.showerror(
                t("error_title"),
                t("error_file_not_found", path="контейнер"),
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
        if password != confirm:
            self._on_status(t("status_not_ready"))
            messagebox.showerror(
                t("error_title"), t("error_passwords_mismatch")
            )
            return

        output_path = generate_output_path(str(carrier))

        self._join_btn.configure(state="disabled")
        self._progress_show(t("progress_join"))
        self._on_status(t("status_processing"))

        self._worker.run(
            target=join_files,
            args=(str(carrier), str(container), str(output_path), password),
            on_success=self._on_join_success,
            on_error=self._on_join_error,
            on_finish=self._on_join_finish,
            root=self.winfo_toplevel(),
        )

    def _on_join_success(self, result: Path) -> None:
        """Callback при успешном соединении."""
        self._on_status(self._config.t("status_completed_join"))

    def _on_join_error(self, error_msg: str) -> None:
        """Callback при ошибке соединения."""
        messagebox.showerror(self._config.t("error_title"), error_msg)
        self._on_status(self._config.t("status_not_ready"))

    def _on_join_finish(self) -> None:
        """Callback по завершении (всегда)."""
        self._progress_hide()
        self._join_btn.configure(state="normal")
