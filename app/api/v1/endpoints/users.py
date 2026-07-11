from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.schemas.user import UserRead, UserUpdate
from app.crud.crud_user import crud_user
from app.core.security import get_current_user, require_admin
from app.db.models.user import User

router = APIRouter(prefix='/users', tags=['Users'])


@router.get('/me', response_model=UserRead)
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch('/me', response_model=UserRead)
async def update_me(
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Users cannot change their own role
    payload = payload.model_copy(update={'role': None})
    return await crud_user.update(db, db_obj=current_user, obj_in=payload)


@router.get('/', response_model=list[UserRead])
async def list_users(
    skip: int = 0,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return await crud_user.get_tenant_users(
        db, tenant_id=current_user.tenant_id, skip=skip, limit=limit
    )


@router.patch('/{user_id}', response_model=UserRead)
async def update_user(
    user_id: int,
    payload: UserUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    user = await crud_user.get(db, user_id)
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    return await crud_user.update(db, db_obj=user, obj_in=payload)


@router.delete('/{user_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if user_id == admin.id:
        raise HTTPException(status_code=400, detail='Cannot delete yourself')
    await crud_user.delete(db, id=user_id)
