from os import times_result
from core.corgi_interface import CorgiInterface, str_len
import threading
from time import sleep

BUFFER_SIZE = 10


class GCodeInterface:
    def __init__(self, address: str):
        self.buffer_used: int = 0
        self.buffer: list[str] = []

        self.time_left: int = 10

    def open(self) -> None:
        return

    def send(self, msg: str) -> None:
        assert msg.endswith("\n")

        byte_count: int = str_len(msg)
        self.buffer_used += byte_count
        self.buffer.append(msg)

        print(f"sent {msg}, buffer_used: {self.buffer_used}")

        assert self.buffer_used <= BUFFER_SIZE

    def recv(self) -> None | str:
        if self.time_left > 0:
            self.time_left -= 1
            return None
        elif len(self.buffer) > 0:
            self.time_left = 10
            msg = self.buffer.pop(0)
            self.buffer_used -= str_len(msg)
            return "ok"


def test_buffer():
    interface = CorgiInterface(GCodeInterface("asdasd"), buffer_size=BUFFER_SIZE)
    t = threading.Thread(target=interface.main_loop, daemon=True)
    t.start()

    interface.send_lines(["12345", "12345", "12", "12345", "123124214"])
    sleep(1)
    assert len(interface.queue) == 0
