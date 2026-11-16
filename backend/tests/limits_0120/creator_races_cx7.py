"""Race real creator services on independent database connections."""
from conftest import _BoundedThreadPoolExecutor as ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections, connection, connections
from rest_framework.exceptions import APIException

from apps.hardware_requests.exceptions import workflow_exception_handler


def race_creators(create):
    barrier = Barrier(2)

    def worker(index):
        close_old_connections()
        try:
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
            barrier.wait(timeout=15)
            try:
                create(index)
            except APIException as exc:
                response = workflow_exception_handler(exc, {})
                return response.status_code, str(response.data["code"])
            return 201, "created"
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, index) for index in range(2)]
        return sorted(future.result(timeout=30) for future in futures)
