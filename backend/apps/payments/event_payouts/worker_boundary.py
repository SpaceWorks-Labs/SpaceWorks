"""Core worker locks. No runtime Events/R/module or interactive finance bypass."""
from contextlib import contextmanager
from django.db import transaction
from apps.encryption.account_write_fence import account_fences
from apps.makerspaces.models import Makerspace
from .obligation_models import EventPayoutObligation
from .attachment_models import FinanceAttachment
from .errors import require
from .transactions import prepared_scope


def retained_accounts(owner_id):
    # Tenant-owned retention cannot be stranded by erasure of the account vault.
    # A concurrent erasure still wins the account fence and forces a safe retry;
    # subsequent passes need only the tenant fence for already-erased owners.
    if owner_id is None:
        return ()
    from apps.encryption.account_models import PiiAccountWriteFence
    erased = PiiAccountWriteFence.objects.filter(user_id=owner_id, state="erased").exists()
    return () if erased else (owner_id,)


@contextmanager
def locked_asset(asset_id):
    seed = FinanceAttachment.objects.get(pk=asset_id)
    accounts = retained_accounts(seed.owner_member_id)
    with prepared_scope(seed.makerspace_id), transaction.atomic(), account_fences(
        accounts, (seed.makerspace_id,),
    ):
        Makerspace.objects.select_for_update().get(pk=seed.makerspace_id)
        obligation = EventPayoutObligation.objects.select_for_update().filter(pk=seed.obligation_id).first() if seed.obligation_id else None
        if obligation:
            list(obligation.payee_revisions.select_for_update().order_by("pk"))
        row = FinanceAttachment.objects.select_for_update().get(pk=seed.pk)
        require((row.obligation_id, row.makerspace_id, row.owner_member_id) == (
            seed.obligation_id, seed.makerspace_id, seed.owner_member_id), "attachment_scope_changed")
        yield row, obligation


@contextmanager
def locked_obligation(obligation_id):
    seed = EventPayoutObligation.objects.get(pk=obligation_id)
    accounts = retained_accounts(seed.owner_member_id)
    with prepared_scope(seed.makerspace_id), transaction.atomic(), account_fences(
        accounts, (seed.makerspace_id,),
    ):
        Makerspace.objects.select_for_update().get(pk=seed.makerspace_id)
        row = EventPayoutObligation.objects.select_for_update().get(pk=seed.pk)
        require(row.owner_member_id == seed.owner_member_id and row.makerspace_id == seed.makerspace_id, "scope_changed")
        yield row
