import os
import uuid
import aiofiles
from fastapi import APIRouter, Depends, File, UploadFile, HTTPException, status, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.db.schemas.document import DocumentRead, DocumentUpdate
from app.db.models.document import Document
from app.db.models.framework import Framework
from app.crud.base import CRUDBase
from app.core.security import get_current_user
from app.core.config import settings
from app.services.document_ai import document_ai_service
from app.services.scoring import scoring_service
from app.services.alerts import alert_service
from app.db.models.user import User
from sqlalchemy import select

router = APIRouter(prefix='/documents', tags=['Documents'])
crud_doc = CRUDBase(Document)

UPLOAD_DIR = '/tmp/aicomply_uploads'
os.makedirs(UPLOAD_DIR, exist_ok=True)


async def _analyze_document(db, doc_id: int, file_bytes: bytes, tenant_id: int):
    """Background task: run AI analysis and persist results."""
    from app.db.session import AsyncSessionLocal
    async with AsyncSessionLocal() as bg_db:
        result = await bg_db.execute(select(Document).where(Document.id == doc_id))
        doc = result.scalars().first()
        if not doc:
            return

        fw = None
        if doc.framework_id:
            fw_result = await bg_db.execute(
                select(Framework).where(Framework.id == doc.framework_id)
            )
            fw = fw_result.scalars().first()

        file_text = await document_ai_service.extract_text(file_bytes, doc.file_type)
        analysis = await document_ai_service.analyze(bg_db, doc, file_text, fw)

        doc.ai_summary = analysis.get('summary', '')
        doc.ai_gaps = analysis.get('gaps', [])
        doc.ai_tags = analysis.get('tags', [])

        scoring_result = await scoring_service.score_document(bg_db, doc, fw)
        doc.compliance_score = scoring_result.score
        doc.risk_level = scoring_result.risk_level
        doc.status = 'analyzed'
        bg_db.add(doc)
        await bg_db.commit()

        if scoring_result.score < 40:
            fw_name = fw.name if fw else 'Unknown Framework'
            await alert_service.send_low_score_alert(bg_db, tenant_id, scoring_result.score, fw_name)


@router.post('/', response_model=DocumentRead, status_code=status.HTTP_201_CREATED)
async def upload_document(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    framework_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Validate extension
    ext = (file.filename or '').rsplit('.', 1)[-1].lower()
    if ext not in settings.ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400,
                            detail=f'File type .{ext} not allowed. Allowed: {settings.ALLOWED_EXTENSIONS}')

    file_bytes = await file.read()
    if len(file_bytes) > settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail='File too large')

    # Save locally
    unique_name = f'{uuid.uuid4().hex}.{ext}'
    save_path = os.path.join(UPLOAD_DIR, unique_name)
    async with aiofiles.open(save_path, 'wb') as f_out:
        await f_out.write(file_bytes)

    doc = Document(
        filename=unique_name,
        original_name=file.filename or unique_name,
        file_type=ext,
        file_size=len(file_bytes),
        storage_path=save_path,
        tenant_id=current_user.tenant_id,
        uploader_id=current_user.id,
        framework_id=framework_id,
        status='pending',
    )
    db.add(doc)
    await db.flush()
    await db.refresh(doc)
    doc_id = doc.id

    background_tasks.add_task(
        _analyze_document, db, doc_id, file_bytes, current_user.tenant_id
    )

    return doc


@router.get('/', response_model=list[DocumentRead])
async def list_documents(
    skip: int = 0,
    limit: int = 50,
    framework_id: int | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = select(Document).where(Document.tenant_id == current_user.tenant_id)
    if framework_id:
        q = q.where(Document.framework_id == framework_id)
    q = q.offset(skip).limit(limit)
    result = await db.execute(q)
    return list(result.scalars().all())


@router.get('/{doc_id}', response_model=DocumentRead)
async def get_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.tenant_id == current_user.tenant_id)
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail='Document not found')
    return doc


@router.delete('/{doc_id}', status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    doc_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Document).where(Document.id == doc_id, Document.tenant_id == current_user.tenant_id)
    )
    doc = result.scalars().first()
    if not doc:
        raise HTTPException(status_code=404, detail='Document not found')
    if doc.storage_path and os.path.exists(doc.storage_path):
        os.remove(doc.storage_path)
    await db.delete(doc)
