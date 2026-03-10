from time import sleep
import serial


def str_len(string: str) -> int:
    return len(string.encode("utf-8"))


class CorgiInterface:
    def __init__(
        self,
        serial_port: str,
        buffer_size: int = 128,
    ):
        self._interface = serial.Serial(serial_port, timeout=0.1, baudrate=115200)

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
        # print(f"DEBUG: {string}", end=)
        byte_count: int = str_len(string)
        self._interface.write(string.encode())
        self.buffer_corgi.append(string)
        self.buffer_used += byte_count

    def main_loop(self):
        while True:
            if (msg := self._interface.readline().decode()) != "":
                # print(msg, end="")
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
