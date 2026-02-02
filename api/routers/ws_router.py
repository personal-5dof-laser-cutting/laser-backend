import Geometry3D
from fastapi import APIRouter, WebSocket

from core.corgi_interface import CorgiInterface
from core.pipeline.pipeline import full_pipline_unoptimized
from gcode_lib.gcode_interface import GCodeInterface

import threading

ws_router = APIRouter()


@ws_router.websocket("/ws/cut_svg")
async def ws_cut_svg(ws: WebSocket):
    await ws.accept()
    Geometry3D.set_sig_figures(4)
    data = await ws.receive_json()
    pipeline = full_pipline_unoptimized(
        websocket=ws,
        material_thickness=data["material_thickness"],
        laser_off=data["laser_off"],
        cut_speed_mm_per_s=data["cut_speed"],
    )
    result: str = pipeline.run(data["svg"])
    corgi_interface = CorgiInterface(GCodeInterface("192.168.0.1:81"))
    threading.Thread(target=corgi_interface.main_loop, daemon=True).start()
    corgi_interface.send_lines(("$h\n" + result).split("\n"))
