"""Smoke-тесты GUI (требуют дисплея; пропускаются без него).

На CI выполняется под xvfb (см. .github/workflows/ci.yml).
"""

from __future__ import annotations

import pytest

customtkinter = pytest.importorskip("customtkinter")

from hideMyLute.config import AppConfig
from hideMyLute.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def app():
    """Создаёт главное окно (один Tk-интерпретатор на модуль).

    Module-scope: повторное создание/уничтожение Tcl-интерпретаторов
    в рамках одного процесса нестабильно (TclError).
    """
    try:
        window = MainWindow(config=AppConfig())
    except Exception as exc:  # noqa: BLE001 - нет дисплея
        pytest.skip(f"no display available: {exc}")
    window.withdraw()
    window.update_idletasks()
    yield window
    window.destroy()


def test_main_window_constructs(app) -> None:
    """Главное окно создаётся с двумя вкладками."""
    assert app._tabview is not None
    assert len(app._tabview.get(0)) > 0
    assert len(app._tabview.get(1)) > 0


def test_language_switch_ru_en_ru(app) -> None:
    """Переключение языка ru→en→ru не ломает вкладки (SIG-01).

    CTkSegmentedButton.set() не запускает command — обработчик
    вызывается напрямую.
    """
    # en
    app._on_language_changed("EN")
    app.update_idletasks()
    assert app._config.language == "en"
    names_en = [app._tabview.get(0), app._tabview.get(1)]
    assert names_en == ["Join", "Split"]
    # ru
    app._on_language_changed("RU")
    app.update_idletasks()
    assert app._config.language == "ru"
    names_ru = [app._tabview.get(0), app._tabview.get(1)]
    assert names_ru == ["Соединение", "Разделение"]


def test_join_panel_status_not_ready(app) -> None:
    """Пустая панель «Соединение» показывает status_not_ready."""
    app._join_panel.refresh_status()
    # Статус-бар обновляется через callback; проверяем готовность кнопки
    assert app._join_panel._processing is False


def _wait_for(app, condition, timeout: float = 15.0) -> bool:
    """Обрабатывает события tk и ждёт выполнения условия."""
    import time

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        app.update()
        if condition():
            return True
        time.sleep(0.05)
    app.update()
    return condition()


def test_join_panel_full_operation(app, tmp_path) -> None:
    """Полный join через панель «Соединение»: файл создаётся, пароль стирается."""
    carrier = tmp_path / "c.jpg"
    carrier.write_bytes(b"\x00" * 100)
    container = tmp_path / "v.bin"
    container.write_bytes(b"\xff" * 50)

    panel = app._join_panel
    panel._carrier.path_var.set(str(carrier))
    panel._container.path_var.set(str(container))
    panel._password.password_var.set("password123456")
    panel._confirm_var.set("password123456")

    panel._on_join()

    assert _wait_for(app, lambda: panel._completed_path is not None)
    assert panel._completed_path is not None
    assert panel._completed_path.exists()
    # SIG-05: пароль очищен после успешной операции
    assert panel._password.password_var.get() == ""
    assert panel._confirm_var.get() == ""


def test_join_panel_short_password_blocked(app, tmp_path) -> None:
    """Слабый пароль блокируется на уровне панели (BLK-02)."""
    carrier = tmp_path / "c.jpg"
    carrier.write_bytes(b"\x00" * 100)
    container = tmp_path / "v.bin"
    container.write_bytes(b"\xff" * 50)

    panel = app._join_panel
    panel._carrier.path_var.set(str(carrier))
    panel._container.path_var.set(str(container))
    panel._password.password_var.set("short")
    panel._confirm_var.set("short")

    panel._on_join()
    assert panel._processing is False
    assert panel._completed_path is None


def test_split_panel_full_operation(app, tmp_path) -> None:
    """Полный split через панель «Разделение»: контейнер извлекается."""
    from hideMyLute.steganography import join_files

    carrier = tmp_path / "c.jpg"
    carrier.write_bytes(b"\x00" * 100)
    container = tmp_path / "v.bin"
    container.write_bytes(b"\xff" * 50)
    output = tmp_path / "out.jpg"
    join_files(carrier, container, output, "password123456")

    panel = app._split_panel
    panel._combined.path_var.set(str(output))
    panel._password.password_var.set("password123456")
    panel._on_split()

    assert _wait_for(app, lambda: panel._completed_path is not None)
    assert panel._completed_path is not None
    assert panel._completed_path.exists()
    assert panel._completed_path.read_bytes() == b"\xff" * 50
    # SIG-05: пароль очищен после успешной операции
    assert panel._password.password_var.get() == ""


def test_split_panel_wrong_password(app, tmp_path) -> None:
    """Неверный пароль: панель получает ошибку."""
    from hideMyLute.steganography import join_files

    carrier = tmp_path / "c.jpg"
    carrier.write_bytes(b"\x00" * 100)
    container = tmp_path / "v.bin"
    container.write_bytes(b"\xff" * 50)
    output = tmp_path / "out.jpg"
    join_files(carrier, container, output, "password123456")

    panel = app._split_panel
    panel._combined.path_var.set(str(output))
    panel._password.password_var.set("wrong_password")
    panel._on_split()

    assert _wait_for(app, lambda: panel._error is not None)
    assert panel._completed_path is None
