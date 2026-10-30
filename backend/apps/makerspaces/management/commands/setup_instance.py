import os
import secrets

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.core.exceptions import ValidationError
from django.db import transaction
from django.http import Http404
from django.utils.text import slugify
from rest_framework.exceptions import APIException

from apps.accounts.staff_identity import is_platform
from apps.makerspaces.models import Makerspace
from apps.makerspaces.module_install import apply_profile
from apps.makerspaces.module_profiles import PROFILES
from apps.organizations.models import OrganizationMakerspace
from apps.organizations.services_owner import (
    assign_owner_organization,
    bootstrap_owner_organization,
)
from apps.tenant_migration.gate_errors import SourceMigrationGateError
from apps.tenant_migration.gate_runtime import assert_write_allowed


class Command(BaseCommand):
    help = "Create the first superadmin and makerspace for a self-hosted instance."

    def add_arguments(self, parser):
        parser.add_argument("--username", default=None)
        parser.add_argument("--email", default=os.getenv("SETUP_SUPERADMIN_EMAIL", "admin@example.com"))
        parser.add_argument("--password", default=None)
        parser.add_argument("--makerspace-name", default=os.getenv("SETUP_MAKERSPACE_NAME", "My Makerspace"))
        parser.add_argument("--makerspace-slug", default=os.getenv("SETUP_MAKERSPACE_SLUG", ""))
        parser.add_argument(
            "--organization-name", default=os.getenv("SETUP_ORGANIZATION_NAME"),
            help="Owner organization name (defaults to the makerspace name).",
        )
        parser.add_argument(
            "--profile",
            choices=sorted(PROFILES),
            default=os.getenv("SETUP_MODULE_PROFILE") or None,
            help="Which modules to install on the first makerspace.",
        )

    @staticmethod
    def _owner(makerspace):
        return OrganizationMakerspace.objects.filter(
            makerspace=makerspace, relationship=OrganizationMakerspace.Relationship.OWNER,
        ).select_related("organization").first()

    def handle(self, *args, **options):
        username = options["username"] or os.getenv("SETUP_SUPERADMIN_USERNAME") or "superadmin"
        env_password = os.getenv("SETUP_SUPERADMIN_PASSWORD")
        explicit_password = bool(options["password"] or env_password)
        password = options["password"] or env_password or secrets.token_urlsafe(24)

        User = get_user_model()
        user, created = User.objects.get_or_create(
            username=username,
            defaults={
                "account_kind": "platform",
                "email": options["email"],
                "role": User.Role.SUPERADMIN,
                "is_staff": True,
                "is_superuser": True,
            },
        )
        # CLI access already overrides application rules; this assertion makes an
        # improbable collision loud instead of silently changing a person record.
        if not created and not is_platform(user):
            raise CommandError("Setup requires a separate platform account; existing member/staff accounts cannot be promoted.")
        if not created and user.is_walk_in:
            raise CommandError(f"Cannot set up {username!r}: the existing user is a walk-in.")
        if created:
            user.set_password(password)
            generated = os.getenv("SETUP_SUPERADMIN_PASSWORD_GENERATED", "false").lower() in {"1", "true", "yes"}
            user.must_change_password = generated or not explicit_password
            user.save()
        else:
            changed = False
            if not user.is_superuser:
                user.is_superuser = True
                changed = True
            if not user.is_staff:
                user.is_staff = True
                changed = True
            if user.role != User.Role.SUPERADMIN:
                user.role = User.Role.SUPERADMIN
                changed = True
            if changed:
                user.save(update_fields=["is_superuser", "is_staff", "role"])

        from apps.accounts.login_methods_services import setup_login_methods_from_environment

        try:
            setup_login_methods_from_environment(user)
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc

        slug = options["makerspace_slug"] or slugify(options["makerspace_name"])
        with transaction.atomic():
            makerspace, space_created = Makerspace.objects.get_or_create(
                slug=slug,
                defaults={"name": options["makerspace_name"], "created_by": user},
            )
            if space_created:
                assert_write_allowed(makerspace.pk)
                makerspace = Makerspace.objects.select_for_update().get(pk=makerspace.pk)
                # Only on creation: reruns must preserve the operator's current module
                # selection. The installer applies its confirmed areas afterwards with
                # apply_setup_areas, so a profile is optional here.
                if options["profile"]:
                    apply_profile(makerspace, options["profile"], actor=user)
            owner = self._owner(makerspace)
            organization_name = options["organization_name"] or options["makerspace_name"]
            if space_created:
                owner = bootstrap_owner_organization(user, makerspace.pk, new_name=organization_name)
            elif owner is None:
                try:
                    # assign_owner_organization re-checks under the tenant lock, so
                    # concurrent setup runs cannot both attach an owner.
                    owner = assign_owner_organization(user, makerspace.pk, new_name=organization_name)
                except (Http404, APIException, SourceMigrationGateError) as exc:
                    # An existing space may be hidden from this superadmin or frozen by a
                    # migration gate; setup reruns must not fail on an optional backfill.
                    self.stderr.write(f"Skipped assigning an owner organization: {exc}")

        self.stdout.write(
            self.style.SUCCESS(
                f"{'Created' if created else 'Found'} superadmin {user.username}; "
                f"{'created' if space_created else 'found'} makerspace {makerspace.slug}."
            )
        )
        if owner is not None:
            self.stdout.write(f"Owner organization: {owner.organization.name} (owns {makerspace.name}).")
        if space_created and options["profile"]:
            self.stdout.write(
                f"Installed the '{options['profile']}' module profile "
                f"({len(makerspace.enabled_modules)} modules). "
                "Change it with: python manage.py list_modules / install_module <key>."
            )
        if created and not explicit_password:
            self.stdout.write(
                self.style.WARNING(
                    f"Generated superadmin password: {password}\n"
                    f"Username: {user.username}. Save this password now; "
                    "it must be changed on first login."
                )
            )
