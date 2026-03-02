from gcode_lib.gcode_interface import GCodeInterface

from core.corgi_interface import CorgiInterface
import threading
from time import time, sleep
from pytest_mock import MockerFixture

BUFFER_SIZE = 10


def test_buffer(mocker: MockerFixture):
    mock_interface = mocker.Mock(spec=GCodeInterface)
    mock_interface.recv.return_value = "ok"
    corgi_interface = CorgiInterface(mock_interface, buffer_size=BUFFER_SIZE)

    t = threading.Thread(target=corgi_interface.main_loop, daemon=True)
    t.start()

    lines = ["12345", "12345", "12", "12345", "123124214"]
    corgi_interface.send_lines(lines)

    start_time = time()
    while len(corgi_interface.queue) > 0 and time() - start_time < 20:
        sleep(0.01)
    assert len(corgi_interface.queue) == 0
    mock_interface.open.assert_called_once()
    assert mock_interface.send.call_count == len(lines)
    for line in lines:
        mock_interface.send.assert_any_call(line + "\n")
    mock_interface.recv.assert_called()
