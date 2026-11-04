"""Free capacity locks have short database timeouts, including settlement."""
from contextlib import contextmanager

from django.db import connection, transaction


@contextmanager
def accounting_transaction():
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT current_setting('lock_timeout'), current_setting('statement_timeout')")
            previous = cursor.fetchone()
            cursor.execute("SELECT set_config('lock_timeout', '1000', true), set_config('statement_timeout', '1000', true)")
        try:
            yield
        finally:
            if not connection.needs_rollback:
                with connection.cursor() as cursor:
                    cursor.execute("SELECT set_config('lock_timeout', %s, true), set_config('statement_timeout', %s, true)", previous)
