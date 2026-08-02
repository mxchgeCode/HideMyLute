"""Переиспользуемые виджеты для UI hideMyLute."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from tkinter import filedialog
from typing import Any

import customtkinter as ctk


def open_in_file_manager(path: str | Path) -> None:
    """Открывает каталог, содержащий файл, в файловом менеджере.

    Args:
        path: Путь к файлу — откроется его родительский каталог.
    """
    target = Path(path)
    if not target.is_dir():
        target = target.parent
    try:
        if sys.platform == "win32":
            os.startfile(str(target))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(target)])
        else:
            subprocess.Popen(["xdg-open", str(target)])
    except OSError:
        pass


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
        trace_callback: Any = None,
        **kwargs: Any,
    ) -> None:
        """Инициализирует FileSelector.

        Args:
            parent: Родительский виджет.
            label: Текст метки.
            browse_text: Текст кнопки обзора.
            file_types: Кортеж типов файлов для диалога
                        (("Описание", "*.ext"), ...).
            trace_callback: Callback при изменении пути
                            (вызывается с *args от StringVar.trace).
        """
        super().__init__(parent, fg_color="transparent", **kwargs)

        self._file_types = file_types or (
            ("Все файлы", "*.*"),
        )

        self.path_var = ctk.StringVar()

        self._label = ctk.CTkLabel(self, text=label, anchor="w")
        self._label.pack(
            fill="x", padx=0, pady=(10, 2)
        )

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=0, pady=(0, 5))

        ctk.CTkEntry(
            row,
            textvariable=self.path_var,
            state="readonly",
            height=44,
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))

        self._browse_btn = ctk.CTkButton(
            row,
            text=browse_text,
            width=120,
            height=44,
            command=self._browse,
        )
        self._browse_btn.pack(side="right")

        if trace_callback:
            self.path_var.trace_add("write", trace_callback)

    def update_labels(self, label: str, browse_text: str) -> None:
        """Обновляет тексты метки и кнопки (для смены языка).

        Args:
            label: Новый текст метки.
            browse_text: Новый текст кнопки обзора.
        """
        self._label.configure(text=label)
        self._browse_btn.configure(text=browse_text)

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
        super().__init__(parent, fg_color="transparent", **kwargs)

        self.password_var = ctk.StringVar()

        self._label = ctk.CTkLabel(self, text=label, anchor="w")
        self._label.pack(
            fill="x", padx=0, pady=(10, 2)
        )

        ctk.CTkEntry(
            self,
            textvariable=self.password_var,
            show="•",
            height=44,
        ).pack(fill="x", padx=0, pady=(0, 2))

        if trace_callback:
            self.password_var.trace_add("write", trace_callback)

    def update_label(self, label: str) -> None:
        """Обновляет текст метки (для смены языка).

        Args:
            label: Новый текст метки.
        """
        self._label.configure(text=label)


class StatusBar(ctk.CTkFrame):
    """Строка состояния приложения.

    При установке текста с указанием click_path строка становится
    кликабельной и открывает каталог с файлом в файловом менеджере.
    """

    LINK_COLOR = ("#1f6aa5", "#4ea1ff")

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
        super().__init__(parent, height=50, **kwargs)

        self._click_path: Path | None = None

        self._label = ctk.CTkLabel(
            self,
            text=initial_text,
            anchor="w",
        )
        self._default_color = self._label.cget("text_color")
        self._label.pack(fill="x", padx=10, pady=8)

        self._label.bind("<Button-1>", self._on_click)
        self.bind("<Button-1>", self._on_click)

    def set_text(self, text: str, click_path: Path | None = None) -> None:
        """Устанавливает текст статуса.

        Args:
            text: Текст статуса.
            click_path: Путь к файлу результата; строка становится
                        кликабельной и открывает каталог с файлом.
        """
        self._label.configure(text=text)
        self._click_path = click_path
        if click_path is None:
            self._label.configure(
                cursor="arrow", text_color=self._default_color
            )
        else:
            self._label.configure(
                cursor="hand2", text_color=self.LINK_COLOR
            )

    def _on_click(self, _event: Any) -> None:
        """Открывает каталог с файлом результата по клику."""
        if self._click_path is not None:
            open_in_file_manager(self._click_path)

