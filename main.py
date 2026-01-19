from fastapi import FastAPI
import uvicorn
from api.routers.base_router import router
from fastapi.middleware.cors import CORSMiddleware


def app_factory():
    api = FastAPI(title="Example FastAPI App")
    origins = [
        "http://localhost:8080",
        "http://127.0.0.1:8080",
    ]
    api.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    api.include_router(router)
    return api


app = app_factory()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
