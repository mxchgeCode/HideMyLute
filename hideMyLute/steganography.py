"""Ядро стеганографии: соединение и разделение файлов с футером.

Операции:
- join_files: копирует носитель, дописывает контейнер, затем футер
  с зашифрованными метаданными.
- split_file: читает футер, сверяет хеши носителя и контейнера,
  отрезает контейнер.
- generate_output_path: генерирует правдоподобное имя выходного файла.
"""

from __future__ import annotations

import os
import time
import uuid
from enum import Enum, auto
from pathlib import Path

from .config import CHUNK_SIZE, MIN_PASSWORD_LENGTH
from .exceptions import (
    FileOperationError,
    FooterError,
    OperationCancelled,
    ValidationError,
)
from .footer import pack_footer, read_footer_size, sha256_region, unpack_footer
from .logging_config import get_logger

logger = get_logger("steganography")


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
            f"Файл-носитель не найден: {carrier}",
            msg_key="error_carrier_not_found",
            path=str(carrier),
        )

    if strategy is NamingStrategy.UUID:
        short_uuid = uuid.uuid4().hex[:8]
        stem = f"output_{short_uuid}"
        return base_dir / f"{stem}.bin"

    if strategy is NamingStrategy.SAME_AS_CARRIER:
        stem = carrier.stem
        suffix = carrier.suffix
        candidate = base_dir / f"{stem}_joined{suffix}"
        if not candidate.exists():
            return candidate
        counter = 2
        while True:
            candidate = base_dir / f"{stem}_joined ({counter}){suffix}"
            if not candidate.exists():
                return candidate
            counter += 1

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
    cancel_event=None,
) -> Path:
    """Соединяет носитель и контейнер в один файл с зашифрованным футером.

    Процесс:
    1. Копирует носитель во временный файл ``<output>.part``.
    2. Дописывает контейнер и футер во временный файл.
    3. Атомарно переименовывает временный файл в целевой (replace).

    Атомарность гарантирует, что при любой ошибке или отмене операции
    на диске не остаётся частичного файла (важно для правдоподобного
    отрицания): временный файл удаляется в ``except``.

    Хеши носителя и контейнера вычисляются по фактически записанным
    регионам временного файла, а не по исходным файлам (устраняет
    TOCTOU между копированием и хешированием).

    Args:
        carrier_path: Путь к файлу-носителю.
        container_path: Путь к файлу-контейнеру.
        output_path: Путь для сохранения собранного файла.
        password: Парольная фраза для шифрования футера.
        cancel_event: Опциональное событие отмены (threading.Event).

    Returns:
        Path к созданному файлу.

    Raises:
        ValidationError: При некорректных путях.
        FileOperationError: При ошибке записи.
        FooterError: При ошибке формирования футера.
        OperationCancelled: При отмене операции.
    """
    carrier = Path(carrier_path)
    container = Path(container_path)
    output = Path(output_path)

    # Валидация входных параметров
    _validate_paths(carrier, container, output)

    # Политика пароля: слабый пароль недопустим при создании футера.
    # (при разделении минимальная длина не проверяется — это сохраняет
    #  совместимость с legacy-файлами, собранными слабым паролем)
    if len(password) < MIN_PASSWORD_LENGTH:
        raise ValidationError(
            f"Пароль должен быть не менее {MIN_PASSWORD_LENGTH} символов",
            msg_key="error_password_short",
        )

    tmp = output.with_name(output.name + ".part")
    start = time.monotonic()
    logger.info(
        "join: start carrier_size=%d container_size=%d",
        carrier.stat().st_size,
        container.stat().st_size,
    )
    try:
        # 1. Копируем носитель
        _copy_file(carrier, tmp, cancel_event)
        carrier_size = tmp.stat().st_size
        carrier_hash = sha256_region(tmp, 0, carrier_size, cancel_event)

        # 2. Дописываем контейнер
        _append_file(container, tmp, cancel_event)
        container_size = tmp.stat().st_size - carrier_size
        container_hash = sha256_region(
            tmp, carrier_size, container_size, cancel_event
        )

        # 3. Формируем и дописываем футер
        footer = pack_footer(
            str(carrier),
            str(container),
            password,
            carrier_size=carrier_size,
            container_size=container_size,
            carrier_hash=carrier_hash,
            container_hash=container_hash,
            container_name=container.name,
        )
        with open(tmp, "ab") as fh:
            fh.write(footer)

        # 4. Атомарная публикация результата
        tmp.replace(output)
        logger.info(
            "join: done output_size=%d elapsed=%.3fs",
            output.stat().st_size,
            time.monotonic() - start,
        )
        return output

    except OSError as exc:
        # Никаких улик при сбое: удаляем временный файл
        tmp.unlink(missing_ok=True)
        logger.error("join: failed (%s)", type(exc).__name__)
        raise FileOperationError(
            f"Ошибка при соединении файлов: {exc}",
            msg_key="error_join_failed",
            error=str(exc),
        ) from exc
    except BaseException as exc:
        # Никаких улик при сбое или отмене: удаляем временный файл
        tmp.unlink(missing_ok=True)
        logger.error("join: aborted (%s)", type(exc).__name__)
        raise


