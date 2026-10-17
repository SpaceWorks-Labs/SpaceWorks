"""Authoritative tenant lookup for mixed-audience downloads and kiosk operators."""

from django.apps import apps

STATION_ACCOUNT_ROUTES = frozenset({
    "kiosk-station-operator-lease", "kiosk-station-work-package",
    "kiosk-station-evidence-prepare", "kiosk-station-command-online",
})


def account_route_targets(name, kwargs):
    if name in STATION_ACCOUNT_ROUTES:
        target = apps.get_model("makerspaces.StationCredential").objects.filter(
            public_token=kwargs.get("public_token"),
        ).values_list("station__makerspace_id", flat=True).first()
    elif name == "payment-document-download":
        target = apps.get_model("payments.PaymentDocument").objects.filter(
            pk=kwargs.get("document_id"),
        ).values_list("makerspace_id", flat=True).first()
    else:
        return None
    return name, {target} if target is not None else set(), target is None, True
