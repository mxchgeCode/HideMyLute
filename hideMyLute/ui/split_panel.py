"""Панель вкладки «Разделение»."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import customtkinter as ctk

from ..config import MAX_PASSWORD_LENGTH, AppConfig
from ..exceptions import HideMyLuteError
from ..steganography import split_file
from ..worker import BackgroundWorker
from .operation_panel import OperationPanel
from .widgets import FileSelector, PasswordField


class SplitPanel(OperationPanel):
    """Панель для разделения собранного файла на носитель и контейнер."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        config: AppConfig,
        worker: BackgroundWorker,
        on_status: Any,
        **kwargs: Any,
    ) -> None:
        """Инициализирует панель разделения.

        Args:
            parent: Родительский виджет.
            config: Конфигурация приложения (DI).
            worker: Фоновый воркер (DI).
            on_status: Callback для строки статуса.
        """
        super().__init__(parent, config=config, worker=worker,
                         on_status=on_status, **kwargs)
        self._build_ui()

    def _build_ui(self) -> None:
        """Строит интерфейс панели."""
        t = self._config.t

        # Выбор собранного файла
        self._combined = FileSelector(
            self,
            label=t("combined_file"),
            browse_text=t("browse"),
            trace_callback=self._on_file_changed,
        )
        self._combined.pack(fill="x", padx=10, pady=(5, 0))

        # Пароль
        self._password = PasswordField(
            self,
            label=t("password"),
            trace_callback=self._on_password_changed,
        )
        self._password.pack(fill="x", padx=10)

        # Кнопка разделения
        self._action_btn = ctk.CTkButton(
            self,
            text=t("split_btn"),
            height=60,
            font=ctk.CTkFont(size=28, weight="bold"),
            command=self._on_split,
        )
        self._action_btn.pack(pady=15)

        # Прогресс-бар (индикатор неопределённого прогресса, скрыт по умолчанию)
        self._progress_bar = ctk.CTkProgressBar(
            self,
            mode="indeterminate",
            height=16,
        )
        self._progress_bar.pack(fill="x", padx=10, pady=(0, 5))
        self._progress_bar.pack_forget()

    def update_language(self) -> None:
        """Обновляет тексты всех виджетов при смене языка."""
        t = self._config.t

        self._combined.update_labels(t("combined_file"), t("browse"))
        self._password.update_label(t("password"))
        self._action_btn.configure(text=t("split_btn"))

    def refresh_status(self) -> None:
        """Пересчитывает статус-бар по текущему состоянию полей."""
        t = self._config.t

        if self._processing:
            self._on_status(t("status_processing"))
            return
        if self._error is not None:
            self._on_status(self._format_error(self._error))
            return
        if self._completed_path is not None:
            self._on_status(
                f"{t('status_completed_split')} \u2014 {self._completed_path}",
                click_path=self._completed_path,
            )
            return
        if not self._combined.path_or_none:
            self._on_status(t("status_not_ready"))
            return
        pwd = self._password.password_var.get()
        if not pwd:
            self._on_status(t("status_not_ready"))
            return
        # Минимальная длина не проверяется при разделении — это сохраняет
        # совместимость с legacy-файлами, собранными слабым паролем.
        if len(pwd) > MAX_PASSWORD_LENGTH:
            self._on_status(
                t("error_password_too_long", max_len=str(MAX_PASSWORD_LENGTH))
            )
            return
        self._on_status(t("status_ready_split"))

    def _on_split(self) -> None:
        """Обработчик нажатия кнопки «Разделить»."""
        t = self._config.t

        combined = self._combined.path_or_none
        password = self._password.password_var.get()

        if not combined:
            self._on_status(t("status_not_ready"))
            return
        if not password:
            self._on_status(t("error_password_empty"))
            return
        if len(password) > MAX_PASSWORD_LENGTH:
            self._on_status(
                t("error_password_too_long", max_len=str(MAX_PASSWORD_LENGTH))
            )
            return

        output_dir = combined.parent
        self._begin_processing()

        self._run_operation(
            target=split_file,
            args=(str(combined), str(output_dir), password),
            on_success=self._on_split_success,
            on_error=self._on_split_error,
        )

    def _on_split_success(self, result: tuple[Path, dict]) -> None:
        """Callback при успешном разделении."""
        container_path, _metadata = result
        self._completed_path = container_path
        t = self._config.t
        self._on_status(
            f"{t('status_completed_split')} \u2014 {container_path}",
            click_path=container_path,
        )
        # Секрет не должен оставаться в памяти UI после завершения
        self._clear_password_fields()

    def _on_split_error(self, error: str | HideMyLuteError) -> None:
        """Callback при ошибке разделения."""
        self._error = error
        self._on_status(self._format_error(error))
