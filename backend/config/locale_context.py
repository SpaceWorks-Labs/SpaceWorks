"""The two locale middlewares around Django's own ``LocaleMiddleware`` (phase 8 i18n).

``LocaleContextResetMiddleware`` sits just inside the request-id/metrics layers and OUTSIDE
every middleware that can answer early (the control-plane reach check, the source-migration
gate, tenant host validation, ...). It opens a fresh ``translation.override`` for each
request, so an early refusal can never inherit the previous request's locale, and it stamps
``Content-Language`` and ``Vary`` on whatever answer comes back. Anything added above it must
be pass-through only or build its answer inside ``early_response_locale`` (the recovery gate
does); ``tests/i18n/test_locale_middleware_order.py`` pins that.

``ExplicitLocaleMiddleware`` runs right after Django's ``LocaleMiddleware`` and re-applies a
valid ``X-SpaceWorks-Locale`` choice for anonymous and session traffic. JWT-authenticated API
requests are re-resolved inside DRF authentication, which runs after all middleware.
"""

from django.utils import translation
from django.utils.cache import patch_vary_headers

from config.locale_resolution import (
    ACCEPT_LANGUAGE,
    EXPLICIT,
    SYSTEM,
    VARY_HEADERS,
    ambient_from_request,
    apply,
    explicit_from_request,
    finalize_response,
    preliminary,
)
from config.locale_registry import SYSTEM_LOCALE, canonicalize


class LocaleContextResetMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        code, source = preliminary(request)
        with translation.override(code):
            apply(request, code, source)
            response = self.get_response(request)
            return finalize_response(response)


class ExplicitLocaleMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        explicit = explicit_from_request(request)
        if explicit:
            apply(request, explicit, EXPLICIT)
        else:
            code = canonicalize(translation.get_language()) or SYSTEM_LOCALE
            apply(request, code, ACCEPT_LANGUAGE if ambient_from_request(request) else SYSTEM)
        response = self.get_response(request)
        patch_vary_headers(response, VARY_HEADERS)
        return response
