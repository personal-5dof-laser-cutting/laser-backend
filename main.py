from fastapi import FastAPI
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
    print(f"#{'-' * 11}#")
    return api


app = app_factory()


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
