from core.service_container import Container, containers


class OverrideContainer(Container):
    wiring_config = containers.WiringConfiguration(
        auto_wire=True, packages=["core.pipeline", "api.routers", "tests"]
    )


def pytest_sessionstart(session):
    """
    Called after the Session object has been created and
    before performing collection and entering the run test loop.
    """
    print("Preparing: wiring DI")
    Container.override(OverrideContainer)
    Container()
