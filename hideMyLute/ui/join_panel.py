"""Панель вкладки «Соединение»."""

from __future__ import annotations

from pathlib import Path
from tkinter import messagebox
from typing import Any

import customtkinter as ctk

from ..config import AppConfig
from ..steganography import generate_output_path, join_files
from ..worker import BackgroundWorker
from .widgets import FileSelector, PasswordField


class JoinPanel(ctk.CTkFrame):
    """Панель для соединения файла-носителя и контейнера.

    Содержит поля выбора носителя, контейнера, выходного файла,
    пароль с подтверждением и кнопку «Соединить».
    """

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
        self._carrier.pack(fill="x", padx=10)

        # Выбор файла-контейнера
        self._container = FileSelector(
            self,
            label=t("container_file"),
            browse_text=t("browse"),
        )
        self._container.pack(fill="x", padx=10)

        # Пароль
        self._password = PasswordField(
            self,
            label=t("password"),
        )
        self._password.pack(fill="x", padx=10)

        # Подтверждение пароля
        self._password_confirm_label = ctk.CTkLabel(
            self,
            text=t("password_confirm"),
            anchor="w",
        )
        self._password_confirm_label.pack(
            fill="x", padx=10, pady=(15, 2)
        )

        self._password_confirm_var = ctk.StringVar()
        self._password_confirm_entry = ctk.CTkEntry(
            self,
            textvariable=self._password_confirm_var,
            show="•",
        )
        self._password_confirm_entry.pack(
            fill="x", padx=10, pady=(0, 20)
        )

        # Кнопка соединения
        self._join_btn = ctk.CTkButton(
            self,
            text=t("join_btn"),
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._on_join,
        )
        self._join_btn.pack(pady=20)

    def _on_join(self) -> None:
        """Обработчик нажатия кнопки «Соединить»."""
        t = self._config.t

        carrier = self._carrier.path_or_none
        container = self._container.path_or_none
        password = self._password.password_var.get()
        confirm = self._password_confirm_var.get()

        # Валидация ввода
        if not carrier:
            messagebox.showerror(
                t("error_title"), t("error_file_not_found", path="носитель")
            )
            return
        if not container:
            messagebox.showerror(
                t("error_title"), t("error_file_not_found", path="контейнер")
            )
            return
        if not password:
            messagebox.showerror(
                t("error_title"), "Пароль не может быть пустым"
            )
            return
        if password != confirm:
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
        )

    def _on_join_success(self, result: Path) -> None:
        """Callback при успешном соединении."""
        t = self._config.t
        messagebox.showinfo(
            t("app_title"),
            f"{t('success_join')}\n\n{result}",
        )
        self._on_status(t("status_ready"))

    def _on_join_error(self, error_msg: str) -> None:
        """Callback при ошибке соединения."""
        t = self._config.t
        messagebox.showerror(t("error_title"), error_msg)
        self._on_status(t("status_ready"))

    def _on_join_finish(self) -> None:
        """Callback по завершении (всегда)."""
        self._progress_hide()
        self._join_btn.configure(state="normal")
