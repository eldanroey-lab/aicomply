import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

logger = logging.getLogger(__name__)
scheduler = AsyncIOScheduler()


async def _run_compliance_digest():
    from app.db.session import AsyncSessionLocal
    from app.services.alerts import alert_service
    async with AsyncSessionLocal() as db:
        await alert_service.send_overdue_task_alerts(db)
    logger.info("Compliance digest completed")


async def _run_score_refresh():
    from app.db.session import AsyncSessionLocal
    from app.services.scoring import scoring_service
    async with AsyncSessionLocal() as db:
        await scoring_service.refresh_all_tenant_scores(db)
    logger.info("Score refresh completed")


def start_scheduler():
    scheduler.add_job(_run_compliance_digest, CronTrigger(hour=8, minute=0), id="daily_digest")
    scheduler.add_job(_run_score_refresh, CronTrigger(day_of_week="mon", hour=6), id="weekly_score")
    scheduler.start()
    logger.info("Scheduler started")


def stop_scheduler():
    scheduler.shutdown(wait=False)
    logger.info("Scheduler stopped")
