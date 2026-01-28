import asyncio
from fastapi import APIRouter, WebSocket

from core.pipeline.pipeline import full_pipline_unoptimized


ws_router = APIRouter()


@ws_router.websocket("/ws/cut_svg")
async def ws_cut_svg(ws: WebSocket):
    print("backend connected")
    await ws.accept()

    data = await ws.receive_json()
    pipeline = full_pipline_unoptimized(
        websocket=ws,
        material_thickness=data["material_thickness"],
        laser_off=data["laser_off"],
        cut_speed_mm_per_s=data["cut_speed"],
    )

    loop = asyncio.get_running_loop()

    def worker():
        result = pipeline.run(data["svg"])
        loop.call_soon_threadsafe(
            asyncio.create_task, ws.send_json({"type": "result", "content": result})
        )

    await loop.run_in_executor(None, worker)
