from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from authlib.integrations.starlette_client import OAuth
from starlette.config import Config

from app.db.session import get_db
from app.db.schemas.user import TokenPair, LoginRequest, UserCreate, TenantCreate
from app.crud.crud_user import crud_user, crud_tenant
from app.core.security import (
    create_access_token, create_refresh_token,
    verify_password, decode_token,
)
from app.core.config import settings

router = APIRouter(prefix='/auth', tags=['Authentication'])

# ─── Google OAuth setup ──────────────────────────────────────────────────────
_config = Config(environ={
    'GOOGLE_CLIENT_ID': settings.GOOGLE_CLIENT_ID or '',
    'GOOGLE_CLIENT_SECRET': settings.GOOGLE_CLIENT_SECRET or '',
})
oauth = OAuth(_config)
oauth.register(
    name='google',
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
    client_kwargs={'scope': 'openid email profile'},
)


@router.post('/register', response_model=TokenPair, status_code=status.HTTP_201_CREATED)
async def register(payload: UserCreate, db: AsyncSession = Depends(get_db)):
    """Register a new user (and implicitly create a tenant)."""
    existing = await crud_user.get_by_email(db, payload.email)
    if existing:
        raise HTTPException(status_code=400, detail='Email already registered')

    # Auto-create tenant if tenant_id not provided as 0
    if payload.tenant_id == 0:
        tenant = await crud_tenant.create(
            db, obj_in=TenantCreate(name=payload.email.split('@')[0])
        )
        payload = payload.model_copy(update={'tenant_id': tenant.id})

    user = await crud_user.create(db, obj_in=payload)
    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)
    return TokenPair(access_token=access, refresh_token=refresh)


@router.post('/login', response_model=TokenPair)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)):
    """Email + password login."""
    user = await crud_user.get_by_email(db, payload.email)
    if not user or not user.hashed_password:
        raise HTTPException(status_code=401, detail='Invalid credentials')
    if not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail='Invalid credentials')
    if not user.is_active:
        raise HTTPException(status_code=403, detail='Account disabled')
    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.post('/refresh', response_model=TokenPair)
async def refresh_token(refresh_token: str, db: AsyncSession = Depends(get_db)):
    """Issue a new access token using a valid refresh token."""
    payload = decode_token(refresh_token)
    if payload.get('type') != 'refresh':
        raise HTTPException(status_code=400, detail='Not a refresh token')
    user = await crud_user.get(db, int(payload['sub']))
    if not user:
        raise HTTPException(status_code=404, detail='User not found')
    return TokenPair(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


@router.get('/google/login')
async def google_login(request: Request):
    """Redirect to Google OAuth consent screen."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=501, detail='Google OAuth not configured')
    redirect_uri = settings.GOOGLE_REDIRECT_URI
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get('/callback')
async def google_callback(request: Request, db: AsyncSession = Depends(get_db)):
    """Handle Google OAuth callback, create/login user, return tokens."""
    token = await oauth.google.authorize_access_token(request)
    userinfo = token.get('userinfo')
    if not userinfo:
        raise HTTPException(status_code=400, detail='Failed to fetch user info from Google')

    user = await crud_user.get_by_google_sub(db, userinfo['sub'])
    if not user:
        # Check by email
        user = await crud_user.get_by_email(db, userinfo['email'])
        if user:
            user.google_sub = userinfo['sub']
            user.avatar_url = userinfo.get('picture')
            db.add(user)
        else:
            # New user — create tenant automatically
            tenant = await crud_tenant.create(
                db, obj_in=TenantCreate(name=userinfo['email'].split('@')[0])
            )
            user = await crud_user.create(
                db,
                obj_in=UserCreate(
                    email=userinfo['email'],
                    full_name=userinfo.get('name'),
                    tenant_id=tenant.id,
                ),
            )
            user.google_sub = userinfo['sub']
            user.avatar_url = userinfo.get('picture')
            db.add(user)

    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id)
    # In production, redirect to frontend with tokens
    return {'access_token': access, 'refresh_token': refresh, 'token_type': 'bearer'}
