"""Ядро стеганографии: соединение и разделение файлов с футером.

Операции:
- join_files: копирует носитель, дописывает контейнер, затем футер
  с зашифрованными метаданными.
- split_file: читает футер, сверяет хеш носителя, отрезает контейнер.
- generate_output_path: генерирует правдоподобное имя выходного файла.
"""

from __future__ import annotations

import uuid
from enum import Enum, auto
from pathlib import Path

from .config import CHUNK_SIZE
from .exceptions import FileOperationError, FooterError, ValidationError
from .footer import pack_footer, unpack_footer


class NamingStrategy(Enum):
    """Стратегия именования выходного файла."""

    WINDOWS_STYLE = auto()
    """Числовой суффикс: photo.jpg → photo (2).jpg."""

    UUID = auto()
    """Случайный UUID: output_a1b2c3d4.bin."""

    SAME_AS_CARRIER = auto()
    """Сохраняет расширение носителя (для правдоподобия)."""


def generate_output_path(
    carrier_path: str | Path,
    output_dir: str | Path | None = None,
    strategy: NamingStrategy = NamingStrategy.WINDOWS_STYLE,
) -> Path:
    """Генерирует правдоподобный путь для выходного файла.

    Стратегия WINDOWS_STYLE подбирает свободное имя с числовым
    суффиксом: photo.jpg → photo (2).jpg, photo (3).jpg и т.д.

    Стратегия UUID генерирует имя с коротким UUID (первые 8 символов),
    что полезно для максимальной анонимности.

    Стратегия SAME_AS_CARRIER сохраняет расширение носителя,
    но добавляет '_joined' перед расширением.

    Args:
        carrier_path: Путь к исходному файлу-носителю.
        output_dir: Директория для выходного файла. Если None —
                    рядом с носителем.
        strategy: Стратегия именования.

    Returns:
        Путь к выходному файлу.

    Raises:
        ValidationError: При некорректных параметрах.
    """
    carrier = Path(carrier_path)
    base_dir = Path(output_dir) if output_dir else carrier.parent

    if not carrier.exists():
        raise ValidationError(
            f"Файл-носитель не найден: {carrier}"
        )

    if strategy is NamingStrategy.UUID:
        short_uuid = uuid.uuid4().hex[:8]
        stem = f"output_{short_uuid}"
        return base_dir / f"{stem}.bin"

    if strategy is NamingStrategy.SAME_AS_CARRIER:
        stem = carrier.stem
        suffix = carrier.suffix
        candidate = base_dir / f"{stem}_joined{suffix}"
        return candidate

    # WINDOWS_STYLE: числовой суффикс
    stem = carrier.stem
    suffix = carrier.suffix
    candidate = base_dir / f"{stem}{suffix}"
    if not candidate.exists():
        return candidate

    counter = 2
    while True:
        candidate = base_dir / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def join_files(
    carrier_path: str | Path,
    container_path: str | Path,
    output_path: str | Path,
    password: str,
) -> Path:
    """Соединяет носитель и контейнер в один файл с зашифрованным футером.

    Процесс:
    1. Копирует носитель в output_path.
    2. Дописывает контейнер в конец output_path.
    3. Формирует и дописывает зашифрованный футер с метаданными.

    Args:
        carrier_path: Путь к файлу-носителю.
        container_path: Путь к файлу-контейнеру.
        output_path: Путь для сохранения собранного файла.
        password: Парольная фраза для шифрования футера.

    Returns:
        Path к созданному файлу.

    Raises:
        ValidationError: При некорректных путях.
        FileOperationError: При ошибке записи.
        FooterError: При ошибке формирования футера.
    """
    carrier = Path(carrier_path)
    container = Path(container_path)
    output = Path(output_path)

    # Валидация входных параметров
    _validate_paths(carrier, container, output)

    try:
        # 1. Копируем носитель
        _copy_file(carrier, output)

        # 2. Дописываем контейнер
        _append_file(container, output)

        # 3. Формируем и дописываем футер
        footer = pack_footer(str(carrier), str(container), password)
        with open(output, "ab") as fh:
            fh.write(footer)

        return output

    except (FooterError, FileOperationError):
        raise
    except OSError as exc:
        raise FileOperationError(
            f"Ошибка при соединении файлов: {exc}"
        ) from exc


