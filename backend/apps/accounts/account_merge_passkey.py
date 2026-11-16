"""A passkey as the factor of a ``credentials`` account-merge proof (#65; GAP2 M6).

#65: a merge needs the other (source) account's password AND its authenticator. S-A's
``passkeys.assertion.begin_proof``/``verify_proof`` let one of the SOURCE's passkeys stand in
for its TOTP, so a converted staff account that only ever had a passkey can link without the
two emailed codes.

1. ``passkey_options``: the password is checked first and a wrong one counts as a failed try
   (the intent's shared attempt budget), so the offered credential list never answers "does
   this account exist" or "which passkeys does it have". Then the source's passkeys on this
   address are offered (``factor_enrolment_required`` when it has none usable here: no
   passkey, the platform switch off, or ``security.passkeys_allowed`` off for that person).
2. ``prove`` with ``password`` + ``passkey`` (``check_passkey``): the password again, then the
   ceremony, which must belong to the source and is spent once whatever the outcome.
"""

from django.db import transaction
from django.utils import timezone

from apps.accounts import account_merge_proofs as proofs
from apps.accounts.account_merge_eligibility import (
    FACTOR_ENROLMENT_REQUIRED, PROOF_EXPIRED, PROOF_FAILED, MergeRefused, require_survivor,
)
from apps.accounts.models_account_merge import AccountMergeIntent as Intent

NO_PASSKEY = (FACTOR_ENROLMENT_REQUIRED,
              "That account has no passkey you can use here. Use its authenticator code or emailed codes.")


def _has_passkey_here(request, source):
    from apps.accounts.models_webauthn import WebAuthnCredential
    from apps.accounts.passkeys.policy import passkeys_usable
    from apps.accounts.passkeys.rp_id import request_origin_and_rp_id
    if not passkeys_usable(source):
        return False
    _origin, rp_id = request_origin_and_rp_id(request)
    return bool(rp_id) and WebAuthnCredential.objects.filter(user=source, rp_id=rp_id).exists()


def passkey_options(request, intent_id, password):
    survivor = request.user
    require_survivor(survivor)
    now = timezone.now()
    with transaction.atomic():
        intent = proofs.locked_intent(survivor, intent_id)
        if intent.method != Intent.Method.CREDENTIALS or not proofs._live(intent, now):
            failure = (PROOF_EXPIRED, "This link request expired. Start again.")
        else:
            failure = proofs.check_password(intent.source, password)
            if failure is None:
                if not _has_passkey_here(request, intent.source):
                    failure = NO_PASSKEY
                else:
                    from apps.accounts.passkeys.assertion import begin_proof
                    return begin_proof(request, intent.source)
            else:
                proofs.count_failure(survivor, intent, now)
    raise MergeRefused(*failure)


def check_passkey(request, source, password, passkey):
    """For ``prove``: None when the password matches and the source's passkey answered."""
    failure = proofs.check_password(source, password)
    if failure is not None:
        return failure
    from apps.accounts.passkeys.assertion import verify_proof
    if request is None or not verify_proof(request, source, passkey.get("ceremony"), passkey.get("credential")):
        return PROOF_FAILED, "The account details are wrong."
    return None
