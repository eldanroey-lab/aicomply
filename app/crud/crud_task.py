from datetime import date
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from app.crud.base import CRUDBase
from app.db.models.task import Task
from app.db.schemas.task import TaskCreate


class CRUDTask(CRUDBase[Task]):
    async def get_tenant_tasks(
        self,
        db: AsyncSession,
        tenant_id: int,
        status: str | None = None,
        assignee_id: int | None = None,
        skip: int = 0,
        limit: int = 100,
    ) -> list[Task]:
        conditions = [Task.tenant_id == tenant_id]
        if status:
            conditions.append(Task.status == status)
        if assignee_id:
            conditions.append(Task.assignee_id == assignee_id)
        result = await db.execute(
            select(Task).where(and_(*conditions)).offset(skip).limit(limit)
        )
        return list(result.scalars().all())

    async def get_overdue(self, db: AsyncSession, tenant_id: int) -> list[Task]:
        result = await db.execute(
            select(Task).where(
                and_(
                    Task.tenant_id == tenant_id,
                    Task.due_date < date.today(),
                    Task.status.notin_(['done']),
                )
            )
        )
        return list(result.scalars().all())

    async def create_for_tenant(
        self, db: AsyncSession, *, obj_in: TaskCreate, tenant_id: int, created_by_id: int
    ) -> Task:
        data = obj_in.model_dump()
        db_obj = Task(**data, tenant_id=tenant_id, created_by_id=created_by_id)
        db.add(db_obj)
        await db.flush()
        await db.refresh(db_obj)
        return db_obj


crud_task = CRUDTask(Task)
