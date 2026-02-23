from app.utils.classes import Config, ConfigLoader

__version__ = "0.1.0"
version = __version__

config_loader = ConfigLoader()
config: Config = config_loader.config
