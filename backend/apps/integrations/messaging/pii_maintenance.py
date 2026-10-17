"""Use the registered write-fence operation, never an independent bypass flag."""
from django.db import connection


def consent_phone_maintenance_allowed(makerspace_id):
    if not connection.in_atomic_block:
        return False
    with connection.cursor() as cursor:
        cursor.execute("""SELECT EXISTS (
            SELECT 1 FROM encryption_piiglobalwritefence
            WHERE state = 'closed' AND operation_id::text = current_setting('app.pii_fence_operation', true)
              AND operation_kind IN ('enable_transition', 'decrypt_rollback')
            UNION ALL
            SELECT 1 FROM encryption_piimakerspacewritefence
            WHERE state = 'closed' AND operation_id::text = current_setting('app.pii_fence_operation', true)
              AND operation_kind IN ('enable_transition', 'decrypt_rollback') AND makerspace_id = %s
        )""", [makerspace_id])
        return cursor.fetchone()[0]
