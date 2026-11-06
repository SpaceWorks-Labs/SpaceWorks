"""Which locale a request or a piece of background output renders in (phase 8 i18n).

Precedence, highest first, and the ``source`` each step records:

1. ``explicit`` -- a valid ``X-SpaceWorks-Locale`` header: a deliberate in-app choice.
2. ``user`` -- the signed-in account's ``preferred_locale``.
3. ``makerspace`` -- the default of a makerspace the caller has ALREADY resolved through
   its own scoping; never one looked up from an unchecked id, slug or body field.
4. ``accept_language`` -- the browser's ambient ``Accept-Language``.
5. ``system`` -- ``en``.

The source is kept beside the code so a later makerspace resolution can replace only an
ambient or system result, never an explicit choice or an account preference, even though
English is today the only locale and every step yields ``en``.
"""

from contextlib import contextmanager

from django.utils import translation
from django.utils.cache import patch_vary_headers

from config.locale_registry import SYSTEM_LOCALE, canonicalize, supported_codes

EXPLICIT, USER, MAKERSPACE, ACCEPT_LANGUAGE, SYSTEM = (
    "explicit", "user", "makerspace", "accept_language", "system",
)
EXPLICIT_HEADER_META = "HTTP_X_SPACEWORKS_LOCALE"
VARY_HEADERS = ("Accept-Language", "X-SpaceWorks-Locale")
_REPLACEABLE = {ACCEPT_LANGUAGE, SYSTEM}


def explicit_from_request(request):
    """The dedicated header's code, or None when absent, multiple, malformed or unsupported."""
    raw = request.META.get(EXPLICIT_HEADER_META)
    if not raw or "," in raw:
        return None
    return canonicalize(raw)


def ambient_from_request(request):
    """The best supported language from ``Accept-Language``; never an explicit choice."""
    header = request.META.get("HTTP_ACCEPT_LANGUAGE", "")
    for code, _quality in translation.trans_real.parse_accept_lang_header(header):
        if code != "*" and (supported := canonicalize(code)):
            return supported
    return None


def makerspace_default(makerspace):
    """An authoritatively resolved makerspace's default (instance or id), else None.

    A one-locale deployment answers from the registry and never pays a query: the field's
    choices make any stored default that one code.
    """
    if makerspace is None:
        return None
    if hasattr(makerspace, "pk"):
        return canonicalize(getattr(makerspace, "default_locale", None))
    codes = supported_codes()
    if len(codes) == 1:
        return codes[0]
    from apps.makerspaces.models import Makerspace

    value = Makerspace.objects.filter(pk=makerspace).values_list("default_locale", flat=True).first()
    return canonicalize(value)


def resolve(*, explicit=None, user=None, makerspace=None, ambient=None):
    """``(code, source)`` from the candidates in precedence order."""
    if code := canonicalize(explicit):
        return code, EXPLICIT
    if code := canonicalize(getattr(user, "preferred_locale", None)):
        return code, USER
    if code := makerspace_default(makerspace):
        return code, MAKERSPACE
    if code := canonicalize(ambient):
        return code, ACCEPT_LANGUAGE
    return SYSTEM_LOCALE, SYSTEM


def preliminary(request):
    """The pre-authentication locale: dedicated header, then ambient, then system."""
    return resolve(explicit=explicit_from_request(request), ambient=ambient_from_request(request))


def _django_request(request):
    return getattr(request, "_request", request)


def apply(request, code, source):
    """Activate ``code`` for the rest of this request and record where it came from."""
    translation.activate(code)
    targets = (request,) if _django_request(request) is request else (request, _django_request(request))
    for target in targets:
        target.resolved_locale, target.locale_source, target.LANGUAGE_CODE = code, source, code
    return code


def activate_authenticated_locale(request, user, makerspace=None):
    """Called by authentication once a principal is valid, before any refusal can render."""
    code, source = resolve(
        explicit=explicit_from_request(request), user=user, makerspace=makerspace,
        ambient=ambient_from_request(request),
    )
    return apply(request, code, source)


def activate_resolved_makerspace_locale(request, makerspace):
    """After an endpoint scopes its makerspace: its default replaces only ambient/system."""
    current = getattr(_django_request(request), "locale_source", SYSTEM)
    code = makerspace_default(makerspace)
    if current in _REPLACEABLE and code:
        return apply(request, code, MAKERSPACE)
    return translation.get_language()


def finalize_response(response):
    """``Content-Language`` from the final active locale; vary on both locale headers."""
    response.headers.setdefault("Content-Language", translation.get_language() or SYSTEM_LOCALE)
    patch_vary_headers(response, VARY_HEADERS)
    return response


@contextmanager
def early_response_locale(request):
    """For a refusal built OUTSIDE the reset boundary (the recovery gate)."""
    code, _source = preliminary(request)
    with translation.override(code):
        yield code


def locale_for(user=None, makerspace=None):
    """Background output: recipient preference, then makerspace default, then ``en``.

    ``user`` may be a zero-argument callable so a caller never loads a recipient row just to
    learn that a one-locale deployment renders in that locale.
    """
    codes = supported_codes()
    if len(codes) == 1:
        return codes[0]
    if callable(user):
        user = user()
    return resolve(user=user, makerspace=makerspace)[0]


@contextmanager
def override_for(user=None, makerspace=None):
    """Render non-request output (email, PDF, chat, a notification row) in its locale.

    Coerce lazy strings to ``str`` inside the block before handing them to SMTP, a chat
    API, ReportLab, a model field or a ``transaction.on_commit`` callback.
    """
    code = locale_for(user=user, makerspace=makerspace)
    with translation.override(code):
        yield code
