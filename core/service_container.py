from core.services.config_service import ConfigService, ConfigServiceImpl
from core.services.laser_service import LaserService, LaserServiceImpl
from core.services.cost_function_service import (
    CostFunctionService,
    CostFunctionServiceImpl,
)


class Container:
    """Service container. All services and gateways are registered here.
    Access by importing this module and using the attributes of the Container class.
    """

    config_service: ConfigService = ConfigServiceImpl()

    laser_service: LaserService = LaserServiceImpl()

    cost_function: CostFunctionService = CostFunctionServiceImpl()
