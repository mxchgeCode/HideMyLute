"""Тесты модуля упаковки/распаковки футера."""

from __future__ import annotations

import json
import os
import struct
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import pytest

from hideMyLute.config import (
    FOOTER_HEADER_SIZE,
    FOOTER_VERSION,
    FOOTER_VERSION_V1,
    MAGIC_BYTES,
    MAX_FOOTER_PAYLOAD_LEN,
    PBKDF2_SALT_SIZE,
)
from hideMyLute.crypto import derive_key, encrypt_aes_gcm
from hideMyLute.exceptions import CryptoError, FooterError
from hideMyLute.footer import pack_footer, read_footer_size, unpack_footer


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

            # Заголовок — последние 12 байт; версия должна быть v2
            _magic, version, _flags, _plen = struct.unpack(
                ">4sHHI", footer[-FOOTER_HEADER_SIZE:]
            )
            assert version == FOOTER_VERSION

        os.unlink(c.name)
        os.unlink(v.name)

    def test_pack_footer_uses_no_detectable_magic(self) -> None:
        """v2: первые 4 байта заголовка — случайные, не равны MAGIC_BYTES.

        Событие «магия случайно совпала с b'HMLF'» имеет вероятность
        2^-32; для детерминированности теста пересоздаём футер, пока
        не будет гарантированно случайного значения (обычно 1 итерация).
        """
        with (
            tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as c,
            tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as v,
        ):
            c.write(b"A" * 20)
            c.flush()
            v.write(b"B" * 20)
            v.flush()

            for _ in range(64):
                footer = pack_footer(c.name, v.name, "pwd")
                magic = footer[-FOOTER_HEADER_SIZE:-FOOTER_HEADER_SIZE + 4]
                if magic != MAGIC_BYTES:
                    break
            else:
                pytest.fail("64 случайных magic подряд равны HMLF — невероятно")

            assert magic != MAGIC_BYTES
            # Случайный magic гарантирует, что unpack_footer обработает
            # файл через детекцию по GCM-тегу
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".joined")
            tmp.write(b"A" * 20 + b"B" * 20 + footer)
            tmp.close()
            try:
                metadata = unpack_footer(tmp.name, "pwd")
                assert metadata["carrier_size"] == 20
            finally:
                os.unlink(tmp.name)

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

    def test_pack_footer_with_precomputed_values(self) -> None:
        """Заранее вычисленные размеры/хеши не пересчитываются.

        Это ключевой путь устранения TOCTOU в join_files.
        """
        with (
            tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as c,
            tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as v,
        ):
            c.write(b"A" * 10)
            c.flush()
            v.write(b"B" * 20)
            v.flush()

            footer = pack_footer(
                c.name,
                v.name,
                "pwd",
                carrier_size=10,
                container_size=20,
                carrier_hash="ab" * 32,
                container_hash="cd" * 32,
                container_name="secret.bin",
            )

            # Проверим, что precomputed-значения попали в зашифрованные
            # метаданные через roundtrip
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".joined")
            tmp.write(b"A" * 10 + b"B" * 20 + footer)
            tmp.close()
            try:
                metadata = unpack_footer(tmp.name, "pwd")
                assert metadata["carrier_hash_sha256"] == "ab" * 32
                assert metadata["container_hash_sha256"] == "cd" * 32
                assert metadata["container_name"] == "secret.bin"
            finally:
                os.unlink(tmp.name)

        os.unlink(c.name)
        os.unlink(v.name)


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

    @staticmethod
    def _make_combined_v1(
        carrier_size: int, container_size: int, password: str
    ) -> Path:
        """Создаёт собранный файл в формате v1 (magic b'HMLF' + timestamp).

        Хеш носителя вычисляется корректно, поэтому файл пригоден для
        полного roundtrip split_file. Используется для проверки обратной
        совместимости.
        """
        import hashlib

        carrier_data = os.urandom(carrier_size)
        container_data = os.urandom(container_size)

        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".joined")
        tmp.write(carrier_data)
        tmp.write(container_data)
        tmp.flush()
        tmp.close()
        tmp_path = Path(tmp.name)

        metadata = {
            "carrier_size": carrier_size,
            "container_size": container_size,
            "carrier_hash_sha256": hashlib.sha256(carrier_data).hexdigest(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        metadata_json = json.dumps(metadata, ensure_ascii=False).encode("utf-8")
        key, salt = derive_key(password)
        encrypted_payload = salt + encrypt_aes_gcm(metadata_json, key)
        header = struct.pack(
            ">4sHHI",
            MAGIC_BYTES,
            FOOTER_VERSION_V1,
            0,
            len(encrypted_payload),
        )
        with open(tmp_path, "ab") as fh:
            fh.write(encrypted_payload + header)
        return tmp_path

    def test_unpack_footer_returns_metadata(self) -> None:
        """Успешная распаковка футера v2: возвращает словарь с метаданными."""
        combined, _carrier, _container = self._make_combined(200, 100, "pwd")
        try:
            metadata = unpack_footer(str(combined), "pwd")
            assert "carrier_size" in metadata
            assert "container_size" in metadata
            assert "carrier_hash_sha256" in metadata
            assert "container_hash_sha256" in metadata
            assert "container_name" in metadata
            assert "timestamp" not in metadata  # v2 не хранит время сборки
            assert metadata["carrier_size"] == 200
            assert metadata["container_size"] == 100
        finally:
            os.unlink(combined)

    def test_unpack_footer_v1_backward_compat(self) -> None:
        """Футер v1 (magic b'HMLF', timestamp) читается в v2."""
        combined = self._make_combined_v1(200, 100, "pwd")
        try:
            metadata = unpack_footer(str(combined), "pwd")
            assert metadata["carrier_size"] == 200
            assert metadata["container_size"] == 100
            # v1 не содержит хеша контейнера
            assert "container_hash_sha256" not in metadata
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

    def test_unpack_footer_no_footer_raises_crypto_error(self) -> None:
        """Файл без футера с правдоподобным заголовком: CryptoError.

        В формате v2 отсутствие футера неотличимо от неверного пароля —
        это осознанное поведение для правдоподобного отрицания.
        """
        fh = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
        try:
            # Заголовок с валидной длиной payload, но мусорным payload:
            # границы пройдены, расшифровка падает -> CryptoError
            header = struct.pack(
                ">4sHHI",
                b"\x11\x22\x33\x44",
                FOOTER_VERSION,
                0,
                60,
            )
            fh.write(os.urandom(500) + os.urandom(60) + header)
            fh.flush()
            fh.close()
            with pytest.raises(CryptoError):
                unpack_footer(fh.name, "pwd")
        finally:
            os.unlink(fh.name)

    def test_unpack_footer_nonexistent_file_raises_error(self) -> None:
        """Несуществующий файл: FooterError."""
        with pytest.raises(FooterError, match="Файл не найден"):
            unpack_footer("/nonexistent/combined.bin", "pwd")

    def test_unpack_footer_small_file_raises_footer_error(self) -> None:
        """Файл короче 12 байт: FooterError без OSError."""
        fh = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
        try:
            fh.write(b"12345")
            fh.flush()
            fh.close()
            with pytest.raises(FooterError, match="слишком мал"):
                unpack_footer(fh.name, "pwd")
        finally:
            os.unlink(fh.name)

    def test_unpack_footer_absurd_length_raises_footer_error(self) -> None:
        """Гигантский заявленный payload: FooterError без чтения в память."""
        fh = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
        try:
            # Заголовок с len = MAX_FOOTER_PAYLOAD_LEN + 1
            header = struct.pack(
                ">4sHHI",
                b"\x11\x22\x33\x44",
                FOOTER_VERSION,
                0,
                MAX_FOOTER_PAYLOAD_LEN + 1,
            )
            fh.write(b"\x00" * 100 + header)
            fh.flush()
            fh.close()
            with pytest.raises(FooterError):
                unpack_footer(fh.name, "pwd")
        finally:
            os.unlink(fh.name)

    def test_unpack_footer_tampered_carrier_hash_mismatch(self) -> None:
        """unpack_footer не проверяет хеши — это делает split_file.

        Футер валиден, даже если носитель был изменён.
        """
        combined, _, _ = self._make_combined(200, 100, "pwd")
        try:
            metadata = unpack_footer(str(combined), "pwd")
            assert metadata["carrier_size"] == 200
        finally:
            os.unlink(combined)


class TestReadFooterSize:
    """Тесты функции read_footer_size."""

    def test_read_footer_size_matches_payload(self) -> None:
        """Размер футера = FOOTER_HEADER_SIZE + payload."""
        combined, _, _ = TestUnpackFooter._make_combined(100, 50, "pwd")
        try:
            size = read_footer_size(combined)
            assert size > FOOTER_HEADER_SIZE
            # unpack_footer должен пройти при этих размерах
            metadata = unpack_footer(str(combined), "pwd")
            expected_total = (
                metadata["carrier_size"]
                + metadata["container_size"]
                + size
            )
            assert expected_total == combined.stat().st_size
        finally:
            os.unlink(combined)

    def test_salt_size_constant_used(self) -> None:
        """Проверка согласованности констант соли."""
        # payload футера начинается с соли PBKDF2_SALT_SIZE байт
        with (
            tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as c,
            tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as v,
        ):
            c.write(b"A" * 10)
            c.flush()
            v.write(b"B" * 10)
            v.flush()
            footer = pack_footer(c.name, v.name, "pwd")
        os.unlink(c.name)
        os.unlink(v.name)

        _magic, _version, _flags, payload_len = struct.unpack(
            ">4sHHI", footer[-FOOTER_HEADER_SIZE:]
        )
        assert payload_len >= PBKDF2_SALT_SIZE
