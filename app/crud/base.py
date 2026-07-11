from typing import Any, Generic, Optional, Type, TypeVar
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.db.base import Base

ModelType = TypeVar('ModelType', bound=Base)


class CRUDBase(Generic[ModelType]):
    def __init__(self, model: Type[ModelType]):
        self.model = model

    async def get(self, db: AsyncSession, id: int) -> Optional[ModelType]:
        result = await db.execute(select(self.model).where(self.model.id == id))
        return result.scalars().first()

    async def get_multi(
        self, db: AsyncSession, *, skip: int = 0, limit: int = 100, **filters
    ) -> list[ModelType]:
        q = select(self.model)
        for attr, val in filters.items():
            if val is not None and hasattr(self.model, attr):
                q = q.where(getattr(self.model, attr) == val)
        q = q.offset(skip).limit(limit)
        result = await db.execute(q)
        return list(result.scalars().all())

    async def create(self, db: AsyncSession, *, obj_in: Any) -> ModelType:
        data = obj_in.model_dump() if hasattr(obj_in, 'model_dump') else dict(obj_in)
        db_obj = self.model(**data)
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def update(self, db: AsyncSession, *, db_obj: ModelType, obj_in: Any) -> ModelType:
        data = obj_in.model_dump(exclude_unset=True) if hasattr(obj_in, 'model_dump') else dict(obj_in)
        for field, val in data.items():
            setattr(db_obj, field, val)
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def delete(self, db: AsyncSession, *, id: int) -> Optional[ModelType]:
        obj = await self.get(db, id=id)
        if obj:
            await db.delete(obj)
            await db.flush()
        return obj
