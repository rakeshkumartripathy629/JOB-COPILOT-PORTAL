import logging

from celery import Celery
from celery.schedules import crontab

from app.config import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    broker_connection_retry_on_startup=False,
    broker_connection_retry=False,
    broker_connection_max_retries=0,
    task_publish_retry=False,
    broker_transport_options={
        "master_name": "celerybeat",
        "socket_connect_timeout": 1,
        "socket_timeout": 1,
        "retry_on_timeout": False,
    },
    result_backend_transport_options={
        "retry_policy": {
            "max_retries": 0,
            "interval_start": 0,
            "interval_step": 0,
            "interval_max": 0,
        },
        "socket_connect_timeout": 1,
        "socket_timeout": 1,
        "retry_on_timeout": False,
    },
    task_ignore_result=True,
    task_store_eager_result=False,
    beat_schedule={
        "scan-due-reminders-hourly": {
            "task": "app.tasks.notification_tasks.scan_due_reminders",
            "schedule": crontab(minute=0, hour="*"),
        },
        "refresh-expired-jobs-daily": {
            "task": "app.tasks.job_tasks.refresh_expired_jobs",
            "schedule": crontab(minute=15, hour=2),
        },
    },
)

celery_app.autodiscover_tasks(["app.tasks"])
