import asyncio
from queue import PriorityQueue, Queue
from typing import Tuple

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from api.models.base import WebsocketMessage
from api.routers.jobs import jobs
from core.corgi_interface import CorgiInterface
from core.pipeline.base import Pipeline


ws_router = APIRouter()


@ws_router.websocket("/ws/main")
async def connect(ws: WebSocket):
    corgi_interface: CorgiInterface = ws.app.state.corgi

    await ws.accept()
    print("WS Connection accepted")
    await ws_send(ws, WebsocketMessage(type="info", content="WS Connection accepted"))
    incoming_messages: PriorityQueue[Tuple[int, WebsocketMessage]] = (
        ws.app.state.incoming
    )
    outgoing_messages: Queue[WebsocketMessage] = ws.app.state.outgoing

    loop = asyncio.get_running_loop()

    async def run_job(job_id: str, corgi_interface: CorgiInterface) -> bool:
        job = jobs.pop(job_id, None)
        if job is None:
            return False

        await ws_send(
            ws,
            WebsocketMessage(type="info", content=f"Starting job {job_id}"),
        )

        pipeline: Pipeline = job.pipeline
        result: str = await loop.run_in_executor(None, pipeline.run, job.init_value)
        corgi_interface.send_lines(("$h\n" + result).split("\n"))
        return True

    async def listen():
        message_priority = {"abort": 0}
        while True:
            try:
                msg = await ws.receive_json()
                print(f"got msg: {msg}")
                try:
                    ws_input: WebsocketMessage = WebsocketMessage.model_validate(msg)
                except ValidationError as e:
                    print(f"Invalid message received: {e}")
                    await ws_send(
                        ws,
                        WebsocketMessage(
                            type="error", content=f"Invalid Message recieved: {msg}"
                        ),
                    )
                    continue
                if ws_input.type == "job_id":
                    if not corgi_interface.connected:
                        await ws_send(
                            ws,
                            WebsocketMessage(
                                type="error", content="Corgi not connected"
                            ),
                        )
                        continue

                    job_id = str(ws_input.content)
                    job_is_valid = await run_job(job_id, corgi_interface)
                    if not job_is_valid:
                        await ws_send(
                            ws,
                            WebsocketMessage(
                                type="error",
                                content=f"Invalid job ID: {job_id}. Couldn't start the job.",
                            ),
                        )
                    else:
                        await ws_send(
                            ws,
                            WebsocketMessage(type="info", content="Job's done"),
                        )
                    continue

                priority = message_priority.get(ws_input.type, 10)
                incoming_messages.put((priority, ws_input))
            except WebSocketDisconnect:
                print("WebSocket Connection lost")
                raise

    async def broadcast():
        while True:
            output: WebsocketMessage = await loop.run_in_executor(
                None, outgoing_messages.get
            )
            await ws_send(ws, output)

    listen_task = asyncio.create_task(listen())
    broadcast_task = asyncio.create_task(broadcast())
    try:
        await asyncio.gather(listen_task, broadcast_task)
    except Exception as e:
        print(f"Websocket disconnected: {e}")
    finally:
        listen_task.cancel()
        broadcast_task.cancel()


async def ws_send(ws: WebSocket, msg: WebsocketMessage):
    await ws.send_json(msg.model_dump())


async def close_ws(ws: WebSocket, code: int, reason: str):
    await ws.close(code=code, reason=reason)
