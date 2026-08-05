"""Версионирование hideMyLute — единый источник версии приложения.

Схема версий — семантическое версионирование MAJOR.MINOR.PATCH:

- **MAJOR** — несовместимые изменения формата футера или публичного API.
- **MINOR** — новые возможности (новая функция, новая вкладка UI).
- **PATCH** — количество изменений (исправлений и доработок) с момента
  предыдущего минорного релиза.

История изменений ведётся в ``CHANGELOG.md``; здесь хранится только
текущая версия. При каждом новом изменении PATCH увеличивается на 1;
при появлении новой возможности увеличивается MINOR, а PATCH сбрасывается
в 0; несовместимое изменение формата увеличивает MAJOR.
"""

from __future__ import annotations

__all__ = [
    "VERSION",
    "VERSION_MAJOR",
    "VERSION_MINOR",
    "VERSION_PATCH",
    "VERSION_STRING",
]

VERSION_MAJOR: int = 3
"""Основная версия — несовместимые изменения формата/API."""

VERSION_MINOR: int = 1
"""Минорная версия — новые возможности с предыдущего релиза."""

VERSION_PATCH: int = 6
"""Количество изменений с предыдущего минорного релиза."""

VERSION: tuple[int, int, int] = (
    VERSION_MAJOR,
    VERSION_MINOR,
    VERSION_PATCH,
)
"""Кортеж компонентов версии (MAJOR, MINOR, PATCH)."""

VERSION_STRING: str = ".".join(str(part) for part in VERSION)
"""Строковое представление версии: ``MAJOR.MINOR.PATCH``."""
