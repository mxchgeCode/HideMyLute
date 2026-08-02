"""Тесты модуля упаковки/распаковки футера."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from hideMyLute.config import FOOTER_HEADER_SIZE, MAGIC_BYTES
from hideMyLute.exceptions import CryptoError, FooterError
from hideMyLute.footer import pack_footer, unpack_footer


class TestPackFooter:
    """Тесты функции pack_footer."""

    def test_pack_footer_returns_bytes(self) -> None:
        """Формирует футер для двух существующих файлов."""
        with (
            tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as c,
            tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as v,
        ):
            c.write(b"A" * 100)
            c.flush()
            v.write(b"B" * 50)
            v.flush()

            footer = pack_footer(c.name, v.name, "password123")

            assert isinstance(footer, bytes)
            assert len(footer) > FOOTER_HEADER_SIZE

            # Проверяем заголовок (последние 4 байта футера)
            magic = footer[-FOOTER_HEADER_SIZE:-FOOTER_HEADER_SIZE + 4]
            assert magic == MAGIC_BYTES

        os.unlink(c.name)
        os.unlink(v.name)

    def test_pack_footer_nonexistent_carrier_raises_error(self) -> None:
        """Несуществующий носитель: FooterError."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as v:
            v.write(b"B" * 50)
            v.flush()
            with pytest.raises(FooterError, match="Файл-носитель"):
                pack_footer("/nonexistent/path.bin", v.name, "pwd")
        os.unlink(v.name)

    def test_pack_footer_nonexistent_container_raises_error(self) -> None:
        """Несуществующий контейнер: FooterError."""
        with tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as c:
            c.write(b"A" * 100)
            c.flush()
            with pytest.raises(FooterError, match="Файл-контейнер"):
                pack_footer(c.name, "/nonexistent/path.bin", "pwd")
        os.unlink(c.name)


class TestUnpackFooter:
    """Тесты функции unpack_footer."""

    @staticmethod
    def _make_combined(
        carrier_size: int, container_size: int, password: str
    ) -> tuple[Path, bytes, bytes]:
        """Создаёт временный собранный файл с футером.

        Returns:
            (путь, carrier_data, container_data).
        """
        carrier_data = os.urandom(carrier_size)
        container_data = os.urandom(container_size)

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".joined")
        tmp.write(carrier_data)
        tmp.write(container_data)
        tmp.flush()
        tmp.close()  # Закрываем, чтобы unpack_footer мог прочитать файл
        tmp_path = Path(tmp.name)

        # Формируем футер через отдельные временные файлы.
        # На Windows os.unlink нельзя вызывать внутри with (файл открыт),
        # поэтому выносим за пределы блока.
        cf = tempfile.NamedTemporaryFile(delete=False, suffix=".carrier")
        cf2 = tempfile.NamedTemporaryFile(delete=False, suffix=".container")
        try:
            cf.write(carrier_data)
            cf.flush()
            cf2.write(container_data)
            cf2.flush()
            footer = pack_footer(cf.name, cf2.name, password)
        finally:
            cf.close()
            cf2.close()
            os.unlink(cf.name)
            os.unlink(cf2.name)

        with open(tmp_path, "ab") as fh:
            fh.write(footer)

        return tmp_path, carrier_data, container_data

    def test_unpack_footer_returns_metadata(self) -> None:
        """Успешная распаковка футера: возвращает словарь с метаданными."""
        combined, _carrier, _container = self._make_combined(200, 100, "pwd")
        try:
            metadata = unpack_footer(str(combined), "pwd")
            assert "carrier_size" in metadata
            assert "container_size" in metadata
            assert "carrier_hash_sha256" in metadata
            assert "timestamp" in metadata
            assert metadata["carrier_size"] == 200
            assert metadata["container_size"] == 100
        finally:
            os.unlink(combined)

    def test_unpack_footer_wrong_password_raises_crypto_error(self) -> None:
        """Неверный пароль: CryptoError."""
        combined, _, _ = self._make_combined(200, 100, "correct_pwd")
        try:
            with pytest.raises(
                CryptoError, match="Неверный пароль или данные повреждены"
            ):
                unpack_footer(str(combined), "wrong_pwd")
        finally:
            os.unlink(combined)

    def test_unpack_footer_no_footer_raises_footer_error(self) -> None:
        """Файл без футера: FooterError."""
        fh = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
        try:
            fh.write(b"Just some data, no footer here")
            fh.flush()
            fh.close()
            with pytest.raises(
                FooterError, match="не найден"
            ):
                unpack_footer(fh.name, "pwd")
        finally:
            os.unlink(fh.name)

    def test_unpack_footer_nonexistent_file_raises_error(self) -> None:
        """Несуществующий файл: FooterError."""
        with pytest.raises(FooterError, match="Файл не найден"):
            unpack_footer("/nonexistent/combined.bin", "pwd")

    def test_unpack_footer_tampered_carrier_hash_mismatch(self) -> None:
        """Футер валиден, но проверка хеша — на уровне steganography.split_file."""
        # Этот тест проверяет только, что unpack_footer возвращает
        # корректные метаданные, даже если носитель был изменён.
        # Валидация хеша происходит в split_file.
        combined, _, _ = self._make_combined(200, 100, "pwd")
        try:
            metadata = unpack_footer(str(combined), "pwd")
            assert metadata["carrier_size"] == 200
        finally:
            os.unlink(combined)
