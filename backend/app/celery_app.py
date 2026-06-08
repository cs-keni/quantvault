from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "quantvault",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL,
    include=[
        # Task modules are registered here as each lands:
        "app.services.optimization_service",
        "app.services.simulation_service",
        "app.services.backtest_service",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    # Pin the Celery 6.0 startup-retry behavior now to silence the
    # CPendingDeprecationWarning that fires on every worker boot.
    broker_connection_retry_on_startup=True,
)

# When USE_CELERY=false (single-service Render deployment), tasks run
# synchronously in the request thread — no worker process needed.
# task_eager_propagates=False lets the endpoints handle exceptions normally
# instead of having .delay() raise immediately.
if not settings.USE_CELERY:
    celery_app.conf.update(
        task_always_eager=True,
        task_eager_propagates=False,
    )
