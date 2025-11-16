from dependency_injector import containers, providers

from core.services.config_service import ConfigService, ConfigServiceImpl
from core.services.laser_service import LaserService, LaserServiceImpl


class Container(containers.DeclarativeContainer):
    """Service container. All services and gateways are registered here.
    Use @inject decorator to inject dependencies.
    Example:
        @inject
        def foo(service: MyService = Provide[Container.my_service]): ...

    For fastapi endpoints, use instead:
        service: Annotated[MyService, Depends(Provide[Container.my_service])]

    Notes:
    - Packages not listed in wiring_config will not be wired. Add yours if needed.
    - Services can be registered as singletons or factories depending on
      whether you want a single shared instance or a new instance per use.
    - Gateways, such as database clients or external APIs, should generally
      be singletons to manage resources efficiently
    """

    wiring_config = containers.WiringConfiguration(
        auto_wire=True, packages=["core.pipeline", "api.routers"]
    )

    # Gateways (none defined yet)

    # Services
    config_service: providers.Singleton[ConfigService] = providers.Singleton(
        ConfigServiceImpl
    )

    laser_service: providers.Singleton[LaserService] = providers.Singleton(
        LaserServiceImpl
    )
