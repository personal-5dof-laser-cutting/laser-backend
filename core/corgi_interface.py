from collections import deque
from enum import IntEnum, StrEnum, auto
from itertools import count
import logging
from queue import Empty, PriorityQueue, Queue
import re
from threading import Event, Lock, RLock, Thread
from time import sleep
from typing import Final, Optional, TypeGuard

from gcode_lib import FluidNCSerialDriver, FluidNCWebsocketsDriver, CommunicationProxy
import serial
import serial.tools
import serial.tools.list_ports
from websockets import InvalidHandshake, InvalidURI

from api.models.base import ErrorMessage, UpdateMessage, WebsocketMessage

_ALLOW_WIFI_CONNECTION: Final[bool] = False
_DISCONNECTED_STATUS: Final[str] = "Disconnected"
_CORGI_STATUS_RE: Final[re.Pattern] = re.compile(
    r"<([A-Z][a-z]+(?:\:\d+)?)((?:\|[^\|>]+)+)>"
)

log = logging.getLogger(__name__)


class CommandPriority(IntEnum):
    URGENT = auto()
    HIGH = auto()
    DEFAULT = auto()


class InterfaceState(StrEnum):
    DISCONNECTED = auto()
    READY = auto()
    RUNNING = auto()


def is_connected(
    proxy: CommunicationProxy | None,) -> TypeGuard[CommunicationProxy]:
    return proxy is not None and proxy.is_connected


