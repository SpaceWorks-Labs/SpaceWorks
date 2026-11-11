from django.utils.translation import gettext
from django.db import transaction
from django.utils import timezone
from rest_framework import serializers

from apps.accounts.models import User
from apps.makerspaces import domain_verification
from apps.makerspaces.models import (
    Makerspace,
    default_branding_config,
)


HIDDEN_MODULE, HIDDEN_KEY = "public_site", "hidden_from_central_directory"


class MakerspaceMutationMixin:
    def _validate_event_default(self, instance, values):
        if values.get("event_default_registration_audience") == "participating_organizations":
            from apps.makerspaces.platform import feature_enabled
            if not feature_enabled(instance, "events.organization_audience"):
                raise serializers.ValidationError({"event_default_registration_audience": gettext("Enable organization audience first.")})

    @transaction.atomic
    def create(self, validated_data):
        organization_id = validated_data.pop("organization_id", None)
        organization_name = validated_data.pop("organization_name", None)
        setup = validated_data.pop("creation_setup", None)
        install_profile_id = validated_data.pop("install_profile_id", None)
        public_display_name = validated_data.pop("public_display_name", None)
        if public_display_name is not None:
            branding = default_branding_config()
            branding["display_name"] = public_display_name
            validated_data["branding_config"] = branding
        provider_values = {key: validated_data.pop(key) for key in ("email_provider", "email_provider_config") if key in validated_data}
        instance = super().create(validated_data)
        from apps.integrations.email_provider_serializers import apply_provider_update
        apply_provider_update(instance, provider_values)
        if provider_values:
            instance.save(update_fields=["email_provider", "email_provider_config"])
        self._validate_event_default(instance, validated_data)
        if (domain_verification.is_self_host() and instance.frontend_domain
                and domain_verification.is_operator(self.context["request"].user)):
            instance.frontend_domain_status = Makerspace.DomainStatus.VERIFIED
            instance.domain_verified_at = timezone.now()
            instance.save(
                update_fields=[
                    "frontend_domain_status",
                    "domain_verified_at",
                    "updated_at",
                ]
            )
        if install_profile_id is not None:
            from apps.makerspaces.space_pack_services import apply_saved_profile
            apply_saved_profile(self.context["request"].user, instance, install_profile_id)
            instance.refresh_from_db()
        if setup is not None:
            from apps.makerspaces.creation_setup import configure_creation
            configure_creation(self.context["request"].user, instance, setup)
        if setup is None or "modules" not in setup:
            # Decision 295: an organization workspace starts with Events, Memberships and
            # Bookings; an explicit module choice in the creation setup wins.
            from apps.makerspaces.space_kind import apply_kind_defaults
            apply_kind_defaults(self.context["request"].user, instance)
            instance.refresh_from_db()
        from apps.organizations.services_owner import assign_owner_organization
        assign_owner_organization(
            self.context["request"].user, instance.pk,
            organization_id=organization_id, new_name=organization_name,
        )
        return instance

    def update(self, instance, validated_data):
        if "kind" in validated_data and validated_data["kind"] != instance.kind:
            raise serializers.ValidationError({"kind": gettext("The kind of a space is chosen when it is created.")})
        validated_data.pop("kind", None)
        owner_fields = {field: "Choose an owner organization only when creating a makerspace."
                        for field in ("organization_id", "organization_name") if field in validated_data}
        if owner_fields:
            raise serializers.ValidationError(owner_fields)
        if "creation_setup" in validated_data:
            raise serializers.ValidationError({"creation_setup": gettext("Use setup only when creating a makerspace.")})
        if "install_profile_id" in validated_data:
            raise serializers.ValidationError({"install_profile_id": gettext("Choose a profile only when creating a makerspace.")})
        missing = object()
        telegram_bot_token = validated_data.pop("telegram_bot_token", missing)
        smtp_password = validated_data.pop("smtp_password", missing)
        slack_webhook_url = validated_data.pop("slack_webhook_url", missing)
        mattermost_webhook_url = validated_data.pop("mattermost_webhook_url", missing)
        discord_webhook_url = validated_data.pop("discord_webhook_url", missing)
        public_display_name = validated_data.pop("public_display_name", missing)

        with transaction.atomic():
            locked = Makerspace.objects.select_for_update().get(pk=instance.pk)
            old_domain = locked.frontend_domain
            actor = self.context["request"].user
            is_superadmin = actor.is_superuser or actor.role == User.Role.SUPERADMIN
            from apps.integrations.email_provider_serializers import apply_provider_update
            apply_provider_update(locked, validated_data)
            hidden_before = locked.hidden_from_central_directory
            hidden_decision = self._hidden_decision(actor, locked, validated_data)
            if "resource_limit_overrides" in validated_data:
                from apps.makerspaces.limits_storage_backfill import backfill_if_newly_limited
                backfill_if_newly_limited(locked, locked.resource_limit_overrides, validated_data["resource_limit_overrides"])
            for field, value in validated_data.items():
                setattr(locked, field, value)
            self._validate_event_default(locked, validated_data)
            if (
                "frontend_domain" in validated_data
                and validated_data["frontend_domain"] != old_domain
            ):
                self._apply_frontend_domain_change(
                    locked, validated_data["frontend_domain"], is_superadmin
                )
            if public_display_name is not missing:
                branding = dict(locked.branding_config or {})
                branding["display_name"] = public_display_name
                locked.branding_config = branding
            if telegram_bot_token is not missing:
                locked.set_telegram_bot_token(telegram_bot_token)
            if smtp_password is not missing:
                locked.set_smtp_password(smtp_password)
            if slack_webhook_url is not missing:
                locked.set_slack_webhook_url(slack_webhook_url)
            if mattermost_webhook_url is not missing:
                locked.set_mattermost_webhook_url(mattermost_webhook_url)
            if discord_webhook_url is not missing:
                locked.set_discord_webhook_url(discord_webhook_url)
            locked.save()
            if hidden_decision is not None:
                from apps.makerspaces.settings_authority import record_change
                record_change(actor, locked, HIDDEN_MODULE, HIDDEN_KEY, hidden_before,
                              locked.hidden_from_central_directory, hidden_decision)
            from apps.makerspaces.membership_admission_settings import sync_legacy_settings
            sync_legacy_settings(actor, locked, validated_data)
            return locked

    @staticmethod
    def _hidden_decision(actor, locked, validated_data):
        """#192: "hide from the platform" is the Space Manager's own setting, written
        through the settings authority and audited as `settings.changed`."""
        current = locked.hidden_from_central_directory
        if validated_data.get("hidden_from_central_directory", current) == current:
            return None
        from apps.makerspaces.settings_authority import assert_setting_write
        return assert_setting_write(actor, locked, HIDDEN_MODULE, HIDDEN_KEY)

    @staticmethod
    def _apply_frontend_domain_change(locked, frontend_domain, is_superadmin):
        # #192: a Space Manager may set the domain on self-host too; only the superadmin's
        # is trusted at once, a Space Manager's waits for the DNS TXT proof (VERIFIED gate).
        domain_verification.apply_domain_change(locked, frontend_domain, operator_trusted=is_superadmin)
