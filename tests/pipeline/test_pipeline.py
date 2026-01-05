import requests
import json
import uvicorn
import threading
from time import sleep


def start_backend():
    from main import app

    uvicorn.run(app, host="127.0.0.1", port=8000)


def test_unoptimized_pipeline():
    threading.Thread(target=start_backend, daemon=True).start()
    sleep(5)

    data = {
        "material_thickness": 10,
        "laser_off": True,
        "cut_speed": 10,
        "svg": open("tests/svg5dof/svgs/circle_2.svg").read(),
    }
    r = requests.post("http://127.0.0.1:8000/post", json.dumps(data))
    assert r.status_code == 200