class CorgiInterface:
    def __init__(
        self,
        address: str | None = None,
        port: int | None = None,
        buffer_size: int = 128,
        max_reconnect_timeout: int = 10,
    ):
        if not _ALLOW_WIFI_CONNECTION and (address is not None or port is not None):
            log.warning("Address passed but wifi connection is forbidden")

        self._address = address
        self._port = port
        self.max_reconnect_timeout: int = max_reconnect_timeout

        self._reconnect_timeout: int = 0
        self._driver: FluidNCSerialDriver | FluidNCWebsocketsDriver | None = None
        self._proxy: CommunicationProxy | None = None

        self._command_queue: deque[str] = deque()
        self._outstanding_rts: int = (
            0  # number of sent Real-Time signals without responses
        )

        self.outgoing_messages: Queue[WebsocketMessage] = Queue()

        self._setup_lock: RLock = RLock()
        self._manipulate_queue_lock: RLock = RLock()
        self._fetch_status_lock: RLock = RLock()

        self._is_fetching_status: bool = False
        self._new_status_event: Event = Event()
        self._status: str = ""
        self._status_dict: dict[str, str] = {}
        self._status_requests: int = 0

        self._thread_should_run: bool = False
        self._interface_state: InterfaceState = InterfaceState.DISCONNECTED
        self._interface_state_lock: Lock = Lock()


        self._buffer_worker_thread: Thread = Thread(
            target=self._buffer_loop, daemon=True
        )

    def _find_serial_port(self) -> str | None:
        working_ports: list[str] = []
        for port in serial.tools.list_ports.comports():
            if port.vid is None:
                continue

            try:
                s = serial.Serial(port.device)
                s.close()
                working_ports.append(port.device)
            except serial.SerialException:
                pass
            except PermissionError:
                log.warning(f"No permission for port {port.device}")
                continue

        if len(working_ports) > 1:
            raise RuntimeError(
                f"Too many serial devices connected: {','.join(working_ports)}"
            )
        elif len(working_ports) == 0:
            return None

        return working_ports[0]

    def _try_connect(self) -> bool:
        if not is_connected(self._proxy) or self._driver is None:
            sleep(self._reconnect_timeout)
            self._reconnect_timeout = (
                1
                if self._reconnect_timeout == 0
                else min(self._reconnect_timeout * 2, self.max_reconnect_timeout)
            )

            serial_port = self._find_serial_port()
            if serial_port:
                self._driver = FluidNCSerialDriver(serial_port)
            else:
                if not _ALLOW_WIFI_CONNECTION or self._address is None:
                    log.error(
                        "No serial port detected. Connection to Corgi not possible"
                    )
                    self._driver = None
                    return False
                else:
                    self._driver = FluidNCWebsocketsDriver(self._address, self._port)
        try:

            self._proxy = CommunicationProxy(driver=self._driver).connect(setup_reporting=False)
            log.info("Connected to corgi")
            self._reconnect_timeout = 0
        except (
            serial.SerialException,
            InvalidURI,
            OSError,
            InvalidHandshake,
            TimeoutError,
        ) as e:
            log.error(f"Could not connect to corgi: {e}")
            self._proxy = None
            self._driver = None

        return is_connected(self._proxy)

    def _is_homed(self) -> bool:
        status, _ = self._get_status()
        if status == _DISCONNECTED_STATUS:
            return False

        if status.startswith("Alarm"):
            log.info(f"Corgi is in Alarmstate: {status}")
            return False

        return True

    def _is_done(self) -> bool:
        with self._setup_lock:
            with self._manipulate_queue_lock:
                queue_empty = len(self._command_queue) == 0
                rts_empty = self._outstanding_rts == 0

            return (
                queue_empty and rts_empty and self._is_in_done_status()
            )

    def _is_in_done_status(self):
        return self._status in [_DISCONNECTED_STATUS, "Idle", "Alarm"]

    def _is_real_time_signal(self, command: str) -> bool:
        return command.strip() in [
            "?",
            "!",
            "~",
            "\x18",
        ]  # 0x18 is Ctrl+X: reset / emergency stop

    def _set_interface_state(self, state: InterfaceState):
        with self._interface_state_lock:
            self._interface_state = state

    def _fetch_status(self):
        if not is_connected(self._proxy):
            return
        with self._fetch_status_lock:
            if not self._is_fetching_status:
                log.info("Fetching cutter status")
                self._new_status_event.clear()
                self._send_command("?", internal=True)
                self._is_fetching_status = True

    def _get_status(self) -> tuple[str, dict[str, str]]:
        if not is_connected(self._proxy):
            log.warning("Corgi not connected")
            self._status = _DISCONNECTED_STATUS
            self._status_dict = {}
        else:
            self._fetch_status()
            self._new_status_event.wait()
        return self._status, self._status_dict

    def _set_status(self, status_message: str, status_infos: list[str]):
        status_dict = dict(info.split(":") for info in status_infos)
        with self._fetch_status_lock:
            self._is_fetching_status = False
            self._status = status_message
            self._status_dict = status_dict
            self._new_status_event.set()

    def _send_command(
        self,
        line: str,
        internal: bool,
    ):
        if not is_connected(self._proxy):
            return
        line_cleaned: str = line.rstrip("\n") + "\n"

        with self._manipulate_queue_lock:
            if line_cleaned == "?\n":
                self._outstanding_rts += 1
                if not internal:
                    self._status_requests += 1
            self._proxy.send(line_cleaned)

    def _send_commands(
        self,
        lines: list[str],
        internal: bool,
    ):
        for line in lines:
            self._send_command(line, internal)

    def _handle_incoming_message(self, msg: str):
        msg = msg.strip()
        if not msg:
            return

        if msg == "ok":
            self.outgoing_messages.put(
                UpdateMessage(type="update", form="progress", content=None)
            )
        elif msg.startswith("error"):
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
            with self._manipulate_queue_lock:
                self._outstanding_rts = max(0, self._outstanding_rts - 1)

            self._set_status(
                response_match.group(1), response_match.group(2)[1:].split("|")
            )
            if self._is_done():
                self._set_interface_state(InterfaceState.READY)

        elif msg.startswith("Grbl") or msg.startswith("FluidNC"):
            log.info(f"Controller booted/reset: {msg}")

            # The hardware resets its RX buffer entirely on boot. We must match it
            # otherwise Python hangs waiting for responses to vaporized commands.
            with self._manipulate_queue_lock:
                self._outstanding_rts = 0

            self._fetch_status()


    def _work_buffer(self):
        if not is_connected(self._proxy):
            return

        # Adaptive Polling: lower CPU usage to near 0 when we're completely idle
        with self._manipulate_queue_lock:
            is_idle = (
                len(self._command_queue) == 0
                and self._outstanding_rts == 0
            )

        read_timeout = 0.1 if is_idle else 0.01

        msg = self._proxy.read_message(timeout=read_timeout)
        if msg is not None:
            self._handle_incoming_message(msg)

    def _buffer_loop(self):
        while self._thread_should_run:
            try:
                if is_connected(self._proxy) or self._try_connect():
                    self._work_buffer()
            except (serial.SerialException, OSError) as e:
                log.error(f"Hardware connection lost: {e}")
                self._clean_up()
            except Exception as e:
                log.exception(f"Unexpected error in buffer loop: {e}")
                sleep(1)

    def connect(self):
        with self._manipulate_queue_lock:
            if self._thread_should_run and self._buffer_worker_thread.is_alive():
                self._set_interface_state(InterfaceState.READY)
                return

            self._command_queue.clear()
            self._thread_should_run = True
            self._set_interface_state(InterfaceState.READY)
            self._buffer_worker_thread = Thread(target=self._buffer_loop, daemon=True)
            self._buffer_worker_thread.start()

        self._send_command("?", internal=False)

    def disconnect(self):
        self._thread_should_run = False
        if self._buffer_worker_thread.is_alive():
            self._buffer_worker_thread.join(timeout=1.0)
        self._clean_up()

    def _clean_up(self):
        with self._manipulate_queue_lock:
            self._command_queue.clear()
            self._outstanding_rts = 0
            self._set_interface_state(InterfaceState.DISCONNECTED)
            if is_connected(self._proxy):
                self._proxy.close()
                self._proxy = None

    def _home_cutter(self):
        with self._setup_lock:
            # Send an explicit Unlock ($X) directly before homing to force
            # the machine out of any lingering abort/limit alarm states
            self._send_command("$X", internal=True)
            self._send_command("$h", internal=True)

        self.outgoing_messages.put(UpdateMessage(type="update", form="status", content="homed"))
        

    def send_command(self, line: str):
        self._send_command(line, internal=False)

    def abort(self):
        """
        Sends the hardware abort signal immediately and clears queued events.
        """
        log.info("Aborting...")
        with self._manipulate_queue_lock:
            self._command_queue.clear()

            self._outstanding_rts = 0
            self._status_requests = 0

            if is_connected(self._proxy):
                self._send_command(self._proxy._driver.safety_shutoff_command, internal=True)

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
            self._set_interface_state(InterfaceState.RUNNING)

            if not self._is_homed():
                return False

            self._send_commands(lines, internal=False)
            return True
