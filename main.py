import Geometry3D
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import uvicorn
from api.routers.base_router import router
from api.routers.ws_router import ws_router
from fastapi.middleware.cors import CORSMiddleware


def app_factory():
    api = FastAPI(title="Laser Backend API", version="0.1.0")
    origins = [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
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

    @api.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content={"type": "error", "content": type(exc).__name__},
        )

    print(f"#{'-' * 11}#")
    return api


Geometry3D.set_sig_figures(4)
app = app_factory()


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
