"""The borrower identity in a space without member accounts (owner decisions #80/#91).

There, accounts are staff-only, so everyone who requests or self-checks-out is named by
the name, phone and email they typed, the email proven by a one-time code. One confirmed
contact yields:

* ``key``    -- a per-makerspace fingerprint of the email; it is the person for borrow
  limits and for matching a self-checkout return to its checkout, stored on the request
  as ``anonymous_payload_fingerprint`` (no address in a lookup column);
* ``marker`` -- one value per consumed code, stored as
  ``anonymous_idempotency_key_fingerprint``, which marks the row as account-less for every
  owner/contact-mail path and satisfies the per-makerspace uniqueness constraint.

The durable ``requester`` is the makerspace's inert principal; name, phone and email live
only in the request's scoped-PII encrypted snapshot.
"""

from dataclasses import dataclass

from django.core import signing

from apps.accounts.audit_events import fingerprint
from apps.hardware_requests.contact_verification import consume_code, email_key, normalize_email
from apps.makerspaces.anonymous_requesters import get_or_create_anonymous_requester

EVIDENCE_GRANT_SALT = "spaceworks.public-tool.contact-evidence"
EVIDENCE_GRANT_MAX_AGE = 60 * 60


@dataclass(frozen=True)
class ContactIdentity:
    principal: object
    name: str
    email: str
    phone: str
    key: str
    marker: str


def confirm_contact(makerspace, data):
    """Consume the email code and return the confirmed identity (raises 400 otherwise)."""
    challenge = consume_code(makerspace, data["contact_email"], data["email_code"])
    return ContactIdentity(
        principal=get_or_create_anonymous_requester(makerspace),
        name=data["contact_name"].strip(),
        email=normalize_email(data["contact_email"]),
        phone=data["contact_phone"].strip(),
        key=email_key(makerspace, data["contact_email"]),
        marker=fingerprint(f"contact-code:{challenge.pk}"),
    )


def evidence_grant(makerspace, evidence_id, email):
    """Bind an account-less evidence upload to the address that will be confirmed.

    Every account-less upload belongs to the same principal, so ``uploaded_by`` cannot
    tell two borrowers apart; the signed grant, returned only to the uploader, can.
    """
    return signing.dumps(
        {"m": makerspace.pk, "e": evidence_id, "k": email_key(makerspace, email)},
        salt=EVIDENCE_GRANT_SALT,
    )


def grant_matches(makerspace, grant, evidence_id, key):
    try:
        data = signing.loads(grant or "", salt=EVIDENCE_GRANT_SALT, max_age=EVIDENCE_GRANT_MAX_AGE)
    except signing.BadSignature:
        return False
    return data == {"m": makerspace.pk, "e": evidence_id, "k": key}
