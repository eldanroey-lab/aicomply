from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud.base import CRUDBase
from app.db.models.user import User, Tenant
from app.db.schemas.user import UserCreate, UserUpdate
from app.core.security import hash_password


class CRUDUser(CRUDBase[User]):
    async def get_by_email(self, db: AsyncSession, email: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.email == email))
        return result.scalars().first()

    async def get_by_google_sub(self, db: AsyncSession, sub: str) -> Optional[User]:
        result = await db.execute(select(User).where(User.google_sub == sub))
        return result.scalars().first()

    async def create(self, db: AsyncSession, *, obj_in: UserCreate) -> User:
        data = obj_in.model_dump()
        raw_password = data.pop('password', None)
        if raw_password:
            data['hashed_password'] = hash_password(raw_password)
        db_obj = User(**data)
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj

    async def get_tenant_users(
        self, db: AsyncSession, tenant_id: int, skip: int = 0, limit: int = 100
    ) -> list[User]:
        result = await db.execute(
            select(User).where(User.tenant_id == tenant_id).offset(skip).limit(limit)
        )
        return list(result.scalars().all())


class CRUDTenant(CRUDBase[Tenant]):
    async def get_by_name(self, db: AsyncSession, name: str) -> Optional[Tenant]:
        result = await db.execute(select(Tenant).where(Tenant.name == name))
        return result.scalars().first()


crud_user = CRUDUser(User)
crud_tenant = CRUDTenant(Tenant)
