"""Who is giving (#128 C-14b): anyone.

* A signed-in person gives as themselves: the gift and its charge are their account's.
* Anyone else gives as a guest with name, email and the one-time email code -- the #80
  machinery account-less borrowers use (`hardware_requests.contact_verification`), so a guest
  cannot give in someone else's name. The guest's details live only in the gift's scoped-PII
  columns; the charge belongs to no account and the space's inert principal records it.
"""

from django.utils.translation import gettext
from dataclasses import dataclass

from .gates import DonationRefused


@dataclass(frozen=True)
class Donor:
    account: object
    name: str
    email: str
    actor: object

    @property
    def is_guest(self):
        return self.account is None


def _person(user):
    if not getattr(user, "is_authenticated", False):
        return None
    if getattr(user, "account_kind", None) != "member" or not user.is_active:
        return None
    return user


def donor_for(request, space, data):
    """The giver behind a public request: the signed-in person, else a code-confirmed guest."""
    person = _person(request.user)
    if person is not None:
        name = (person.get_full_name() or getattr(person, "display_name", "") or person.username).strip()
        return Donor(account=person, name=name[:200], email=(person.email or "")[:254], actor=person)
    name, email, code = (str(data.get(key) or "").strip() for key in ("donor_name", "donor_email", "email_code"))
    if not name or not email or not code:
        raise DonationRefused(gettext("Sign in, or give your name, email and the code we emailed you."),
                              "donor_identity_required")
    from apps.hardware_requests.contact_verification import consume_code, normalize_email
    from apps.makerspaces.anonymous_requesters import get_or_create_anonymous_requester

    consume_code(space, email, code)
    return Donor(account=None, name=name[:200], email=normalize_email(email)[:254],
                 actor=get_or_create_anonymous_requester(space))


def send_code(space, email):
    from apps.hardware_requests.contact_verification import issue_code

    if "@" not in str(email or ""):
        raise DonationRefused(gettext("Enter a valid email address."), "email_invalid", "donor_email")
    issue_code(space, email)


STATUS_SALT = "spaceworks.donation-status"
PLEDGE_SALT = "spaceworks.pledge-manage"


def link_token(row, field, salt):
    """A signed link naming one row and binding its random secret; nothing about the person."""
    from django.core import signing

    return signing.dumps([row.pk, getattr(row, field)[:24]], salt=salt)


def resolve_link(model, field, token, salt, **lookup):
    """The row a signed link names, while its secret still matches; else None (never an oracle)."""
    import hmac

    from django.core import signing

    if not token or len(token) > 200:
        return None
    try:
        row_id, secret = signing.loads(token, salt=salt)
    except (signing.BadSignature, TypeError, ValueError):
        return None
    row = model.objects.filter(pk=row_id, **lookup).first()
    if row is None or not hmac.compare_digest(str(getattr(row, field))[:24], str(secret)):
        return None
    return row
