from celery import shared_task

from .stock_snapshots import snapshot_inventory_stock


@shared_task
def snapshot_stock_task():
    return snapshot_inventory_stock()
