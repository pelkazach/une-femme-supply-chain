"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab

from src.config import settings

# Create Celery app
celery_app = Celery(
    "une_femme",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=[
        "src.tasks.winedirect_sync",
        "src.tasks.forecast_retrain",
        "src.tasks.email_processor",
        "src.tasks.quickbooks_sync",
    ],
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
        "retrain-forecasts-weekly": {
            "task": "src.tasks.forecast_retrain.retrain_forecasts",
            # Run every Monday at 7 AM UTC (after WineDirect daily sync)
            "schedule": crontab(hour=7, minute=0, day_of_week=1),
            "options": {"queue": "default"},
        },
        "process-emails-periodic": {
            "task": "src.tasks.email_processor.process_emails",
            # Run every 5 minutes to check for new emails
            # Target: 100+ emails/day throughput = ~7 emails per 5 min avg
            # Processing latency <15 seconds per email
            "schedule": crontab(minute="*/5"),
            "kwargs": {"max_emails": 50},
            "options": {"queue": "default"},
        },
        "sync-quickbooks-inventory": {
            "task": "src.tasks.quickbooks_sync.sync_quickbooks_inventory",
            # Run every 4 hours for bidirectional inventory sync
            # Per spec: sync completes within 15 minutes
            "schedule": crontab(minute=0, hour="*/4"),
            "kwargs": {"direction": "bidirectional"},
            "options": {"queue": "default"},
        },
        "sync-quickbooks-invoices-daily": {
            "task": "src.tasks.quickbooks_sync.sync_quickbooks_invoices",
            # Run daily at 8 AM UTC to pull invoices from QuickBooks
            # Per spec: Invoices synced daily from QBO → Platform
            "schedule": crontab(hour=8, minute=0),
            "kwargs": {"days_back": 1},
            "options": {"queue": "default"},
        },
    },
)
