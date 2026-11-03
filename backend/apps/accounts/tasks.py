from celery import shared_task
from apps.accounts.saved_details.tasks import process_saved_details  # noqa: F401

from apps.accounts.services_challenge_purge import purge_spent_challenges
from apps.accounts.services_password_reset_drain import drain_password_reset_envelopes
from apps.accounts.tasks_login_security import purge_login_security_task  # noqa: F401 -- S-C retention


@shared_task(name="apps.accounts.tasks.purge_auth_challenges_task")
def purge_auth_challenges_task():
    return purge_spent_challenges()


@shared_task(name="apps.accounts.tasks.drain_password_reset_envelopes_task")
def drain_password_reset_envelopes_task():
    return drain_password_reset_envelopes()


@shared_task(name="apps.accounts.tasks.purge_deleted_accounts_task")
def purge_deleted_accounts_task():
    from apps.accounts.account_purge import purge_deleted_accounts
    return purge_deleted_accounts()


# One bounded batch per tick; the oldest lapsed windows close first, and any left over
# are picked up on the next tick (or lazily by the superadmin's next read).
PII_EXPIRY_BATCH = 500


@shared_task(name="apps.accounts.tasks.expire_pii_access_windows_task")
def expire_pii_access_windows_task():
    from apps.accounts.pii_access import sweep_expired
    return sweep_expired(limit=PII_EXPIRY_BATCH)


@shared_task(name="apps.accounts.tasks.revoke_apple_tokens_task")
def revoke_apple_tokens_task(user_id):
    from apps.accounts.apple_revocation import sweep_revocations
    return sweep_revocations(user_id)
