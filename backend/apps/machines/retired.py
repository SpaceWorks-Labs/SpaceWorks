"""Tombstone for the retired certification / training / induction HTTP surface (decision 319 addendum).

The routes stay registered, so route catalogs, origin scopes and OpenAPI keep resolving, but every
call answers 410 `certifications_retired` before authentication or any lookup runs. Records are kept
(read-only, in data export and /control/); `machines.access_grants` is the replacement.
"""
from django.utils.translation import gettext_lazy
from rest_framework.exceptions import APIException


class CertificationsRetired(APIException):
    status_code = 410
    default_code = "certifications_retired"
    default_detail = gettext_lazy("Machine certifications were retired. A space manager now grants machine access.")

    def __init__(self):
        super().__init__({"detail": self.default_detail, "code": self.default_code}, self.default_code)


class RetiredCertificationView:
    """Mixin placed before `APIView`: refuses every request with 410."""

    def initial(self, request, *args, **kwargs):
        raise CertificationsRetired()
