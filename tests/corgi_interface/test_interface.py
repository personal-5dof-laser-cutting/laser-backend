"""
Tests for core.corgi_interface using a stateful fake FluidNC serial responder.

Rather than mocking SerialInterface with static canned responses, FakeFluidNCSerial
emulates enough of the real grbl/FluidNC status-report state machine (Alarm -> Idle
-> Run -> Idle) to exercise the actual parsing/gating logic in _CorgiInterface
(_is_homed, _is_done, buffer accounting), not just "does it call send()".

Status report format reference (real FluidNC):
  <Alarm|MPos:0.000,0.000,0.000|FS:0,0>
  <Idle|MPos:0.000,0.000,0.000|FS:0,0|Ov:100,100,100>
  <Run|WPos:0.120,0.000,0.000|FS:126,0|Ov:100,100,100>
"""

from threading import Lock
from time import sleep, time
from typing import override

import pytest
from pytest_mock import MockerFixture

from core.corgi_interface import CorgiInterface, InterfaceState
from gcode_lib import CommunicationProxy


class FakeFluidNCSerial(CommunicationProxy):
    """
    Drop-in stand-in for SerialInterface. Implements the same public surface
    (open/send/recv) so nothing in _CorgiInterface hits an AttributeError,
    and tracks enough internal state to answer '?' realistically depending
    on whether it has been homed / is idle / is mid-job.
    """

    def __init__(self, homed: bool = False):
        self._lock = Lock()
        self._homed = homed
        self._running = False
        self._pending_lines: list[str] = []
        self._outbox: list[str] = []
        self._is_open = True


    # --- SerialInterface-compatible API -------------------------------

    @property
    def is_connected(self):
        return True

    @override
    def connect(self, setup_reporting: bool = True, timeout: float = 5.0, clear_messages: bool = True) -> "FakeFluidNCSerial":
        self._is_open = True
        return self

    @override
    def close(self):
        pass

    def send(self, message: str):
        line = message.strip()
        with self._lock:
            if line == "?":
                self._outbox.append(self._status_report())
                return
            if line == "$h":
                self._homed = True
                self._outbox.append("ok")
                return
            if line == "M112":
                # emergency stop: drop everything, go to alarm
                self._pending_lines.clear()
                self._running = False
                self._homed = False
                self._outbox.append("ok")
                return
            if not self._homed:
                self._outbox.append(
                    "error:9"  # Error::SystemGcLock -> "GCode cannot be executed in lock or alarm state"
                )
                return
            # normal gcode line: accept and simulate brief execution
            self._pending_lines.append(line)
            self._running = True
            self._outbox.append("ok")

    def read_message(self, timeout: float | None = None) -> str | None:
        sleep(0.05)
        with self._lock:
            if self._pending_lines and self._running:
                # simulate the line finishing "execution" after being read once
                self._pending_lines.pop(0)
                if not self._pending_lines:
                    self._running = False
            if self._outbox:
                return self._outbox.pop(0) + "\n"
        if timeout:
            sleep(min(timeout, 0.01))
        return None

    # --- internals -------------------------------------------------------

    def _status_report(self) -> str:
        if not self._homed:
            return "<Alarm|MPos:0.000,0.000,0.000|FS:0,0>"
        if self._running:
            return "<Run|MPos:1.000,0.000,0.000|FS:100,0|Ov:100,100,100>"
        return "<Idle|MPos:0.000,0.000,0.000|FS:0,0|Ov:100,100,100>"


@pytest.fixture
def corgi(mocker: MockerFixture):
    """Fresh _CorgiInterface per test, wired to a FakeFluidNCSerial, no real thread state leakage."""
    instance = CorgiInterface()
    fake = FakeFluidNCSerial(homed=False)
    instance._proxy = fake
    instance.connect()
    yield instance, fake
    # best-effort cleanup so the background buffer thread doesn't keep running
    instance._clean_up()


def _wait_until_idle(instance: CorgiInterface, timeout: float = 10.0):
    start = time()
    while time() - start < timeout:
        if (
            len(instance._command_queue) == 0
            and instance._interface_state is InterfaceState.READY
        ):
            return True
        sleep(0.05)
    return False


def test_run_job_aborts_when_not_homed(corgi):
    instance, fake = corgi
    assert fake._homed is False

    lines = ["G1 X10", "G1 X20"]
    assert instance.run_job(lines) is False


def test_run_job_skips_homing_when_already_homed(corgi):
    instance, fake = corgi
    fake._homed = True

    lines = ["G1 X10"]
    instance.run_job(lines)

    assert _wait_until_idle(instance)
    # still homed, never re-triggered an alarm/homing cycle
    assert fake._homed is True


def test_status_reflects_alarm_before_homing(corgi):
    instance, fake = corgi
    status, _ = instance._get_status()
    assert status == "Alarm"


def test_status_reflects_idle_after_homing(corgi):
    instance, fake = corgi
    fake._homed = True
    sleep(1)
    status, _ = instance._get_status()
    assert status == "Idle"


def test_buffer_accounting_reaches_zero(corgi):
    instance, fake = corgi
    fake._homed = True

    lines = ["12345", "12345", "12", "12345", "123124214"]
    instance.run_job(lines)

    assert _wait_until_idle(instance, 999)
    assert len(instance._command_queue) == 0


def test_second_run_job_rejected_while_running(corgi):
    instance, fake = corgi
    fake._homed = True

    instance.run_job(["G1 X10", "G1 X20", "G1 X30"])
    # immediately try to start another job before the first finishes
    assert instance.run_job(["G1 X99"]) is False

    assert _wait_until_idle(instance)
