"""access.cache: a signed, expiring list of allowed NFC digests so a door or machine can decide while OFFLINE.

Rules (decision 321f):
- DIGESTS ONLY (the same tenant-keyed HMAC the credential row holds); no PIN material, no names, no member ids;
- a digest is listed only if its member is an active, unrestricted member of the space and, for a machine binding,
  passes the single machine-access function ``access_grants.can_use`` (standing, presence, booking and supervision
  are online-only rules and are NOT evaluated offline: the adapter must fail closed when unsure);
- short TTL (binding config ``offline_cache_ttl_seconds`` or ``ADAPTER_ACCESS_CACHE_TTL_SECONDS``, default 15 minutes);
  revoking a credential or a grant is reflected on the adapter's next sync; the list never outlives a listed grant:
  it ends at the earliest grant end, and a grant ending within a minute is left out;
- the document is signed with the deployment Ed25519 key (``services_adapter_core.sign``, ``kid`` in the envelope) over
  domain-separated, length-framed bytes; the adapter verifies with the public keys from hello and must refuse an
  unsigned, unknown-kid or expired list;
- offline decisions are reported on reconnect and become append-only ``AdapterAccessLog`` rows (``offline=True``).
"""
import hashlib
from datetime import datetime, timedelta, timezone as dt_timezone

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.utils import timezone

from apps.devices.adapter_access import OFFLINE_SWITCH, adapter_device, binding_for
from apps.devices.adapters.caps.access_authorize import REASONS
from apps.devices.adapters.caps.access_cache import OFFLINE_BODY, OFFLINE_DECISION
from apps.devices.models import AdapterAccessCache, AdapterAccessLog, AdapterCredential
from apps.devices.services_adapter_core import (CACHE_DOMAIN, AdapterError, audit_adapter, check, current_kid,
                                                framed, sign)

MAX_ENTRIES = 5000
DEFAULT_TTL = 900
MAX_FUTURE_SECONDS = 300
MIN_ENTRY_SECONDS = 60
DEFAULT_MAX_AGE = 7 * 86400


def ttl_seconds(binding):
    from apps.devices.services_adapter_safety import config_of
    value = config_of(binding).get("offline_cache_ttl_seconds") or getattr(
        settings, "ADAPTER_ACCESS_CACHE_TTL_SECONDS", DEFAULT_TTL)
    return max(60, min(int(value), 86400))


def _member_allowed(binding, member, now):
    from apps.devices.services_adapter_access import _entry_refusal
    if _entry_refusal(binding.makerspace, member) is not None:
        return False
    if binding.target_type == "machine" and binding.machine_id:
        from apps.machines.access_grants import can_use
        return can_use(member, binding.machine, now=now)[0]
    return binding.target_type in ("door", "space")


def _grant_until(binding, member, now):
    """When the member's machine access ends (None = no end): the cache never outlives the grant it lists."""
    if binding.target_type != "machine" or not binding.machine_id or binding.machine.open_to_all_members:
        return None
    from apps.machines.access_grants import live_grants_for
    machine = binding.machine
    ends = list(live_grants_for(member, binding.makerspace_id, now).filter(
        Q(machine_id=machine.pk) | Q(machine_type_id=machine.machine_type_id, machine__isnull=True)
    ).values_list("expires_at", flat=True))
    return None if not ends or None in ends else max(ends)


def allowed_entries(binding, now):
    """{digest: access end or None} for every credential the binding may admit offline."""
    rows = AdapterCredential.objects.select_related("user").filter(
        makerspace_id=binding.makerspace_id, kind="nfc", disabled_at__isnull=True, user__is_active=True
    ).order_by("pk")[:MAX_ENTRIES + 1]
    entries = {row.digest: _grant_until(binding, row.user, now)
               for row in rows if _member_allowed(binding, row.user, now)}
    if len(entries) > MAX_ENTRIES:
        raise AdapterError("cache_too_large", "Too many credentials for an offline cache on this binding.",
                           status_code=409)
    return entries


def allowed_digests(binding, now):
    return sorted(allowed_entries(binding, now))


def bounded(entries, issued, expires):
    """(sorted digests, expires): drop entries ending within a minute; end the list at the earliest remaining end."""
    kept = []
    for digest, until in entries.items():
        if until is not None and until.timestamp() < issued + MIN_ENTRY_SECONDS:
            continue
        if until is not None:
            expires = min(expires, int(until.timestamp()))
        kept.append(digest)
    return sorted(kept), expires


def canonical(binding_id, kid, version, issued, expires, digests):
    """The signed bytes: domain-separated and length-framed (``services_adapter_core.framed``)."""
    fingerprint = hashlib.sha256(",".join(digests).encode("utf-8")).hexdigest()
    return framed(CACHE_DOMAIN, binding_id, kid, version, issued, expires, fingerprint)


