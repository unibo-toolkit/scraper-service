from typing import Dict, Sequence
from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert

from app.core.database.base import Operations
from app.models.generated import Classrooms, TimetableEvents
from app.models.timetable import Classroom, ClassroomKey

NAME_ADDRESS_CONSTRAINT = "classrooms_name_address_key"


class ClassroomsOperations(Operations):
    async def upsert_many(self, classrooms: Sequence[Classroom]) -> Dict[ClassroomKey, UUID]:
        """
        Returns the id of every given classroom, keyed by (name, address).

        The unique constraint does not cover a NULL address, so those rows are
        matched by hand instead of going through ON CONFLICT.
        """
        with_address = [room for room in classrooms if room.address]
        without_address = [room for room in classrooms if not room.address]

        await self.__upsert_with_address(with_address)
        for room in without_address:
            await self.__upsert_without_address(room)

        await self.session.flush()
        return await self.__ids_of(classrooms)

    async def cleanup_unused(self) -> int:
        used = select(TimetableEvents.classroom_id).where(
            TimetableEvents.classroom_id.is_not(None)
        )
        result = await self.session.execute(
            delete(Classrooms).where(Classrooms.id.not_in(used))
        )
        await self.session.flush()
        return result.rowcount

    async def __upsert_with_address(self, classrooms: Sequence[Classroom]) -> None:
        if not classrooms:
            return

        stmt = insert(Classrooms).values(
            [
                {
                    "name": room.name,
                    "address": room.address,
                    "latitude": room.latitude,
                    "longitude": room.longitude,
                }
                for room in classrooms
            ]
        )
        # Coordinates are not always present in the feed: never overwrite known
        # ones with NULL.
        stmt = stmt.on_conflict_do_update(
            constraint=NAME_ADDRESS_CONSTRAINT,
            set_={
                "latitude": func.coalesce(stmt.excluded.latitude, Classrooms.latitude),
                "longitude": func.coalesce(stmt.excluded.longitude, Classrooms.longitude),
            },
        )
        await self.session.execute(stmt)

    async def __upsert_without_address(self, room: Classroom) -> None:
        query = select(Classrooms).where(
            Classrooms.name == room.name, Classrooms.address.is_(None)
        )
        existing = (await self.session.execute(query)).scalar_one_or_none()

        if not existing:
            self.session.add(
                Classrooms(name=room.name, latitude=room.latitude, longitude=room.longitude)
            )
            return

        if room.latitude is not None:
            existing.latitude = room.latitude
        if room.longitude is not None:
            existing.longitude = room.longitude

    async def __ids_of(self, classrooms: Sequence[Classroom]) -> Dict[ClassroomKey, UUID]:
        if not classrooms:
            return {}

        names = {room.name for room in classrooms}
        query = select(Classrooms.id, Classrooms.name, Classrooms.address).where(
            Classrooms.name.in_(names)
        )
        rows = (await self.session.execute(query)).all()

        wanted = {room.key for room in classrooms}
        return {(name, address): id_ for id_, name, address in rows if (name, address) in wanted}
