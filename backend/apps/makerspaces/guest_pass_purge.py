"""Decision 223: what a purge removes of the guest-pass tables.

Passes PROTECT their day-pass product and their waiver, so passes go first. The `Payment`
rows a paid day pass raised are ledger money and are never touched here (CLAUDE.md: the
payment ledger is permanently core); they keep `subject_label` for their receipts.
"""


def _querysets(makerspace):
    from apps.makerspaces.models import DayPassProduct, GuestPass, GuestPassPolicy
    return (GuestPass.objects.filter(makerspace=makerspace), DayPassProduct.objects.filter(makerspace=makerspace),
            GuestPassPolicy.objects.filter(makerspace=makerspace))


def delete_guest_passes(makerspace):
    for queryset in _querysets(makerspace):
        queryset.delete()


def module_delete(makerspace):
    """`(passes_deleted, model_labels)` in the shape the module purge collectors use."""
    from apps.makerspaces.module_purge_collectors_single_model import _delete
    passes, products, policies = _querysets(makerspace)
    count, labels = _delete(passes)
    _p, product_labels = _delete(products)
    _s, policy_labels = _delete(policies)
    return count, labels | product_labels | policy_labels


def preview(makerspace):
    passes, products, _policies = _querysets(makerspace)
    return {"guest_passes": passes.count(), "day_pass_products": products.count()}
