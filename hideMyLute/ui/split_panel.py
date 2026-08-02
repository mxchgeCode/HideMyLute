"""Панель вкладки «Разделение»."""

from __future__ import annotations

from pathlib import Path
from tkinter import messagebox
from typing import Any

import customtkinter as ctk

from ..config import AppConfig
from ..steganography import split_file
from ..worker import BackgroundWorker
from .widgets import FileSelector, PasswordField


class SplitPanel(ctk.CTkFrame):
    """Панель для разделения собранного файла на носитель и контейнер.

    Содержит поля выбора собранного файла, директории для контейнера,
    пароль и кнопку «Разделить».
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
        self._combined.pack(fill="x", padx=10)

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
            height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
            command=self._on_split,
        )
        self._split_btn.pack(pady=20)

        # Секция метаданных (скрыта до успешного разделения)
        self._metadata_frame = ctk.CTkFrame(
            self, fg_color="transparent"
        )

        self._carrier_size_label = ctk.CTkLabel(
            self._metadata_frame,
            text="",
            anchor="w",
        )
        self._carrier_size_label.pack(fill="x", padx=10)

        self._container_size_label = ctk.CTkLabel(
            self._metadata_frame,
            text="",
            anchor="w",
        )
        self._container_size_label.pack(fill="x", padx=10)

    def _on_split(self) -> None:
        """Обработчик нажатия кнопки «Разделить»."""
        t = self._config.t

        combined = self._combined.path_or_none
        password = self._password.password_var.get()

        if not combined:
            messagebox.showerror(
                t("error_title"),
                t("error_file_not_found", path="собранный файл"),
            )
            return
        if not password:
            messagebox.showerror(
                t("error_title"), "Пароль не может быть пустым"
            )
            return

        # Сохраняем контейнер рядом с собранным файлом
        output_dir = combined.parent

        self._split_btn.configure(state="disabled")
        self._metadata_frame.pack_forget()
        self._progress_show(t("progress_split"))
        self._on_status(t("status_processing"))

        self._worker.run(
            target=split_file,
            args=(str(combined), str(output_dir), password),
            on_success=self._on_split_success,
            on_error=self._on_split_error,
            on_finish=self._on_split_finish,
        )

    def _on_split_success(self, result: tuple[Path, dict]) -> None:
        """Callback при успешном разделении."""
        t = self._config.t
        container_path, metadata = result

        # Показываем метаданные
        self._carrier_size_label.configure(
            text=(
                f"{t('carrier_original_size')} "
                f"{metadata['carrier_size']:,} байт"
            )
        )
        self._container_size_label.configure(
            text=(
                f"{t('container_size')} "
                f"{metadata['container_size']:,} байт"
            )
        )
        self._metadata_frame.pack(fill="x", padx=10, pady=10)

        messagebox.showinfo(
            t("app_title"),
            f"{t('success_split')}\n\n{container_path}",
        )
        self._on_status(t("status_ready"))

    def _on_split_error(self, error_msg: str) -> None:
        """Callback при ошибке разделения."""
        t = self._config.t
        messagebox.showerror(t("error_title"), error_msg)
        self._on_status(t("status_ready"))

    def _on_split_finish(self) -> None:
        """Callback по завершении (всегда)."""
        self._progress_hide()
        self._split_btn.configure(state="normal")
