"""Тесты криптографического модуля."""

from __future__ import annotations

import pytest

from hideMyLute.config import AES_KEY_SIZE, PBKDF2_SALT_SIZE
from hideMyLute.crypto import (
    decrypt_aes_gcm,
    derive_key,
    encrypt_aes_gcm,
)
from hideMyLute.exceptions import CryptoError


class TestDeriveKey:
    """Тесты функции derive_key."""

    def test_derive_without_salt_returns_key_and_salt(self) -> None:
        """Без соли: возвращает ключ 32 байта + соль 32 байта."""
        key, salt = derive_key("password123")
        assert len(key) == AES_KEY_SIZE
        assert len(salt) == PBKDF2_SALT_SIZE

    def test_derive_with_provided_salt_is_deterministic(self) -> None:
        """С заданной солью: одинаковый пароль + соль = одинаковый ключ."""
        salt = b"\x01" * PBKDF2_SALT_SIZE
        key1, _ = derive_key("password123", salt)
        key2, _ = derive_key("password123", salt)
        assert key1 == key2

    def test_different_passwords_produce_different_keys(self) -> None:
        """Разные пароли с одной солью: разные ключи."""
        salt = b"\x02" * PBKDF2_SALT_SIZE
        key1, _ = derive_key("password1", salt)
        key2, _ = derive_key("password2", salt)
        assert key1 != key2

    def test_empty_password_raises_crypto_error(self) -> None:
        """Пустой пароль: CryptoError."""
        with pytest.raises(CryptoError, match="не может быть пустым"):
            derive_key("")

    def test_wrong_salt_size_raises_crypto_error(self) -> None:
        """Соль неверной длины: CryptoError."""
        with pytest.raises(CryptoError, match="Соль должна быть длиной"):
            derive_key("password", b"short")

    def test_too_long_password_raises_crypto_error(self) -> None:
        """Пароль длиннее MAX_PASSWORD_LENGTH: CryptoError (DoS-защита)."""
        from hideMyLute.config import MAX_PASSWORD_LENGTH

        with pytest.raises(CryptoError, match="слишком длинный"):
            derive_key("p" * (MAX_PASSWORD_LENGTH + 1))


class TestEncryptDecryptAesGcm:
    """Тесты AES-256-GCM шифрования/расшифрования."""

    def test_roundtrip_encrypt_decrypt(self) -> None:
        """Данные после encrypt→decrypt совпадают с оригиналом."""
        key, _ = derive_key("test_password")
        plaintext = b"Hello, World! This is a test."
        encrypted = encrypt_aes_gcm(plaintext, key)
        decrypted = decrypt_aes_gcm(encrypted, key)
        assert decrypted == plaintext

    def test_wrong_key_fails_decryption(self) -> None:
        """Неверный ключ: CryptoError."""
        key1, _ = derive_key("password1")
        key2, _ = derive_key("password2")
        plaintext = b"Secret data"
        encrypted = encrypt_aes_gcm(plaintext, key1)
        with pytest.raises(
            CryptoError, match="Неверный пароль или данные повреждены"
        ):
            decrypt_aes_gcm(encrypted, key2)

    def test_tampered_data_fails_decryption(self) -> None:
        """Повреждённый ciphertext: CryptoError."""
        key, _ = derive_key("password")
        plaintext = b"Secret data"
        encrypted = bytearray(encrypt_aes_gcm(plaintext, key))
        # Поменяем байт в ciphertext (после nonce)
        encrypted[-1] ^= 0xFF
        with pytest.raises(
            CryptoError, match="Неверный пароль или данные повреждены"
        ):
            decrypt_aes_gcm(bytes(encrypted), key)

    def test_encrypt_with_aad(self) -> None:
        """Шифрование с ассоциированными данными: roundtrip."""
        key, _ = derive_key("password")
        plaintext = b"Data with AAD"
        aad = b"associated data"
        encrypted = encrypt_aes_gcm(plaintext, key, aad)
        decrypted = decrypt_aes_gcm(encrypted, key, aad)
        assert decrypted == plaintext

    def test_wrong_aad_fails_decryption(self) -> None:
        """Неверный AAD: CryptoError."""
        key, _ = derive_key("password")
        plaintext = b"Data with AAD"
        aad = b"correct aad"
        wrong_aad = b"wrong aad"
        encrypted = encrypt_aes_gcm(plaintext, key, aad)
        with pytest.raises(
            CryptoError, match="Неверный пароль или данные повреждены"
        ):
            decrypt_aes_gcm(encrypted, key, wrong_aad)

    def test_encrypted_output_size(self) -> None:
        """Размер зашифрованных данных = nonce(12) + plaintext + tag(16)."""
        key, _ = derive_key("password")
        plaintext = b"A" * 100
        encrypted = encrypt_aes_gcm(plaintext, key)
        # 12 nonce + 100 plaintext + 16 GCM tag = 128
        assert len(encrypted) == 12 + 100 + 16

    def test_empty_plaintext(self) -> None:
        """Шифрование пустых данных: roundtrip."""
        key, _ = derive_key("password")
        encrypted = encrypt_aes_gcm(b"", key)
        decrypted = decrypt_aes_gcm(encrypted, key)
        assert decrypted == b""

    def test_decrypt_too_short_data_raises_error(self) -> None:
        """Слишком короткие данные: CryptoError."""
        key, _ = derive_key("password")
        with pytest.raises(
            CryptoError, match="слишком короткие"
        ):
            decrypt_aes_gcm(b"short", key)
