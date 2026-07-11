from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.schemas.framework import FrameworkCreate, FrameworkRead, FrameworkUpdate
from app.crud.crud_framework import crud_framework
from app.core.security import get_current_user
from app.db.models.user import User

router = APIRouter(prefix='/frameworks', tags=['Frameworks'])


@router.get('/', response_model=list[FrameworkRead])
async def list_frameworks(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await crud_framework.get_tenant_frameworks(db, current_user.tenant_id)


@router.post('/', response_model=FrameworkRead, status_code=status.HTTP_201_CREATED)
async def create_framework(
    payload: FrameworkCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await crud_framework.create_for_tenant(
        db, obj_in=payload, tenant_id=current_user.tenant_id
    )


@router.get('/{framework_id}', response_model=FrameworkRead)
async def get_framework(
    framework_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    fw = await crud_framework.get(db, framework_id)
    if not fw or fw.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail='Framework not found')
    return fw


@router.patch('/{framework_id}', response_model=FrameworkRead)
async def update_framework(
    framework_id: int,
    payload: FrameworkUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    fw = await crud_framework.get(db, framework_id)
    if not fw or fw.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail='Framework not found')
    return await crud_framework.update(db, db_obj=fw, obj_in=payload)


@router.delete('/{framework_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_framework(
    framework_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    fw = await crud_framework.get(db, framework_id)
    if not fw or fw.tenant_id != current_user.tenant_id:
        raise HTTPException(status_code=404, detail='Framework not found')
    await crud_framework.delete(db, id=framework_id)
