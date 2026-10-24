from celery import shared_task
from apps.accounts.saved_details.tasks import process_saved_details  # noqa: F401

from apps.accounts.services_challenge_purge import purge_spent_challenges
from apps.accounts.services_password_reset_drain import drain_password_reset_envelopes


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


@shared_task(name="apps.accounts.tasks.revoke_apple_tokens_task")
def revoke_apple_tokens_task(user_id):
    from apps.accounts.apple_revocation import sweep_revocations
    return sweep_revocations(user_id)
