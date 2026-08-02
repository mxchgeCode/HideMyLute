"""Главное окно приложения hideMyLute."""

from __future__ import annotations

from typing import Any

import customtkinter as ctk

from ..config import AppConfig
from ..logging_config import setup_logging
from ..worker import BackgroundWorker
from .join_panel import JoinPanel
from .split_panel import SplitPanel
from .widgets import ProgressOverlay, StatusBar


class MainWindow(ctk.CTk):
    """Главное окно с вкладками «Соединение» и «Разделение».

    Управляет жизненным циклом фонового воркера, статус-баром
    и прогресс-оверлеем.
    """

    APP_TITLE = "hideMyLute"
    WINDOW_WIDTH = 520
    WINDOW_HEIGHT = 580

    def __init__(
        self,
        config: AppConfig | None = None,
        **kwargs: Any,
    ) -> None:
        """Инициализирует главное окно.

        Args:
            config: Конфигурация приложения (DI). Если None,
                    создаётся AppConfig по умолчанию.
        """
        super().__init__(**kwargs)

        if config is None:
            config = AppConfig()

        self._config = config
        setup_logging(self._config)

        self._worker = BackgroundWorker()

        self._setup_window()
        self._build_ui()

        # Блокировка повторного закрытия
        self._closing = False
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _setup_window(self) -> None:
        """Настраивает параметры окна."""
        self.title(self.APP_TITLE)
        self.geometry(f"{self.WINDOW_WIDTH}x{self.WINDOW_HEIGHT}")
        self.minsize(480, 500)

        # Центрирование на экране
        self.update_idletasks()
        screen_w = self.winfo_screenwidth()
        screen_h = self.winfo_screenheight()
        x = (screen_w - self.WINDOW_WIDTH) // 2
        y = (screen_h - self.WINDOW_HEIGHT) // 2
        self.geometry(f"+{x}+{y}")

        # Тема
        ctk.set_appearance_mode("system")
        ctk.set_default_color_theme("blue")

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

        # Вкладка «Соединение»
        self._join_panel = JoinPanel(
            self._tabview.tab(t("tab_join")),
            config=self._config,
            worker=self._worker,
            on_status=self._set_status,
            progress_show=self._show_progress,
            progress_hide=self._hide_progress,
        )
        self._join_panel.pack(fill="both", expand=True)

        # Вкладка «Разделение»
        self._split_panel = SplitPanel(
            self._tabview.tab(t("tab_split")),
            config=self._config,
            worker=self._worker,
            on_status=self._set_status,
            progress_show=self._show_progress,
            progress_hide=self._hide_progress,
        )
        self._split_panel.pack(fill="both", expand=True)

        # Статус-бар
        self._status_bar = StatusBar(self)
        self._status_bar.grid(
            row=1, column=0, sticky="ew", padx=5, pady=5
        )
        self._set_status(t("status_not_ready"))

        # Прогресс-оверлей (скрыт по умолчанию)
        self._overlay = ProgressOverlay(self)
        self._overlay.hide()

        # Выбор языка (правый верхний угол)
        self._build_language_selector()

    def _build_language_selector(self) -> None:
        """Создаёт переключатель языка."""
        t = self._config.t

        self._lang_frame = ctk.CTkFrame(
            self, fg_color="transparent"
        )
        self._lang_frame.place(relx=1.0, rely=0.0, x=-10, y=5, anchor="ne")

        ctk.CTkLabel(
            self._lang_frame,
            text=t("language_label"),
            font=ctk.CTkFont(size=11),
        ).pack(side="left", padx=(0, 5))

        self._lang_switch = ctk.CTkSegmentedButton(
            self._lang_frame,
            values=["RU", "EN"],
            command=self._on_language_changed,
            width=80,
        )
        self._lang_switch.pack(side="left")
        self._lang_switch.set("RU" if self._config.language == "ru" else "EN")

    def _on_language_changed(self, value: str) -> None:
        """Обработчик смены языка."""
        new_lang = "ru" if value == "RU" else "en"
        if new_lang == self._config.language:
            return

        # AppConfig frozen — создаём новый
        new_config = AppConfig(language=new_lang)
        self._config = new_config

        # Разбираем и перестраиваем UI
        self._lang_frame.destroy()
        self._tabview.destroy()
        self._status_bar.destroy()
        self._build_ui()

    def _set_status(self, text: str) -> None:
        """Устанавливает текст статус-бара."""
        self._status_bar.set_text(text)

    def _show_progress(self, text: str) -> None:
        """Показывает прогресс-оверлей."""
        self._overlay.show(text)

    def _hide_progress(self) -> None:
        """Скрывает прогресс-оверлей."""
        self._overlay.hide()

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
