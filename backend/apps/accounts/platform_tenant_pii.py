"""Presentation masking for the superadmin inside a makerspace's staff routes.

Owner decisions #111 Q12 and #114: the superadmin reads a space's PII only while a PII
window on that space is open. #115 opens every Space-Manager route to the superadmin, so
this is the net under those routes: after the view has built its response and before it
renders, person-identifying values are replaced for a superadmin without a window. It is
presentation only -- workflows, mail and audit keep the real values -- and it never runs
for anyone but an admitted platform superadmin (`platform_tenant_surface.admits`).

Keys are matched by name. DIRECT keys always identify a person. GENERIC keys (`name`,
`note`, `subject`, ...) are masked only inside a dict that also carries a non-empty
DIRECT key, i.e. a person record such as a booking or a registration. A masked value
must never come back as data, so a JSON write carrying the mask is refused.
"""

from django.http.request import RawPostDataException
from rest_framework.exceptions import ValidationError

from apps.accounts.pii_seam import MASK, pii_visible

DIRECT_KEYS = frozenset("""
email phone phone_e164 first_name last_name display_name
requester_username requester_name requester_email requester_phone
requester_contact_email requester_contact_phone contact_name contact_email contact_phone
to_email printed_name recipient_name member_name member_display_name member_email
user_email user_display_name booker_name inviter_name invite_email applicant_email
applicant_phone client_email payout_email anonymous_contact_email candidate_destination
answers_snapshot profile_snapshot application_answers custom_answers form_answers
""".split())
GENERIC_KEYS = frozenset("name note notes subject text_body html_body body remark".split())
_SPACES_ATTR = "_platform_tenant_spaces"
_JSON = "application/json"
# The mask arrives either as raw UTF-8 or as JSON \u escapes.
_MASK_BYTES = (MASK.encode(), MASK.encode("unicode_escape"))


def _django_request(request):
    return getattr(request, "_request", request)


def remember_spaces(request, targets):
    """Mark the request as a superadmin tenant request over these makerspaces."""
    setattr(_django_request(request), _SPACES_ATTR, frozenset(targets or ()))


def admitted_spaces(request):
    return getattr(_django_request(request), _SPACES_ATTR, None)


def refuse_masked_write(request):
    if request.method in ("GET", "HEAD", "OPTIONS"):
        return
    raw = _django_request(request)
    if not (raw.content_type or "").startswith(_JSON):
        return
    try:
        body = raw.body
    except RawPostDataException:  # already streamed by an earlier reader; nothing to inspect
        return
    if any(marker in body for marker in _MASK_BYTES):
        raise ValidationError({"detail": "Open a PII access window on this space before saving personal data.",
                               "code": "pii_access_required"})


def _filled(value):
    return value not in (None, "", [], {})


def _blank(value):
    if isinstance(value, dict):
        return {}
    if isinstance(value, (list, tuple)):
        return []
    return MASK if isinstance(value, str) else value


class _Masker:
    def __init__(self, viewer, targets):
        self.viewer = viewer
        self.default = next(iter(targets)) if len(targets) == 1 else None
        self.cache = {}
        self.masked = False

    def visible(self, row):
        space = row.get("makerspace_id", row.get("makerspace"))
        space = space if isinstance(space, int) and not isinstance(space, bool) else self.default
        if space not in self.cache:
            self.cache[space] = pii_visible(self.viewer, space)
        return self.cache[space]

    def walk(self, data):
        if isinstance(data, list):
            for item in data:
                self.walk(item)
        elif isinstance(data, dict):
            self.mask_row(data)
            for value in data.values():
                if isinstance(value, (dict, list)):
                    self.walk(value)

    def mask_row(self, row):
        direct = [key for key in row if key in DIRECT_KEYS and _filled(row[key])]
        if not direct or self.visible(row):
            return
        for key in (*direct, *(key for key in row if key in GENERIC_KEYS and _filled(row[key]))):
            row[key] = _blank(row[key])
        self.masked = True


def mask_response(request, response):
    targets = admitted_spaces(request)
    data = getattr(response, "data", None)
    if targets is None or not isinstance(data, (dict, list)):
        return response
    masker = _Masker(getattr(request, "user", None), targets)
    masker.walk(data)
    if masker.masked:
        response["X-PII-Masked"] = "1"
    return response


class PlatformTenantPiiMiddleware:
    """Runs `mask_response` on DRF responses before they render."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        return self.get_response(request)

    def process_template_response(self, request, response):
        return mask_response(request, response)
