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
from core.corgi_interface import CorgiInterface
from core.pipeline.base import Pipeline
from core.pipeline.pipeline import full_pipeline


ws_router = APIRouter()
logger = logging.getLogger(__name__)
WebsocketMessage_ta: TypeAdapter[WebsocketMessage] = TypeAdapter(WebsocketMessage)


class WebSocketContext:
    def __init__(self, websocket: WebSocket):
        self.websocket: WebSocket = websocket
        self.corgi_interface: CorgiInterface = CorgiInterface()

    async def send(self, message: WebsocketMessage):
        await self.websocket.send_json(message.model_dump())

    async def close_ws(self, code: int, reason: str):
        await self.websocket.close(code=code, reason=reason)


@ws_router.websocket("/ws/main")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    logger.info("WS Connection accepted")
    ctx = WebSocketContext(ws)
    await ctx.send(InfoMessage(type="info", content="WS Connection accepted"))

    loop = asyncio.get_running_loop()

    async def listen():
        while True:
            try:
                msg = await ws.receive_text()
                try:
                    ws_message = WebsocketMessage_ta.validate_json(msg)
                except ValidationError as e:
                    logger.exception(f"`{msg}` is an invalid message: {e}")
                    await ctx.send(
                        ErrorMessage(
                            type="error", content=f"Invalid Message recieved: {msg}"
                        ),
                    )
                    continue

                logger.info(f"Recieved {ws_message.type} Message")

                match ws_message.type:
                    case "job":
                        await execute_job(ctx, ws_message, loop)
                    case "action":
                        await handle_action(ctx, ws_message)
                    case _:
                        raise NotImplementedError(
                            f"Input type {ws_message.type} not handled yet"
                        )
            except WebSocketDisconnect:
                logger.warning("WebSocket Connection lost")
                raise

    async def broadcast():
        while True:
            output: WebsocketMessage = await loop.run_in_executor(
                None, ctx.corgi_interface.outgoing_messages.get
            )
            await ctx.send(output)

    listen_task = asyncio.create_task(listen())
    broadcast_task = asyncio.create_task(broadcast())
    try:
        await asyncio.gather(listen_task, broadcast_task)
    except Exception as e:
        logger.exception(f"Websocket disconnected due to internal error: {e}")
    finally:
        listen_task.cancel()
        broadcast_task.cancel()


async def execute_job(
    ctx: WebSocketContext, message: JobMessage, loop: asyncio.AbstractEventLoop
):
    logger.info("Running job")
    job_is_valid = await run_job(ctx, message.input, loop)
    logging.debug("Ran job")
    if not job_is_valid:
        response = ErrorMessage(
            type="error",
            content="Internal server error. Couldn't start the job.",
        )
    else:
        response = InfoMessage(type="info", content="Job's done")

    await ctx.send(response)


async def run_job(
    ctx: WebSocketContext, input: FrontendInput, loop: asyncio.AbstractEventLoop
) -> bool:
    pipeline: Pipeline = full_pipeline(input)
    result: str = await loop.run_in_executor(None, pipeline.run, input.svg)
    logger.debug(result)
    ctx.corgi_interface.run_job(result.split("\n"))
    return True


async def handle_action(ctx: WebSocketContext, input: ActionMessage):
    logger.info(f"Performing action {input.action}")
    match input.action:
        case "abort":
            ctx.corgi_interface.abort()
            pass
        case "home":
            ctx.corgi_interface.request_homing()
            pass