def split_file(
    combined_path: str | Path,
    output_dir: str | Path,
    password: str,
    cancel_event=None,
) -> tuple[Path, dict]:
    """Разделяет собранный файл на носитель и контейнер.

    Процесс:
    1. Читает и расшифровывает футер.
    2. Проверяет SHA-256 хеши регионов носителя и (для формата v2)
       контейнера.
    3. Отрезает контейнер, сохраняет в output_dir с исходным именем.

    При ошибке или отмене частично записанный файл контейнера удаляется.

    Args:
        combined_path: Путь к собранному файлу.
        output_dir: Директория для сохранения контейнера.
        password: Парольная фраза для расшифровки футера.
        cancel_event: Опциональное событие отмены (threading.Event).

    Returns:
        Кортеж (путь_к_контейнеру, словарь_метаданных).

    Raises:
        ValidationError: При некорректных путях.
        FooterError: При отсутствии или повреждении футера.
        CryptoError: При неверном пароле.
        FileOperationError: При ошибке записи.
        OperationCancelled: При отмене операции.
    """
    combined = Path(combined_path)
    out_dir = Path(output_dir)
    start = time.monotonic()

    if not combined.exists():
        raise ValidationError(
            f"Файл не найден: {combined}",
            msg_key="error_file_not_found",
            path=str(combined),
        )

    # 1. Извлекаем метаданные из футера
    metadata = unpack_footer(str(combined), password)
    carrier_size = metadata["carrier_size"]
    container_size = metadata["container_size"]
    expected_hash = metadata["carrier_hash_sha256"]
    expected_container_hash = metadata.get("container_hash_sha256")

    combined_size = combined.stat().st_size
    footer_size = read_footer_size(combined)

    # Проверяем, что размеры сходятся
    expected_total = carrier_size + container_size + footer_size
    if combined_size != expected_total:
        raise FooterError(
            f"Размер файла ({combined_size}) не соответствует "
            f"ожидаемому ({expected_total}). Файл мог быть изменён.",
            msg_key="error_size_mismatch",
            size=combined_size,
            expected=expected_total,
        )

    # 2. Проверяем SHA-256 региона носителя (первые carrier_size байт)
    actual_hash = sha256_region(
        str(combined), 0, carrier_size, cancel_event
    )
    if actual_hash != expected_hash:
        raise FooterError(
            "Хеш носителя не совпадает. Файл-носитель был изменён "
            "после сборки.",
            msg_key="error_hash_mismatch",
        )

    # 2b. Проверяем SHA-256 региона контейнера (формат v2)
    if expected_container_hash is not None:
        actual_container_hash = sha256_region(
            str(combined), carrier_size, container_size, cancel_event
        )
        if actual_container_hash != expected_container_hash:
            raise FooterError(
                "Хеш контейнера не совпадает. Контейнер был изменён "
                "после сборки.",
                msg_key="error_container_hash_mismatch",
            )

    # 3. Извлекаем контейнер
    container_name = _safe_container_name(metadata.get("container_name"))
    container_path = _allocate_container_path(out_dir, container_name)

    out_dir.mkdir(parents=True, exist_ok=True)

    try:
        with open(combined, "rb") as src_fh:
            src_fh.seek(carrier_size)
            with open(container_path, "wb") as dst_fh:
                remaining = container_size
                while remaining > 0:
                    if cancel_event is not None and cancel_event.is_set():
                        raise OperationCancelled()
                    chunk_size = min(CHUNK_SIZE, remaining)
                    chunk = src_fh.read(chunk_size)
                    if not chunk:
                        break
                    dst_fh.write(chunk)
                    remaining -= len(chunk)
    except OSError as exc:
        # Удаляем частичный файл контейнера при ошибке записи
        container_path.unlink(missing_ok=True)
        logger.error("split: failed (%s)", type(exc).__name__)
        raise FileOperationError(
            f"Ошибка при извлечении контейнера: {exc}",
            msg_key="error_extract_failed",
            error=str(exc),
        ) from exc
    except BaseException as exc:
        # Удаляем частичный файл контейнера при отмене
        container_path.unlink(missing_ok=True)
        logger.error("split: aborted (%s)", type(exc).__name__)
        raise

    logger.info(
        "split: done container_size=%d elapsed=%.3fs",
        container_size,
        time.monotonic() - start,
    )
    return container_path, metadata


