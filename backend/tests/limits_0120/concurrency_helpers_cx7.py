"""Run two actual HTTP requests on separate connections at the same starting line."""
from conftest import _BoundedThreadPoolExecutor as ThreadPoolExecutor
from threading import Barrier

from django.db import close_old_connections, connection, connections


def race_posts(callers, url, bodies):
    barrier = Barrier(2)

    def post(caller, body):
        close_old_connections()
        try:
            if connection.vendor == "postgresql":
                with connection.cursor() as cursor:
                    cursor.execute("SET lock_timeout = '5s'")
            barrier.wait(timeout=15)
            response = caller.post(url, body, format="json")
            return response.status_code, response.json()
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(post, caller, body) for caller, body in zip(callers, bodies)]
        return [future.result(timeout=30) for future in futures]
