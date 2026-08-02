"""Тесты фонового воркера (BackgroundWorker)."""

from __future__ import annotations

import threading
import time

from hideMyLute.exceptions import HideMyLuteError
from hideMyLute.worker import BackgroundWorker


class TestBackgroundWorker:
    """Тесты фонового воркера."""

    def _wait_until(self, condition, timeout: float = 3.0) -> bool:
        """Ожидает выполнения условия с таймаутом."""
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if condition():
                return True
            time.sleep(0.02)
        return False

    def test_run_calls_on_success_with_result(self) -> None:
        """Успешная операция: on_success получает результат."""
        worker = BackgroundWorker()
        results = []

        worker.run(
            target=lambda: "ok",
            on_success=lambda r: results.append(r),
            on_error=lambda e: results.append(("err", e)),
        )

        assert self._wait_until(lambda: len(results) == 1)
        assert results == ["ok"]

    def test_run_calls_on_finish(self) -> None:
        """on_finish вызывается после завершения операции."""
        worker = BackgroundWorker()
        finished = []

        worker.run(
            target=lambda: None,
            on_success=lambda r: None,
            on_error=lambda e: None,
            on_finish=lambda: finished.append(True),
        )

        assert self._wait_until(lambda: bool(finished))

    def test_second_run_while_running_is_rejected(self) -> None:
        """Повторный запуск во время выполнения отклоняется."""
        worker = BackgroundWorker()
        results = []

        def slow() -> str:
            time.sleep(0.5)
            return "ok"

        worker.run(
            target=slow,
            on_success=lambda r: results.append(r),
            on_error=lambda e: results.append(e),
        )
        # Второй запуск сразу — должен быть отклонён
        worker.run(
            target=slow,
            on_success=lambda r: results.append(r),
            on_error=lambda e: results.append(e),
        )

        assert self._wait_until(lambda: len(results) == 2)
        # Второй запуск отклонён синхронно (до завершения первой операции),
        # поэтому порядок callbacks не гарантирован
        assert "ok" in results
        assert any(
            "Операция уже выполняется" in str(item) for item in results
        )

    def test_hide_mylute_error_goes_to_on_error(self) -> None:
        """HideMyLuteError передаётся в on_error."""
        worker = BackgroundWorker()
        results = []

        def fail() -> None:
            raise HideMyLuteError("boom", msg_key="error_no_footer")

        worker.run(
            target=fail,
            on_success=lambda r: results.append(("ok", r)),
            on_error=lambda e: results.append(("err", e)),
        )

        assert self._wait_until(lambda: len(results) == 1)
        kind, exc = results[0]
        assert kind == "err"
        assert isinstance(exc, HideMyLuteError)
        assert exc.msg_key == "error_no_footer"

    def test_unexpected_exception_goes_to_on_error(self) -> None:
        """Неожиданное исключение передаётся в on_error как строка."""
        worker = BackgroundWorker()
        results = []

        def fail() -> None:
            raise RuntimeError("unexpected")

        worker.run(
            target=fail,
            on_success=lambda r: results.append(("ok", r)),
            on_error=lambda e: results.append(("err", e)),
        )

        assert self._wait_until(lambda: len(results) == 1)
        kind, msg = results[0]
        assert kind == "err"
        assert "unexpected" in str(msg)

    def test_cancel_suppresses_callbacks(self) -> None:
        """Отмена подавляет on_success/on_error/on_finish."""
        worker = BackgroundWorker()
        results = []

        def slow() -> str:
            time.sleep(0.3)
            return "ok"

        worker.run(
            target=slow,
            on_success=lambda r: results.append(("ok", r)),
            on_error=lambda e: results.append(("err", e)),
            on_finish=lambda: results.append("finish"),
        )
        worker.cancel()

        # Ждём достаточно долго — callbacks не должны появиться
        time.sleep(0.7)
        assert results == []

    def test_cancel_event_reaches_target(self) -> None:
        """Целевая функция получает cancel_event и может прерваться."""
        worker = BackgroundWorker()
        results = []
        received_event = []

        def target(cancel_event=None) -> str:
            received_event.append(cancel_event)
            # Ждём отмену — операция не должна завершиться успешно
            if cancel_event is not None:
                cancel_event.wait(timeout=3.0)
                if cancel_event.is_set():
                    raise HideMyLuteError(
                        "cancelled", msg_key="error_operation_cancelled"
                    )
            return "done"

        worker.run(
            target=target,
            on_success=lambda r: results.append(("ok", r)),
            on_error=lambda e: results.append(("err", e)),
        )
        assert self._wait_until(lambda: len(received_event) == 1)
        assert isinstance(received_event[0], threading.Event)

        worker.cancel()
        # callbacks подавлены после отмены
        time.sleep(0.3)
        assert results == []

    def test_consecutive_runs_work(self) -> None:
        """После завершения операции воркер можно использовать повторно."""
        worker = BackgroundWorker()
        results = []

        def slow() -> str:
            time.sleep(0.1)
            return "ok"

        worker.run(
            target=slow,
            on_success=lambda r: results.append(r),
            on_error=lambda e: results.append(e),
        )
        assert self._wait_until(lambda: len(results) == 1)
        assert worker.is_running is False

        worker.run(
            target=slow,
            on_success=lambda r: results.append(r),
            on_error=lambda e: results.append(e),
        )
        assert self._wait_until(lambda: len(results) == 2)
        assert results == ["ok", "ok"]

    def test_is_running_during_operation(self) -> None:
        """is_running возвращает True во время выполнения."""
        worker = BackgroundWorker()

        def slow() -> str:
            time.sleep(0.3)
            return "ok"

        worker.run(
            target=slow,
            on_success=lambda r: None,
            on_error=lambda e: None,
        )
        assert self._wait_until(lambda: worker.is_running)
        time.sleep(0.35)
        assert worker.is_running is False
