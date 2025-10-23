import logging


class BaseService:
    """Base service class. All services should inherit from this class.

    ALWAYS create a base service and a service implementation:
        MyService(BaseService):
            pass # define the interface of MyService

        MyServiceImpl(MyService):
            pass # define the implementation of MyService

    Also, list your service in the service_container.py file for Dependency Injection.
    """

    def __init__(self) -> None:
        self.logger = logging.getLogger(
            f"{__name__}.{self.__class__.__name__}",
        )
