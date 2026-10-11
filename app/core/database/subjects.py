from datetime import UTC, datetime
from typing import Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import insert, select, update

from app.core.database.base import Operations
from app.models.generated import Subjects
from app.models.timetable import Subject, SubjectKey


class SubjectsOperations(Operations):
    async def list_by_curriculum(
        self, curriculum_id: UUID, active_only: bool = True
    ) -> List[Subject]:
        query = select(Subjects).where(Subjects.curriculum_id == curriculum_id)
        if active_only:
            query = query.where(Subjects.is_active.is_(True))

        rows = (await self.session.execute(query)).scalars().all()
        return [_to_subject(row) for row in rows]

    async def get_curriculum_id(self, subject_id: UUID) -> Optional[UUID]:
        query = select(Subjects.curriculum_id).where(Subjects.id == subject_id)
        return (await self.session.execute(query)).scalar_one_or_none()

    async def sync(self, curriculum_id: UUID, subjects: Sequence[Subject]) -> Dict[SubjectKey, UUID]:
        """
        Upserts the given subjects, deactivates the ones that disappeared and
        returns the id of every subject of the curriculum, including inactive
        ones (events may still reference them).
        """
        existing = {row.key: row for row in await self.list_by_curriculum(curriculum_id, False)}
        incoming = {subject.key: subject for subject in subjects}

        await self.__update(existing, incoming)
        await self.__insert(curriculum_id, existing, incoming)
        await self.__deactivate(existing, incoming)
        await self.session.flush()

        rows = await self.list_by_curriculum(curriculum_id, active_only=False)
        return {row.key: row.id for row in rows}

    async def __update(
        self, existing: Dict[SubjectKey, Subject], incoming: Dict[SubjectKey, Subject]
    ) -> None:
        payload = [
            {
                "id": existing[key].id,
                "credits": subject.credits,
                "group_id": subject.group_id,
                "is_active": True,
                "updated_at": datetime.now(UTC),
            }
            for key, subject in incoming.items()
            if key in existing
        ]
        if payload:
            await self.session.execute(update(Subjects), payload)

    async def __insert(
        self,
        curriculum_id: UUID,
        existing: Dict[SubjectKey, Subject],
        incoming: Dict[SubjectKey, Subject],
    ) -> None:
        payload = [
            {
                "curriculum_id": curriculum_id,
                "title": subject.title,
                "module_code": subject.module_code,
                "professor": subject.professor,
                "credits": subject.credits,
                "group_id": subject.group_id,
                "is_active": True,
            }
            for key, subject in incoming.items()
            if key not in existing
        ]
        if payload:
            await self.session.execute(insert(Subjects), payload)

    async def __deactivate(
        self, existing: Dict[SubjectKey, Subject], incoming: Dict[SubjectKey, Subject]
    ) -> None:
        stale = [
            subject.id
            for key, subject in existing.items()
            if key not in incoming and subject.is_active
        ]
        if stale:
            await self.session.execute(
                update(Subjects).where(Subjects.id.in_(stale)).values(is_active=False)
            )


def _to_subject(row: Subjects) -> Subject:
    return Subject(
        id=row.id,
        title=row.title,
        module_code=row.module_code,
        professor=row.professor,
        credits=row.credits,
        group_id=row.group_id,
        is_active=row.is_active,
    )
