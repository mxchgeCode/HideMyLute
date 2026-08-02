"""Криптографический модуль hideMyLute.

Реализует:
- PBKDF2-HMAC-SHA256 для безопасной деривации ключа из пароля
  (600 000 итераций, согласно OWASP 2023).
- AES-256-GCM для аутентифицированного шифрования с проверкой
  целостности и подлинности данных.
"""

from __future__ import annotations

import os

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

from .config import (
    AES_KEY_SIZE,
    AES_NONCE_SIZE,
    PBKDF2_ITERATIONS,
    PBKDF2_SALT_SIZE,
)
from .exceptions import CryptoError


def derive_key(password: str, salt: bytes | None = None) -> tuple[bytes, bytes]:
    """Извлекает 256-битный AES-ключ из пароля с помощью PBKDF2-HMAC-SHA256.

    Если соль не предоставлена, генерирует новую криптографически
    безопасную случайную соль.

    Args:
        password: Парольная фраза пользователя.
        salt: 32-байтовая соль. Если None — генерируется новая.

    Returns:
        Кортеж (key: 32 байта, salt: 32 байта).

    Raises:
        CryptoError: При ошибке деривации ключа.
    """
    if not password:
        raise CryptoError("Пароль не может быть пустым")

    if salt is None:
        salt = os.urandom(PBKDF2_SALT_SIZE)
    elif len(salt) != PBKDF2_SALT_SIZE:
        raise CryptoError(
            f"Соль должна быть длиной {PBKDF2_SALT_SIZE} байт"
        )

    try:
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=AES_KEY_SIZE,
            salt=salt,
            iterations=PBKDF2_ITERATIONS,
        )
        key = kdf.derive(password.encode("utf-8"))
        return key, salt
    except Exception as exc:
        raise CryptoError(
            f"Ошибка деривации ключа: {exc}"
        ) from exc


def encrypt_aes_gcm(
    plaintext: bytes, key: bytes, associated_data: bytes | None = None
) -> bytes:
    """Шифрует данные с помощью AES-256-GCM.

    Формат вывода: nonce (12 байт) || ciphertext (с тегом GCM).

    AES-GCM обеспечивает одновременно конфиденциальность, целостность
    и аутентичность данных. Тег аутентификации (16 байт) встроен
    в ciphertext библиотекой cryptography.

    Args:
        plaintext: Открытые данные для шифрования.
        key: 32-байтовый AES-ключ.
        associated_data: Ассоциированные данные (AAD), не шифруются,
                         но проверяются на целостность.

    Returns:
        nonce (12 байт) + ciphertext (с тегом GCM).

    Raises:
        CryptoError: При ошибке шифрования.
    """
    if len(key) != AES_KEY_SIZE:
        raise CryptoError(
            f"Ключ должен быть длиной {AES_KEY_SIZE} байт"
        )

    nonce = os.urandom(AES_NONCE_SIZE)
    try:
        aesgcm = AESGCM(key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data)
        return nonce + ciphertext
    except Exception as exc:
        raise CryptoError(f"Ошибка шифрования AES-GCM: {exc}") from exc


def decrypt_aes_gcm(
    encrypted_data: bytes, key: bytes, associated_data: bytes | None = None
) -> bytes:
    """Расшифровывает данные, зашифрованные AES-256-GCM.

    Ожидаемый формат: nonce (12 байт) || ciphertext (с тегом GCM).

    При неверном ключе, повреждении данных или подделке
    библиотека cryptography выбрасывает InvalidTag — функция
    перехватывает его и выбрасывает CryptoError.

    Args:
        encrypted_data: nonce + ciphertext.
        key: 32-байтовый AES-ключ.
        associated_data: Ассоциированные данные (AAD).

    Returns:
        Расшифрованные данные (plaintext).

    Raises:
        CryptoError: При неверном ключе или повреждении данных.
    """
    if len(key) != AES_KEY_SIZE:
        raise CryptoError(
            f"Ключ должен быть длиной {AES_KEY_SIZE} байт"
        )

    if len(encrypted_data) < AES_NONCE_SIZE + 16:
        raise CryptoError("Зашифрованные данные слишком короткие")

    nonce = encrypted_data[:AES_NONCE_SIZE]
    ciphertext = encrypted_data[AES_NONCE_SIZE:]

    try:
        aesgcm = AESGCM(key)
        plaintext = aesgcm.decrypt(nonce, ciphertext, associated_data)
        return plaintext
    except Exception as exc:
        raise CryptoError(
            "Неверный пароль или данные повреждены"
        ) from exc
