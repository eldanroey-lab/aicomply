from fastapi import APIRouter
from app.api.v1.endpoints import auth, users, frameworks, documents, scoring, tasks, copilot, igaming, euai, soc2, gdpr

api_router = APIRouter(prefix='/api/v1')
api_router.include_router(auth.router)
api_router.include_router(users.router)
api_router.include_router(frameworks.router)
api_router.include_router(documents.router)
api_router.include_router(scoring.router)
api_router.include_router(tasks.router)
api_router.include_router(copilot.router)
api_router.include_router(igaming.router)
api_router.include_router(euai.router)
api_router.include_router(soc2.router)
api_router.include_router(gdpr.router)
