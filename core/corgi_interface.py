from collections import deque
from enum import IntEnum, StrEnum, auto
from itertools import count
import logging
from queue import Empty, PriorityQueue, Queue, ShutDown
import re
from threading import Event, Lock, RLock, Thread
from time import sleep
import time
from typing import Final, Optional, TypeGuard

from gcode_lib.gcode_interface import GCodeInterface
import serial
import serial.tools
import serial.tools.list_ports
from websockets import InvalidHandshake, InvalidURI

from api.models.base import UpdateMessage, WebsocketMessage

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

    def open(self) -> SerialInterface:
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
    """
    The Priorities are listed in order of their Priority descending
    Meaning URGENT has the highest Priority and DEFAULT the lowest
    PriorityQueue pops the lowest element which is why higher Priority has a lower integer value
    """

    URGENT = auto()
    HIGH = auto()
    DEFAULT = auto()


class InterfaceState(StrEnum):
    DISCONNECTED = auto()
    ABORTED = auto()
    READY = auto()
    RUNNING = auto()


def is_connected(
    interface: SerialInterface | GCodeInterface | None,
) -> TypeGuard[SerialInterface | GCodeInterface]:
    return interface is not None


type QueueContentType = tuple[CommandPriority, int, str]


class CorgiAbortedError(Exception):
    pass


