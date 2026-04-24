from time import sleep

from gcode_lib.gcode_interface import GCodeInterface
import serial
import serial.tools
import serial.tools.list_ports


def str_len(string: str) -> int:
    return len(string.encode("utf-8"))


class SerialInterface:
    def __init__(self, port: str):
        self._interface = serial.Serial(port)

    def send(self, message: str):
        self._interface.write(message.encode())

    def recv(self) -> str | None:
        try:
            message = self._interface.readline().decode()
        except UnicodeDecodeError as UDE:
            print(f"Could not decode message: {UDE}")
            return None
        if message == "":
            return None
        return message or None


class CorgiInterface:
    def __init__(
        self,
        address: str,
        buffer_size: int = 128,
    ):
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
                print(f"No permission for port {port}")
                break
        if len(workingPorts) > 1:
            raise RuntimeError(
                f"Too many serial devices connected: {','.join(workingPorts)}"
            )
        elif len(workingPorts) == 0:
            self._interface = GCodeInterface(address)
            self._interface.open()
        else:
            self._interface = SerialInterface(workingPorts[0])

        self.buffer_size: int = buffer_size
        self.buffer_used: int = 0
        self.buffer_corgi: list[str] = []

        self.queue: list[str] = []

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

    def main_loop(self):
        while True:
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
            sleep(0.001)
