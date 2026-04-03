import os
import sys
from dataclasses import dataclass

from dotenv import find_dotenv, load_dotenv

from app.utils.custom_logger import CustomLogger


class MissingConfiguration(Exception):
    def __init__(self, key: str):
        self.key = key

    def __str__(self):
        return f"Missing configuration: {self.key}"


@dataclass
class AppConfig:
    debug_mode: bool
    port: int
    log_level: str
    skip_startup_jobs: bool


@dataclass
class DatabaseConfig:
    host: str
    port: int
    database: str
    user: str
    password: str

    @property
    def url(self) -> str:
        return f"postgresql+asyncpg://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"


@dataclass
class RedisConfig:
    host: str
    port: int
    db: int

    @property
    def url(self) -> str:
        return f"redis://{self.host}:{self.port}/{self.db}"


@dataclass
class ScraperConfig:
    request_timeout: int
    cache_courses_list_ttl: int
    cache_subjects_ttl: int
    timetable_events_ttl: int
    delay_between_curricula_requests: float
    delay_between_site_url_requests: float
    delay_between_timetable_requests: float


@dataclass
class SchedulerConfig:
    timezone: str
    update_courses_interval_seconds: int
    update_timetables_interval_seconds: int
    cleanup_stale_events_interval_seconds: int


class Config:
    def __init__(
        self,
        app: AppConfig,
        database: DatabaseConfig,
        redis: RedisConfig,
        scraper: ScraperConfig,
        scheduler: SchedulerConfig,
    ):
        self.app = app
        self.database = database
        self.redis = redis
        self.scraper = scraper
        self.scheduler = scheduler


class ConfigLoader:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(ConfigLoader, cls).__new__(cls)
            cls._instance._load_config()
        return cls._instance

    @classmethod
    def _load_config(cls):
        cls.config = cls._parse_config()

    @staticmethod
    def _parse_config() -> Config:
        logger = CustomLogger("ConfigLoader")
        logger.info("Loading config")

        try:
            load_dotenv(find_dotenv())

            app = AppConfig(
                debug_mode=os.getenv("DEBUG_MODE", "false").lower() == "true",
                port=int(os.getenv("PORT", 8083)),
                log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
                skip_startup_jobs=os.getenv("SKIP_STARTUP_JOBS", "false").lower() == "true",
            )

            database = DatabaseConfig(
                host=os.getenv("DB_HOST", "localhost"),
                port=int(os.getenv("DB_PORT", 5432)),
                database=os.getenv("DB_NAME", "unibo_toolkit"),
                user=os.getenv("DB_USER", "unibo_user"),
                password=os.getenv("DB_PASSWORD", "unibo_pass"),
            )

            redis = RedisConfig(
                host=os.getenv("REDIS_HOST", "localhost"),
                port=int(os.getenv("REDIS_PORT", 6379)),
                db=int(os.getenv("REDIS_DB", 3)),
            )

            scraper = ScraperConfig(
                request_timeout=int(os.getenv("SCRAPER_REQUEST_TIMEOUT", 30)),
                cache_courses_list_ttl=int(os.getenv("CACHE_COURSES_LIST_TTL", 86400)),
                cache_subjects_ttl=int(os.getenv("CACHE_SUBJECTS_TTL", 86400)),
                timetable_events_ttl=int(os.getenv("TIMETABLE_EVENTS_TTL", 3600)),
                delay_between_curricula_requests=float(os.getenv("DELAY_BETWEEN_CURRICULA_REQUESTS", 0.1)),
                delay_between_site_url_requests=float(os.getenv("DELAY_BETWEEN_SITE_URL_REQUESTS", 0.1)),
                delay_between_timetable_requests=float(os.getenv("DELAY_BETWEEN_TIMETABLE_REQUESTS", 0.1)),
            )

            scheduler = SchedulerConfig(
                timezone=os.getenv("SCHEDULER_TIMEZONE", "UTC"),
                update_courses_interval_seconds=int(
                    os.getenv("UPDATE_COURSES_INTERVAL_SECONDS", 43200)
                ),
                update_timetables_interval_seconds=int(
                    os.getenv("UPDATE_TIMETABLES_INTERVAL_SECONDS", 3600)
                ),
                cleanup_stale_events_interval_seconds=int(
                    os.getenv("CLEANUP_STALE_EVENTS_INTERVAL_SECONDS", 7200)
                ),
            )

            logger.info("Config loaded")
            return Config(app, database, redis, scraper, scheduler)
        except Exception as e:
            logger.error("Error during config parsing", error=str(e))
            sys.exit(1)
