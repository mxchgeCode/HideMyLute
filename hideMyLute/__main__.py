"""Точка входа hideMyLute — ``python -m hideMyLute``."""

from __future__ import annotations

from hideMyLute.config import AppConfig
from hideMyLute.ui.main_window import MainWindow


def main() -> None:
    """Запускает приложение."""
    config = AppConfig()
    app = MainWindow(config=config)
    app.run()


if __name__ == "__main__":
    main()
