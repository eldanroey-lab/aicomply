from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud.base import CRUDBase
from app.db.models.framework import Framework
from app.db.schemas.framework import FrameworkCreate, FrameworkUpdate


class CRUDFramework(CRUDBase[Framework]):
    async def get_tenant_frameworks(
        self, db: AsyncSession, tenant_id: int
    ) -> list[Framework]:
        result = await db.execute(
            select(Framework).where(Framework.tenant_id == tenant_id)
        )
        return list(result.scalars().all())

    async def create_for_tenant(
        self, db: AsyncSession, *, obj_in: FrameworkCreate, tenant_id: int
    ) -> Framework:
        data = obj_in.model_dump()
        if data.get('controls'):
            data['controls'] = [c.model_dump() for c in obj_in.controls]
        db_obj = Framework(**data, tenant_id=tenant_id)
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj


crud_framework = CRUDFramework(Framework)
