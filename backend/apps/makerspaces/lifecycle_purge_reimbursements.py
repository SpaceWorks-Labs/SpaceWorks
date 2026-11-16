"""Whole-tenant purge of stage forms, travel support and the core payout ledger.

Unlike a module purge, this has no unfinished-work or unpaid-debt precondition: the
makerspace itself is going. Permanent FK-free cleanup locators are refreshed first so
finance and stage bytes keep being deleted after the rows that named them are gone.
Must run before the Events graph, whose form revisions these rows PROTECT.
"""


def delete_reimbursement_graph(makerspace, cursor):
    from apps.payments.event_payouts.purge import collect_whole_tenant_locked
    collect_whole_tenant_locked(makerspace.pk)
    from apps.event_reimbursements.purge import delete_domain_for_tenant
    delete_domain_for_tenant(makerspace, cursor)
    from apps.events.staged_forms.purge import delete_locked
    delete_locked(makerspace=makerspace, module_key="tenant")
    # Claim lines PROTECT their receipts, so core rows go only after the domain graph.
    from apps.payments.event_payouts.models import (
        EventPayoutObligation, FinanceAttachment, PayoutExportBatch, ReceiptUse,
    )
    for model in (PayoutExportBatch, EventPayoutObligation, FinanceAttachment, ReceiptUse):
        model._base_manager.filter(makerspace=makerspace).delete()
