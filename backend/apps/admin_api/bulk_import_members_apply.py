"""Member import, part 2: writing the planned rows (G18, #128 C-13).

Runs under `membership.import` and `manage_members`, one transaction for the whole file
(a refused row never half-applies the batch). For each planned row:

* `create` -> an `ImportedMember`. Unless the row or staff marked it "record only", an
  invitation (`MembershipRequest`, kind INVITE, NO user) is created and emailed to the
  row's address. Nothing links to an account until that person signs in with the
  verified email and accepts (`membership_import_accept`).
* `update` -> refreshes the pending row's details (never its email or status).
* `skip`   -> reported with its reason.

Audited once as `membership.imported` with counts, the batch id and the source kind
(`file` or `google_sheet`, never the sheet's link) -- never row data.
"""
from django.db import transaction

from apps.admin_api.bulk_import_members import existing_state, plan_rows
from apps.audit import services as audit
from apps.makerspaces.membership_features import require_membership_feature_locked
from apps.makerspaces.models import ImportedMember, MembershipImportBatch, MembershipRequest

DETAIL_FIELDS = ("name", "phone", "state_code", "gstin")


def _invite(actor, space, imported, role):
    from apps.makerspaces.notifications_p2_members import notify_invitation
    if MembershipRequest.objects.filter(makerspace=space, invite_email=imported.email,
                                        state__in=("requested", "invited", "awaiting_vouches", "awaiting_payment", "changes_requested")).exists():
        return False
    request = MembershipRequest.objects.create(
        makerspace=space, user=None, invite_email=imported.email, kind=MembershipRequest.Kind.INVITE,
        state=MembershipRequest.State.INVITED, invited_by=actor, assigned_role=role)
    imported.invitation = request
    imported.save()
    audit.record(actor, "membership.invited", makerspace=space, target=request,
                 meta={"role_id": role.pk, "source": "import", "imported_member_id": imported.pk})
    notify_invitation(request)
    return True


def _fill(imported, data, plans):
    for name in DETAIL_FIELDS:
        setattr(imported, name, data[name])
    imported.staff_notes = data["notes"]
    imported.external_number = data["member_number"]
    imported.plan = plans.get(data["plan"].lower()) if data["plan"] else None
    imported.starts_on, imported.ends_on = data["starts_on"], data["ends_on"]


def apply_members(actor, makerspace, raw_rows, mapping, *, record_only_rows=(), skip_rows=(),
                  file_name="", file_kind="csv", source="file", unit_id=None, verify=False):
    from apps.makerspaces.membership_helpers import _member_role
    record_only_rows, skip_rows = set(record_only_rows), set(skip_rows)
    with transaction.atomic():
        from apps.tenant_migration.gate_runtime import assert_write_allowed
        assert_write_allowed(makerspace.pk)
        space = require_membership_feature_locked(makerspace.pk, "import")
        from apps.admin_api.bulk_import_members_units import attach_unit, resolve_import_unit
        unit = resolve_import_unit(actor, space, unit_id, verify)  # parity O-B1; None without a unit
        state = existing_state(space)
        planned = plan_rows(space, raw_rows, mapping, existing=state)
        role = _member_role(space)
        batch = MembershipImportBatch.objects.create(makerspace=space, file_name=file_name[:200],
                                                     file_kind=file_kind, created_by=actor)
        totals = {"created": 0, "updated": 0, "skipped": 0, "invited": 0, "record_only": 0}
        results = []
        for item in planned:
            data, action, reason = item["data"], item["action"], item["reason"]
            if action != "skip" and item["row"] in skip_rows:
                action, reason = "skip", "skipped_by_staff"
            status = ""
            if action == "create":
                record_only = data["record_only"] or item["row"] in record_only_rows or (unit is not None and verify)
                imported = ImportedMember(makerspace=space, batch=batch, email=data["email"], created_by=actor,
                                          status=ImportedMember.Status.RECORD_ONLY if record_only
                                          else ImportedMember.Status.INVITED)
                _fill(imported, data, state["plans"])
                imported.save()
                if not record_only and not _invite(actor, space, imported, role):
                    imported.status = ImportedMember.Status.RECORD_ONLY
                    imported.save()
                    reason = "open_request_exists"
                if unit is not None:
                    attach_unit(imported, unit, verify)
                status = imported.status
                totals["created"] += 1
                totals["record_only" if status == ImportedMember.Status.RECORD_ONLY else "invited"] += 1
            elif action == "update":
                imported = ImportedMember.objects.select_for_update().get(pk=state["pending"][data["email"]].pk)
                _fill(imported, data, state["plans"])
                imported.save()
                status = imported.status
                totals["updated"] += 1
            else:
                totals["skipped"] += 1
            results.append({"row": item["row"], "action": action, "reason": reason, "status": status,
                            "email": data["email"]})
        batch.counts = totals
        batch.save(update_fields=["counts"])
        audit.record(actor, "membership.imported", makerspace=space, target=batch,
                     meta={"batch_id": batch.pk, "created": totals["created"], "updated": totals["updated"],
                           "skipped": totals["skipped"], "invited": totals["invited"],
                           "record_only": totals["record_only"], "source": source})
    return batch, results
