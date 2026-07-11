from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.schemas.task import TaskCreate, TaskRead, TaskUpdate
from app.crud.crud_task import crud_task
from app.core.security import get_current_user
from app.db.models.user import User

router = APIRouter(prefix='/tasks', tags=['Tasks'])


@router.get('/', response_model=list[TaskRead])
async def list_tasks(
    status: str | None = None,
    assignee_id: int | None = None,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await crud_task.get_tenant_tasks(
        db,
        tenant_id=current_user.tenant_id,
        status=status,
        assignee_id=assignee_id,
        skip=skip,
        limit=limit,
    )


@router.post('/', response_model=TaskRead, status_code=status.HTTP_201_CREATED)
async def create_task(
    payload: TaskCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await crud_task.create_for_tenant(
        db, obj_in=payload, tenant_id=current_user.tenant_id, created_by_id=current_user.id
    )


@router.get('/overdue', response_model=list[TaskRead])
async def overdue_tasks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await crud_task.get_overdue(db, current_user.tenant_id)


@router.get('/{task_id}', response_model=TaskRead)
async def get_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await crud_task.get(db, task_id)
    if not task or task.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail='Task not found')
    return task


@router.patch('/{task_id}', response_model=TaskRead)
async def update_task(
    task_id: int,
    payload: TaskUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await crud_task.get(db, task_id)
    if not task or task.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail='Task not found')
    return await crud_task.update(db, db_obj=task, obj_in=payload)


@router.delete('/{task_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_task(
    task_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    task = await crud_task.get(db, task_id)
    if not task or task.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail='Task not found')
    await crud_task.delete(db, id=task_id)
