"""Точка входа hideMyLute — ``python -m hideMyLute``.

Поддерживает GUI (по умолчанию) и командную строку:

- ``hideMyLute join НОСИТЕЛЬ КОНТЕЙНЕР ВЫХОД [--password]``
- ``hideMyLute split СОБРАННЫЙ [--output-dir КАТАЛОГ] [--password]``
- ``hideMyLute info СОБРАННЫЙ [--password]``
- ``hideMyLute --version``

Если ``--password`` не передан, пароль запрашивается интерактивно
(getpass), что не оставляет его в истории командной оболочки.
"""

from __future__ import annotations

import argparse
import getpass
import sys
from pathlib import Path

from hideMyLute._version import VERSION_STRING
from hideMyLute.config import (
    MAX_PASSWORD_LENGTH,
    MIN_PASSWORD_LENGTH,
    AppConfig,
)
from hideMyLute.exceptions import HideMyLuteError


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
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
    sub = parser.add_subparsers(dest="command")

    join_p = sub.add_parser(
        "join", help="Соединить носитель и контейнер в один файл"
    )
    join_p.add_argument("carrier", help="Путь к файлу-носителю")
    join_p.add_argument("container", help="Путь к файлу-контейнеру")
    join_p.add_argument("output", help="Путь к выходному файлу")
    join_p.add_argument(
        "--password", default=None, help="Пароль (иначе — интерактивный запрос)"
    )

    split_p = sub.add_parser(
        "split", help="Разделить собранный файл и извлечь контейнер"
    )
    split_p.add_argument("combined", help="Путь к собранному файлу")
    split_p.add_argument(
        "--output-dir",
        default=None,
        help="Каталог для контейнера (по умолчанию — рядом с файлом)",
    )
    split_p.add_argument(
        "--password", default=None, help="Пароль (иначе — интерактивный запрос)"
    )

    info_p = sub.add_parser(
        "info", help="Показать метаданные футера собранного файла"
    )
    info_p.add_argument("combined", help="Путь к собранному файлу")
    info_p.add_argument(
        "--password", default=None, help="Пароль (иначе — интерактивный запрос)"
    )

    return parser.parse_args(argv)


def _read_password(explicit: str | None) -> str:
    """Возвращает пароль: из аргумента или интерактивного запроса.

    Интерактивный запрос через getpass не оставляет пароль в истории
    командной оболочки и в списке процессов.
    """
    if explicit is not None:
        return explicit
    return getpass.getpass("Password: ")


def _run_cli(args: argparse.Namespace) -> int:
    """Выполняет CLI-команду. Возвращает код возврата."""
    try:
        if args.command == "join":
            from .steganography import join_files

            password = _read_password(args.password)
            if len(password) < MIN_PASSWORD_LENGTH:
                print(
                    f"Ошибка: пароль должен быть не менее "
                    f"{MIN_PASSWORD_LENGTH} символов",
                    file=sys.stderr,
                )
                return 2
            if len(password) > MAX_PASSWORD_LENGTH:
                print(
                    f"Ошибка: пароль слишком длинный "
                    f"(максимум {MAX_PASSWORD_LENGTH} символов)",
                    file=sys.stderr,
                )
                return 2
            result = join_files(args.carrier, args.container, args.output, password)
            print(f"OK: {result}")
            return 0

        if args.command == "split":
            from .steganography import split_file

            password = _read_password(args.password)
            out_dir = args.output_dir or str(Path(args.combined).parent)
            container, metadata = split_file(args.combined, out_dir, password)
            print(f"OK: {container}")
            print(f"carrier_size: {metadata['carrier_size']}")
            print(f"container_size: {metadata['container_size']}")
            return 0

        if args.command == "info":
            from .footer import unpack_footer

            password = _read_password(args.password)
            metadata = unpack_footer(args.combined, password)
            for key in sorted(metadata):
                print(f"{key}: {metadata[key]}")
            return 0

        # Без подкоманды — запускаем GUI (main не вызывает _run_cli)
        return 0

    except HideMyLuteError as exc:
        print(f"Ошибка: {exc}", file=sys.stderr)
        return 1
    except OSError as exc:
        print(f"Ошибка ввода-вывода: {exc}", file=sys.stderr)
        return 1


def main(argv: list[str] | None = None) -> None:
    """Запускает приложение (GUI) или CLI-команду."""
    args = _parse_args(argv)

    if args.command is None:
        # GUI-импорт выполняется лениво, чтобы CLI не тянул customtkinter
        from hideMyLute.ui.main_window import MainWindow

        config = AppConfig.from_env()
        app = MainWindow(config=config)
        app.run()
        return

    raise SystemExit(_run_cli(args))


if __name__ == "__main__":
    main()
