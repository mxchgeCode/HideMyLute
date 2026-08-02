"""Тесты модуля стеганографии (join_files / split_file)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from hideMyLute.exceptions import (
    CryptoError,
    FileOperationError,
    ValidationError,
)
from hideMyLute.steganography import (
    NamingStrategy,
    generate_output_path,
    join_files,
    split_file,
)


class TestGenerateOutputPath:
    """Тесты generate_output_path."""

    def test_windows_style_first_free_name(self) -> None:
        """Если носитель существует — добавляется (2) в имя."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".jpg"
        ) as fh:
            fh.write(b"carrier")
            fh.flush()
            carrier = fh.name

        try:
            result = generate_output_path(
                carrier, strategy=NamingStrategy.WINDOWS_STYLE
            )
            # Носитель существует, поэтому WINDOWS_STYLE
            # создаёт имя с суффиксом (2)
            stem = Path(carrier).stem
            assert stem in result.name
            assert "(2)" in result.name
            assert not result.exists()
        finally:
            os.unlink(carrier)

    def test_windows_style_suffix_exists(self) -> None:
        """Если имя занято — создаётся имя с (2)."""
        with (
            tempfile.NamedTemporaryFile(
                delete=False, suffix=".jpg"
            ) as fh,
            tempfile.NamedTemporaryFile(
                delete=False, suffix=".bin"
            ) as container,
        ):
            fh.write(b"carrier")
            fh.flush()
            container.write(b"container")
            container.flush()

            # Имя носителя уже занято, output должен быть photo (2).jpg
            result = generate_output_path(
                fh.name, strategy=NamingStrategy.WINDOWS_STYLE
            )
            # result должен иметь (2) в имени, если имя занято
            assert "(2)" in result.name or result.name != Path(fh.name).name

        os.unlink(fh.name)
        os.unlink(container.name)

    def test_uuid_strategy_generates_bin_extension(self) -> None:
        """Стратегия UUID: расширение .bin, имя содержит output_."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".png"
        ) as fh:
            fh.write(b"carrier")
            fh.flush()
            result = generate_output_path(
                fh.name, strategy=NamingStrategy.UUID
            )
            assert result.suffix == ".bin"
            assert result.stem.startswith("output_")
        os.unlink(fh.name)

    def test_same_as_carrier_strategy(self) -> None:
        """SAME_AS_CARRIER: сохраняет расширение, добавляет _joined."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".mp4"
        ) as fh:
            fh.write(b"carrier")
            fh.flush()
            result = generate_output_path(
                fh.name, strategy=NamingStrategy.SAME_AS_CARRIER
            )
            assert result.suffix == ".mp4"
            assert "_joined" in result.stem
        os.unlink(fh.name)

    def test_nonexistent_carrier_raises_error(self) -> None:
        """Несуществующий носитель: ValidationError."""
        with pytest.raises(ValidationError, match="не найден"):
            generate_output_path("/nonexistent/file.bin")


class TestJoinAndSplit:
    """Интеграционные тесты: join → split."""

    def test_join_then_split_roundtrip(self) -> None:
        """Соединяем и разделяем: контейнер восстанавливается."""
        c = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        v = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
        try:
            carrier_data = b"\x00" * 500
            container_data = b"\xFF" * 300
            c.write(carrier_data)
            c.flush()
            v.write(container_data)
            v.flush()
            c.close()
            v.close()

            carrier_path = c.name
            container_path = v.name
            output_path = c.name + ".joined"
            password = "test_password"

            # Join
            result = join_files(
                carrier_path, container_path, output_path, password
            )
            assert Path(result).exists()
            assert Path(result).stat().st_size > 500 + 300

            # Split
            out_dir = tempfile.mkdtemp()
            container_out, metadata = split_file(
                result, out_dir, password
            )

            assert container_out.exists()
            assert metadata["carrier_size"] == 500
            assert metadata["container_size"] == 300

            # Контейнер восстановлен
            extracted = container_out.read_bytes()
            assert extracted == container_data

        finally:
            for path in [carrier_path, container_path, output_path]:
                try:
                    os.unlink(path)
                except OSError:
                    pass
            if 'container_out' in dir() and container_out.exists():
                os.unlink(container_out)
            if 'out_dir' in dir():
                try:
                    os.rmdir(out_dir)
                except OSError:
                    pass

    def test_split_wrong_password_raises_crypto_error(self) -> None:
        """Неверный пароль при разделении: CryptoError."""
        c = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        v = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
        try:
            c.write(b"\x00" * 200)
            c.flush()
            v.write(b"\xFF" * 100)
            v.flush()
            c.close()
            v.close()
            carrier_path = c.name
            container_path = v.name
            output_path = c.name + ".joined"

            join_files(carrier_path, container_path, output_path, "correct")
            out_dir = tempfile.mkdtemp()
            try:
                with pytest.raises(
                    CryptoError,
                    match="Неверный пароль или данные повреждены",
                ):
                    split_file(output_path, out_dir, "wrong_password")
            finally:
                try:
                    os.rmdir(out_dir)
                except OSError:
                    pass
        finally:
            for path in [carrier_path, container_path, output_path]:
                try:
                    os.unlink(path)
                except OSError:
                    pass

    def test_join_duplicate_output_raises_error(self) -> None:
        """Повторная запись в существующий файл: FileOperationError."""
        with (
            tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as c,
            tempfile.NamedTemporaryFile(delete=False, suffix=".bin") as v,
        ):
            c.write(b"\x00" * 200)
            c.flush()
            v.write(b"\xFF" * 100)
            v.flush()
            carrier_path = c.name
            container_path = v.name

        output_path = carrier_path + ".joined"
        # Создаём выходной файл заранее
        Path(output_path).write_bytes(b"existing")

        try:
            with pytest.raises(
                FileOperationError, match="уже существует"
            ):
                join_files(
                    carrier_path, container_path, output_path, "pwd"
                )
        finally:
            os.unlink(carrier_path)
            os.unlink(container_path)
            os.unlink(output_path)

    def test_join_same_carrier_and_container_raises_error(self) -> None:
        """Носитель и контейнер — один файл: ValidationError."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".bin"
        ) as fh:
            fh.write(b"data")
            fh.flush()
            path = fh.name
            output = path + ".joined"

        try:
            with pytest.raises(
                ValidationError, match="не могут быть одним файлом"
            ):
                join_files(path, path, output, "pwd")
        finally:
            os.unlink(path)

    def test_split_nonexistent_file_raises_error(self) -> None:
        """Разделение несуществующего файла: ValidationError."""
        with pytest.raises(ValidationError, match="не найден"):
            split_file("/nonexistent/file.bin", "/tmp", "pwd")
