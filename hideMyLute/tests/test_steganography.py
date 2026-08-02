"""Тесты модуля стеганографии (join_files / split_file)."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest

from hideMyLute.exceptions import (
    CryptoError,
    FileOperationError,
    FooterError,
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

            join_files(carrier_path, container_path, output_path, "correct_password")
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


class TestJoinSplitEdgeCases:
    """Граничные случаи join/split (блокирующие и критичные замечания)."""

    def _make_sources(
        self, carrier_data: bytes, container_data: bytes
    ) -> tuple[str, str, str]:
        """Создаёт carrier/container и возвращает (carrier, container, output)."""
        c = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        v = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
        c.write(carrier_data)
        c.flush()
        v.write(container_data)
        v.flush()
        c.close()
        v.close()
        return c.name, v.name, c.name + ".joined"

    def test_split_tiny_file_raises_footer_error_not_oserror(self) -> None:
        """Файл короче 12 байт: FooterError, а не сырой OSError."""
        tiny = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        tiny.write(b"12345")
        tiny.flush()
        tiny.close()
        out_dir = tempfile.mkdtemp()
        try:
            with pytest.raises(FooterError, match="слишком мал"):
                split_file(tiny.name, out_dir, "pwd")
        finally:
            os.unlink(tiny.name)
            os.rmdir(out_dir)

    def test_split_tampered_container_rejected(self) -> None:
        """Подмена региона контейнера обнаруживается при разделении."""
        carrier_path, container_path, output_path = self._make_sources(
            b"\x00" * 300, b"\xFF" * 200
        )
        out_dir = tempfile.mkdtemp()
        try:
            join_files(carrier_path, container_path, output_path, "password123456")

            # Повреждаем байт в регионе контейнера
            data = bytearray(Path(output_path).read_bytes())
            data[300] ^= 0xFF
            Path(output_path).write_bytes(bytes(data))

            with pytest.raises(FooterError, match="контейнера"):
                split_file(output_path, out_dir, "password123456")
        finally:
            for p in (carrier_path, container_path, output_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass
            try:
                os.rmdir(out_dir)
            except OSError:
                pass

    def test_split_truncated_file_rejected(self) -> None:
        """Усечённый файл: разделение не выполняется."""
        carrier_path, container_path, output_path = self._make_sources(
            b"\x00" * 200, b"\xFF" * 100
        )
        out_dir = tempfile.mkdtemp()
        try:
            join_files(carrier_path, container_path, output_path, "password123456")
            data = Path(output_path).read_bytes()
            Path(output_path).write_bytes(data[:-1])
            with pytest.raises(FooterError):
                split_file(output_path, out_dir, "password123456")
        finally:
            for p in (carrier_path, container_path, output_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass
            try:
                os.rmdir(out_dir)
            except OSError:
                pass

    def test_split_preserves_container_name(self) -> None:
        """Извлечённый контейнер сохраняет исходное имя и расширение."""
        carrier_path, container_path, output_path = self._make_sources(
            b"\x00" * 200, b"\xFF" * 100
        )
        out_dir = tempfile.mkdtemp()
        try:
            join_files(carrier_path, container_path, output_path, "password123456")
            container_out, _ = split_file(output_path, out_dir, "password123456")
            # Имя контейнера = имя исходного файла контейнера
            assert Path(container_out).name == Path(container_path).name
            assert Path(container_out).suffix == Path(container_path).suffix
            assert Path(container_out).read_bytes() == b"\xFF" * 100
        finally:
            for p in (carrier_path, container_path, output_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass
            for leftover in Path(out_dir).iterdir():
                leftover.unlink()
            os.rmdir(out_dir)

    def test_split_does_not_overwrite_existing_file(self) -> None:
        """При занятом имени контейнера создаётся имя с суффиксом."""
        carrier_path, container_path, output_path = self._make_sources(
            b"\x00" * 200, b"\xFF" * 100
        )
        out_dir = tempfile.mkdtemp()
        try:
            join_files(carrier_path, container_path, output_path, "password123456")

            # Занимаем имя, которое будет у извлечённого контейнера
            container_name = Path(container_path).name
            occupied = Path(out_dir) / container_name
            occupied.write_bytes(b"original")

            container_out, _ = split_file(output_path, out_dir, "password123456")
            assert container_out != occupied
            assert occupied.read_bytes() == b"original"
            assert Path(container_out).read_bytes() == b"\xFF" * 100
        finally:
            for p in (carrier_path, container_path, output_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass
            for leftover in Path(out_dir).iterdir():
                leftover.unlink()
            os.rmdir(out_dir)

    def test_split_container_name_path_traversal_sanitized(self) -> None:
        """Имя контейнера с путями не может выйти за пределы каталога."""
        carrier_path, container_path, output_path = self._make_sources(
            b"\x00" * 200, b"\xFF" * 100
        )
        out_dir = tempfile.mkdtemp()
        try:
            join_files(carrier_path, container_path, output_path, "password123456")

            # Фабрикуем метаданные со злонамеренным именем контейнера
            from hideMyLute.footer import pack_footer

            evil_footer = pack_footer(
                carrier_path,
                container_path,
                "password123456",
                container_name="..\\..\\..\\evil.bin",
            )
            data = Path(output_path).read_bytes()
            # Пересобираем: отрезаем старый футер и пишем новый
            from hideMyLute.footer import read_footer_size

            old_footer_size = read_footer_size(output_path)
            body = data[:-old_footer_size]
            Path(output_path).write_bytes(body + evil_footer)

            container_out, _ = split_file(output_path, out_dir, "password123456")
            # Имя должно быть только "evil.bin" внутри out_dir
            assert Path(container_out).parent == Path(out_dir)
            assert Path(container_out).name == "evil.bin"
        finally:
            for p in (carrier_path, container_path, output_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass
            for leftover in Path(out_dir).iterdir():
                leftover.unlink()
            os.rmdir(out_dir)

    def test_split_v1_file_backward_compat(self) -> None:
        """Файл формата v1 разделяется в v2 (обратная совместимость)."""
        from hideMyLute.tests.test_footer import TestUnpackFooter

        combined = TestUnpackFooter._make_combined_v1(200, 100, "pwd")
        out_dir = tempfile.mkdtemp()
        try:
            container_out, metadata = split_file(str(combined), out_dir, "pwd")
            assert metadata["carrier_size"] == 200
            assert metadata["container_size"] == 100
            assert Path(container_out).read_bytes() == Path(combined).read_bytes()[
                200:300
            ]
        finally:
            try:
                os.unlink(combined)
            except OSError:
                pass
            for leftover in Path(out_dir).iterdir():
                leftover.unlink()
            os.rmdir(out_dir)

    def test_join_short_password_rejected(self) -> None:
        """Слабый (короткий) пароль при join отклоняется (BLK-02)."""
        carrier_path, container_path, output_path = self._make_sources(
            b"\x00" * 50, b"\xFF" * 30
        )
        try:
            with pytest.raises(ValidationError, match="не менее"):
                join_files(carrier_path, container_path, output_path, "short")
        finally:
            for p in (carrier_path, container_path, output_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass

    def test_join_cancellation_leaves_no_files(self) -> None:
        """Отмена join не оставляет ни выходного, ни временного файла."""
        from hideMyLute.exceptions import OperationCancelled

        carrier_path, container_path, output_path = self._make_sources(
            b"\x00" * 1024, b"\xff" * 2048
        )
        tmp_path = output_path + ".part"

        class CountingCancel:
            def is_set(self) -> bool:
                return True  # отменено с самого начала

        try:
            with pytest.raises(OperationCancelled):
                join_files(
                    carrier_path,
                    container_path,
                    output_path,
                    "password123456",
                    cancel_event=CountingCancel(),
                )
            assert not Path(output_path).exists()
            assert not Path(tmp_path).exists()
        finally:
            for p in (carrier_path, container_path, output_path, tmp_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass

    def test_split_cancellation_cleans_up_partial_container(self) -> None:
        """Отмена split удаляет частично записанный файл контейнера."""
        from hideMyLute.exceptions import OperationCancelled

        carrier_path, container_path, output_path = self._make_sources(
            b"\x00" * 1024, b"\xff" * 2048
        )
        out_dir = tempfile.mkdtemp()

        class CountingCancel:
            """Срабатывает на третьем вызове is_set.

            Вызовы: хеш носителя (1), хеш контейнера (2),
            первый чанк извлечения (3) — отмена внутри записи.
            """

            def __init__(self, set_after: int = 3) -> None:
                self._count = 0
                self._set_after = set_after

            def is_set(self) -> bool:
                self._count += 1
                return self._count >= self._set_after

        try:
            join_files(
                carrier_path, container_path, output_path, "password123456"
            )
            with pytest.raises(OperationCancelled):
                split_file(
                    output_path,
                    out_dir,
                    "password123456",
                    cancel_event=CountingCancel(),
                )
            # В каталоге не должно остаться файлов контейнера
            assert list(Path(out_dir).iterdir()) == []
        finally:
            for p in (carrier_path, container_path, output_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass
            for leftover in Path(out_dir).iterdir():
                leftover.unlink()
            os.rmdir(out_dir)

    def test_join_empty_carrier_and_container(self) -> None:
        """Пустые носитель и контейнер: join и split проходят."""
        carrier_path, container_path, output_path = self._make_sources(b"", b"")
        out_dir = tempfile.mkdtemp()
        try:
            join_files(carrier_path, container_path, output_path, "password123456")
            container_out, metadata = split_file(output_path, out_dir, "password123456")
            assert metadata["carrier_size"] == 0
            assert metadata["container_size"] == 0
            assert Path(container_out).read_bytes() == b""
        finally:
            for p in (carrier_path, container_path, output_path):
                try:
                    os.unlink(p)
                except OSError:
                    pass
            for leftover in Path(out_dir).iterdir():
                leftover.unlink()
            os.rmdir(out_dir)


class TestGenerateOutputPathMore:
    """Дополнительные тесты generate_output_path."""

    def test_same_as_carrier_collision_adds_suffix(self) -> None:
        """SAME_AS_CARRIER при занятом имени добавляет числовой суффикс."""
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=".mp4"
        ) as fh:
            fh.write(b"carrier")
            fh.flush()
            carrier = fh.name

        try:
            stem = Path(carrier).stem
            # Занимаем имя "_joined"
            occupied = Path(carrier).with_name(f"{stem}_joined.mp4")
            occupied.write_bytes(b"taken")

            result = generate_output_path(
                carrier, strategy=NamingStrategy.SAME_AS_CARRIER
            )
            assert result.suffix == ".mp4"
            assert result.name != occupied.name
            assert not result.exists()
            os.unlink(occupied)
        finally:
            os.unlink(carrier)
