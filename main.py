from fastapi import FastAPI
import uvicorn
from api.routers.base_router import router


def app_factory():
    api = FastAPI(title="Example FastAPI App")
    api.include_router(router)
    return api


app = app_factory()

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
