"""Главное окно приложения hideMyLute."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import customtkinter as ctk

from .. import __version__
from ..config import AppConfig
from ..logging_config import setup_logging
from ..worker import BackgroundWorker
from .join_panel import JoinPanel
from .split_panel import SplitPanel
from .widgets import StatusBar


class MainWindow(ctk.CTk):
    """Главное окно с вкладками «Соединение» и «Разделение».

    Управляет жизненным циклом фонового воркера, статус-баром
    и прогресс-оверлеем.
    """

    APP_NAME = "hideMyLute"
    WINDOW_WIDTH = 660
    WINDOW_HEIGHT = 700

    def __init__(
        self,
        config: AppConfig | None = None,
        **kwargs: Any,
    ) -> None:
        """Инициализирует главное окно.

        Args:
            config: Конфигурация приложения (DI). Если None,
                    создаётся AppConfig с умолчаниями.
        """
        super().__init__(**kwargs)

        if config is None:
            config = AppConfig()

        self._config = config
        setup_logging(
            enabled=self._config.logging_enabled,
            log_file=self._config.log_file,
            level=logging.INFO,
        )

        self._worker = BackgroundWorker()

        self._setup_window()
        self._build_ui()

        # Блокировка повторного закрытия
        self._closing = False
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_window(self) -> None:
        """Настраивает параметры окна."""
        # Тема
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

        # Увеличение шрифта по умолчанию в 2 раза (13 → 26)
        ctk.ThemeManager.theme["CTkFont"]["size"] = 26

        title = f"{self.APP_NAME} v{__version__}"
        self.title(title)
        self.geometry(f"{self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}")
        self.minsize(580, 640)

        # Центрирование на экране
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - self.WINDOW_WIDTH) // 2
        y = (screen_h - self.WINDOW_HEIGHT) // 2
        self.geometry(f"+{x}+{y}")

    def _build_ui(self) -> None:
        """Строит интерфейс главного окна."""
        t = self._config.t

        # Сетка: строки для вкладок и статус-бара
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=1)

        # Контейнер вкладок
        self._tabview = ctk.CTkTabview(self)
        self._tabview.grid(
            row=0, column=0, sticky="nsew", padx=5, pady=(5, 0)
        )

        self._tabview.add(t("tab_join"))
        self._tabview.add(t("tab_split"))

        # Workaround: публичного API для высоты вкладок нет (customtkinter 6.0).
        # Обращение защищено try/except — при изменении внутренностей
        # библиотеки приложение не упадёт.
        try:
            self._tabview._segmented_button.configure(height=48)
        except AttributeError:
            pass

        # Вкладка «Соединение»
        self._join_panel = JoinPanel(
            self._tabview.tab(t("tab_join")),
            config=self._config,
            worker=self._worker,
            on_status=self._set_status,
        )
        self._join_panel.pack(fill="both", expand=True)

        # Вкладка «Разделение»
        self._split_panel = SplitPanel(
            self._tabview.tab(t("tab_split")),
            config=self._config,
            worker=self._worker,
            on_status=self._set_status,
        )
        self._split_panel.pack(fill="both", expand=True)

        # Статус-бар
        self._status_bar = StatusBar(self)
        self._status_bar.grid(
            row=1, column=0, sticky="ew", padx=5, pady=5
        )
        self._set_status(t("status_not_ready"))

        # Выбор языка (правый верхний угол)
        self._build_language_selector()

    def _build_language_selector(self) -> None:
        """Создаёт переключатель языка."""
        t = self._config.t

        self._lang_frame = ctk.CTkFrame(
            self, fg_color="transparent"
        )
        self._lang_frame.place(relx=1.0, rely=0.0, x=-10, y=5, anchor="ne")

        self._lang_label = ctk.CTkLabel(
            self._lang_frame,
            text=t("language_label"),
            font=ctk.CTkFont(size=22),
        )
        self._lang_label.pack(side="left", padx=(0, 5))

        self._lang_switch = ctk.CTkSegmentedButton(
            self._lang_frame,
            values=["RU", "EN"],
            command=self._on_language_changed,
            width=110,
            height=40,
        )
        self._lang_switch.pack(side="left")
        self._lang_switch.set("RU" if self._config.language == "ru" else "EN")

    def _on_language_changed(self, value: str) -> None:
        """Обработчик смены языка — обновляет только тексты, данные сохраняются."""
        new_lang = "ru" if value == "RU" else "en"
        if new_lang == self._config.language:
            return

        self._config.set_language(new_lang)
        self._apply_language_switch()

    def _apply_language_switch(self) -> None:
        """Применяет смену языка ко всем текстам интерфейса.

        Использует только публичный API CTkTabview (rename/get), без
        обращения к приватным атрибутам библиотеки.
        """
        t = self._config.t

        old_names = [
            self._tabview.get(0),
            self._tabview.get(1),
        ]
        new_names = [t("tab_join"), t("tab_split")]
        tab_map = dict(zip(old_names, new_names))

        current_name = self._tabview.get()
        for old_name, new_name in tab_map.items():
            if old_name != new_name:
                self._tabview.rename(old_name, new_name)

        # Восстановление активной вкладки
        self._tabview.set(tab_map.get(current_name, new_names[0]))

        # Обновление текстов в панелях
        self._join_panel.update_language()
        self._split_panel.update_language()

        # Обновление метки языка
        self._lang_label.configure(text=t("language_label"))

        # Пересчёт статуса активной вкладки
        current = self._tabview.get()
        if current == new_names[0]:
            self._join_panel.refresh_status()
        else:
            self._split_panel.refresh_status()

    def _set_status(self, text: str, click_path: Path | None = None) -> None:
        """Устанавливает текст статус-бара.

        Args:
            text: Текст статуса.
            click_path: Путь к файлу результата; при клике по строке
                        статуса открывается каталог с этим файлом.
        """
        self._status_bar.set_text(text, click_path)

    def _on_close(self) -> None:
        """Обработчик закрытия окна."""
        if self._closing:
            return
        self._closing = True
        self._worker.cancel()
        self.destroy()

    def run(self) -> None:
        """Запускает главный цикл приложения."""
        self.mainloop()
