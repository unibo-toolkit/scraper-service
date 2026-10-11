from unibo_toolkit import HTTPClient
from unibo_toolkit.models import Curriculum as UniBoCurriculum
from unibo_toolkit.scrapers import TimetableScraper as UniBoTimetableScraper

from app import config
from app.core.scraper.mapper import to_timetable
from app.models.courses import Curriculum
from app.models.timetable import Timetable
from app.utils.custom_logger import CustomLogger


class TimetableScraper:
    def __init__(self, logger: CustomLogger):
        self.logger = logger

    async def fetch(self, course_url: str, curriculum: Curriculum) -> Timetable:
        self.logger.info(
            "fetching timetable",
            curriculum_code=curriculum.code,
            year=curriculum.academic_year,
        )

        async with HTTPClient(timeout=config.scraper.request_timeout) as client:
            async with UniBoTimetableScraper(http_client=client) as scraper:
                timetable = await scraper.get_curriculum_timetable(
                    course_site_url=course_url,
                    curriculum=UniBoCurriculum(code=curriculum.code, label=curriculum.label),
                    academic_year=curriculum.academic_year,
                )

        return to_timetable(timetable)
