"""
Document AI service — extracts text, summarises content, and identifies
compliance gaps using Claude (Anthropic).  Falls back to a deterministic
heuristic when no API key is configured.
"""
import logging
import re
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.document import Document
from app.db.models.framework import Framework

logger = logging.getLogger(__name__)


class DocumentAIService:
    async def _call_claude(self, prompt: str) -> str:
        """Call Anthropic messages API."""
        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            message = await client.messages.create(
                model='claude-opus-4-6',
                max_tokens=1024,
                messages=[{'role': 'user', 'content': prompt}],
            )
            return message.content[0].text
        except Exception as e:
            logger.warning(f'Claude API error: {e}')
            return ''

    def _heuristic_summary(self, text: str, filename: str) -> str:
        words = re.findall(r'\b\w+\b', text.lower())
        top = sorted(set(words), key=words.count, reverse=True)[:10]
        return (
            f'Document "{filename}" covers topics: {", ".join(top[:5])}. '
            f'Heuristic analysis — configure ANTHROPIC_API_KEY for AI insights.'
        )

    async def analyze(
        self,
        db: AsyncSession,
        document: Document,
        file_text: str,
        framework: Optional[Framework] = None,
    ) -> dict:
        """
        Returns:
          summary: str
          gaps: list[{control_id, gap, recommendation}]
          tags: list[str]
        """
        if settings.ANTHROPIC_API_KEY:
            controls_str = ''
            if framework and framework.controls:
                controls_str = '\n'.join(
                    f'- [{c["id"]}] {c["title"]}: {c.get("description","")}' 
                    for c in framework.controls
                )

            prompt = f"""You are a compliance analyst. Analyse this document excerpt for compliance.

DOCUMENT ({document.original_name}):
{file_text[:3000]}

{f'FRAMEWORK CONTROLS TO CHECK:{chr(10)}{controls_str}' if controls_str else ''}

Respond in JSON with keys:
- "summary": 2-3 sentence summary
- "gaps": array of {{"control_id": str, "gap": str, "recommendation": str}}
- "tags": array of relevant compliance tags (e.g. GDPR, SOC2, ISO27001)
"""
            response = await self._call_claude(prompt)
            try:
                import json, re as _re
                match = _re.search(r'\{.*\}', response, _re.DOTALL)
                if match:
                    return json.loads(match.group())
            except Exception:
                pass

        # Fallback heuristic
        summary = self._heuristic_summary(file_text, document.original_name)
        tags = []
        text_lower = file_text.lower()
        if 'gdpr' in text_lower or 'personal data' in text_lower:
            tags.append('GDPR')
        if 'soc' in text_lower or 'audit' in text_lower:
            tags.append('SOC2')
        if 'iso' in text_lower or '27001' in text_lower:
            tags.append('ISO27001')
        if 'hipaa' in text_lower or 'phi' in text_lower:
            tags.append('HIPAA')
        if not tags:
            tags = ['General Compliance']

        return {'summary': summary, 'gaps': [], 'tags': tags}

    async def extract_text(self, file_bytes: bytes, file_type: str) -> str:
        """Extract plain text from uploaded file."""
        if file_type in ('txt', 'csv'):
            try:
                return file_bytes.decode('utf-8', errors='replace')
            except Exception:
                return ''
        if file_type == 'pdf':
            try:
                import pypdf
                from io import BytesIO
                reader = pypdf.PdfReader(BytesIO(file_bytes))
                return ' '.join(page.extract_text() or '' for page in reader.pages)
            except ImportError:
                logger.warning('pypdf not installed; skipping PDF text extraction')
        if file_type == 'docx':
            try:
                from docx import Document as DocxDoc
                from io import BytesIO
                doc = DocxDoc(BytesIO(file_bytes))
                return ' '.join(p.text for p in doc.paragraphs)
            except ImportError:
                logger.warning('python-docx not installed; skipping DOCX extraction')
        return f'[Binary file: {file_type}]'


document_ai_service = DocumentAIService()
