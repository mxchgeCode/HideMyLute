"""Оценка надёжности пароля.

Использует оценку энтропии (длина × log2 размера алфавита) с учётом
штрафов за повторяющиеся символы, последовательности и словарные пароли.
"""

from __future__ import annotations

import math
import re
from enum import Enum

from .config import MIN_PASSWORD_LENGTH

_LOWER_RE = re.compile(r"[a-zа-яё]")
_UPPER_RE = re.compile(r"[A-ZА-ЯЁ]")
_DIGIT_RE = re.compile(r"\d")
_SYMBOL_RE = re.compile(r"[^a-zA-Zа-яА-ЯЁё0-9\s]")

_REPEAT_RE = re.compile(r"(.)\1{2,}")

# Типичные последовательности на клавиатуре и линейные цепочки
_SEQUENCE_RE = re.compile(
    "|".join(
        re.escape(seq)
        for seq in (
            "123", "234", "345", "456", "567", "678", "789", "890",
            "abc", "bcd", "cde", "def", "efg", "fgh", "ghi", "hij",
            "qwe", "wer", "ert", "rty", "tyu", "yui", "uio", "iop",
            "asd", "sdf", "dfg", "fgh", "ghj", "hjk", "jkl",
            "zxc", "xcv", "cvb", "vbn", "bnm",
            "qaz", "wsx", "edc", "rfv", "tgb", "yhn", "ujm",
            "1qaz", "2wsx", "3edc", "4rfv", "5tgb", "6yhn",
            "йцу", "цук", "уке", "кен", "енг", "нгш", "гшщ",
        )
    )
)

# Часто используемые пароли и словарные слова
_COMMON_PASSWORDS: frozenset[str] = frozenset({
    "password", "passw0rd", "p@ssw0rd", "password1", "password123",
    "123456", "1234567", "12345678", "123456789", "1234567890",
    "qwerty", "qwerty123", "qwertyuiop", "abc123", "admin", "admin123",
    "letmein", "welcome", "iloveyou", "monkey", "dragon", "master",
    "football", "shadow", "sunshine", "princess", "superman", "batman",
    "trustno1", "loveme", "whatever", "test", "guest", "root",
    "hello", "secret", "pass", "123123", "123321", "654321",
    "000000", "111111", "11111111", "222222", "88888888",
    "qazwsx", "zxcvbn", "пароль", "привет", "любовь", "мама",
})

_ENTROPY_OK: float = 35.0
_ENTROPY_STRONG: float = 60.0


class Strength(Enum):
    """Уровень надёжности пароля."""

    WEAK = "weak"
    OK = "ok"
    STRONG = "strong"


def assess_password_strength(password: str) -> Strength:
    """Оценивает надёжность пароля.

    Args:
        password: Проверяемый пароль.

    Returns:
        Уровень надёжности: WEAK, OK или STRONG.
    """
    length = len(password)
    if length < MIN_PASSWORD_LENGTH:
        return Strength.WEAK

    pool = 0
    if _LOWER_RE.search(password):
        pool += 26
    if _UPPER_RE.search(password):
        pool += 26
    if _DIGIT_RE.search(password):
        pool += 10
    if _SYMBOL_RE.search(password):
        pool += 33

    entropy = length * math.log2(max(pool, 1))

    unique_ratio = len(set(password)) / length
    if unique_ratio < 0.3:
        entropy *= 0.7
    elif unique_ratio < 0.5:
        entropy *= 0.8
    if _REPEAT_RE.search(password):
        entropy *= 0.85
    lowered = password.lower()
    if _SEQUENCE_RE.search(lowered):
        entropy *= 0.8
    if _contains_common_password(lowered):
        entropy *= 0.6

    # Короткие пароли не могут быть надёжными
    if length < 6:
        return Strength.OK if entropy >= _ENTROPY_OK else Strength.WEAK

    if entropy >= _ENTROPY_STRONG:
        return Strength.STRONG
    if entropy >= _ENTROPY_OK:
        return Strength.OK
    return Strength.WEAK


def _contains_common_password(lowered: str) -> bool:
    """True, если пароль содержит часто используемое слово-пароль.

    Слово учитывается только если оно составляет заметную часть пароля,
    иначе обычное слово внутри случайной строки не даёт штраф.
    """
    min_len = min(8, int(len(lowered) * 0.6))
    for word in _COMMON_PASSWORDS:
        if len(word) >= min_len and word in lowered:
            return True
    return False
