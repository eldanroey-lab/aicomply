"""
AI Chat Copilot — an Anthropic-powered conversational assistant
specialised in compliance questions for the user's tenant context.
"""
import logging
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.framework import Framework
from app.db.models.task import Task

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """You are AiComply Copilot, an expert AI compliance assistant helping SMEs
navigate regulatory frameworks like GDPR, ISO 27001, SOC 2, HIPAA, and PCI-DSS.
Be concise, practical, and cite specific control requirements when relevant.
If you don't know something specific about a user's setup, say so."""


class ChatCopilotService:
    async def chat(
        self,
        db: AsyncSession,
        tenant_id: int,
        message: str,
        history: list[dict] | None = None,
    ) -> str:
        """
        Send a message to the copilot and return a response string.
        Enriches context with tenant's frameworks and open tasks.
        """
        # Build context
        fw_result = await db.execute(
            select(Framework).where(Framework.tenant_id == tenant_id)
        )
        frameworks = fw_result.scalars().all()
        task_result = await db.execute(
            select(Task).where(Task.tenant_id == tenant_id, Task.status != 'done').limit(10)
        )
        tasks = task_result.scalars().all()

        context_lines = []
        if frameworks:
            fw_names = ', '.join(f.name for f in frameworks)
            context_lines.append(f'Active frameworks: {fw_names}')
        if tasks:
            context_lines.append(f'Open tasks ({len(tasks)}): ' +
                                  '; '.join(t.title for t in tasks[:5]))

        context_note = ('\n\nTenant context:\n' + '\n'.join(context_lines)) if context_lines else ''

        if not settings.ANTHROPIC_API_KEY:
            return (
                f'Copilot is not yet configured (ANTHROPIC_API_KEY missing).{context_note}\n\n'
                f'Your question: {message}\n\n'
                'To enable AI responses, add your Anthropic API key to the .env file.'
            )

        try:
            import anthropic
            client = anthropic.AsyncAnthropic(api_key=settings.ANTHROPIC_API_KEY)
            messages = list(history or [])
            messages.append({'role': 'user', 'content': message + context_note})
            response = await client.messages.create(
                model='claude-opus-4-6',
                max_tokens=1024,
                system=SYSTEM_PROMPT,
                messages=messages,
            )
            return response.content[0].text
        except Exception as e:
            logger.error(f'Copilot error: {e}')
            return f'Copilot encountered an error: {str(e)}'


chat_copilot_service = ChatCopilotService()
