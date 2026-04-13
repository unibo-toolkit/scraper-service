import logging
import logging.handlers
import sys
from pathlib import Path

import coloredlogs

from app import config


def setup() -> None:
    format_string = "[%(asctime)s] [%(name)s/%(levelname)s]: %(message)s"
    log_format = logging.Formatter(format_string)
    root_logger = logging.getLogger()

    root_logger.setLevel(getattr(logging, config.app.log_level))

    log_file = Path("logs.log")
    log_file.parent.mkdir(exist_ok=True)

    file_handler = logging.handlers.RotatingFileHandler(
        log_file,
        maxBytes=5 * (2**20),
        backupCount=10,
        encoding="utf-8",
    )
    file_handler.setFormatter(log_format)
    root_logger.addHandler(file_handler)

    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.ERROR)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    class HealthCheckFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            return "/health" not in record.getMessage()

    uvicorn_access = logging.getLogger("uvicorn.access")
    uvicorn_access.addFilter(HealthCheckFilter())

    coloredlogs.DEFAULT_LEVEL_STYLES = {
        **coloredlogs.DEFAULT_LEVEL_STYLES,
        "trace": {"color": 246},
        "critical": {"background": "red"},
        "debug": coloredlogs.DEFAULT_LEVEL_STYLES["info"],
    }

    coloredlogs.DEFAULT_LOG_FORMAT = format_string

    coloredlogs.install(level=getattr(logging, config.app.log_level), stream=sys.stdout)
