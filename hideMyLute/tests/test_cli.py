"""Тесты командной строки (CLI-подкоманды join/split/info)."""

from __future__ import annotations

import pytest

from hideMyLute import __main__


def _run_cli(argv) -> int:
    """Выполняет CLI-команду и возвращает код возврата.

    main() для CLI-команд завершается через SystemExit(code).
    """
    with pytest.raises(SystemExit) as excinfo:
        __main__.main(argv)
    return excinfo.value.code


class TestCli:
    """Тесты CLI-интерфейса."""

    def test_version(self, capsys) -> None:
        """--version выводит версию и завершается с кодом 0."""
        assert _run_cli(["--version"]) == 0
        out = capsys.readouterr().out
        assert "hideMyLute" in out

    def test_join_and_split_roundtrip(self, capsys, tmp_path) -> None:
        """join → split через CLI извлекает контейнер."""
        carrier = tmp_path / "c.jpg"
        carrier.write_bytes(b"\x00" * 100)
        container = tmp_path / "v.bin"
        container.write_bytes(b"\xff" * 50)
        output = tmp_path / "out.jpg"

        assert _run_cli(
            [
                "join",
                str(carrier),
                str(container),
                str(output),
                "--password",
                "password123456",
            ]
        ) == 0
        assert output.exists()

        out_dir = tmp_path / "out"
        out_dir.mkdir()
        assert _run_cli(
            [
                "split",
                str(output),
                "--output-dir",
                str(out_dir),
                "--password",
                "password123456",
            ]
        ) == 0

        files = list(out_dir.iterdir())
        assert len(files) == 1
        assert files[0].read_bytes() == b"\xff" * 50

    def test_split_wrong_password_fails(self, capsys, tmp_path) -> None:
        """Неверный пароль при split: ненулевой код возврата."""
        carrier = tmp_path / "c.jpg"
        carrier.write_bytes(b"\x00" * 100)
        container = tmp_path / "v.bin"
        container.write_bytes(b"\xff" * 50)
        output = tmp_path / "out.jpg"
        assert _run_cli(
            [
                "join",
                str(carrier),
                str(container),
                str(output),
                "--password",
                "password123456",
            ]
        ) == 0

        assert _run_cli(
            [
                "split",
                str(output),
                "--output-dir",
                str(tmp_path),
                "--password",
                "wrong_password",
            ]
        ) == 1

    def test_join_short_password_fails(self, capsys, tmp_path) -> None:
        """Слабый пароль при join: код возврата 2."""
        carrier = tmp_path / "c.jpg"
        carrier.write_bytes(b"\x00" * 10)
        container = tmp_path / "v.bin"
        container.write_bytes(b"\xff" * 10)
        output = tmp_path / "out.jpg"

        assert _run_cli(
            [
                "join",
                str(carrier),
                str(container),
                str(output),
                "--password",
                "short",
            ]
        ) == 2
        assert not output.exists()

    def test_info_shows_metadata(self, capsys, tmp_path) -> None:
        """info выводит метаданные футера."""
        carrier = tmp_path / "c.jpg"
        carrier.write_bytes(b"\x00" * 100)
        container = tmp_path / "v.bin"
        container.write_bytes(b"\xff" * 50)
        output = tmp_path / "out.jpg"
        assert _run_cli(
            [
                "join",
                str(carrier),
                str(container),
                str(output),
                "--password",
                "password123456",
            ]
        ) == 0

        assert _run_cli(
            ["info", str(output), "--password", "password123456"]
        ) == 0
        out = capsys.readouterr().out
        assert "carrier_size: 100" in out
        assert "container_size: 50" in out

    def test_join_missing_inputs_fails(self, capsys, tmp_path) -> None:
        """Несуществующий носитель: код возврата 1."""
        assert _run_cli(
            [
                "join",
                str(tmp_path / "missing.jpg"),
                str(tmp_path / "v.bin"),
                str(tmp_path / "out.jpg"),
                "--password",
                "password123456",
            ]
        ) == 1
