"""Shared fixtures for the L3 (ID cards) local tests."""
from tests.account_split.sweep_helpers import configured_membership, make_role_account
from tests.return_helpers import authenticated_client, make_member, make_space


def card_space(slug, *, modules=("membership", "member_accounts", "email", "events"), features=()):
    space = make_space(slug)
    space.enabled_modules = sorted(set(space.enabled_modules or []) | set(modules))
    space.enabled_features = sorted(set(space.enabled_features or []) | set(features))
    space.save(update_fields=["enabled_modules", "enabled_features", "updated_at"])
    return space


def manager(space, name="sm"):
    return make_member(f"{name}-{space.slug}", space)


def member(space, name="member"):
    user = make_role_account(space, role_slug="member", username=f"{name}-{space.slug}", access_status="active",
                             email=f"{name}-{space.slug}@e.com")
    return user, configured_membership(user=user, makerspace=space)


def custom_staff(space, slugs, name="staff"):
    """A person holding exactly these built-in roles (roles are a fixed catalogue now)."""
    from tests.fixed_roles.helpers import staff_account
    return staff_account(space, f"{name}-{space.slug}", *slugs)


def card_event(space, title="Night"):
    from django.utils import timezone
    from apps.events.models import Event
    now = timezone.now()
    return Event.objects.create(makerspace=space, title=title, starts_at=now + timezone.timedelta(days=1),
                                ends_at=now + timezone.timedelta(days=1, hours=2))


def client(user):
    return authenticated_client(user)


def issue(space, membership, by=None):
    from apps.makerspaces import member_card_services
    return member_card_services.issue_card(by or manager(space, "issuer"), membership)
