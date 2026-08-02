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
│      "container_hash_sha256": hex str,                │
│      "container_name": str                            │
│    })                                                 │
│  Формат: salt(32) || nonce(12) || ciphertext_with_tag │
├──────────────────────────────────────────────────────┤
│ Заголовок футера (FOOTER_HEADER_SIZE = 12 байт)       │
│  • random_bytes:    4 байта  (случайные, без сигнатуры)│
│  • version:          2 байта  (uint16, сейчас 2)      │
│  • flags:            2 байта  (uint16, зарезервировано)│
│  • footer_data_len:  4 байта  (uint32, длина payload) │
└──────────────────────────────────────────────────────┘

Заголовок расположен в ПОСЛЕДНИХ 12 байтах файла.

Детекция футера v2 (версия >= 2):
- magic-поле заполнено случайными байтами и НЕ содержит детектируемой
  сигнатуры (в отличие от v1 с фиксированным b'HMLF').
- Наличие футера подтверждается аутентифицированной расшифровкой
  payload (GCM-тег), поэтому для файла без футера и для неверного
  пароля возвращается неразличимое сообщение «неверный пароль или
  данные повреждены» — что согласуется с парадигмой правдоподобного
  отрицания.

Обратная совместимость: файлы v1 (magic b'HMLF') читаются по-прежнему.
"""

from __future__ import annotations

import hashlib
import json
import os
import struct
from pathlib import Path

from .config import (
    CHUNK_SIZE,
    FOOTER_HEADER_SIZE,
    FOOTER_VERSION,
    FOOTER_VERSION_V1,
    MAGIC_BYTES,
    MAX_FOOTER_PAYLOAD_LEN,
    MIN_FOOTER_PAYLOAD_LEN,
    PBKDF2_SALT_SIZE,
)
from .crypto import decrypt_aes_gcm, derive_key, encrypt_aes_gcm
from .exceptions import FooterError


def pack_footer(
    carrier_path: str | Path,
    container_path: str | Path,
    password: str,
    *,
    carrier_size: int | None = None,
    container_size: int | None = None,
    carrier_hash: str | None = None,
    container_hash: str | None = None,
    container_name: str | None = None,
) -> bytes:
    """Формирует зашифрованный футер для добавления в конец файла.

    Формирует JSON с метаданными (размеры, хеши носителя и контейнера,
    имя контейнера), шифрует его с помощью ключа, извлечённого из
    пароля. Время сборки (timestamp) в метаданные не включается —
    метка времени раскрывала бы момент сборки файла.

    Args:
        carrier_path: Путь к файлу-носителю.
        container_path: Путь к файлу-контейнеру.
        password: Парольная фраза пользователя.
        carrier_size: Заранее вычисленный размер носителя (для
            устранения TOCTOU между копированием и хешированием).
        container_size: Заранее вычисленный размер контейнера.
        carrier_hash: Заранее вычисленный SHA-256 носителя.
        container_hash: Заранее вычисленный SHA-256 контейнера.
        container_name: Имя контейнера для восстановления при разделении.

    Returns:
        Полный футер (заголовок + зашифрованный payload).

    Raises:
        FooterError: При ошибке формирования футера.
    """
    carrier = Path(carrier_path)
    container = Path(container_path)

    if not carrier.exists():
        raise FooterError(
            f"Файл-носитель не найден: {carrier}",
            msg_key="error_carrier_not_found",
            path=str(carrier),
        )
    if not container.exists():
        raise FooterError(
            f"Файл-контейнер не найден: {container}",
            msg_key="error_container_not_found",
            path=str(container),
        )

    if carrier_size is None:
        carrier_size = carrier.stat().st_size
    if container_size is None:
        container_size = container.stat().st_size
    if carrier_hash is None:
        carrier_hash = sha256_file(carrier)
    if container_hash is None:
        container_hash = sha256_file(container)
    if container_name is None:
        container_name = container.name

    metadata = {
        "carrier_size": carrier_size,
        "container_size": container_size,
        "carrier_hash_sha256": carrier_hash,
        "container_hash_sha256": container_hash,
        "container_name": container_name,
    }
    metadata_json = json.dumps(metadata, ensure_ascii=False).encode("utf-8")

    # Шифруем метаданные
    key, salt = derive_key(password)
    encrypted_payload = salt + encrypt_aes_gcm(metadata_json, key)

    # Случайные байты вместо детектируемой сигнатуры (CRT-06)
    random_magic = os.urandom(4)

    # Формируем заголовок футера
    header = struct.pack(
        ">4sHHI",
        random_magic,                   # 4 байта случайных байт
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

    Детекция футера:
    - файлы v1: проверка фиксированной сигнатуры magic + версии;
    - файлы v2 и произвольные файлы: подтверждение через
      аутентифицированную расшифровку (GCM-тег).

    Args:
        combined_path: Путь к собранному файлу с футером.
        password: Парольная фраза пользователя.

    Returns:
        Словарь с ключами: carrier_size, container_size,
        carrier_hash_sha256 и (для v2) container_hash_sha256,
        container_name.

    Raises:
        FooterError: При отсутствии футера или ошибке формата.
        CryptoError: При неверном пароле или повреждении данных.
    """
    combined = Path(combined_path)

    if not combined.exists():
        raise FooterError(
            f"Файл не найден: {combined}",
            msg_key="error_file_not_found",
            path=str(combined),
        )

    file_size = combined.stat().st_size

    if file_size < FOOTER_HEADER_SIZE:
        raise FooterError(
            "Файл слишком мал для содержания футера",
            msg_key="error_footer_too_small",
        )

    # Читаем заголовок футера (последние FOOTER_HEADER_SIZE байт)
    with open(combined, "rb") as fh:
        fh.seek(-FOOTER_HEADER_SIZE, 2)
        header_data = fh.read(FOOTER_HEADER_SIZE)

    magic, version, _flags, payload_len = struct.unpack(
        ">4sHHI", header_data
    )

    # v1-совместимость: фиксированная сигнатура
    if magic == MAGIC_BYTES:
        if version == FOOTER_VERSION_V1:
            return _unpack_payload(
                combined, file_size, payload_len, password, legacy=True
            )
        if version == FOOTER_VERSION:
            # крайне редкое совпадение случайного magic v2 с b'HMLF'
            return _unpack_payload(
                combined, file_size, payload_len, password, legacy=False
            )
        raise FooterError(
            f"Несовместимая версия футера: {version} "
            f"(ожидается {FOOTER_VERSION})",
            msg_key="error_footer_version",
            version=version,
            expected=FOOTER_VERSION,
        )

    # v2 или случайный файл — детекция через GCM-тег
    return _unpack_payload(
        combined, file_size, payload_len, password, legacy=False
    )


