"""Celery application factory and task discovery."""
from __future__ import annotations

from celery import Celery
from celery.signals import setup_logging

from src.config import settings


def _build_celery() -> Celery:
    app = Celery(
        "prodaxis",
        broker=settings.celery_broker,
        backend=settings.celery_backend,
        include=[
            "src.tasks.send_message_task",
            "src.tasks.send_campaign_task",
            "src.tasks.webhook_processor_task",
        ],
    )

    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        timezone="Asia/Kolkata",
        enable_utc=True,
        task_time_limit=settings.CELERY_TASK_TIME_LIMIT,
        task_soft_time_limit=settings.CELERY_TASK_SOFT_TIME_LIMIT,
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=4,
        worker_max_tasks_per_child=200,
        broker_connection_retry_on_startup=True,
        result_expires=86_400,
        task_default_queue="prodaxis.default",
        task_routes={
            "src.tasks.send_message_task.*": {"queue": "prodaxis.messages"},
            "src.tasks.send_campaign_task.*": {"queue": "prodaxis.campaigns"},
            "src.tasks.webhook_processor_task.*": {"queue": "prodaxis.webhooks"},
        },
    )

    return app


celery_app = _build_celery()


@setup_logging.connect
def _configure_celery_logging(**_kwargs):  # type: ignore[no-untyped-def]
    """Hand Celery's logging over to Loguru."""
    from src.logger import setup_logging as configure

    configure()
