"""Public expected-back date (inventory.expected_back, inventory D16).

Only for an item that opts in, whose public availability is not hidden and that has
nothing free right now: the local DATE of the earliest due-back among its open loans.
Never who holds it, how many are out, or a time of day, so it adds one derived date to
the public page and nothing about any borrower.
"""

from apps.makerspaces.platform import feature_enabled

FEATURE = "inventory.expected_back"
OUT = ("issued", "partially_returned")


def expected_back_on(product, cache):
    if not getattr(product, "public_show_expected_back", False) or product.available_quantity > 0:
        return None
    if product.public_availability_mode == "hidden":
        return None
    key = ("expected_back", product.makerspace_id)
    if key not in cache:
        cache[key] = feature_enabled(product.makerspace, FEATURE)
    if not cache[key]:
        return None
    from django.db.models import Min
    from django.utils import timezone

    from apps.hardware_requests.models import HardwareRequest
    due = HardwareRequest.objects.filter(
        makerspace_id=product.makerspace_id, status__in=OUT, return_due_at__isnull=False,
        items__product_id=product.pk,
    ).aggregate(first=Min("return_due_at"))["first"]
    if due is None:
        return None
    from zoneinfo import ZoneInfo
    return timezone.localtime(due, ZoneInfo(product.makerspace.timezone)).date()
