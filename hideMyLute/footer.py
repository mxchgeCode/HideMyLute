"""Модуль упаковки/распаковки зашифрованного футера.

Футер — это структура в конце собранного файла, содержащая
зашифрованные метаданные, необходимые для разделения.

СТРУКТУРА ФУТЕРА (все числа — big-endian):
┌──────────────────────────────────────────────────────┐
│ Payload: footer_data_len байт                         │
│  = salt(32) || AES-256-GCM(JSON {                     │
│      "carrier_size": int,                             │
│      "container_size": int,                           │
│      "carrier_hash_sha256": hex str,                  │
│      "timestamp": ISO 8601 str                        │
│    })                                                 │
│  Формат: salt(32) || nonce(12) || ciphertext_with_tag │
├──────────────────────────────────────────────────────┤
│ Заголовок футера (FOOTER_HEADER_SIZE = 12 байт)       │
│  • magic_bytes:     4 байта  (b'HMLF')               │
│  • version:          2 байта  (uint16, сейчас 1)      │
│  • flags:            2 байта  (uint16, зарезервировано)│
│  • footer_data_len:  4 байта  (uint32, длина payload) │
└──────────────────────────────────────────────────────┘

Заголовок расположен в ПОСЛЕДНИХ 12 байтах файла, что позволяет
найти его простым seek(-12, 2) без знания полного размера футера.
"""

from __future__ import annotations

import json
import struct
from datetime import datetime, timezone
from pathlib import Path

from .config import (
    FOOTER_HEADER_SIZE,
    FOOTER_VERSION,
    MAGIC_BYTES,
)
from .crypto import decrypt_aes_gcm, derive_key, encrypt_aes_gcm
from .exceptions import FooterError


def pack_footer(
    carrier_path: str | Path,
    container_path: str | Path,
    password: str,
) -> bytes:
    """Формирует зашифрованный футер для добавления в конец файла.

    Вычисляет SHA-256 хеш файла-носителя, формирует JSON с метаданными,
    шифрует его с помощью ключа, извлечённого из пароля.

    Args:
        carrier_path: Путь к файлу-носителю.
        container_path: Путь к файлу-контейнеру.
        password: Парольная фраза пользователя.

    Returns:
        Полный футер (заголовок + зашифрованный payload).

    Raises:
        FooterError: При ошибке формирования футера.
    """
    carrier = Path(carrier_path)
    container = Path(container_path)

    if not carrier.exists():
        raise FooterError(f"Файл-носитель не найден: {carrier}")
    if not container.exists():
        raise FooterError(f"Файл-контейнер не найден: {container}")


    carrier_size = carrier.stat().st_size
    container_size = container.stat().st_size

    # SHA-256 хеш носителя — для проверки целостности при разделении
    carrier_hash = _sha256_file(carrier)

    metadata = {
        "carrier_size": carrier_size,
        "container_size": container_size,
        "carrier_hash_sha256": carrier_hash,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    metadata_json = json.dumps(metadata, ensure_ascii=False).encode("utf-8")

    # Шифруем метаданные
    key, salt = derive_key(password)
    encrypted_payload = salt + encrypt_aes_gcm(metadata_json, key)

    # Формируем заголовок футера
    header = struct.pack(
        ">4sHHI",
        MAGIC_BYTES,                    # 4 байта magic
        FOOTER_VERSION,                 # 2 байта version
        0,                              # 2 байта flags (зарезерв.)
        len(encrypted_payload),         # 4 байта длина payload
    )

    # Заголовок ПОСЛЕ payload — для чтения с конца файла
    return encrypted_payload + header


def unpack_footer(
    combined_path: str | Path,
    password: str,
) -> dict:
    """Извлекает и расшифровывает метаданные из футера файла.

    Ищет футер в конце файла по сигнатуре magic bytes,
    проверяет версию формата, расшифровывает payload.

    Args:
        combined_path: Путь к собранному файлу с футером.
        password: Парольная фраза пользователя.

    Returns:
        Словарь с ключами: carrier_size, container_size,
        carrier_hash_sha256, timestamp.

    Raises:
        FooterError: При отсутствии футера или ошибке формата.
        CryptoError: При неверном пароле или повреждении данных.
    """
    combined = Path(combined_path)

    if not combined.exists():
        raise FooterError(f"Файл не найден: {combined}")

    file_size = combined.stat().st_size

    # Читаем заголовок футера (последние FOOTER_HEADER_SIZE байт)
    with open(combined, "rb") as fh:
        # Сначала читаем заголовок
        fh.seek(-FOOTER_HEADER_SIZE, 2)
        header_data = fh.read(FOOTER_HEADER_SIZE)

    if len(header_data) < FOOTER_HEADER_SIZE:
        raise FooterError("Файл слишком мал для содержания футера")

    magic, version, _flags, payload_len = struct.unpack(
        ">4sHHI", header_data
    )

    if magic != MAGIC_BYTES:
        raise FooterError(
            "Футер hideMyLute не найден в файле "
            "(неверная сигнатура)"
        )

    if version != FOOTER_VERSION:
        raise FooterError(
            f"Несовместимая версия футера: {version} "
            f"(ожидается {FOOTER_VERSION})"
        )

    total_footer_size = FOOTER_HEADER_SIZE + payload_len
    if total_footer_size > file_size:
        raise FooterError(
            "Заявленный размер футера превышает размер файла"
        )

    # Читаем payload
    with open(combined, "rb") as fh:
        fh.seek(-total_footer_size, 2)
        payload_data = fh.read(payload_len)

    # Извлекаем соль (первые 32 байта) и зашифрованные данные
    salt = payload_data[:32]
    encrypted_metadata = payload_data[32:]

    # Деривируем ключ и расшифровываем
    key, _ = derive_key(password, salt)
    metadata_json = decrypt_aes_gcm(encrypted_metadata, key)

    try:
        metadata = json.loads(metadata_json.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise FooterError(
            "Не удалось распарсить метаданные футера"
        ) from exc

    required_keys = {"carrier_size", "container_size", "carrier_hash_sha256"}
    missing = required_keys - set(metadata.keys())
    if missing:
        raise FooterError(
            f"В метаданных футера отсутствуют поля: {missing}"
        )

    return metadata


def _sha256_file(filepath: Path) -> str:
    """Вычисляет SHA-256 хеш файла потоково (не загружая в память).

    Args:
        filepath: Путь к файлу.

    Returns:
        Хеш в виде hex-строки (64 символа).
    """
    import hashlib

    sha256 = hashlib.sha256()
    with open(filepath, "rb") as fh:
        while True:
            chunk = fh.read(1024 * 1024)  # 1 МБ буфер
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()
