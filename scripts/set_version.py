"""Устанавливает версию приложения из git-тега (используется в CI).

Переписывает константы VERSION_MAJOR/VERSION_MINOR/VERSION_PATCH
в hideMyLute/_version.py по тегу вида vMAJOR.MINOR.PATCH, чтобы
собранный exe (заголовок окна, --version, ресурсы Windows) содержал
версию тега. Для нетэговых сборок версия остаётся из исходников.

Использование:
    python scripts/set_version.py v3.1.0
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_VERSION_FILE = _ROOT / "hideMyLute" / "_version.py"

_CONSTANT_RE = re.compile(r"^VERSION_(MAJOR|MINOR|PATCH): int = \d+\r?$", re.MULTILINE)


def set_version(tag: str) -> None:
    version = tag.removeprefix("v")
    parts = version.split(".")
    if len(parts) < 3 or not all(p.isdigit() for p in parts):
        sys.exit(f"Некорректный тег версии: {tag!r} (ожидается vMAJOR.MINOR.PATCH)")
    major, minor, patch = (int(p) for p in parts[:3])

    values = {"MAJOR": major, "MINOR": minor, "PATCH": patch}
    text = _VERSION_FILE.read_text(encoding="utf-8")

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        return f"VERSION_{name}: int = {values[name]}"

    new_text, count = _CONSTANT_RE.subn(replace, text)
    if count != 3:
        sys.exit("Не найдены все три константы VERSION_* в hideMyLute/_version.py")
    _VERSION_FILE.write_text(new_text, encoding="utf-8")
    print(f"Версия установлена: {major}.{minor}.{patch} (из тега {tag})")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    set_version(sys.argv[1])
