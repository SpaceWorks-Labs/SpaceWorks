"""Platform provider credentials in the web superadmin console (#190, parity with /control/).

SMS, push, WhatsApp and app attestation. Superadmin only, recent re-authentication on
every write, the /control/ form's own validation and storage (``platform_credentials``),
and one audit row per save naming the changed fields only -- the same action /control/
writes, marked ``via: console``. Secrets are never returned.
"""

from drf_spectacular.utils import extend_schema, extend_schema_view, inline_serializer
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.reauthentication_permissions import RecentReauthenticationMixin
from apps.admin_api.permissions import IsActiveSuperAdmin
from apps.audit import services as audit
from apps.openapi_errors import errors

from . import platform_credential_checks as checks
from .platform_credentials import SPECS, current_row, form_data, payload, record_save
from .serializers_platform_credentials import (
    AttestationCredentialsUpdate, LoginMethodsUpdate, PlatformCredentialsSerializer, PushCredentialsUpdate, SmsCredentialsUpdate,
    SmsTestSerializer, WhatsAppCredentialsUpdate,
)

TAGS = ["Platform providers"]
CheckResult = inline_serializer("PlatformProviderCheckResult", {
    "outcome": serializers.CharField(), "checked": serializers.ListField(child=serializers.CharField(), required=False)})


class _CredentialsView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]
    http_method_names = ["get", "patch", "head", "options"]
    provider = ""
    update_serializer = None

    def get(self, request):
        spec = SPECS[self.provider]
        return Response(payload(spec, current_row(spec)))

    def patch(self, request):
        spec = SPECS[self.provider]
        body = self.update_serializer(data=request.data, partial=True)
        body.is_valid(raise_exception=True)
        row = current_row(spec)
        created = row.pk is None or not spec.model.objects.filter(pk=row.pk).exists()
        form = spec.form(data=form_data(spec, row, body.validated_data), instance=row)
        if not form.is_valid():
            return Response(_form_errors(spec, form), status=400)
        row = form.save()
        record_save(request.user, spec.key, row, created, sorted(form.changed_data))
        return Response(payload(spec, row))


def _form_errors(spec, form):
    """Form errors in API field names (``auth_token_raw`` -> ``auth_token``); values never echoed."""
    names = {raw: name for name, (raw, _clear) in spec.secrets.items()}
    names.update({clear: "clear_" + name for name, (_raw, clear) in spec.secrets.items()})
    out = {}
    for key, messages in form.errors.items():
        out["non_field_errors" if key == "__all__" else names.get(key, key)] = list(messages)
    return out


def _schema(name, update):
    return extend_schema_view(
        get=extend_schema(tags=TAGS, summary=f"Platform {name} credentials (secrets are write-only)",
                          responses={200: PlatformCredentialsSerializer, **errors(401, 403)}),
        patch=extend_schema(tags=TAGS, summary=f"Change the platform {name} credentials", request=update,
                            responses={200: PlatformCredentialsSerializer, **errors(400, 401, 403)}),
    )


@_schema("SMS", SmsCredentialsUpdate)
class PlatformSmsSettingsView(_CredentialsView):
    provider, update_serializer = "sms", SmsCredentialsUpdate


@_schema("push", PushCredentialsUpdate)
class PlatformPushSettingsView(_CredentialsView):
    provider, update_serializer = "push", PushCredentialsUpdate


@_schema("WhatsApp", WhatsAppCredentialsUpdate)
class PlatformWhatsAppSettingsView(_CredentialsView):
    provider, update_serializer = "whatsapp", WhatsAppCredentialsUpdate


@_schema("app attestation", AttestationCredentialsUpdate)
class PlatformAttestationSettingsView(_CredentialsView):
    provider, update_serializer = "attestation", AttestationCredentialsUpdate


@_schema("sign-in methods", LoginMethodsUpdate)
class PlatformLoginMethodsView(_CredentialsView):
    """Which ways in the deployment offers; the /control/ form refuses a change that would lock everyone out."""
    provider, update_serializer = "login_methods", LoginMethodsUpdate


class _TestView(RecentReauthenticationMixin, APIView):
    permission_classes = [IsActiveSuperAdmin]
    http_method_names = ["post", "options"]
    provider = ""

    def _run(self, request, run):
        spec = SPECS[self.provider]
        try:
            result = run(current_row(spec))
        except (checks.ProviderNotConfigured, checks.ProviderTestFailed) as exc:
            audit.record(request.user, "platform.provider_test", meta={
                "via": "console", "provider": spec.key, "outcome": exc.default_code})
            raise
        audit.record(request.user, "platform.provider_test", meta={
            "via": "console", "provider": spec.key, "outcome": result["outcome"]})
        return Response(result)


_TEST_ERRORS = errors(400, 401, 403, 409, 503, e409="Credentials are not saved or incomplete (`provider_not_configured`).",
                      e503="The provider refused or could not be reached (`provider_test_failed`).")


class PlatformSmsTestView(_TestView):
    provider = "sms"

    @extend_schema(tags=TAGS, summary="Send one test SMS from the platform sign-in number",
                   request=SmsTestSerializer, responses={200: CheckResult, **_TEST_ERRORS})
    def post(self, request):
        body = SmsTestSerializer(data=request.data)
        body.is_valid(raise_exception=True)
        return self._run(request, lambda row: checks.check_sms(row, body.validated_data["to"]))


class PlatformPushTestView(_TestView):
    provider = "push"

    @extend_schema(tags=TAGS, summary="Check the platform push credentials (FCM sign-in, APNs key)",
                   request=None, responses={200: CheckResult, **_TEST_ERRORS})
    def post(self, request):
        return self._run(request, checks.check_push)


class PlatformWhatsAppTestView(_TestView):
    provider = "whatsapp"

    @extend_schema(tags=TAGS, summary="Check the platform WhatsApp credentials with Meta",
                   request=None, responses={200: CheckResult, **_TEST_ERRORS})
    def post(self, request):
        return self._run(request, checks.check_whatsapp)
