"""Owner-only admission projection. Draft consent is never stamped evidence."""
import json
from apps.events.serializers_ticketing_public import EventTicketingPublicSerializer
from apps.events.serializers_public import PublicEventSerializer
from apps.events.host_waivers import has_current_host_consent
from apps.makerspaces.models import MakerspaceMembership, MakerspaceWaiver
from apps.makerspaces.platform import feature_enabled
from .admission_ports import ports


def admission_requirements(event, actor, *, request=None, registration=None):
    ticketing = EventTicketingPublicSerializer(event, context={"request": request}).data
    waiver = None
    if event.registration_audience == "participating_organizations":
        current = MakerspaceWaiver.objects.filter(makerspace_id=event.makerspace_id, is_active=True).first()
        if current:
            membership = MakerspaceMembership.objects.filter(makerspace_id=event.makerspace_id, user=actor, status="active").first()
            required = not has_current_host_consent(current, membership, registration)
            accepted_version = accepted_at = None
            if registration and registration.host_waiver_id == current.pk:
                accepted_version, accepted_at = registration.host_waiver_version_accepted, registration.host_waiver_accepted_at
            if not required and membership and accepted_at is None:
                accepted_version = current.version
                accepted_at = membership.waiver_accepted_at or membership.witnessed_at
            waiver = {"id": current.pk, "version": current.version, "body": current.body,
                      "acceptance_required": required, "accepted_version": accepted_version, "accepted_at": accepted_at}
    invites = feature_enabled(event.makerspace, "events.invites")
    return {
        "registration_audience": event.registration_audience,
        "ticket_selection_required": ticketing["ticket_selection_required"],
        "ticket_types": ticketing["ticket_types"],
        "currency": PublicEventSerializer().get_currency(event),
        "promo_codes_enabled": ticketing["promo_codes_enabled"],
        "invite_code_allowed": invites and event.registration_audience in ("invite", "participating_organizations"),
        "verified_email_invite_supported": invites and event.registration_audience in ("invite", "participating_organizations"),
        "contact_requirements": {"email": {"fallback_required": not bool(actor.email)},
                                 "phone": {"fallback_required": not bool(actor.phone)}},
        "host_waiver": waiver,
    }


def owner_admission_projection(application, *, actor):
    if application.member_id != actor.pk:
        from .admission_errors import fail
        fail("not_found", "Not found.", status=404)
    registration = application.registration
    draft = json.loads(application.admission_draft)
    if registration is None:
        return {"ticket_type_id": draft.get("ticket_type_id"),
                "contact": {"name": actor.display_name or actor.get_full_name() or actor.username,
                            "email": actor.email or draft.get("email", ""), "phone": actor.phone or draft.get("phone", "")},
                "quote": None, "invite_applied": False, "promo_applied": False,
                "host_waiver_acceptance": None}
    return {"ticket_type_id": registration.ticket_type_id,
            "contact": {"name": registration.name, "email": registration.email, "phone": registration.phone},
            "quote": {"amount": str(registration.quoted_amount),
                      "discount_amount": str(registration.discount_amount),
                      "currency": PublicEventSerializer().get_currency(application.event)},
            "invite_applied": bool(registration.invite_id), "promo_applied": bool(registration.promo_code_id),
            "host_waiver_acceptance": ({"id": registration.host_waiver_id,
                "version": registration.host_waiver_version_accepted,
                "accepted_at": registration.host_waiver_accepted_at} if registration.host_waiver_id else None)}


def allowed_actions(application):
    if application is None or application.state == "draft":
        return ["edit", "submit"]
    if application.state == "offered":
        return ["rsvp", "withdraw"]
    if application.state in ("submitted", "waitlisted", "confirmed"):
        return (["edit"] if application.state == "submitted" and not application.answer_locked_at else []) + ["withdraw"]
    return ["edit"] if application.state in ("rejected", "declined", "expired", "withdrawn") else []


def project_owner(application, *, event, actor, form, coc=None, request=None):
    if application is None:
        return {"id": None, "event_id": event.pk, "version": 0, "state": "draft", "registration_id": None,
                "allowed_actions": ["edit", "submit"], "form": form, "answers": [], "coc": coc,
                "admission_requirements": admission_requirements(event, actor, request=request),
                "admission": {"ticket_type_id": None, "contact": {"name": actor.display_name or actor.get_full_name() or actor.username,
                              "email": actor.email or "", "phone": actor.phone or ""},
                              "quote": None, "invite_applied": False, "promo_applied": False, "host_waiver_acceptance": None},
                "save_intent": None, "optional_consent_purposes": ["mlh_data_sharing"] if event.hackathon_config.optional_mlh_schema else []}
    if application.member_id != actor.pk or application.event_id != event.pk:
        from .admission_errors import fail
        fail("not_found", "Not found.", status=404)
    snapshot = json.loads(application.answers_snapshot)
    projected = ports().forms.project_owner(application=application, snapshot=snapshot)
    from .admission_ports import OwnerAnswers
    if not isinstance(projected, OwnerAnswers):
        raise RuntimeError("The owner-answer adapter must supply typed review metadata.")
    requirements = admission_requirements(event, actor, request=request, registration=application.registration)
    actions = allowed_actions(application)
    if application.date_review_required:
        actions.append("date_review")
    if requirements["host_waiver"] and requirements["host_waiver"]["acceptance_required"] and application.state in ("submitted", "offered", "waitlisted", "confirmed"):
        actions.append("repair_host_consent")
    return {"id": application.pk, "event_id": event.pk, "version": application.version,
            "state": application.state, "registration_id": application.registration_id,
            "allowed_actions": actions, "form": form, "answers": projected.answers,
            "answer_review": projected.answer_review, "omitted_question_ids": list(projected.omitted_question_ids),
            "optional_consent_purposes": ["mlh_data_sharing"] if event.hackathon_config.optional_mlh_schema else [],
            "optional_consents": application.optional_consents,
            "rsvp_due_at": application.rsvp_due_at, "rsvp_accepted_at": application.rsvp_accepted_at,
            "coc": coc,
            "admission_requirements": requirements,
            "admission": owner_admission_projection(application, actor=actor),
            "save_intent": ports().forms.project_intent(application=application)}
