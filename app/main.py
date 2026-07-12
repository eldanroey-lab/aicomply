from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from starlette.middleware.sessions import SessionMiddleware

from app.core.config import settings
from app.core.scheduler import start_scheduler, stop_scheduler
from app.api.v1.api_router import api_router
from app.startup import create_tables


@asynccontextmanager
async def lifespan(app: FastAPI):
    await create_tables()
    start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description='AI-powered compliance platform for SMEs',
    docs_url='/docs',
    redoc_url='/redoc',
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)
app.add_middleware(SessionMiddleware, secret_key=settings.SECRET_KEY)

app.include_router(api_router)


@app.get('/health', tags=['Health'])
async def health():
    return {'status': 'ok', 'version': settings.APP_VERSION}


@app.get('/', include_in_schema=False)
async def serve_ui():
    return FileResponse('aicomply-ui.html')
