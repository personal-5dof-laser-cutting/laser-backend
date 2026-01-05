import requests
import json


def test_unoptimized_pipeline():
    data = {
        "material_thickness": 10,
        "laser_off": True,
        "cut_speed": 10,
        "svg": open("tests/svg5dof/svgs/circle_2.svg").read(),
    }
    r = requests.post("http://127.0.0.1:8000/post", json.dumps(data))
    assert r.status_code == 200