def _unpack_payload(
    combined: Path,
    file_size: int,
    payload_len: int,
    password: str,
    *,
    legacy: bool,
) -> dict:
    """Читает, расшифровывает и валидирует payload футера."""
    total_footer_size = FOOTER_HEADER_SIZE + payload_len

    # Отбраковка заведомо невозможных футеров
    if (
        payload_len < MIN_FOOTER_PAYLOAD_LEN
        or payload_len > MAX_FOOTER_PAYLOAD_LEN
    ):
        raise FooterError(
            "Футер hideMyLute не найден в файле",
            msg_key="error_no_footer",
        )
    if total_footer_size > file_size:
        if legacy:
            raise FooterError(
                "Заявленный размер футера превышает размер файла",
                msg_key="error_footer_too_large",
            )
        raise FooterError(
            "Футер hideMyLute не найден в файле",
            msg_key="error_no_footer",
        )

    # Читаем payload
    with open(combined, "rb") as fh:
        fh.seek(-total_footer_size, 2)
        payload_data = fh.read(payload_len)

    # Извлекаем соль и зашифрованные данные
    salt = payload_data[:PBKDF2_SALT_SIZE]
    encrypted_metadata = payload_data[PBKDF2_SALT_SIZE:]

    # Деривируем ключ и расшифровываем.
    # Для v2 (и случайных файлов) неверный пароль и отсутствие футера
    # неразличимы — оба приводят к CryptoError (правдоподобное отрицание).
    key, _ = derive_key(password, salt)
    metadata_json = decrypt_aes_gcm(encrypted_metadata, key)

    try:
        metadata = json.loads(metadata_json.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise FooterError(
            "Не удалось распарсить метаданные футера",
            msg_key="error_footer_parse",
        ) from exc

    required_keys = {
        "carrier_size",
        "container_size",
        "carrier_hash_sha256",
    }
    missing = required_keys - set(metadata.keys())
    if missing:
        raise FooterError(
            f"В метаданных футера отсутствуют поля: {missing}",
            msg_key="error_footer_fields",
            fields=", ".join(sorted(missing)),
        )

    return metadata


def read_footer_size(combined: str | Path) -> int:
    """Возвращает полный размер футера (payload + заголовок) в файле.

    Централизованная точка чтения размера футера, используемая при
    разделении. Заголовок читается из последних FOOTER_HEADER_SIZE байт.

    Args:
        combined: Путь к собранному файлу.

    Returns:
        Полный размер футера в байтах.

    Raises:
        OSError: При невозможности прочитать файл.
    """
    path = Path(combined)
    with open(path, "rb") as fh:
        fh.seek(-FOOTER_HEADER_SIZE, 2)
        header = fh.read(FOOTER_HEADER_SIZE)
    _magic, _version, _flags, payload_len = struct.unpack(
        ">4sHHI", header
    )
    return FOOTER_HEADER_SIZE + payload_len


def sha256_file(filepath: Path) -> str:
    """Вычисляет SHA-256 хеш файла потоково (не загружая в память).

    Args:
        filepath: Путь к файлу.

    Returns:
        Хеш в виде hex-строки (64 символа).
    """
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as fh:
        while True:
            chunk = fh.read(CHUNK_SIZE)
            if not chunk:
                break
            sha256.update(chunk)
    return sha256.hexdigest()


def sha256_region(filepath: str | Path, start: int, length: int) -> str:
    """Вычисляет SHA-256 фрагмента файла [start, start + length).

    Используется для проверки целостности региона контейнера при
    разделении и для хеширования фактически записанных байт при
    соединении (устраняет TOCTOU).

    Args:
        filepath: Путь к файлу.
        start: Смещение начала фрагмента.
        length: Длина фрагмента.

    Returns:
        Хеш фрагмента в виде hex-строки (64 символа).
    """
    sha256 = hashlib.sha256()
    with open(filepath, "rb") as fh:
        fh.seek(start)
        remaining = length
        while remaining > 0:
            chunk_size = min(CHUNK_SIZE, remaining)
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            sha256.update(chunk)
            remaining -= len(chunk)
    return sha256.hexdigest()
