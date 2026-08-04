from collections import deque
from enum import IntEnum, StrEnum, auto
from itertools import count
import logging
from queue import Empty, PriorityQueue, Queue
import re
from threading import Event, Lock, RLock, Thread
from time import sleep
from typing import Final, Optional, TypeGuard

from gcode_lib.gcode_interface import GCodeInterface
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


def _str_len(string: str) -> int:
    return len(string.encode("utf-8"))


class SerialInterface:
    _interface: serial.Serial

    def __init__(self, port: str):
        self._interface = serial.Serial(port, baudrate=115200, timeout=0.5)
        sleep(0.5)
        if self._interface.in_waiting > 0:
            boot_logs = self._interface.read(self._interface.in_waiting).decode(
                "utf-8", errors="ignore"
            )
            log.info("Corgi Controller Booted successfully")
            log.debug(boot_logs)
        else:
            log.info("No boot logs detected, sending wake-up ping...")
            self._interface.write(b"\r\n")
            sleep(0.2)
            if self._interface.in_waiting > 0:
                log.info(
                    f"Corgi Wake-up response: {self._interface.read(self._interface.in_waiting).decode('utf-8', errors='ignore').strip()}"
                )

    def open(self) -> "SerialInterface":
        if not self._interface.is_open:
            self._interface.open()
        return self

    def close(self):
        self._interface.close()

    def send(self, message: str):
        self._interface.write(message.encode("utf-8"))

    def recv(self, timeout: Optional[float] = None) -> str | None:
        self._interface.timeout = 0 if timeout is None else timeout
        try:
            message = self._interface.readline().decode("utf-8")
        except UnicodeDecodeError as UDE:
            log.warning(f"Could not decode message: {UDE}")
            return None
        return message or None


class CommandPriority(IntEnum):
    URGENT = auto()
    HIGH = auto()
    DEFAULT = auto()


class InterfaceState(StrEnum):
    DISCONNECTED = auto()
    READY = auto()
    RUNNING = auto()


def is_connected(
    interface: SerialInterface | GCodeInterface | None,
) -> TypeGuard[SerialInterface | GCodeInterface]:
    return interface is not None


type QueueContentType = tuple[CommandPriority, int, str]


