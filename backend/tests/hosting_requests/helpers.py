import re
from datetime import timedelta

from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts import rbac
from apps.accounts.models import User
from apps.hosting_requests import tokens
from apps.hosting_requests.models import HostingRequest
from apps.makerspaces.models import Makerspace
from apps.organizations import governance
from apps.organizations.models import Organization, OrganizationMakerspace, OrganizationMembership
from tests.accounts.account_factories import make_staff

SUBMIT = "/api/v1/public/hosting/requests"
OPEN = "/api/v1/public/hosting/requests/open"
RESOLVE = "/api/v1/public/hosting/invitations/resolve"
ANSWER = "/api/v1/public/hosting/invitations/submit"


def payload(**overrides):
    data = {
        "applicant_name": "Ada Applicant",
        "applicant_email": "Ada@Example.test",
        "applicant_phone": "+15550100",
        "space_name": "Riverside Makers",
        "location": "Riverside, Springfield",
        "space_website_url": "https://riverside.example.test",
        "description": "A community workshop with laser cutters and 3D printers.",
        "proposed_slug": "riverside",
        "new_organization_name": "Riverside Makers Collective",
    }
    data.update(overrides)
    return data


def anonymous():
    # Managed hosting validates Host; `testserver` is added to INFRA_HOSTS by the fixture.
    return APIClient(HTTP_HOST="testserver")


def client_for(user):
    client = APIClient(HTTP_HOST="testserver")
    client.force_authenticate(user=user)
    return client


def space(slug, **fields):
    return Makerspace.objects.create(name=slug.title(), slug=slug, **fields)


def superadmin(username="hostreq-root"):
    return User.objects.create_superuser(
        username=username, email=f"{username}@example.test", password="x",
        account_kind=User.AccountKind.PLATFORM, role=User.Role.SUPERADMIN,
        access_status=User.AccessStatus.ACTIVE,
    )


def space_manager(makerspace, username=None):
    return make_staff(
        makerspace, username=username or f"{makerspace.slug}-manager",
        email=f"{makerspace.slug}-manager@example.test", access_status=User.AccessStatus.ACTIVE,
    )


def member(username):
    return User.objects.create_user(
        username=username, email=f"{username}@example.test",
        access_status=User.AccessStatus.ACTIVE,
    )


def owned_space(slug, org_name="Owner Org"):
    makerspace = space(slug)
    organization = Organization.objects.create(name=org_name, slug=f"{slug}-org")
    OrganizationMakerspace.objects.create(
        organization=organization, makerspace=makerspace,
        relationship=OrganizationMakerspace.Relationship.OWNER,
    )
    return makerspace, organization


def org_member(organization, username, *, governance_actions=(), granted=()):
    user = member(username)
    OrganizationMembership.objects.create(
        organization=organization, user=user,
        governance_actions=list(governance_actions), granted_actions=list(granted),
    )
    return user


def member_governor(organization, username="org-governor"):
    """A member account that governs the org and holds manage_makerspace through it."""
    return org_member(
        organization, username,
        governance_actions=[governance.MANAGE_ORGANIZATION_MEMBERS],
        granted=[rbac.Action.MANAGE_MAKERSPACE],
    )


def last_token(path="/hosting/request#token="):
    body = mail.outbox[-1].body
    match = re.search(re.escape(path) + r"([A-Za-z0-9_\-%]+)", body)
    assert match, body
    return match.group(1)


def public_row(status=HostingRequest.Status.SUBMITTED, **fields):
    raw, digest = tokens.mint()
    now = timezone.now()
    defaults = {
        "status": status, "source": HostingRequest.Source.PUBLIC,
        "applicant_name": "Ada", "applicant_email": "ada@example.test",
        "space_name": "Row Space", "location": "Somewhere", "description": "x" * 30,
        "access_token_digest": digest, "verification_expires_at": now + timedelta(hours=48),
    }
    if status in (HostingRequest.Status.ACCEPTED, HostingRequest.Status.REJECTED):
        defaults["decided_at"] = now
    if status == HostingRequest.Status.REJECTED:
        defaults["rejection_reason"] = "Not a fit for this platform."
    if status == HostingRequest.Status.WITHDRAWN:
        defaults["withdrawn_at"] = now
    defaults.update(fields)
    return HostingRequest.objects.create(**defaults), raw


def invited_row(*, makerspace=None, organization=None, status=HostingRequest.Status.INVITED, **fields):
    raw, digest = tokens.mint()
    kind = "organization" if makerspace is None else "makerspace"
    defaults = {
        "status": status, "source": HostingRequest.Source.INVITED, "inviter_kind": kind,
        "inviter_makerspace": makerspace, "inviter_organization": organization,
        "applicant_email": "invitee@example.test", "space_name": "Invited Space",
        "invite_token_digest": digest, "invite_expires_at": timezone.now() + timedelta(days=14),
        "organization_choice": "join" if organization is not None else "own",
    }
    if status == HostingRequest.Status.WITHDRAWN:
        defaults["withdrawn_at"] = timezone.now()
    defaults.update(fields)
    return HostingRequest.objects.create(**defaults), raw


def set_rates(monkeypatch, **rates):
    from django.core.cache import cache
    from rest_framework.throttling import ScopedRateThrottle, SimpleRateThrottle

    updated = {**SimpleRateThrottle.THROTTLE_RATES, **rates}
    monkeypatch.setattr(SimpleRateThrottle, "THROTTLE_RATES", updated)
    monkeypatch.setattr(ScopedRateThrottle, "THROTTLE_RATES", updated)
    cache.clear()
