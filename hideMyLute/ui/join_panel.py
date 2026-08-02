"""Панель вкладки «Соединение»."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import customtkinter as ctk

from ..config import (
    MIN_PASSWORD_LENGTH,
    RECOMMENDED_PASSWORD_LENGTH,
    AppConfig,
)
from ..exceptions import HideMyLuteError
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

        # Пароль
        self._password = PasswordField(
            self,
            label=t("password"),
            trace_callback=self._on_password_changed,
        )
        self._password.pack(fill="x", padx=10)

        # Индикатор силы пароля
        self._strength_label = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=11),
            anchor="w",
        )
        self._strength_label.pack(fill="x", padx=10, pady=(0, 2))

        # Подтверждение пароля
        self._confirm_label = ctk.CTkLabel(
            self,
            text=t("password_confirm"),
            anchor="w",
        )
        self._confirm_label.pack(fill="x", padx=10, pady=(5, 2))

        self._confirm_var = ctk.StringVar()
        self._confirm_var.trace_add("write", self._on_confirm_changed)
        self._confirm_entry = ctk.CTkEntry(
            self,
            textvariable=self._confirm_var,
            show="\u2022",
        )
        self._confirm_entry.pack(fill="x", padx=10, pady=(0, 5))

        # Кнопка «Соединить»
        self._join_btn = ctk.CTkButton(
            self,
            text=t("join_btn"),
            height=38,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._on_join,
        )
        self._join_btn.pack(pady=15)

    def update_language(self) -> None:
        """Обновляет тексты всех виджетов при смене языка."""
        t = self._config.t

        self._carrier.update_labels(t("carrier_file"), t("browse"))
        self._container.update_labels(t("container_file"), t("browse"))
        self._password.update_label(t("password"))
        self._confirm_label.configure(text=t("password_confirm"))
        self._join_btn.configure(text=t("join_btn"))
        self._on_password_changed()

    def refresh_status(self) -> None:
        """Пересчитывает статус-бар по текущему состоянию полей."""
        t = self._config.t

        if not self._carrier.path_or_none or not self._container.path_or_none:
            self._on_status(t("status_not_ready"))
            return
        pwd = self._password.password_var.get()
        confirm = self._confirm_var.get()
        if not pwd or not confirm:
            self._on_status(t("status_not_ready"))
            return
        self._check_password_match(pwd, confirm)

    def _on_password_changed(self, *args: Any) -> None:
        """Обновляет индикатор силы пароля и проверяет совпадение."""
        pwd = self._password.password_var.get()
        length = len(pwd)

        if not length:
            self._strength_label.configure(text="")
        elif length < MIN_PASSWORD_LENGTH:
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

        # Если поле подтверждения не пусто — сразу сверяем
        confirm = self._confirm_var.get()
        if confirm:
            self._check_password_match(pwd, confirm)

    def _on_confirm_changed(self, *args: Any) -> None:
        """Проверяет совпадение паролей в реальном времени."""
        pwd = self._password.password_var.get()
        confirm = self._confirm_var.get()
        if not confirm:
            self._on_status(self._config.t("status_not_ready"))
            return
        self._check_password_match(pwd, confirm)

    def _check_password_match(self, pwd: str, confirm: str) -> None:
        """Сравнивает пароль и подтверждение, обновляет статус-бар."""
        if pwd != confirm:
            self._on_status(self._config.t("password_mismatch"))
        else:
            self._on_status(self._config.t("status_ready_join"))

    def _on_join(self) -> None:
        """Обработчик нажатия кнопки «Соединить»."""
        t = self._config.t

        carrier = self._carrier.path_or_none
        container = self._container.path_or_none
        password = self._password.password_var.get()
        confirm = self._confirm_var.get()

        if not carrier:
            self._on_status(t("status_not_ready"))
            return
        if not container:
            self._on_status(t("status_not_ready"))
            return
        if not password:
            self._on_status(t("error_password_empty"))
            return
        if len(password) < MIN_PASSWORD_LENGTH:
            self._on_status(t("error_password_short"))
            return
        if password != confirm:
            self._on_status(t("password_mismatch"))
            return

        output_path = generate_output_path(str(carrier))

        self._join_btn.configure(state="disabled")
        self._progress_show(t("progress_join"))
        self._on_status(t("status_processing"))

        self._worker.run(
            target=join_files,
            args=(
                str(carrier),
                str(container),
                str(output_path),
                password,
            ),
            on_success=self._on_join_success,
            on_error=self._on_join_error,
            on_finish=self._on_join_finish,
            root=self.winfo_toplevel(),
        )

    def _translate_error(self, error: str | HideMyLuteError) -> str:
        """Возвращает переведённое сообщение об ошибке."""
        if isinstance(error, HideMyLuteError) and error.msg_key:
            return self._config.t(error.msg_key, **error.msg_kwargs)
        return str(error)

    def _on_join_success(self, result: Path) -> None:
        """Callback при успешном соединении."""
        t = self._config.t
        self._on_status(
            f"{t('status_completed_join')} \u2014 {result}"
        )

    def _on_join_error(self, error: str | HideMyLuteError) -> None:
        """Callback при ошибке соединения."""
        self._on_status(
            f"{self._config.t('error_title')}: {self._translate_error(error)}"
        )

    def _on_join_finish(self) -> None:
        """Callback по завершении (всегда)."""
        self._progress_hide()
        self._join_btn.configure(state="normal")
