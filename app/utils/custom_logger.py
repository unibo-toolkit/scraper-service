import logging
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass
class LogItem:
    name: str
    value: str

    def __str__(self):
        return f'{self.name}="{self.value}"'


@dataclass
class MultiItem:
    items: Dict[str, str]

    @property
    def all(self) -> List[LogItem]:
        return [LogItem(name, value) for name, value in self.items.items()]


class CustomLogger:
    items: List[LogItem] = []

    def __init__(self, name: str, **items: Any):
        self.name = name
        self.logger = logging.getLogger(name)
        if items.items():
            self.items = self.__transform_items(items).all

    def __send_message(self, message: str, level: int, items: List[LogItem]) -> None:
        log = (
            'msg="' + message + '"' + (" " + " ".join(map(str, items)) if items else "")
        )
        self.logger.log(level, log)

    @staticmethod
    def __transform_items(items: Dict[str, Any]) -> MultiItem:
        return MultiItem({key: str(value) for key, value in items.items()})

    def info(self, message: str, **items: Any) -> None:
        self.__send_message(
            message, logging.INFO, self.items + self.__transform_items(items).all
        )

    def debug(self, message: str, **items: Any) -> None:
        self.__send_message(
            message, logging.DEBUG, self.items + self.__transform_items(items).all
        )

    def warning(self, message: str, **items: Any) -> None:
        self.__send_message(
            message, logging.WARNING, self.items + self.__transform_items(items).all
        )

    def error(self, message: str, **items: Any) -> None:
        self.__send_message(
            message, logging.ERROR, self.items + self.__transform_items(items).all
        )

    def critical(self, message: str, **items: Any) -> None:
        self.__send_message(
            message, logging.CRITICAL, self.items + self.__transform_items(items).all
        )

    def with_items(self, **items: Any) -> None:
        self.items.extend(self.__transform_items(items).all)

    @classmethod
    def clear(cls) -> None:
        cls.items.clear()

    def __del__(self):
        if self.items:
            del self.items
