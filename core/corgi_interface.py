from enum import StrEnum, auto
import logging
import re
from threading import Event, Lock, RLock, Thread
from time import sleep
from typing import Final, Optional, TypeGuard

from gcode_lib import CommunicationProxy
from gcode_lib.drivers.driver_interface import DriverInterface

from api.models.base import ErrorMessage, UpdateMessage, WebsocketMessage
from queue import Queue

_DISCONNECTED_STATUS: Final[str] = "Disconnected"
_CORGI_STATUS_RE: Final[re.Pattern] = re.compile(
    r"<([A-Z][a-z]+(?:\:\d+)?)((?:\|[^\|>]+)+)>"
)

log = logging.getLogger(__name__)


def is_connected(proxy: CommunicationProxy | None) -> TypeGuard[CommunicationProxy]:
    return proxy is not None and proxy.is_connected

class InterfaceState(StrEnum):
    DISCONNECTED = auto()
    READY = auto()
    RUNNING = auto()


class CorgiInterface:
    def __init__(self, driver: DriverInterface, max_reconnect_timeout: int = 10):
        self._driver = driver
        self.max_reconnect_timeout: int = max_reconnect_timeout
        self._reconnect_timeout: int = 0

        self._proxy: Optional[CommunicationProxy] = None

        self.outgoing_messages: Queue[WebsocketMessage] = Queue()

        self._setup_lock: RLock = RLock()

        self._new_status_event: Event = Event()
        self._status: str = ""
        self._status_dict: dict[str, str] = {}
        self._status_requests: int = 0

        self._thread_should_run: bool = False
        self._interface_state: InterfaceState = InterfaceState.DISCONNECTED
        self._interface_state_lock: Lock = Lock()

        self._reader_thread: Thread = Thread(target=self._reader_loop, daemon=True)

    def _set_interface_state(self, state: InterfaceState):
        with self._interface_state_lock:
            self._interface_state = state

    def _is_homed(self) -> bool:
        status, _ = self._get_status()
        if status == _DISCONNECTED_STATUS:
            return False

        if status.startswith("Alarm"):
            log.info(f"Corgi is in Alarmstate: {status}")
            return False

        return True

    def _is_in_done_status(self) -> bool:
        return self._status in [_DISCONNECTED_STATUS, "Idle", "Alarm"]

    def _is_done(self) -> bool:
        return self._is_in_done_status()

    def _fetch_status(self):
        if self._proxy is None or not self._proxy.is_connected:
            return
        self._new_status_event.clear()
        self._status_requests += 1
        self._proxy.send("?")

    def _get_status(self) -> tuple[str, dict[str, str]]:
        if self._proxy is None or not self._proxy.is_connected:
            log.warning("Corgi not connected")
            self._status = _DISCONNECTED_STATUS
            self._status_dict = {}
        else:
            self._fetch_status()
            self._new_status_event.wait()
        return self._status, self._status_dict

    def _set_status(self, status_message: str, status_infos: list[str]):
        status_dict = dict(info.split(":") for info in status_infos)
        self._status = status_message
        self._status_dict = status_dict
        self._new_status_event.set()

    def _handle_incoming_message(self, msg: str):
        msg = msg.strip()
        if not msg:
            return

        if msg == "ok" or msg.startswith("error"):
            if msg == "ok":
                self.outgoing_messages.put(
                    UpdateMessage(type="update", form="progress", content=None)
                )
            else:
                log.error(f"Corgi returned '{msg}'")
                self.outgoing_messages.put(ErrorMessage(type="error", content=msg))

        elif (response_match := _CORGI_STATUS_RE.match(msg)) is not None:
            if self._status_requests > 0:
                self._status_requests -= 1
                self.outgoing_messages.put(
                    UpdateMessage(
                        type="update", form="status", content=response_match.group(0)
                    )
                )

            self._set_status(
                response_match.group(1), response_match.group(2)[1:].split("|")
            )
            if self._is_done():
                self._set_interface_state(InterfaceState.READY)

        elif msg.startswith("Grbl") or msg.startswith("FluidNC"):
            log.info(f"Controller booted/reset: {msg}")
            self._fetch_status()

    def _reader_loop(self):
        while self._thread_should_run:
            if not is_connected(self._proxy):
                self._try_connect()
                if not is_connected(self._proxy):
                    continue
            try:
                msg = self._proxy.read_message(timeout=0.1)
                if msg is not None:
                    self._handle_incoming_message(msg)
            except RuntimeError as e:
                log.error(f"Hardware connection lost: {e}")
                self._clean_up()
            except Exception as e:
                log.exception(f"Unexpected error in reader loop: {e}")
                sleep(1)

    def _try_connect(self) -> bool:
        sleep(self._reconnect_timeout)
        self._reconnect_timeout = (
            1
            if self._reconnect_timeout == 0
            else min(self._reconnect_timeout * 2, self.max_reconnect_timeout)
        )

        try:
            self._proxy = CommunicationProxy(driver=self._driver)
            self._proxy.connect(setup_reporting=False)
            log.info("Connected to corgi")
            self._reconnect_timeout = 0
            return True
        except (TimeoutError, RuntimeError) as e:
            log.error(f"Could not connect to corgi: {e}")
            self._proxy = None
            return False

    def connect(self):
        if self._thread_should_run and self._reader_thread.is_alive():
            self._set_interface_state(InterfaceState.READY)
            return

        self._thread_should_run = True
        self._set_interface_state(InterfaceState.READY)
        self._reader_thread = Thread(target=self._reader_loop, daemon=True)
        self._reader_thread.start()

        self._fetch_status()

    def disconnect(self):
        self._thread_should_run = False
        if self._reader_thread.is_alive():
            self._reader_thread.join(timeout=1.0)
        self._clean_up()

    def _clean_up(self):
        self._status_requests = 0
        self._set_interface_state(InterfaceState.DISCONNECTED)
        if self._proxy is not None:
            self._proxy.close()
            self._proxy = None

    def _home_cutter(self):
        with self._setup_lock:
            if is_connected(self._proxy):
                self._proxy.send("$X")
                self._proxy.send("$h")

    def abort(self):
        """
        Sends the hardware abort signal immediately.
        """
        log.info("Aborting...")
        self._status_requests = 0

        if self._proxy is not None and self._proxy.is_connected:
            self._proxy.send(self._driver.safety_shutoff_command)

        self._set_interface_state(InterfaceState.READY)
        log.info("Done")

    def request_homing(self, block: bool = False) -> bool:
        if self._interface_state in [
            InterfaceState.DISCONNECTED,
            InterfaceState.RUNNING,
        ]:
            return False

        self._home_cutter()
        log.info("Sent homing command")
        if block:
            log.info("Waiting for homing routine to be done")
            delay: int = 20
            while not self._is_homed():
                sleep(delay)
                delay = 5
            log.info("Homing complete")
        return True

    def run_job(self, lines: list[str]) -> bool:
        with self._setup_lock:
            if self._interface_state is InterfaceState.RUNNING:
                log.warning("Another job is already being executed")
                return False

            self.connect()
            if not is_connected(self._proxy):
                log.warning("Unable to connect")
                return False
            self._set_interface_state(InterfaceState.RUNNING)

            if not self._is_homed():
                self._home_cutter()

            for line in lines:
                self._proxy.send(line)
            return True