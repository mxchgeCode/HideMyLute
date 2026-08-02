"""Переиспользуемые виджеты для UI hideMyLute."""

from __future__ import annotations

from pathlib import Path
from tkinter import filedialog
from typing import Any

import customtkinter as ctk


class FileSelector(ctk.CTkFrame):
    """Виджет выбора файла: метка + поле ввода + кнопка «Обзор».

    Attributes:
        path_var: StringVar, связанный с полем пути.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        label: str,
        browse_text: str = "Обзор...",
        file_types: tuple[tuple[str, str], ...] | None = None,
        **kwargs: Any,
    ) -> None:
        """Инициализирует FileSelector.

        Args:
            parent: Родительский виджет.
            label: Текст метки.
            browse_text: Текст кнопки обзора.
            file_types: Кортеж типов файлов для диалога
                        (("Описание", "*.ext"), ...).
        """
        super().__init__(parent, **kwargs)

        self._file_types = file_types or (
            ("Все файлы", "*.*"),
        )

        self.path_var = ctk.StringVar()

        ctk.CTkLabel(self, text=label, anchor="w").pack(
            fill="x", padx=5, pady=(10, 2)
        )

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=5, pady=(0, 5))

        ctk.CTkEntry(
            row,
            textvariable=self.path_var,
            state="readonly",
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))

        ctk.CTkButton(
            row,
            text=browse_text,
            width=80,
            command=self._browse,
        ).pack(side="right")

    def _browse(self) -> None:
        """Открывает диалог выбора файла."""
        filepath = filedialog.askopenfilename(
            title="Выберите файл",
            filetypes=self._file_types,
        )
        if filepath:
            self.path_var.set(filepath)

    @property
    def path(self) -> str:
        """Возвращает выбранный путь."""
        return self.path_var.get()

    @property
    def path_or_none(self) -> Path | None:
        """Возвращает Path или None, если путь пуст."""
        value = self.path.strip()
        return Path(value) if value else None


class PasswordField(ctk.CTkFrame):
    """Поле ввода пароля с меткой.

    Attributes:
        password_var: StringVar, связанный с полем пароля.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        label: str = "Пароль:",
        trace_callback: Any = None,
        **kwargs: Any,
    ) -> None:
        """Инициализирует PasswordField.

        Args:
            parent: Родительский виджет.
            label: Текст метки.
            trace_callback: Callback при изменении пароля
                            (вызывается с *args от StringVar.trace).
        """
        super().__init__(parent, **kwargs)

        self.password_var = ctk.StringVar()

        ctk.CTkLabel(self, text=label, anchor="w").pack(
            fill="x", padx=5, pady=(10, 2)
        )

        ctk.CTkEntry(
            self,
            textvariable=self.password_var,
            show="•",
        ).pack(fill="x", padx=5, pady=(0, 2))

        if trace_callback:
            self.password_var.trace_add("write", trace_callback)


class StatusBar(ctk.CTkFrame):
    """Строка состояния приложения."""

    def __init__(
        self,
        parent: ctk.CTkFrame,
        initial_text: str = "Готов",
        **kwargs: Any,
    ) -> None:
        """Инициализирует StatusBar.

        Args:
            parent: Родительский виджет.
            initial_text: Начальный текст статуса.
        """
        super().__init__(parent, height=30, **kwargs)

        self._label = ctk.CTkLabel(
            self,
            text=initial_text,
            anchor="w",
        )
        self._label.pack(fill="x", padx=10, pady=5)

    def set_text(self, text: str) -> None:
        """Устанавливает текст статуса."""
        self._label.configure(text=text)


class ProgressOverlay(ctk.CTkFrame):
    """Оверлей с прогресс-баром и сообщением.

    Показывается поверх интерфейса во время длительных операций,
    блокируя взаимодействие с UI.
    """

    def __init__(
        self,
        parent: ctk.CTkFrame,
        **kwargs: Any,
    ) -> None:
        """Инициализирует ProgressOverlay."""
        super().__init__(parent, **kwargs)

        self._label = ctk.CTkLabel(
            self,
            text="Обработка...",
            font=ctk.CTkFont(size=14),
        )
        self._label.pack(pady=(30, 10))

        self._progress = ctk.CTkProgressBar(
            self,
            mode="indeterminate",
            width=300,
        )
        self._progress.pack(pady=(0, 30))

    def show(self, message: str = "Обработка...") -> None:
        """Показывает оверлей с сообщением."""
        self._label.configure(text=message)
        self._progress.start()
        self.lift()
        self.place(relx=0.5, rely=0.5, anchor="center")

    def hide(self) -> None:
        """Скрывает оверлей."""
        self._progress.stop()
        self.place_forget()
