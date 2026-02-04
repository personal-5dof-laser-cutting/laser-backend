import Geometry3D
from fastapi import APIRouter, WebSocket
from pydantic import ValidationError

from api.models.base import FrontendInput
from core.corgi_interface import CorgiInterface
from core.pipeline.pipeline import full_pipeline
from gcode_lib.gcode_interface import GCodeInterface

import threading

ws_router = APIRouter()


@ws_router.websocket("/ws/cut_svg")
async def ws_cut_svg(ws: WebSocket):
    await ws.accept()
    Geometry3D.set_sig_figures(4)
    data = await ws.receive_json()
    print("recieved data")
    try:
        frontendInput = FrontendInput(**data)
    except ValidationError as e:
        await ws.send_json({"type": "error", "content": e.errors()})
        print(f"Error parsing Frontend Inputs:\n{e}")
        return
    pipeline = full_pipeline(frontendInput)
    result: str = pipeline.run(data["svg"])
    corgi_interface = CorgiInterface(GCodeInterface("192.168.2.67:81"))
    threading.Thread(target=corgi_interface.main_loop, daemon=True).start()
    corgi_interface.send_lines(("$h\n" + result).split("\n"))
