"""Панель вкладки «Соединение»."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import customtkinter as ctk

from ..config import MAX_PASSWORD_LENGTH, MIN_PASSWORD_LENGTH, AppConfig
from ..exceptions import HideMyLuteError
from ..password_strength import Strength, assess_password_strength
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
        **kwargs: Any,
    ) -> None:
        """Инициализирует панель соединения.

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

        # Выбор файла-носителя
        self._carrier = FileSelector(
            self,
            label=t("carrier_file"),
            browse_text=t("browse"),
            trace_callback=self._on_file_changed,
        )
        self._carrier.pack(fill="x", padx=10, pady=(5, 0))

        # Выбор файла-контейнера
        self._container = FileSelector(
            self,
            label=t("container_file"),
            browse_text=t("browse"),
            trace_callback=self._on_file_changed,
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
            font=ctk.CTkFont(size=22),
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
            height=44,
        )
        self._confirm_entry.pack(fill="x", padx=10, pady=(0, 5))

        # Кнопка «Соединить»
        self._join_btn = ctk.CTkButton(
            self,
            text=t("join_btn"),
            height=60,
            font=ctk.CTkFont(size=28, weight="bold"),
            command=self._on_join,
        )
        self._join_btn.pack(pady=15)

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

        self._carrier.update_labels(t("carrier_file"), t("browse"))
        self._container.update_labels(t("container_file"), t("browse"))
        self._password.update_label(t("password"))
        self._confirm_label.configure(text=t("password_confirm"))
        self._join_btn.configure(text=t("join_btn"))
        self._update_strength_label()

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
                f"{t('status_completed_join')} \u2014 {self._completed_path}",
                click_path=self._completed_path,
            )
            return
        if not self._carrier.path_or_none or not self._container.path_or_none:
            self._on_status(t("status_not_ready"))
            return
        pwd = self._password.password_var.get()
        confirm = self._confirm_var.get()
        if not pwd or not confirm:
            self._on_status(t("status_not_ready"))
            return
        self._check_password_match(pwd, confirm)

    def _on_file_changed(self, *args: Any) -> None:
        """Сбрасывает состояние завершённой операции при смене файла."""
        self._completed_path = None
        self._error = None
        self.refresh_status()

    def _update_strength_label(self) -> None:
        """Обновляет индикатор силы пароля."""
        pwd = self._password.password_var.get()
        if not pwd:
            self._strength_label.configure(text="")
            return

        t = self._config.t
        level = assess_password_strength(pwd)
        if level is Strength.WEAK:
            text, color = t("password_strength_weak"), "red"
        elif level is Strength.OK:
            text, color = t("password_strength_ok"), "orange"
        else:
            text, color = t("password_strength_strong"), "green"
        self._strength_label.configure(text=text, text_color=color)

    def _on_password_changed(self, *args: Any) -> None:
        """Обновляет индикатор силы пароля и проверяет совпадение."""
        self._completed_path = None
        self._error = None
        self._update_strength_label()

        # Если поле подтверждения не пусто — сразу сверяем
        confirm = self._confirm_var.get()
        if confirm:
            self._check_password_match(
                self._password.password_var.get(), confirm
            )

    def _on_confirm_changed(self, *args: Any) -> None:
        """Проверяет совпадение паролей в реальном времени."""
        self._completed_path = None
        self._error = None
        pwd = self._password.password_var.get()
        confirm = self._confirm_var.get()
        if not confirm:
            self._on_status(self._config.t("status_not_ready"))
            return
        self._check_password_match(pwd, confirm)

    def _check_password_match(self, pwd: str, confirm: str) -> None:
        """Сравнивает пароль и подтверждение, обновляет статус-бар.

        Дополнительно проверяет политику длины пароля (минимум и максимум).
        """
        t = self._config.t
        if len(pwd) < MIN_PASSWORD_LENGTH:
            self._on_status(t("error_password_short"))
            return
        if len(pwd) > MAX_PASSWORD_LENGTH:
            self._on_status(
                t("error_password_too_long", max_len=str(MAX_PASSWORD_LENGTH))
            )
            return
        if pwd != confirm:
            self._on_status(t("password_mismatch"))
        else:
            self._on_status(t("status_ready_join"))

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
        if len(password) > MAX_PASSWORD_LENGTH:
            self._on_status(
                t("error_password_too_long", max_len=str(MAX_PASSWORD_LENGTH))
            )
            return
        if password != confirm:
            self._on_status(t("password_mismatch"))
            return

        output_path = generate_output_path(str(carrier))

        self._join_btn.configure(state="disabled")
        self._processing = True
        self._completed_path = None
        self._error = None
        self._progress_bar.pack(fill="x", padx=10, pady=(0, 5))
        self._progress_bar.start()
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

    def _on_join_success(self, result: Path) -> None:
        """Callback при успешном соединении."""
        self._completed_path = result
        t = self._config.t
        self._on_status(
            f"{t('status_completed_join')} \u2014 {result}",
            click_path=result,
        )

    def _on_join_error(self, error: str | HideMyLuteError) -> None:
        """Callback при ошибке соединения."""
        self._error = error
        self._on_status(self._format_error(error))

    def _on_join_finish(self) -> None:
        """Callback по завершении (всегда)."""
        self._processing = False
        self._progress_bar.stop()
        self._progress_bar.pack_forget()
        self._join_btn.configure(state="normal")