def split_file(
    combined_path: str | Path,
    output_dir: str | Path,
    password: str,
) -> tuple[Path, dict]:
    """Разделяет собранный файл на носитель и контейнер.

    Процесс:
    1. Читает и расшифровывает футер.
    2. Проверяет SHA-256 хеш части носителя в файле.
    3. Отрезает контейнер, сохраняет в output_dir.

    Args:
        combined_path: Путь к собранному файлу.
        output_dir: Директория для сохранения контейнера.
        password: Парольная фраза для расшифровки футера.

    Returns:
        Кортеж (путь_к_контейнеру, словарь_метаданных).

    Raises:
        ValidationError: При некорректных путях.
        FooterError: При отсутствии или повреждении футера.
        CryptoError: При неверном пароле.
        FileOperationError: При ошибке записи.
    """
    import hashlib

    combined = Path(combined_path)
    out_dir = Path(output_dir)

    if not combined.exists():
        raise ValidationError(f"Файл не найден: {combined}")

    # 1. Извлекаем метаданные из футера
    metadata = unpack_footer(str(combined), password)
    carrier_size = metadata["carrier_size"]
    container_size = metadata["container_size"]
    expected_hash = metadata["carrier_hash_sha256"]

    combined_size = combined.stat().st_size
    footer_size = _compute_footer_size(combined)

    # Проверяем, что размеры сходятся
    expected_total = carrier_size + container_size + footer_size
    if combined_size != expected_total:
        raise FooterError(
            f"Размер файла ({combined_size}) не соответствует "
            f"ожидаемому ({expected_total}). Файл мог быть изменён."
        )

    # 2. Проверяем SHA-256 части носителя (первые carrier_size байт)
    sha256 = hashlib.sha256()
    with open(combined, "rb") as fh:
        remaining = carrier_size
        while remaining > 0:
            chunk_size = min(CHUNK_SIZE, remaining)
            chunk = fh.read(chunk_size)
            if not chunk:
                break
            sha256.update(chunk)
            remaining -= len(chunk)

    actual_hash = sha256.hexdigest()
    if actual_hash != expected_hash:
        raise FooterError(
            "Хеш носителя не совпадает. Файл-носитель был изменён "
            "после сборки."
        )

    # 3. Извлекаем контейнер
    container_name = f"container_{uuid.uuid4().hex[:8]}"
    container_path = out_dir / container_name

    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        with open(combined, "rb") as src_fh:
            src_fh.seek(carrier_size)
            with open(container_path, "wb") as dst_fh:
                remaining = container_size
                while remaining > 0:
                    chunk_size = min(CHUNK_SIZE, remaining)
                    chunk = src_fh.read(chunk_size)
                    if not chunk:
                        break
                    dst_fh.write(chunk)
                    remaining -= len(chunk)
    except OSError as exc:
        raise FileOperationError(
            f"Ошибка при извлечении контейнера: {exc}"
        ) from exc

    return container_path, metadata


def _validate_paths(
    carrier: Path, container: Path, output: Path
) -> None:
    """Валидирует входные пути для операции соединения."""
    if not carrier.exists():
        raise ValidationError(
            f"Файл-носитель не найден: {carrier}"
        )
    if not container.exists():
        raise ValidationError(
            f"Файл-контейнер не найден: {container}"
        )
    if carrier.resolve() == container.resolve():
        raise ValidationError(
            "Файл-носитель и контейнер не могут быть одним файлом"
        )
    if output.exists():
        raise FileOperationError(
            f"Выходной файл уже существует: {output}"
        )


def _copy_file(src: Path, dst: Path) -> None:
    """Потоково копирует файл (не загружая в память)."""
    try:
        with open(src, "rb") as fh_src, open(dst, "wb") as fh_dst:
            while True:
                chunk = fh_src.read(CHUNK_SIZE)
                if not chunk:
                    break
                fh_dst.write(chunk)
    except OSError as exc:
        raise FileOperationError(
            f"Ошибка копирования {src} → {dst}: {exc}"
        ) from exc


def _append_file(src: Path, dst: Path) -> None:
    """Дописывает src в конец dst потоково."""
    try:
        with open(src, "rb") as fh_src, open(dst, "ab") as fh_dst:
            while True:
                chunk = fh_src.read(CHUNK_SIZE)
                if not chunk:
                    break
                fh_dst.write(chunk)
    except OSError as exc:
        raise FileOperationError(
            f"Ошибка дописывания {src} → {dst}: {exc}"
        ) from exc


def _compute_footer_size(combined: Path) -> int:
    """Вычисляет полный размер футера в файле."""
    import struct

    from .config import FOOTER_HEADER_SIZE

    with open(combined, "rb") as fh:
        fh.seek(-FOOTER_HEADER_SIZE, 2)
        header = fh.read(FOOTER_HEADER_SIZE)
    _, _, _, payload_len = struct.unpack(">4sHHI", header)
    return FOOTER_HEADER_SIZE + payload_len
