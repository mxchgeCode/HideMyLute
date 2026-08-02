"""Тесты оценки надёжности пароля."""

from __future__ import annotations

import pytest

from hideMyLute.password_strength import (
    Strength,
    assess_password_strength,
)


class TestPasswordStrength:
    """Тесты функции assess_password_strength."""

    @pytest.mark.parametrize(
        "password",
        [
            "",
            "1",
            "12",
            "123",
            "aB3",
        ],
    )
    def test_too_short_is_weak(self, password: str) -> None:
        """Короче минимальной длины — слабый."""
        assert assess_password_strength(password) is Strength.WEAK

    @pytest.mark.parametrize(
        "password",
        [
            "password",
            "123456",
            "12345678",
            "qwerty",
            "qwerty123",
            "abc123",
            "letmein",
            "admin",
            "111111",
            "пароль",
            "Password1",
            "passw0rd",
        ],
    )
    def test_common_passwords_are_weak(self, password: str) -> None:
        """Часто используемые пароли — слабые."""
        assert assess_password_strength(password) is Strength.WEAK

    @pytest.mark.parametrize(
        "password",
        [
            "aaaaaaaa",
            "aaaaaaa1",
            "123456789",
            "abcdefg",
        ],
    )
    def test_repeated_or_sequential_is_weak(self, password: str) -> None:
        """Повторы и последовательности — слабые."""
        assert assess_password_strength(password) is Strength.WEAK

    @pytest.mark.parametrize(
        "password",
        [
            "Tr0ub4dor&3x",
            "Kj7#dF2$qZx9",
            "Xk9#mQ4&zR7$aB",
            "correct horse battery staple",
        ],
    )
    def test_strong_passwords_are_strong(self, password: str) -> None:
        """Разнообразные длинные пароли — надёжные."""
        assert assess_password_strength(password) is Strength.STRONG

    @pytest.mark.parametrize(
        "password",
        [
            "mnopqrstuvwx",
            "abcdefghijkl",
            "zyxwvutsrqpn",
            "1qazxsw23edc",
        ],
    )
    def test_medium_passwords_are_ok(self, password: str) -> None:
        """Пароли средней сложности длиной от 12 символов — приемлемые."""
        assert assess_password_strength(password) is Strength.OK

    def test_short_varied_password_is_not_strong(self) -> None:
        """Короткий пароль даже с разнообразием не может быть надёжным."""
        result = assess_password_strength("aB3$eF")
        assert result is not Strength.STRONG

    def test_passwords_shorter_than_minimum_are_weak(self) -> None:
        """Короче минимальной длины (12) — всегда слабый, даже разнообразный."""
        assert assess_password_strength("Tr0ub4dor") is Strength.WEAK
        assert assess_password_strength("Abcd1234!") is Strength.WEAK
