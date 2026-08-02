"""Панель вкладки «Разделение»."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import customtkinter as ctk

from ..config import MAX_PASSWORD_LENGTH, AppConfig
from ..exceptions import HideMyLuteError
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
        **kwargs: Any,
    ) -> None:
        """Инициализирует панель разделения.

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
        self._split_btn = ctk.CTkButton(
            self,
            text=t("split_btn"),
            height=60,
            font=ctk.CTkFont(size=28, weight="bold"),
            command=self._on_split,
        )
        self._split_btn.pack(pady=15)

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
        self._split_btn.configure(text=t("split_btn"))

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

    def _on_file_changed(self, *args: Any) -> None:
        """Сбрасывает состояние завершённой операции при смене файла."""
        self._completed_path = None
        self._error = None
        self.refresh_status()

    def _on_password_changed(self, *args: Any) -> None:
        """Сбрасывает состояние завершённой операции при смене пароля."""
        self._completed_path = None
        self._error = None
        self.refresh_status()

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

        self._split_btn.configure(state="disabled")
        self._processing = True
        self._completed_path = None
        self._error = None
        self._progress_bar.pack(fill="x", padx=10, pady=(0, 5))
        self._progress_bar.start()
        self._on_status(t("status_processing"))

        self._worker.run(
            target=split_file,
            args=(str(combined), str(output_dir), password),
            on_success=self._on_split_success,
            on_error=self._on_split_error,
            on_finish=self._on_split_finish,
            root=self.winfo_toplevel(),
        )

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

    def _on_split_success(self, result: tuple[Path, dict]) -> None:
        """Callback при успешном разделении."""
        container_path, _metadata = result
        self._completed_path = container_path
        t = self._config.t
        self._on_status(
            f"{t('status_completed_split')} \u2014 {container_path}",
            click_path=container_path,
        )

    def _on_split_error(self, error: str | HideMyLuteError) -> None:
        """Callback при ошибке разделения."""
        self._error = error
        self._on_status(self._format_error(error))

    def _on_split_finish(self) -> None:
        """Callback по завершении (всегда)."""
        self._processing = False
        self._progress_bar.stop()
        self._progress_bar.pack_forget()
        self._split_btn.configure(state="normal")