def build(principal, binding_id):
    now = timezone.now()
    with transaction.atomic():
        device = adapter_device(principal, lock=True)
        binding = binding_for(device, binding_id, "access.cache")
        issued = int(now.timestamp())
        digests, expires = bounded(allowed_entries(binding, now), issued, issued + ttl_seconds(binding))
        version = issued
        AdapterAccessCache.objects.update_or_create(binding=binding, defaults={
            "makerspace_id": binding.makerspace_id, "version": version, "entry_count": len(digests),
            "issued_at": now, "expires_at": datetime.fromtimestamp(expires, tz=dt_timezone.utc)})
        audit_adapter(device.makerspace, device, "devices.adapter_access_cache_issued", meta={
            "binding_id": str(binding.pk), "entries": len(digests), "expires_at": expires})
    kid, signature = sign(canonical(binding.pk, current_kid(), version, issued, expires, digests))
    return {"binding_id": str(binding.pk), "kid": kid, "version": version, "issued_at": issued, "expires_at": expires,
            "entries": [{"digest": digest, "type": "nfc"} for digest in digests], "signature": signature}


def flag_for(binding, credential, decided, allowed):
    """Why a reported ALLOW looks wrong (L-A3), or None. A denial is never flagged: it opened nothing."""
    if not allowed:
        return None
    skew = timedelta(seconds=MAX_FUTURE_SECONDS)
    if credential is None or credential.created_at > decided + skew or (
            credential.disabled_at is not None and credential.disabled_at < decided - skew):
        return "digest_not_in_cache"
    issued = AdapterAccessCache.objects.filter(binding=binding).first()
    if issued is None:
        return "no_cache_issued"
    if decided > issued.expires_at + skew:
        return "cache_expired"
    return None


def reconcile(principal, body):
    """Write the adapter's offline decisions into the access log (idempotent by operation id).

    Bounds (L-A3): a decision from the future is refused (400); one older than ``DEFAULT_MAX_AGE`` (7 days)
    is not stored (``rejected``, code ``decided_too_old``). The receive time and every stored
    operation id go to the audit row; an ALLOW whose digest was not live in this space, with no cache ever issued, or
    after the last cache expired is stored AND audited as ``devices.adapter_offline_decision_flagged`` for staff review.
    """
    check(OFFLINE_BODY, body, label="offline decisions")
    now = timezone.now()
    oldest = now - timedelta(seconds=int(getattr(settings, "ADAPTER_OFFLINE_MAX_AGE_SECONDS", DEFAULT_MAX_AGE)))
    results, stored = [], []
    with transaction.atomic():
        device = adapter_device(principal, lock=True)
        for item in body["decisions"]:
            check(OFFLINE_DECISION, item, label="offline decision")
            binding = binding_for(device, item["binding_id"], "access.cache")
            decided = datetime.fromtimestamp(item["decided_at"], tz=dt_timezone.utc)
            if decided > now + timedelta(seconds=MAX_FUTURE_SECONDS):
                raise AdapterError("observed_in_future", "The decision time is in the future.")
            if decided < oldest:
                results.append({"operation_id": item["operation_id"], "result": "rejected", "code": "decided_too_old"})
                continue
            credential = AdapterCredential.objects.filter(
                makerspace_id=device.makerspace_id, kind="nfc", digest=item["digest"]).first() \
                if item.get("digest") else None
            reason = item.get("reason") if item.get("reason") in REASONS else (
                "ok" if item["allowed"] else "offline_denied")
            try:
                with transaction.atomic():
                    AdapterAccessLog.objects.create(
                        makerspace=device.makerspace, device=device, binding=binding,
                        member=credential.user if credential else None, credential_type="nfc",
                        allowed=item["allowed"], reason=reason[:48], offline=True,
                        operation_id=item["operation_id"], created_at=decided)
            except IntegrityError:
                results.append({"operation_id": item["operation_id"], "result": "duplicate"})
                continue
            flag = flag_for(binding, credential, decided, item["allowed"])
            if flag:
                audit_adapter(device.makerspace, device, "devices.adapter_offline_decision_flagged", meta={
                    "binding_id": str(binding.pk), "operation_id": item["operation_id"], "flag": flag,
                    "decided_at": item["decided_at"], "received_at": int(now.timestamp())})
            AdapterAccessCache.objects.filter(binding=binding).update(reconciled_at=now)
            stored.append(item["operation_id"])
            results.append({"operation_id": item["operation_id"], "result": "stored"})
        if stored:
            audit_adapter(device.makerspace, device, "devices.adapter_offline_decisions_reconciled", meta={
                "count": len(stored), "received_at": int(now.timestamp()), "operation_ids": stored})
    return {"results": results}


def status_for(binding):
    row = AdapterAccessCache.objects.filter(binding=binding).first()
    if row is None:
        return None
    return {"version": row.version, "entry_count": row.entry_count, "issued_at": row.issued_at,
            "expires_at": row.expires_at, "reconciled_at": row.reconciled_at}


__all__ = ["OFFLINE_SWITCH", "build", "reconcile", "status_for", "allowed_digests"]
