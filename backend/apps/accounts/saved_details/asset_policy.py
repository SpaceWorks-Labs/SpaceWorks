from django.conf import settings

from .errors import SavedDetailsError


def require_ready(asset):
    if (asset.state != "ready" or (getattr(settings, "ACCOUNT_SAVED_RESUME_SCAN_REQUIRED", False)
                                   and asset.scan_status != "clean")):
        raise SavedDetailsError("asset_not_ready", "This résumé is not ready under the current safety policy.", 409)