class CorgiInterface:
    def __init__(
        self,
        address: str | None = None,
        buffer_size: int = 128,
        max_reconnect_timeout: int = 10,
    ):
        if not _ALLOW_WIFI_CONNECTION and address is not None:
            log.warning("Address passed but wifi connection is forbidden")

        self._address = address
        self._buffer_size: int = buffer_size
        self.max_reconnect_timeout: int = max_reconnect_timeout

        self._reconnect_timeout: int = 0
        self._interface: GCodeInterface | SerialInterface | None = None

        self._buffer_corgi: deque[int] = deque()
        self._buffer_used: int = 0
        self._outstanding_rts: int = (
            0  # number of sent Real-Time signals without responses
        )

        self.outgoing_messages: Queue[WebsocketMessage] = Queue()

        self._setup_lock: RLock = RLock()
        self._manipulate_queue_lock: Lock = Lock()
        self._fetch_status_lock: Lock = Lock()

        self._is_fetching_status: bool = False
        self._new_status_event: Event = Event()
        self._status: str = ""
        self._status_dict: dict[str, str] = {}

        self._thread_should_run: bool = False
        self._interface_state: InterfaceState = InterfaceState.DISCONNECTED
        self._interface_state_lock: Lock = Lock()

        self._command_queue: PriorityQueue[QueueContentType] = PriorityQueue()
        self._count = count()

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
        if not is_connected(self._interface):
            sleep(self._reconnect_timeout)
            self._reconnect_timeout = (
                1
                if self._reconnect_timeout == 0
                else min(self._reconnect_timeout * 2, self.max_reconnect_timeout)
            )
            self._buffer_used = 0
            self._buffer_corgi.clear()
            self._outstanding_rts = 0

            serial_port = self._find_serial_port()
            if serial_port:
                self._interface = SerialInterface(serial_port)
            else:
                if not _ALLOW_WIFI_CONNECTION or self._address is None:
                    log.error(
                        "No serial port detected. Connection to Corgi not possible"
                    )
                    self._interface = None
                    return False
                else:
                    self._interface = GCodeInterface(self._address)
        try:
            self._interface.open()
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
            self._interface = None

        return is_connected(self._interface)

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
            return (
                self._command_queue.empty()
                and self._buffer_used == 0
                and self._outstanding_rts == 0
                and self._is_in_done_status()
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
        if not is_connected(self._interface):
            return
        with self._fetch_status_lock:
            if not self._is_fetching_status:
                log.info("Fetching cutter status")
                self._new_status_event.clear()
                self._prime_command("?", CommandPriority.HIGH)
                self._is_fetching_status = True

    def _get_status(self) -> tuple[str, dict[str, str]]:
        if not is_connected(self._interface):
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

    def _send_to_corgi(self, string: str):
        if not is_connected(self._interface):
            return
        byte_count: int = _str_len(string)
        self._interface.send(string)
        self._buffer_corgi.append(byte_count)
        self._buffer_used += byte_count

    def _prime_command(
        self, line: str, priority: CommandPriority = CommandPriority.DEFAULT
    ):
        line_cleaned: str = line.rstrip("\n") + "\n"
        byte_count = _str_len(line_cleaned)
        if byte_count > self._buffer_size:
            raise ValueError(
                f"Line too long. Buffer length: {self._buffer_size} bytes (passed string: {byte_count})"
            )
        self._command_queue.put((priority, next(self._count), line_cleaned))

    def _prime_commands(
        self, lines: list[str], priority: CommandPriority = CommandPriority.DEFAULT
    ):
        for line in lines:
            self._prime_command(line, priority)

    def _get_command(self) -> QueueContentType | None:
        try:
            return self._command_queue.get_nowait()
        except Empty:
            return None

    def _handle_incoming_message(self, msg: str):
        msg = msg.strip()
        if not msg:
            return

        if msg == "ok" and len(self._buffer_corgi) > 0:
            self.outgoing_messages.put(
                UpdateMessage(type="update", form="progress", content=None)
            )
            popped_bytes: int = self._buffer_corgi.popleft()
            self._buffer_used = max(0, self._buffer_used - popped_bytes)

            if self._command_queue.empty() and self._buffer_used == 0:
                self._fetch_status()

        elif msg.startswith("error"):
            log.error(f"Corgi returned '{msg}'")
            self.outgoing_messages.put(ErrorMessage(type="error", content=msg))

        elif (response_match := _CORGI_STATUS_RE.match(msg)) is not None:
            self.outgoing_messages.put(
                UpdateMessage(
                    type="update", form="status", content=response_match.group(0)
                )
            )
            self._outstanding_rts = max(0, self._outstanding_rts - 1)
            self._set_status(
                response_match.group(1), response_match.group(2)[1:].split("|")
            )
            if self._is_done():
                self._set_interface_state(InterfaceState.READY)

        elif msg.startswith("Grbl") or msg.startswith("FluidNC"):
            log.info(f"Controller booted/reset: {msg}")
            self._fetch_status()

    def _process_outgoing_commands(self):
        if is_connected(self._interface) and (item := self._get_command()) is not None:
            priority, count_idx, command = item
            free_buffer = self._buffer_size - self._buffer_used

            if self._is_real_time_signal(command):
                self._interface.send(command)
                self._outstanding_rts += 1
                self._command_queue.task_done()

            elif _str_len(command) <= free_buffer:
                self._send_to_corgi(command)
                self._command_queue.task_done()

            else:
                self._command_queue.put((priority, count_idx, command))

    def _work_buffer(self):
        if not is_connected(self._interface):
            return

        is_idle = (
            self._command_queue.empty()
            and self._buffer_used == 0
            and self._outstanding_rts == 0
        )
        read_timeout = 0.1 if is_idle else 0.01

        msg = self._interface.recv(timeout=read_timeout)
        if msg is not None:
            self._handle_incoming_message(msg)

        self._process_outgoing_commands()

    def _buffer_loop(self):
        while self._thread_should_run:
            try:
                if self._interface is not None or self._try_connect():
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

            self._command_queue = PriorityQueue()
            self._thread_should_run = True
            self._set_interface_state(InterfaceState.READY)
            self._buffer_worker_thread = Thread(target=self._buffer_loop, daemon=True)
            self._buffer_worker_thread.start()
            self._prime_command("?")

    def disconnect(self):
        self._thread_should_run = False
        if self._buffer_worker_thread.is_alive():
            self._buffer_worker_thread.join(timeout=1.0)
        self._clean_up()

    def _clean_up(self):
        with self._manipulate_queue_lock:
            self._command_queue = PriorityQueue()
            self._buffer_corgi.clear()
            self._buffer_used = 0
            self._outstanding_rts = 0
            self._set_interface_state(InterfaceState.DISCONNECTED)
            if is_connected(self._interface):
                self._interface.close()
                self._interface = None

    def _home_cutter(self):
        with self._setup_lock:
            self._prime_command("$h", CommandPriority.HIGH)

    def abort(self, legacy: bool = False):
        """
        Sends the hardware abort signal immediately and clears queued events.
        """
        with self._manipulate_queue_lock:
            while not self._command_queue.empty():
                try:
                    self._command_queue.get_nowait()
                except Empty:
                    break

            self._buffer_corgi.clear()
            self._buffer_used = 0
            self._outstanding_rts = 0

            if is_connected(self._interface):
                self._interface.send("M112\n" if legacy else "\x18")

            self._set_interface_state(InterfaceState.READY)

    def request_homing(self, block: bool = False) -> bool:
        if self._interface_state in [
            InterfaceState.DISCONNECTED,
            InterfaceState.RUNNING,
        ]:
            return False

        self._home_cutter()
        if block:
            delay: int = 20
            while not self._is_homed():
                sleep(delay)
                delay = 5
        return True

    def run_job(self, lines: list[str]) -> bool:
        with self._setup_lock:
            if self._interface_state is InterfaceState.RUNNING:
                log.warning("Another job is already being executed")
                return False

            self.connect()
            self._set_interface_state(InterfaceState.RUNNING)

            if not self._is_homed():
                self._home_cutter()

            self._prime_commands(lines)
            return True
