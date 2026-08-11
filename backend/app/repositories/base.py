"""Generic async repository base."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any, cast

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.errors import NotFoundError
from app.models.base import Base


class BaseRepository[ModelT: Base]:
    """Typed async CRUD over a single ORM model."""

    model: type[ModelT]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get(self, obj_id: int) -> ModelT | None:
        return await self.session.get(self.model, obj_id)

    async def get_or_raise(self, obj_id: int, *, name: str | None = None) -> ModelT:
        obj = await self.get(obj_id)
        if obj is None:
            label = name or self.model.__tablename__
            raise NotFoundError(f"{label} {obj_id} not found")
        return obj

    async def list(self, *, limit: int = 100, offset: int = 0) -> Sequence[ModelT]:
        table = cast(Any, self.model.__table__)
        stmt = select(self.model).order_by(table.primary_key.columns[0]).limit(limit).offset(offset)
        return (await self.session.scalars(stmt)).all()

    async def list_by(self, *, where: Any, limit: int = 100, offset: int = 0) -> Sequence[ModelT]:
        table = cast(Any, self.model.__table__)
        stmt: Select[tuple[ModelT]] = (
            select(self.model)
            .where(where)
            .order_by(table.primary_key.columns[0])
            .limit(limit)
            .offset(offset)
        )
        return (await self.session.scalars(stmt)).all()

    async def add(self, obj: ModelT) -> ModelT:
        self.session.add(obj)
        await self.session.flush()
        return obj

    async def add_all(self, objs: Sequence[ModelT]) -> None:
        self.session.add_all(objs)
        await self.session.flush()

    async def delete(self, obj: ModelT) -> None:
        await self.session.delete(obj)
        await self.session.flush()

    async def flush(self) -> None:
        await self.session.flush()

    async def refresh(self, obj: ModelT) -> ModelT:
        await self.session.refresh(obj)
        return obj
