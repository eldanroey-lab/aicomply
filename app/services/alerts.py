"""
Alert service — email + in-app notifications for overdue tasks
and critical compliance scores.
"""
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.models.task import Task
from app.db.models.user import User

logger = logging.getLogger(__name__)


class AlertService:
    def _send_email(self, to: str, subject: str, body: str):
        if not settings.SMTP_HOST:
            logger.info(f'[Email stub] To: {to} | Subject: {subject}')
            return
        try:
            msg = MIMEMultipart('alternative')
            msg['Subject'] = subject
            msg['From'] = settings.ALERT_EMAIL_FROM or 'noreply@aicomply.io'
            msg['To'] = to
            msg.attach(MIMEText(body, 'html'))
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as srv:
                srv.starttls()
                if settings.SMTP_USER:
                    srv.login(settings.SMTP_USER, settings.SMTP_PASSWORD or '')
                srv.sendmail(msg['From'], to, msg.as_string())
        except Exception as e:
            logger.error(f'Failed to send email to {to}: {e}')

    async def send_overdue_task_alerts(self, db: AsyncSession):
        result = await db.execute(
            select(Task).where(
                Task.due_date < date.today(),
                Task.status.notin_(['done']),
                Task.assignee_id.is_not(None),
            )
        )
        overdue_tasks = result.scalars().all()
        alerted = 0
        for task in overdue_tasks:
            user_result = await db.execute(select(User).where(User.id == task.assignee_id))
            user = user_result.scalars().first()
            if user:
                self._send_email(
                    to=user.email,
                    subject=f'[AiComply] Overdue Task: {task.title}',
                    body=f'<p>Hi {user.full_name or user.email},</p>'
                         f'<p>Your compliance task <strong>{task.title}</strong> '
                         f'was due on {task.due_date} and is still open. '
                         f'Please update its status in AiComply.</p>',
                )
                alerted += 1
        logger.info(f'Sent {alerted} overdue task alerts')
        return alerted

    async def send_low_score_alert(self, db: AsyncSession, tenant_id: int, score: float, framework_name: str):
        result = await db.execute(
            select(User).where(User.tenant_id == tenant_id, User.role == 'admin')
        )
        admins = result.scalars().all()
        for admin in admins:
            self._send_email(
                to=admin.email,
                subject=f'[AiComply] Low Compliance Score: {framework_name}',
                body=f'<p>Hi {admin.full_name or admin.email},</p>'
                     f'<p>Your framework <strong>{framework_name}</strong> '
                     f'has a compliance score of <strong>{score:.1f}%</strong>, '
                     f'which is below the acceptable threshold. '
                     f'Please review the identified gaps in AiComply.</p>',
            )


alert_service = AlertService()
