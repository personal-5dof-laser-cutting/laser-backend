from queue import PriorityQueue, Queue
from typing import Tuple

from fastapi import APIRouter, WebSocket
from pydantic import ValidationError

from api.models.base import CorgiOutput, FrontendInput, WebsocketInput
from core.corgi_interface import CorgiInterface
from core.pipeline.pipeline import full_pipeline

import threading

ws_router = APIRouter()


@ws_router.websocket("/ws/cut_svg")
async def ws_cut_svg(ws: WebSocket):
    await ws.accept()
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
    incoming_messages: PriorityQueue[Tuple[int, WebsocketInput]] = PriorityQueue()
    outgoing_messages: Queue[CorgiOutput] = Queue()
    corgi_interface = CorgiInterface(
        "192.168.2.67:81", incoming_messages, outgoing_messages
    )
    threading.Thread(target=corgi_interface.main_loop, daemon=True).start()
    corgi_interface.send_lines(("$h\n" + result).split("\n"))
