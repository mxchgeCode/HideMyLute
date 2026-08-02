"""Точка входа hideMyLute — ``python -m hideMyLute``."""

from __future__ import annotations

import argparse

from hideMyLute._version import VERSION_STRING
from hideMyLute.config import AppConfig
from hideMyLute.ui.main_window import MainWindow


def _parse_args() -> argparse.Namespace:
    """Разбирает аргументы командной строки."""
    parser = argparse.ArgumentParser(
        prog="hideMyLute",
        description="Инструмент стеганографии для правдоподобного отрицания.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {VERSION_STRING}",
        help="Показать версию приложения и выйти",
    )
    return parser.parse_args()


def main() -> None:
    """Запускает приложение."""
    _parse_args()
    config = AppConfig()
    app = MainWindow(config=config)
    app.run()


if __name__ == "__main__":
    main()
