"""Selected-revision disclosure and private byte reads reauthorize every chunk."""
from datetime import timedelta
import json
from django.utils import timezone
from django.http import HttpResponse, StreamingHttpResponse
from apps.accounts import rbac
from apps.accounts.reauthentication import binding
from apps.events import event_authority
from apps.forms_schema.sensitive_policy import permitted_questions
from apps.makerspaces.private_upload_transport import ObjectLocator, resolve_range, stream_private, PrivateTransportError
from apps.payments.event_payouts.errors import require
from .upload_models import StageFormAsset
from .response_models import StageFormResponse
from .http import member_event


def reference_matches(asset, reference):
    return reference == {"asset_id": asset.pk, "generation": asset.generation, "sha256": asset.sha256}


def project_references(*, response, selected, question, references, owner=False, finance=False):
    result = []
    for asset in StageFormAsset.objects.filter(assignment=response.assignment, question_id=question["id"],
        form_revision_id=selected.form_revision_id if selected else response.form_revision_id,
        pk__in=[ref["asset_id"] for ref in references]):
        if not any(reference_matches(asset, ref) for ref in references):
            continue
        if owner:
            path = f"/api/v1/member/makerspaces/{response.event.makerspace_id}/events/{response.event_id}/stage-forms/{response.assignment.stage_form_id}/files/{asset.pk}/download/"
        else:
            path = f"/api/v1/admin/events/{response.event_id}/stage-files/{asset.pk}/download/?response_revision={selected.revision}"
        # Staff projections contain only an opaque authorized route, no raw IDs,
        # hashes, object locators or the user's original filename.
        result.append({"download_url": path, "mime": asset.canonical_mime, "bytes": asset.actual_bytes})
    return result


def authorize(request, *, event_id, asset_id, makerspace_id=None, stage_form_id=None, staff=False):
    from apps.makerspaces.guards import require_module
    from apps.tenant_migration.gate_runtime import assert_write_allowed
    from apps.presence.guard import require_active_principal
    asset = StageFormAsset.objects.select_related("event__makerspace", "assignment__stage_form").get(pk=asset_id, event_id=event_id)
    require_module(asset.event.makerspace, "events")
    assert_write_allowed(asset.event.makerspace_id)
    require_active_principal(request.user, asset.event.makerspace)
    if staff:
        binding(request)
        try:
            raw = request.query_params["response_revision"]
            require(raw.isascii() and raw.isdecimal() and len(raw) <= 10 and int(raw) > 0, "invalid_revision", status=400)
            revision = int(raw)
        except (KeyError, ValueError, TypeError):
            require(False, "selected_revision_required", status=400)
        response = StageFormResponse.objects.get(pk=asset.response_id, event_id=event_id, assignment_id=asset.assignment_id)
        selected = response.submitted_revisions.get(revision=revision)
        schema = selected.form_revision.schema
        live = response.assignment.stage_form.current_revision.schema
        question = next((q for q in schema["questions"] if q["id"] == asset.question_id), {})
        current = next((q for q in live["questions"] if q["id"] == asset.question_id), {})
        viewer = "finance" if question.get("sensitive") or current.get("sensitive") else "organizer"
        if viewer == "finance":
            require(rbac.can(request.user, rbac.Action.VIEW_FINANCE, asset.event.makerspace_id), "finance_required", status=403)
        else:
            event_authority.require(request.user, asset.event, "manage_registrations")
            require(rbac.can(request.user, rbac.Action.VIEW_AUDIT, asset.event.makerspace_id), "audit_required", status=403)
        allowed = {q["id"] for q in permitted_questions(schema, viewer=viewer, current_schema=live)}
        snapshot = json.loads(selected.answers_snapshot)
        require(asset.question_id in allowed and selected.form_revision_id == asset.form_revision_id and any(
            answer["id"] == asset.question_id and answer["type"] == "file" and any(reference_matches(asset, ref)
            for ref in answer["value"]) for answer in snapshot["answers"]), "not_found", status=404)
    else:
        member_event(request, event_id, makerspace_id)
        require(asset.owner_member_id == request.user.pk and asset.assignment.stage_form_id == stage_form_id, "not_found", status=404)
    require(asset.expired_at is None and (asset.expires_at is None or timezone.now() < asset.expires_at)
            and asset.state not in ("expired", "deleting", "deleted"), "stage_file_expired", status=410)
    require(asset.state in ("ready", "attached") and asset.scan_status in ("clean", "skipped"), "stage_file_unavailable")
    return asset


def download(request, **kwargs):
    from .storage import storage
    asset = authorize(request, **kwargs)
    try:
        byte_range = resolve_range(request.headers.get("Range"), asset.actual_bytes)
    except PrivateTransportError:
        response = HttpResponse(status=416)
        response["Content-Range"] = f"bytes */{asset.actual_bytes}"
        return response
    until = min(asset.expires_at or timezone.now() + timedelta(minutes=15), timezone.now() + timedelta(minutes=15))
    store = storage()
    stream = stream_private(locator=ObjectLocator(bucket=store.bucket, key=asset.object_key,
        version_id=asset.final_version_id or None), byte_range=byte_range, reader=store.read_range,
        authorize=lambda: authorize(request, **kwargs), clock=timezone.now, not_after=until)
    response = HttpResponse() if request.method == "HEAD" else StreamingHttpResponse(stream)
    response.status_code = 206 if byte_range.partial else 200
    response["Content-Type"] = asset.canonical_mime
    response["Content-Length"] = str(byte_range.length)
    response["Accept-Ranges"] = "bytes"
    if byte_range.partial:
        response["Content-Range"] = byte_range.content_range
    response["Content-Disposition"] = 'attachment; filename="stage-file"'
    response["Content-Security-Policy"] = "default-src 'none'; sandbox"
    return response
