from core.services.config_service import ConfigService, ConfigServiceImpl
from core.services.kinematics_service import KinematicsService, KinematicsServiceImpl
from core.services.laser_cost_service import LaserCostService, LaserCostServiceImpl
from core.services.laser_service import LaserService, LaserServiceImpl
from core.services.laser_config_service import (
    LaserConfigService,
    LaserConfigServiceImpl,
)


class Container:
    """Service container. All services and gateways are registered here.
    Access by importing this module and using the attributes of the Container class.
    """

    config_service: ConfigService = ConfigServiceImpl()

    laser_service: LaserService = LaserServiceImpl()

    laser_config: LaserConfigService = LaserConfigServiceImpl()

    kinematics_service: KinematicsService = KinematicsServiceImpl(
        laser_config.get_rotating_kinematics()
    )

    laser_cost: LaserCostService = LaserCostServiceImpl(
        laser_config.get_max_rates(), kinematics_service
    )
