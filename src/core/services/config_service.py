from dotenv import load_dotenv
from pydantic_settings import BaseSettings
from src.core.services.base import BaseService


class ConfigModel(BaseSettings):
    """Config model. All config values should be defined here. Info: https://docs.pydantic.dev/latest/concepts/pydantic_settings/"""

    pass


class ConfigService(BaseService):
    config: ConfigModel


class ConfigServiceImpl(ConfigService):
    def __init__(self):
        super().__init__()
        self._init_config()

    def _init_config(self):
        load_dotenv()
        self.config = ConfigModel()  # will automatically load .env file values
