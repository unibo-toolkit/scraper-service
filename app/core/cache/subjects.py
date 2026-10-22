from typing import List, Optional
from uuid import UUID

from app import config
from app.core.cache.base import JsonCache
from app.models.timetable import Subject


class SubjectsCache(JsonCache):
    async def get(self, curriculum_id: UUID) -> Optional[List[Subject]]:
        payload = await super().get(_key(curriculum_id))
        return [_to_subject(item) for item in payload] if payload else None

    async def set(self, curriculum_id: UUID, subjects: List[Subject]) -> None:
        payload = [_to_payload(subject) for subject in subjects]
        await super().set(_key(curriculum_id), payload, config.scraper.cache_subjects_ttl)

    async def delete(self, curriculum_id: UUID) -> None:
        await super().delete(_key(curriculum_id))


def _key(curriculum_id: UUID) -> str:
    return f"subjects:{curriculum_id}"


def _to_payload(subject: Subject) -> dict:
    return {
        "id": str(subject.id),
        "title": subject.title,
        "module_code": subject.module_code,
        "credits": subject.credits,
        "professor": subject.professor,
        "group_id": subject.group_id,
    }


def _to_subject(payload: dict) -> Subject:
    return Subject(
        id=UUID(payload["id"]),
        title=payload["title"],
        module_code=payload["module_code"],
        credits=payload["credits"],
        professor=payload["professor"],
        group_id=payload["group_id"],
    )
