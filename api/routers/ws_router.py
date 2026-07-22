import asyncio
import logging
from queue import PriorityQueue, Queue
from typing import Tuple

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import ValidationError

from api.models.base import FrontendInput, WebsocketMessage
from core.corgi_interface import CorgiInterface
from core.pipeline.base import Pipeline
from core.pipeline.pipeline import full_pipeline


ws_router = APIRouter()

logger = logging.getLogger(__name__)


@ws_router.websocket("/ws/main")
async def websocket_endpoint(ws: WebSocket):
    corgi_interface: CorgiInterface = ws.app.state.corgi

    await ws.accept()
    print("WS Connection accepted")
    await ws_send(ws, WebsocketMessage(type="info", content="WS Connection accepted"))
    incoming_messages: PriorityQueue[Tuple[int, WebsocketMessage]] = (
        ws.app.state.incoming
    )
    outgoing_messages: Queue[WebsocketMessage] = ws.app.state.outgoing

    loop = asyncio.get_running_loop()

    async def run_job(input: FrontendInput, corgi_interface: CorgiInterface) -> bool:
        pipeline: Pipeline = full_pipeline(input)
        result: str = await loop.run_in_executor(None, pipeline.run, input.svg)
        corgi_interface.send_lines(("$h\n" + result).split("\n"))
        return True

    async def listen():
        message_priority = {"abort": 0}
        while True:
            try:
                msg = await ws.receive_json()
                print("Got message")
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
                if ws_input.type == "job":
                    if not corgi_interface.connected:
                        await ws_send(
                            ws,
                            WebsocketMessage(
                                type="error", content="Corgi not connected"
                            ),
                        )
                        continue

                    try:
                        parameters: FrontendInput = FrontendInput.model_validate_json(
                            ws_input.content
                        )
                    except ValidationError as e:
                        print(f"Couldn't validate model {ws_input.content}: {e}")
                        await ws_send(
                            ws,
                            WebsocketMessage(
                                type="error",
                                content=f"The passed parameters don't match the required ones: {ws_input.content}",
                            ),
                        )
                        continue
                    print("Running job")
                    job_is_valid = await run_job(parameters, corgi_interface)
                    logging.debug("Ran job")
                    if not job_is_valid:
                        await ws_send(
                            ws,
                            WebsocketMessage(
                                type="error",
                                content="Internal server error. Couldn't start the job.",
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
