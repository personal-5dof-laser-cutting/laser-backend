from src.core.service_container import Container
from fastapi import FastAPI
from src.api.routers.base_router import router


def app_factory():
    api = FastAPI(title="Example FastAPI App")
    Container()  # initialize Dependency Injection Container
    api.include_router(router)
    return api


app = app_factory()
