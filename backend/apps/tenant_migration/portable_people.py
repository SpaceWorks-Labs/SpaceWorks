"""People created by a PORTABLE import (one account per person; #128 C-18, #137 Q-B1).

A CREATE decision makes a walk-in -- an account with no email and no usable password --
unless the archive's credential block carries this person's sign-in credentials. Then the
person is created as a real account (username, email re-stamped unverified, names) so the
travelled password, authenticator and passkeys let them sign in on the target. An email
already held by a target person refuses the import: link that person instead (nothing ever
merges on an email).
"""

from apps.accounts.models import User
from apps.accounts.username_allocation import allocate_username
from config.locale_registry import canonicalize

from .archive_stream import database_value
from .insertion_errors import IdentityResolutionError


def audit_staff_grant(job, source_id, target):
    from apps.audit import services as audit

    audit.record(job.actor, "tenant_migration.staff_roles_granted", makerspace=job.target_makerspace,
                 target=target, meta={"import_id": str(job.pk), "source_user_id": str(source_id)})


def create_person(source, target_pk, credentials, target):
    """A created person: a walk-in, or with travelled credentials a person who signs in."""
    if not credentials:
        _create_walk_in(source, target_pk)
        return 0
    from .credential_block import install_credentials
    user = create_signing_person(source, target_pk)
    install_credentials(user, credentials, target=target)
    return 1


def create_signing_person(source, target_pk):
    from django.db.models.functions import Lower

    from apps.accounts.staff_identity import person_q

    email = (source.get("email") or "").strip()
    if email and User._base_manager.annotate(address=Lower("email")).filter(
            person_q(), address=email.lower()).exists():
        raise IdentityResolutionError("A created person's email already belongs to a target person; link them instead.")

    def create(username):
        user = User(
            pk=target_pk, username=username, email=email,
            first_name=source.get("first_name", ""), last_name=source.get("last_name", ""),
            display_name=source.get("display_name", ""), phone=source.get("phone", ""),
            date_joined=database_value(User._meta.get_field("date_joined"), source["date_joined"]),
            role=User.Role.REQUESTER, access_status=User.AccessStatus.ACTIVE,
            is_walk_in=False, is_staff=False, is_superuser=False,
            is_active=database_value(User._meta.get_field("is_active"), source.get("is_active") or "true"),
            preferred_locale=canonicalize(source.get("preferred_locale")),
        )
        user.set_unusable_password()
        user.save(force_insert=True)
        return user

    return allocate_username(source.get("username", "member"), create=create)


def _create_walk_in(source, target_pk):
    date_joined = database_value(User._meta.get_field("date_joined"), source["date_joined"])
    lifecycle = {
        name: database_value(User._meta.get_field(name), source.get(name))
        for name in ("deletion_requested_at", "deletion_purge_after", "purge_started_at", "account_purged_at")
    }
    deleted = bool(lifecycle["deletion_requested_at"] or lifecycle["account_purged_at"])
    if lifecycle["account_purged_at"]:
        from uuid import uuid4
        source = {**source, "username": "deleted_" + uuid4().hex,
                  "first_name": "", "last_name": "", "display_name": "Deleted member", "phone": ""}

    def create(username):
        user = User(
            pk=target_pk,
            username=username,
            email="",
            first_name=source.get("first_name", ""),
            last_name=source.get("last_name", ""),
            display_name=source.get("display_name", ""),
            phone=source.get("phone", ""),
            phone_e164="",
            phone_verified_at=None,
            email_verified_at=None,
            date_joined=date_joined,
            role=User.Role.REQUESTER,
            access_status=User.AccessStatus.ACTIVE,
            is_walk_in=True,
            is_staff=False,
            is_superuser=False,
            is_active=not deleted,
            # Phase 8 i18n: a supported source preference travels; anything else follows the space.
            preferred_locale=canonicalize(source.get("preferred_locale")),
            **lifecycle,
        )
        user.set_unusable_password()
        user.save(force_insert=True)
        return user

    return allocate_username(source.get("username", "member"), create=create)
