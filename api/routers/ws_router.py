import asyncio
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from pydantic import TypeAdapter, ValidationError

from api.models.base import (
    ActionMessage,
    ErrorMessage,
    FrontendInput,
    InfoMessage,
    JobMessage,
    WebsocketMessage,
)
from core.corgi_interface import corgi_interface
from core.pipeline.base import Pipeline
from core.pipeline.pipeline import full_pipeline


ws_router = APIRouter()
logger = logging.getLogger(__name__)
WebsocketMessage_ta: TypeAdapter[WebsocketMessage] = TypeAdapter(WebsocketMessage)


@ws_router.websocket("/ws/main")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    print("WS Connection accepted")
    await ws_send(ws, InfoMessage(type="info", content="WS Connection accepted"))

    loop = asyncio.get_running_loop()

    async def listen():
        while True:
            try:
                msg = await ws.receive_text()
                print("Got message")
                try:
                    ws_message = WebsocketMessage_ta.validate_json(msg)
                except ValidationError as e:
                    print(f"Invalid message received: {e}")
                    await ws_send(
                        ws,
                        ErrorMessage(
                            type="error", content=f"Invalid Message recieved: {msg}"
                        ),
                    )
                    continue

                match ws_message.type:
                    case "job":
                        if not corgi_interface.connected:
                            await ws_send(
                                ws,
                                ErrorMessage(
                                    type="error", content="Corgi not connected"
                                ),
                            )
                        else:
                            await execute_job(ws, ws_message, loop)
                    case "action":
                        await handle_action(ws, ws_message)
                    case _:
                        raise NotImplementedError(
                            f"Input type {ws_message.type} not handled yet"
                        )
            except WebSocketDisconnect:
                print("WebSocket Connection lost")
                raise

    async def broadcast():
        while True:
            output: WebsocketMessage = await loop.run_in_executor(
                None, corgi_interface.outgoing_messages.get
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


async def execute_job(
    ws: WebSocket, message: JobMessage, loop: asyncio.AbstractEventLoop
):
    print("Running job")
    job_is_valid = await run_job(message.input, loop)
    logging.debug("Ran job")
    if not job_is_valid:
        response = ErrorMessage(
            type="error",
            content="Internal server error. Couldn't start the job.",
        )
    else:
        response = InfoMessage(type="info", content="Job's done")

    await ws_send(ws, response)


async def run_job(input: FrontendInput, loop: asyncio.AbstractEventLoop) -> bool:
    pipeline: Pipeline = full_pipeline(input)
    result: str = await loop.run_in_executor(None, pipeline.run, input.svg)
    await send_gcode(result.split("\n"))
    return True


async def send_gcode(lines: list[str], home: bool = True):
    corgi_interface.send_lines(["$h\n"] * home + lines)


async def handle_action(ws, input: ActionMessage):
    message_priority = {"abort": 0, "home": 1}
    match input.action:
        case "abort":
            corgi_interface.incoming_messages.put(
                (message_priority[input.action], input.action)
            )
            pass
        case "home":
            corgi_interface.incoming_messages.put(
                (message_priority[input.action], input.action)
            )
            pass
