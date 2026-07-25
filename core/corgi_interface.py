import logging
from queue import Empty, PriorityQueue, Queue
from time import sleep
from typing import Tuple

from gcode_lib.gcode_interface import GCodeInterface
import serial
import serial.tools
import serial.tools.list_ports

from api.models.base import CutterActions, ErrorMessage, InfoMessage, WebsocketMessage

log = logging.getLogger("Corgi Interface")


def str_len(string: str) -> int:
    return len(string.encode("utf-8"))


ALLOW_WIFI_CONNECTION = False


class SerialInterface:
    _interface: serial.Serial

    def __init__(self, port: str):
        self._interface = serial.Serial(port, baudrate=115200, timeout=0.5)
        self._interface.dtr = False
        sleep(0.1)
        self._interface.dtr = True
        sleep(2)
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

    def open(self):
        if not self._interface.is_open:
            self._interface.open()

    def send(self, message: str):
        self._interface.write(message.encode("utf-8"))

    def recv(self) -> str | None:
        try:
            if self._interface.in_waiting == 0:
                return None
            message = self._interface.readline().decode("utf-8")
        except UnicodeDecodeError as UDE:
            log.warning(f"Could not decode message: {UDE}")
            return None
        return message or None


class _CorgiInterface:
    _interface: GCodeInterface | SerialInterface
    incoming_messages: PriorityQueue[Tuple[int, CutterActions]] = PriorityQueue()
    outgoing_messages: Queue[WebsocketMessage] = Queue()

    def __init__(
        self,
        address: str | None = None,
        buffer_size: int = 128,
    ):
        if not ALLOW_WIFI_CONNECTION and address is not None:
            log.warning("Address passed but wifi connection is forbidden")
        self.address = address
        self.buffer_size: int = buffer_size
        self.buffer_used: int = 0
        self.buffer_corgi: list[str] = []
        self.connected = False

        self.queue: list[str] = []

    def _find_serial_port(self) -> str | None:
        serial_ports: list[str] = [
            port.device
            for port in serial.tools.list_ports.comports()
            if port.vid is not None
        ]
        workingPorts: list[str] = []

        for port in serial_ports:
            try:
                s = serial.Serial(port)
                s.close()
                workingPorts.append(port)
            except serial.SerialException:
                pass
            except PermissionError:
                log.debug(f"No permission for port {port}")
                break
        if len(workingPorts) > 1:
            raise RuntimeError(
                f"Too many serial devices connected: {','.join(workingPorts)}"
            )
        elif len(workingPorts) == 0:
            return None

        return workingPorts[0]

    def _try_connect(self) -> bool:
        try:
            self._interface.open()
            self.connected = True
            self.buffer_used = 0
            self.buffer_corgi.clear()
            log.info("Connected to corgi")
        except AttributeError:
            serial_port = self._find_serial_port()
            if serial_port:
                self._interface = SerialInterface(serial_port)
            else:
                if not ALLOW_WIFI_CONNECTION or self.address is None:
                    log.error(
                        "No serial port detected. Connection to Corgi not possible"
                    )
                    self.connected = False
                    return self.connected
                else:
                    self._interface = GCodeInterface(self.address)
            self._try_connect()
        except Exception as e:
            log.error(f"Could not connect to corgi: {e}")
            self.connected = False

        return self.connected

    def _check_messages(self) -> str:
        try:
            _, action = self.incoming_messages.get_nowait()
            return action
        except Empty:
            return ""

    def send_line(self, line: str):
        line_cleaned: str = line.rstrip("\n") + "\n"
        byte_count = str_len(line_cleaned)
        if byte_count > self.buffer_size:
            raise Exception("Line too long")
        self.queue.append(line_cleaned)

    def send_lines(self, lines: list[str]):
        for line in lines:
            self.send_line(line)

    def _send_to_corgi(self, string: str):
        byte_count: int = str_len(string)
        self._interface.send(string)
        self.buffer_corgi.append(string)
        self.buffer_used += byte_count

    def _abort(self):
        self.queue.clear()
        self.send_line("M112")

    def _tick(self):
        if ws_msg := self._check_messages():
            if ws_msg == "abort":
                self._abort()
        if (msg := self._interface.recv()) is not None:
            if msg.strip() == "ok" and len(self.buffer_corgi) > 0:
                processed_command: str = self.buffer_corgi.pop(0)
                byte_count: int = str_len(processed_command)
                self.buffer_used -= byte_count

                assert self.buffer_used >= 0
            elif msg.startswith("error"):
                raise Exception(f"Corgi returned '{msg}'")

        if len(self.queue) > 0:
            next_command: str = self.queue[0]
            free_buffer = self.buffer_size - self.buffer_used

            if str_len(next_command) <= free_buffer:
                self._send_to_corgi(next_command)
                self.queue.pop(0)

                assert self.buffer_used <= self.buffer_size

    def main_loop(self):
        while True:
            if not self.connected:
                if self._try_connect():
                    self.outgoing_messages.put(
                        InfoMessage(type="info", content="Corgi connected")
                    )
                else:
                    log.info(
                        f"Wating {self.reconnect_timeout:>2} second{'s' * (self.reconnect_timeout != 1)} to reconnect"
                    )
                    sleep(self.reconnect_timeout)
                    self.reconnect_timeout = min(
                        self.reconnect_timeout * 2, self.max_reconnect_timeout
                    )
                    continue
            try:
                self._tick()
            except Exception as e:
                self.connected = False
                log.error(f"Error running main loop: {e}")
                self.outgoing_messages.put(
                    ErrorMessage(type="error", content="Corgi disconnected")
                )
            sleep(0.001)


corgi_interface: _CorgiInterface = _CorgiInterface()
