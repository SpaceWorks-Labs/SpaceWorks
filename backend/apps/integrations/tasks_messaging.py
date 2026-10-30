"""Database budgets govern retries across Celery and the beatless scheduler."""
import logging

from celery import shared_task

from apps.tenant_migration.gate_errors import SourceMigrationGateClosed

logger = logging.getLogger(__name__)


@shared_task
def deliver_messaging_task(delivery_id):
    from .messaging.worker import deliver
    try:
        deliver(delivery_id)
    except SourceMigrationGateClosed:
        logger.info("messaging_delivery_source_frozen", extra={"delivery_id": delivery_id})


@shared_task
def sweep_messaging_task():
    from .notification_ingress import recover
    return recover()


@shared_task
def canonical_retention_task():
    from .notification_retention import run_canonical_retention
    return run_canonical_retention()
