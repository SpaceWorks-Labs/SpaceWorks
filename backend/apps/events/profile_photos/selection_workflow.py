import hashlib
import json

from django.utils import timezone
from rest_framework.exceptions import NotFound

from apps.audit.services import record
from apps.events.credentials.boundary import event_command
from apps.events.credentials.errors import ProgrammeConflict
from apps.makerspaces.models_profiles import MemberProfile, PublicHandle
from apps.makerspaces.public_profile_access import profile_is_public
from apps.makerspaces.models import MakerspaceMembership

from .models import EventMemberCard, EventMemberPresentation, EventPresentationCommand
from .policy import require_owner_event, source_live


def source_revision(profile):
    return profile.updated_at.isoformat().replace("+00:00", "Z")


def project_owner(row):
    return {"id": row.pk if row else None, "version": row.version if row else 0,
            "profile_id": row.selected_profile_id if row else None,
            "membership_id": row.selected_membership_id if row else None,
            "source_revision": row.source_revision if row and row.source_revision else None,
            "print_photo_consent": row.print_photo_consent if row else False,
            "public_card_consent": row.public_card_consent if row else False,
            "public_card_scopes": row.public_card_scopes if row else []}


def options(event, actor):
    require_owner_event(event, actor)
    rows = MemberProfile.objects.filter(membership__user=actor).select_related(
        "membership__user", "membership__makerspace",
    ).order_by("membership_id")
    result = [{"membership_id": profile.membership_id, "profile_id": profile.pk,
               "makerspace_name": profile.membership.makerspace.name,
               "has_photo": bool(profile.avatar_key), "source_revision": source_revision(profile),
               "public_eligible": bool(profile_is_public(profile) and PublicHandle.objects.filter(
                   profile=profile, user=actor).exists())}
              for profile in rows if source_live(profile, actor.pk)]
    selected = EventMemberPresentation.objects.filter(event=event, member=actor).first()
    return {"selected_profile_id": selected.selected_profile_id if selected else None,
            "options": result, "no_photo_allowed": True}


def select(event_id, *, actor, operation_id, expected_version, profile_id, membership_id,
           source_revision: str | None, print_photo_consent=False,
           public_card_consent=False, public_card_scopes=()):
    from .serializers import PresentationWriteSerializer

    raw = dict(operation_id=str(operation_id), expected_version=expected_version, profile_id=profile_id,
               membership_id=membership_id, source_revision=source_revision,
               print_photo_consent=print_photo_consent, public_card_consent=public_card_consent,
               public_card_scopes=list(public_card_scopes))
    serializer = PresentationWriteSerializer(data=raw)
    serializer.is_valid(raise_exception=True)
    from apps.events.models_event import Event
    require_owner_event(Event.objects.select_related("makerspace").get(pk=event_id), actor)
    if profile_id is not None and not MemberProfile.objects.filter(
            pk=profile_id, membership_id=membership_id, membership__user=actor).exists():
        raise NotFound()
    digest = hashlib.sha256(json.dumps(raw, sort_keys=True).encode()).hexdigest()
    # Discover source tenants unlocked, then re-read/validate after fences/event lock.
    previous = EventMemberPresentation.objects.filter(event_id=event_id, member=actor).first()
    profile_ids = {pk for pk in (profile_id, previous.selected_profile_id if previous else None) if pk}
    sources = tuple(MemberProfile.objects.filter(pk__in=profile_ids).order_by("pk").values_list(
        "pk", "membership_id", "membership__makerspace_id", "membership__user_id"))
    tenant_ids = tuple(source[2] for source in sources)
    previous_selection = (previous.selected_profile_id, previous.selected_membership_id) if previous else (None, None)

    def revalidate(event):
        actual = tuple(MemberProfile.objects.filter(pk__in=profile_ids).order_by("pk").values_list(
            "pk", "membership_id", "membership__makerspace_id", "membership__user_id"))
        current = EventMemberPresentation.objects.filter(event=event, member=actor).first()
        selection = (current.selected_profile_id, current.selected_membership_id) if current else (None, None)
        if actual != sources or selection != previous_selection:
            raise ProgrammeConflict("Photo selection changed. Reload the choices.", code="photo_source_changed")

    with event_command(event_id, tenant_ids=tenant_ids, account_ids=(actor.pk,), revalidate=revalidate) as (event, _):
        from apps.accounts.models import User
        actor = User.objects.get(pk=actor.pk)
        require_owner_event(event, actor)
        # Programme fences admit erased accounts so retained history can be read; a new
        # owner selection is not history. Checked under the held shared account lock.
        from apps.encryption.account_models import PiiAccountWriteFence
        from apps.encryption.account_write_fence import AccountKeyChanged
        if PiiAccountWriteFence.objects.filter(user_id=actor.pk, state=PiiAccountWriteFence.State.ERASED).exists():
            raise AccountKeyChanged("Account key changed.")
        # Lock source parents before profile/selection children. Deletion takes these
        # same rows, so SET_NULL cannot interleave with a newly selected profile.
        list(MakerspaceMembership.objects.select_for_update().filter(
            pk__in=[source[1] for source in sources]).order_by("pk"))
        list(MemberProfile.objects.select_for_update().filter(pk__in=profile_ids).order_by("pk"))
        revalidate(event)
        row, _created = EventMemberPresentation.objects.get_or_create(event=event, member=actor)
        row = EventMemberPresentation.objects.select_for_update().get(pk=row.pk)
        receipt = EventPresentationCommand.objects.filter(presentation=row, operation_id=operation_id).first()
        if receipt:
            if receipt.request_sha256 != digest:
                raise ProgrammeConflict("Operation ID was already used.", code="operation_conflict")
            return receipt.result
        if row.version != expected_version:
            raise ProgrammeConflict()
        profile = None
        if profile_id is not None:
            profile = MemberProfile.objects.filter(
                pk=profile_id, membership_id=membership_id, membership__user=actor,
            ).first()
            if not profile or not source_live(profile, actor.pk):
                raise NotFound()
            if profile.updated_at.isoformat().replace("+00:00", "Z") != source_revision:
                raise ProgrammeConflict("Your profile changed. Reload the choices.", code="photo_source_changed")
        changed = row.selected_profile_id != profile_id
        if changed and row.selected_profile_id and (print_photo_consent or public_card_consent):
            raise ProgrammeConflict("Select the new profile first, then confirm its consent choices.",
                                    code="photo_selection_changed")
        row.selected_profile, row.selected_membership_id = profile, membership_id
        row.source_revision = source_revision or ""
        row.print_photo_consent = print_photo_consent
        row.public_card_consent = public_card_consent
        row.public_card_scopes = sorted(public_card_scopes)
        row.version += 1
        row.consent_revision += 1
        row.consented_at = timezone.now() if print_photo_consent or public_card_consent else None
        row.revoked_at = None if row.consented_at else timezone.now()
        row.full_clean()
        row.save()
        for scope in row.public_card_scopes:
            EventMemberCard.objects.get_or_create(presentation=row, scope=scope)
        record(actor, "event.presentation_updated", makerspace=event.makerspace, target=row,
               meta={"version": row.version, "consent_revision": row.consent_revision,
                     "print_photo_consent": row.print_photo_consent,
                     "public_card_consent": row.public_card_consent, "scopes": row.public_card_scopes})
        result = project_owner(row)
        EventPresentationCommand.objects.create(presentation=row, operation_id=operation_id,
                                                request_sha256=digest, result=result)
        return result
