from sqlalchemy.ext.asyncio import AsyncSession

from app.utils.custom_logger import CustomLogger


class Operations:
    def __init__(self, session: AsyncSession, logger: CustomLogger):
        self.session = session
        self.logger = logger
