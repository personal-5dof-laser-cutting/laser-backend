import logging
from logging.config import dictConfig
import os

import Geometry3D
from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
from api.models.base import ResponseMessage
from api.routers.base_router import router
from api.routers.ws_router import ws_router
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

if os.getenv("ENVIRONMENT", "production") == "production":
    logging_level = logging.INFO
else:
    logging_level = logging.DEBUG

logging_config = dict(
    version=1,
    formatters={
        "f": {"format": "%(asctime)s [%(name)s %(levelname)s] %(message)s"},
    },
    handlers={
        "h": {
            "class": "logging.StreamHandler",
            "formatter": "f",
            "level": logging_level,
        }
    },
    root={"handlers": ["h"], "level": logging_level},
    disable_existing_loggers=False,
)
dictConfig(logging_config)


def app_factory():
    api = FastAPI(title="Laser Backend API", version="0.1.0")

    @api.middleware("http")
    async def catch_exceptions_middleware(request: Request, call_next):
        try:
            return await call_next(request)
        except Exception as exc:
            logging.exception(
                f"Unhandled exception while processing request: {str(exc)}"
            )
            return JSONResponse(
                status_code=500,
                content=ResponseMessage(
                    type="error",
                    reason=type(exc).__name__,
                    content="Internal server error",
                ).model_dump(),
            )

    origins = [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]
    api.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["Content-Disposition"],
    )

    api.include_router(router)
    api.include_router(ws_router)

    print(f"#{'-' * 11}#")
    return api


Geometry3D.set_sig_figures(4)
app = app_factory()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
