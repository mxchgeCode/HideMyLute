#!/usr/bin/env python3
"""Автоматический инкремент PATCH версии для CI-сборок.

Переписывает VERSION_* в hideMyLute/_version.py, обновляет pyproject.toml
и CHANGELOG.md. При флаге --commit создаёт коммит и push с [skip ci].
"""

from __future__ import annotations

import re
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION_FILE = ROOT / "hideMyLute" / "_version.py"
PYPROJECT_FILE = ROOT / "pyproject.toml"
CHANGELOG_FILE = ROOT / "CHANGELOG.md"

VERSION_RE = re.compile(r"^VERSION_(MAJOR|MINOR|PATCH): int = (\d+)", re.MULTILINE)
PYPROJECT_VERSION_RE = re.compile(r'^version = "(\d+\.\d+\.\d+)"', re.MULTILINE)


def get_version() -> tuple[int, int, int]:
    text = VERSION_FILE.read_text(encoding="utf-8")
    matches = VERSION_RE.findall(text)
    values = {name: int(val) for name, val in matches}
    return values["MAJOR"], values["MINOR"], values["PATCH"]


def update_version_file(major: int, minor: int, patch: int) -> None:
    text = VERSION_FILE.read_text(encoding="utf-8")
    values = {"MAJOR": major, "MINOR": minor, "PATCH": patch}

    def replace(match: re.Match[str]) -> str:
        name = match.group(1)
        return f"VERSION_{name}: int = {values[name]}"

    new_text, count = VERSION_RE.subn(replace, text)
    if count != 3:
        sys.exit("Не найдены все три константы VERSION_* в hideMyLute/_version.py")
    VERSION_FILE.write_text(new_text, encoding="utf-8")
    print(f"Обновлена версия в _version.py: {major}.{minor}.{patch}")


def update_pyproject(major: int, minor: int, patch: int) -> None:
    text = PYPROJECT_FILE.read_text(encoding="utf-8")
    version_str = f'version = "{major}.{minor}.{patch}"'
    new_text, count = PYPROJECT_VERSION_RE.subn(version_str, text)
    if count != 1:
        sys.exit("Не найдена строка version в pyproject.toml")
    PYPROJECT_FILE.write_text(new_text, encoding="utf-8")
    print(f"Обновлена версия в pyproject.toml: {major}.{minor}.{patch}")


def update_changelog(major: int, minor: int, patch: int) -> None:
    text = CHANGELOG_FILE.read_text(encoding="utf-8")
    version_str = f"{major}.{minor}.{patch}"
    today = date.today().isoformat()

    new_entry = (
        f"## [{version_str}] — {today}\n"
        f"\n"
        f"### Добавлено\n"
        f"\n"
        f"- Автоматический инкремент версии.\n"
        f"\n"
    )

    lines = text.splitlines(keepends=True)
    insert_idx = len(lines)
    for i, line in enumerate(lines):
        if line.startswith("## ["):
            insert_idx = i
            break

    lines.insert(insert_idx, new_entry)
    CHANGELOG_FILE.write_text("".join(lines), encoding="utf-8")
    print(f"Добавлена запись в CHANGELOG.md: {version_str}")


def commit_and_push(version_str: str) -> None:
    try:
        subprocess.run(["git", "config", "user.email", "dev@hidelute.local"], check=True)
        subprocess.run(["git", "config", "user.name", "HideMyLute Dev"], check=True)

        subprocess.run(
            ["git", "add", str(VERSION_FILE), str(PYPROJECT_FILE), str(CHANGELOG_FILE)],
            check=True,
        )

        result = subprocess.run(
            ["git", "diff", "--cached", "--quiet"], capture_output=True
        )
        if result.returncode == 0:
            print("Нет изменений для коммита")
            return

        subprocess.run(
            ["git", "commit", "-m", f"chore: bump version to {version_str} [skip ci]"],
            check=True,
        )
        subprocess.run(["git", "push"], check=True)
        print(f"Зафиксирована версия {version_str}")
    except subprocess.CalledProcessError as e:
        sys.exit(f"Git operation failed (return code {e.returncode}): {e.cmd}")


def main() -> None:
    major, minor, patch = get_version()
    new_patch = patch + 1
    version_str = f"{major}.{minor}.{new_patch}"

    print(f"Текущая версия: {major}.{minor}.{patch}")
    print(f"Новая версия: {version_str}")

    update_version_file(major, minor, new_patch)
    update_pyproject(major, minor, new_patch)
    update_changelog(major, minor, new_patch)

    if "--commit" in sys.argv:
        commit_and_push(version_str)

    print(f"Версия инкрементирована: {version_str}")


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
