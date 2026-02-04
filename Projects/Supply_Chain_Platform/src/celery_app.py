"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab

from src.config import settings

# Create Celery app
celery_app = Celery(
    "une_femme",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["src.tasks.winedirect_sync"],
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Result backend settings
    result_expires=3600,  # Results expire after 1 hour
    # Worker settings
    worker_prefetch_multiplier=1,
    # Task execution settings
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # Beat schedule for periodic tasks
    beat_schedule={
        "sync-winedirect-daily": {
            "task": "src.tasks.winedirect_sync.sync_winedirect_inventory",
            # Run daily at 6 AM UTC (aligned with WineDirect Data Lake refresh)
            "schedule": crontab(hour=6, minute=0),
            "options": {"queue": "default"},
        },
    },
)
