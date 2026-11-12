"""OpenAPI serializers for browser session endpoints."""

from drf_spectacular.utils import inline_serializer
from rest_framework import serializers


AuthMembershipSerializer = inline_serializer(
    name="AuthMembership",
    fields={
        "id": serializers.IntegerField(),
        "slug": serializers.CharField(),
        # An organization-derived entry claims no role: organization grants confer
        # actions, never identity, so role/role_id/role_slug are null there and
        # role_name carries the organization's name.
        "role": serializers.CharField(allow_null=True),
        "role_id": serializers.IntegerField(allow_null=True),
        "role_ids": serializers.ListField(child=serializers.IntegerField()),
        "role_slugs": serializers.ListField(child=serializers.CharField()),
        "role_names": serializers.ListField(child=serializers.CharField()),
        "role_name": serializers.CharField(),
        "role_slug": serializers.CharField(allow_null=True),
        "source": serializers.ChoiceField(choices=["membership", "organization"]),
        "actions": serializers.ListField(child=serializers.CharField()),
        "can_configure_machine_types": serializers.BooleanField(),
        "is_machine_only": serializers.BooleanField(),
        "can_refer": serializers.BooleanField(),
        "can_verify": serializers.BooleanField(),
        "verified_at": serializers.DateTimeField(allow_null=True),
        "referrals_enabled": serializers.BooleanField(),
        "tracks": serializers.ListField(
            child=serializers.ChoiceField(choices=["community", "staff"]),
            help_text="The person's rows in this space: community (membership) and/or staff (staff roles). Empty for an organization-derived entry.",
        ),
    },
)
StaffRoleEntrySerializer = inline_serializer(
    name="AuthStaffRoleEntry",
    fields={
        "makerspace": inline_serializer(name="AuthStaffRoleMakerspace", fields={
            "id": serializers.IntegerField(), "slug": serializers.CharField(), "name": serializers.CharField(),
        }),
        "roles": serializers.ListField(child=inline_serializer(name="AuthStaffRole", fields={
            "id": serializers.IntegerField(), "slug": serializers.CharField(), "name": serializers.CharField(),
        })),
        "actions": serializers.ListField(child=serializers.CharField()),
    },
)
class SupportedLocaleSerializer(serializers.Serializer):
    code = serializers.CharField()
    label = serializers.CharField()


class AuthUserPayload(serializers.Serializer):
    """Frozen release-2 auth payload (one account per person, #62/#63)."""

    session_authority = serializers.ChoiceField(
        choices=("member", "native_staff", "native_event", "platform", "verification_only"),
        help_text="What this session is: member (a person's browser or native member session; staff routes are "
                  "admitted per request from the person's staff roles), native_staff (a native staff grant fixed to one "
                  "makerspace; tenant operations require a matching X-Makerspace-Id), native_event (a native event-role "
                  "grant limited to one event's programme routes, no staff authority), platform (the superadmin) or "
                  "verification_only (email not yet confirmed).",
    )
    id = serializers.IntegerField()
    username = serializers.CharField()
    email = serializers.EmailField()
    display_name = serializers.CharField()
    phone = serializers.CharField()
    email_verified = serializers.BooleanField()
    role = serializers.CharField()
    is_superuser = serializers.BooleanField()
    must_change_password = serializers.BooleanField()
    kind = serializers.ChoiceField(choices=("person", "platform"),
                                   help_text="person: one account per person; platform: the superadmin.")
    is_platform = serializers.BooleanField(help_text="True for the platform superadmin account.")
    has_staff_role = serializers.BooleanField(
        help_text="The person holds an active staff role in at least one servable makerspace.")
    has_elevated_authority = serializers.BooleanField(
        help_text="A staff role, organization authority or a resource grant anywhere; staff MFA keys on it.")
    has_organizations = serializers.BooleanField(
        help_text="The person holds an active membership of at least one active organization. The console "
                  "shows its Organizations group (organizations, organized events, organization analytics) "
                  "only when true. False for the superadmin, native device sessions and claim sessions.")
    staff_roles = serializers.ListField(
        child=StaffRoleEntrySerializer,
        help_text="Staff authority THIS session may exercise, per makerspace. Native member grants and claim "
                  "sessions list none; a native staff grant lists its fixed tenant only.",
    )
    makerspaces = serializers.ListField(child=AuthMembershipSerializer)
    superadmin_actions = serializers.ListField(
        child=serializers.CharField(),
        help_text="Every action the platform superadmin holds in each servable makerspace (owner decision #115); empty for everyone else.",
    )
    mfa_grace_ends_at = serializers.DateTimeField(
        allow_null=True,
        help_text="When a person who gained a staff role without a second factor must have enrolled (#128 C-1). "
                  "Null when no grace applies. In the past means staff screens refuse with "
                  "mfa_enrollment_required until they enrol; member features keep working.",
    )
    mfa_enrolment_due = serializers.BooleanField(
        help_text="The person holds elevated authority and has no second factor (authenticator or passkey) yet.",
    )
    merge_suggested = serializers.BooleanField(
        help_text="A former staff account that has not linked another account yet: show the \"Link your "
                  "accounts\" nudge (Q17). There is no deadline.",
    )

    handle = serializers.CharField(allow_null=True, help_text="The account's public username (decision 308); null until chosen.")
    handle_required = serializers.BooleanField(
        help_text="True when the account still has no handle: show the blocking 'Choose your username' step. "
                  "State-changing member routes return 403 `handle_required` until one is chosen.")
    handle_suggestion = serializers.CharField(
        allow_null=True, help_text="A valid, free handle to pre-fill the step; null when none fits.")

    preferred_locale = serializers.CharField(
        allow_null=True, help_text="The account's own language; null follows the makerspace default.")
    effective_locale = serializers.CharField(help_text="The language this request resolved to.")
    supported_locales = SupportedLocaleSerializer(many=True)

    def get_fields(self):
        from apps.makerspaces.resource_grant_sources import registered_sources

        fields = super().get_fields()
        for source in registered_sources():
            if source.payload_serializer is not None:
                fields[source.key] = source.payload_serializer(many=True, required=False)
        return fields


UserPayloadSerializer = AuthUserPayload()

LoginRequestSerializer = inline_serializer(
    name="LoginRequest",
    fields={
        "username": serializers.CharField(
            help_text="A person's username or email (a converted staff account whose email was held signs in "
                      "with its username). The platform superadmin signs in by username only from a platform "
                      "origin. Release 2 removed context, makerspace and surface: one account per person.",
        ),
        "password": serializers.CharField(write_only=True),
    },
)
LoginResponseSerializer = inline_serializer(
    name="LoginResponse",
    fields={
        "access": serializers.CharField(),
        "surface": serializers.ChoiceField(choices=("member", "platform", "verification_only")),
        "user": UserPayloadSerializer,
    },
)
RefreshResponseSerializer = inline_serializer(
    name="RefreshResponse", fields={"access": serializers.CharField(), "user": AuthUserPayload()}
)
LogoutResponseSerializer = inline_serializer(
    name="LogoutResponse", fields={"detail": serializers.CharField()}
)