class CorgiInterface:
    def __init__(
        self,
        address: str | None = None,
        buffer_size: int = 128,
        max_reconnect_timeout: int = 10,
        idle_disconnect_timeout_min: int = 10,
    ):
        if not _ALLOW_WIFI_CONNECTION and address is not None:
            log.warning("Address passed but wifi connection is forbidden")
        self._address = address
        self._buffer_size: int = buffer_size
        self.max_reconnect_timeout: int = max_reconnect_timeout
        self.idle_timeout = idle_disconnect_timeout_min

        self._reconnect_timeout: int = 0
        self._interface: GCodeInterface | SerialInterface | None = None

        self._buffer_corgi: deque[int] = deque()
        self._buffer_used: int = 0
        self._is_buffer_space_enough: bool = True
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
        self._idle_since: float | None = time.time()

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
        """
        TODO:
            If the inferface disconnects, we have no way of knowing how the Corgi buffer looks like.
            Maybe an exception needs to be raised or CorgiInterface needs to be fully reset.
        """
        if not is_connected(self._interface):
            sleep(self._reconnect_timeout)
            self._reconnect_timeout = (
                1
                if self._reconnect_timeout == 0
                else min(self._reconnect_timeout * 2, self.max_reconnect_timeout)
            )
            self._buffer_used = 0
            self._buffer_corgi.clear()
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
            if not self._command_queue.empty():
                return False
            if not self._buffer_used == 0:
                return False

            if not self._outstanding_rts == 0:
                return False

            return self._is_in_done_status()

    def _is_in_done_status(self):
        return self._status in [_DISCONNECTED_STATUS, "Idle", "Alarm"]

    def _is_real_time_signal(self, command: str) -> bool:
        return command.strip() in [
            "?",
            "!",
            "~",
            b"\x18",
        ]  # 0x18 is Ctrl+X, reset / emergency stop

    def _check_not_aborted(self):
        if self._interface_state is InterfaceState.ABORTED:
            raise CorgiAbortedError()

    def _set_interface_state(self, state: InterfaceState):
        with self._interface_state_lock:
            if self._interface_state is not InterfaceState.ABORTED:
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
                f"Line too long. The buffer has a length of {self._buffer_size} bytes (passed string contains {byte_count})"
            )
        try:
            self._command_queue.put((priority, next(self._count), line_cleaned))
        except ShutDown:
            log.warning("Command sent even though queue was shut down")

    def _prime_commands(
        self, lines: list[str], priority: CommandPriority = CommandPriority.DEFAULT
    ):
        for line in lines:
            self._prime_command(line, priority)

    def _get_command(self) -> QueueContentType | None:
        try:
            return self._command_queue.get_nowait()
        except Empty, ShutDown:
            return None

    def _work_buffer(self):
        if not is_connected(self._interface):
            return

        if (msg := self._interface.recv(timeout=0.001)) is not None:
            msg = msg.strip()
            log.info(f"Corgi: {msg}")
            if msg == "ok" and len(self._buffer_corgi) > 0:
                self.outgoing_messages.put(
                    UpdateMessage(type="update", form="progress", content=None)
                )
                byte_count: int = self._buffer_corgi.popleft()
                self._buffer_used -= byte_count

                assert self._buffer_used >= 0
                if self._command_queue.empty() and self._buffer_used == 0:
                    self._fetch_status()
            elif msg.startswith("error"):
                log.error(f"Corgi returned '{msg}'")
                raise RuntimeError(f"Corgi returned '{msg}")
            elif (response_match := _CORGI_STATUS_RE.match(msg)) is not None:
                self.outgoing_messages.put(
                    UpdateMessage(
                        type="update", form="status", content=response_match.group(0)
                    )
                )
                self._outstanding_rts -= 1
                self._set_status(
                    response_match.group(1), response_match.group(2)[1:].split("|")
                )
                if self._is_done():
                    self._set_interface_state(InterfaceState.READY)
                    self._idle_since = time.time()

        if (item := self._get_command()) is not None:
            free_buffer = self._buffer_size - self._buffer_used
            command = item[2]
            if self._is_real_time_signal(command):
                self._interface.send(command)
                self._outstanding_rts += 1
            elif _str_len(command) <= free_buffer:
                log.info(f"Sending command {command}")
                self._send_to_corgi(command)
                self._is_buffer_space_enough = True
                assert self._buffer_used <= self._buffer_size
            else:
                self._is_buffer_space_enough = False
                self._command_queue.put(item)
            self._command_queue.task_done()
        else:
            self._is_buffer_space_enough = True

    def _buffer_loop(self):
        while self._thread_should_run and self._idle_time_minutes() < self.idle_timeout:
            try:
                if self._interface is not None or self._try_connect():
                    self._work_buffer()
            except (serial.SerialException, OSError) as e:
                log.error(e)
                self._interface = None
            except Exception as e:
                log.exception(e)
                break
        self._clean_up()

    def _idle_time_minutes(self) -> float:
        if self._idle_since is None:
            return -1
        return (time.time() - self._idle_since) / 60

    def connect(self):
        with self._manipulate_queue_lock:
            if self._interface_state is not InterfaceState.DISCONNECTED:
                return

            self._idle_since = None
            self._check_not_aborted()
            self._command_queue = PriorityQueue()
            self._prime_command("?")
            self._thread_should_run = True
            self._set_interface_state(InterfaceState.READY)
            self._buffer_worker_thread = Thread(target=self._buffer_loop, daemon=True)
            self._buffer_worker_thread.start()

    def disconnect(self):
        """
        Implicitly calls _clean_up() because it sets _thread_should_run to False, which will cause the While-Loop in _buffer_loop to end
        """
        self._thread_should_run = False
        self._buffer_worker_thread.join()

    def _clean_up(self):
        with self._manipulate_queue_lock:
            self._command_queue = PriorityQueue()
            self._set_interface_state(InterfaceState.DISCONNECTED)
            if is_connected(self._interface):
                self._interface.close()
                self._interface = None

    def _home_cutter(self):
        with self._setup_lock:
            self._prime_command("$h", CommandPriority.HIGH)

    def abort(self):
        # TODO: Use 0x18 (Ctrl+X) instead of M112
        with self._manipulate_queue_lock:
            aborted_queue: PriorityQueue[QueueContentType] = PriorityQueue()
            aborted_queue.put((CommandPriority.URGENT, next(self._count), "M112"))
            aborted_queue.shutdown()
            self._command_queue = aborted_queue
            self._command_queue.join()
            self._set_interface_state(InterfaceState.ABORTED)
            self.disconnect()

    def request_homing(self, block: bool = False) -> bool:
        self._check_not_aborted()

        self._idle_since = None
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
            self._check_not_aborted()

            self._idle_since = None
            if self._interface_state is InterfaceState.RUNNING:
                log.warning("Another job is already being executed")
                return False
            self.connect()
            self._set_interface_state(InterfaceState.RUNNING)
            if not self._is_homed():
                self._home_cutter()
            self._prime_commands(lines)
            return True
