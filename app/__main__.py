import asyncio

import uvicorn

from app import config, log, version
from app.api.app import app
from app.utils.custom_logger import CustomLogger
from app.utils.database import close, init
from app.utils.redis_client import redis_client

log.setup()

logger = CustomLogger("Main")


async def setup():
    logger.info("Starting scraper-service", version=version, port=config.app.port)

    await init()
    await redis_client.connect()

    logger.info("Startup complete")


async def shutdown():
    logger.info("Shutting down scraper-service")

    await close()
    await redis_client.disconnect()

    logger.info("Shutdown complete")


async def main():
    await setup()

    config_uvicorn = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=config.app.port,
        log_level=config.app.log_level.lower(),
        log_config=None,
    )
    server = uvicorn.Server(config_uvicorn)

    try:
        await server.serve()
    finally:
        await shutdown()


if __name__ == "__main__":
    asyncio.run(main())
