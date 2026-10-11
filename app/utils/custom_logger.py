import logging
from dataclasses import dataclass
from typing import Any, Dict, List


@dataclass(frozen=True, slots=True)
class LogItem:
    """
    One key=value pair appended to a log line.

    Attributes:
        name: Key as written in the line.
        value: Value, already stringified.
    """

    name: str
    value: str

    def __str__(self) -> str:
        return f'{self.name}="{self.value}"'


class CustomLogger:
    def __init__(self, name: str, **items: Any):
        self.name = name
        self.logger = logging.getLogger(name)
        self.items: List[LogItem] = _as_items(items)

    def log(self, level: int, msg: str, **items: Any) -> None:
        parts = self.items + _as_items(items)
        suffix = " " + " ".join(map(str, parts)) if parts else ""
        self.logger.log(level, f'msg="{msg}"{suffix}')

    def debug(self, msg: str, **items: Any) -> None:
        self.log(logging.DEBUG, msg, **items)

    def info(self, msg: str, **items: Any) -> None:
        self.log(logging.INFO, msg, **items)

    def warning(self, msg: str, **items: Any) -> None:
        self.log(logging.WARNING, msg, **items)

    def error(self, msg: str, **items: Any) -> None:
        self.log(logging.ERROR, msg, **items)

    def critical(self, msg: str, **items: Any) -> None:
        self.log(logging.CRITICAL, msg, **items)

    def with_items(self, **items: Any) -> None:
        self.items.extend(_as_items(items))

    def clear(self) -> None:
        self.items.clear()


def _as_items(items: Dict[str, Any]) -> List[LogItem]:
    return [LogItem(name, str(value)) for name, value in items.items()]