def _safe_container_name(raw_name: str | None) -> str:
    """Возвращает безопасное имя файла контейнера.

    Отбрасывает любые компоненты пути (защита от path traversal),
    пустые и служебные имена. При отсутствии валидного имени
    генерирует случайное.
    """
    if raw_name:
        # Нормализуем оба разделителя пути: на POSIX обратный слеш —
        # допустимый символ имени, и Path.name его не отбросит.
        name = Path(raw_name.replace("\\", "/")).name
        if name and name not in (".", ".."):
            return name
    return f"container_{uuid.uuid4().hex[:8]}"


def _allocate_container_path(out_dir: Path, name: str) -> Path:
    """Подбирает свободное имя файла контейнера в каталоге.

    Не перезаписывает существующие файлы: при занятости имени
    добавляет числовой суффикс (имя (2).ext, имя (3).ext, ...).
    """
    candidate = out_dir / name
    if not candidate.exists():
        return candidate

    stem, suffix = os.path.splitext(name)
    counter = 2
    while True:
        candidate = out_dir / f"{stem} ({counter}){suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _validate_paths(
    carrier: Path, container: Path, output: Path
) -> None:
    """Валидирует входные пути для операции соединения."""
    if not carrier.exists():
        raise ValidationError(
            f"Файл-носитель не найден: {carrier}",
            msg_key="error_carrier_not_found",
            path=str(carrier),
        )
    if not container.exists():
        raise ValidationError(
            f"Файл-контейнер не найден: {container}",
            msg_key="error_container_not_found",
            path=str(container),
        )
    if carrier.resolve() == container.resolve():
        raise ValidationError(
            "Файл-носитель и контейнер не могут быть одним файлом",
            msg_key="error_same_file",
        )
    if output.exists():
        raise FileOperationError(
            f"Выходной файл уже существует: {output}",
            msg_key="error_output_exists",
            path=str(output),
        )


def _copy_file(src: Path, dst: Path, cancel_event=None) -> None:
    """Потоково копирует файл (не загружая в память).

    Args:
        src: Исходный файл.
        dst: Файл назначения.
        cancel_event: Опциональное событие отмены (threading.Event).

    Raises:
        FileOperationError: При ошибке ввода-вывода.
        OperationCancelled: При отмене операции.
    """
    try:
        with open(src, "rb") as fh_src, open(dst, "wb") as fh_dst:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    raise OperationCancelled()
                chunk = fh_src.read(CHUNK_SIZE)
                if not chunk:
                    break
                fh_dst.write(chunk)
    except OSError as exc:
        raise FileOperationError(
            f"Ошибка копирования {src} → {dst}: {exc}",
            msg_key="error_copy_failed",
            src=str(src),
            dst=str(dst),
            error=str(exc),
        ) from exc


def _append_file(src: Path, dst: Path, cancel_event=None) -> None:
    """Дописывает src в конец dst потоково.

    Args:
        src: Исходный файл.
        dst: Файл назначения (дописывается в конец).
        cancel_event: Опциональное событие отмены (threading.Event).

    Raises:
        FileOperationError: При ошибке ввода-вывода.
        OperationCancelled: При отмене операции.
    """
    try:
        with open(src, "rb") as fh_src, open(dst, "ab") as fh_dst:
            while True:
                if cancel_event is not None and cancel_event.is_set():
                    raise OperationCancelled()
                chunk = fh_src.read(CHUNK_SIZE)
                if not chunk:
                    break
                fh_dst.write(chunk)
    except OSError as exc:
        raise FileOperationError(
            f"Ошибка дописывания {src} → {dst}: {exc}",
            msg_key="error_append_failed",
            src=str(src),
            dst=str(dst),
            error=str(exc),
        ) from exc
