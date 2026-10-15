"""Event-owned purge; unrelated domain outboxes survive."""
from .module_purge_collectors_single_model import _counts, _delete


def events_delete(makerspace, cursor):
    from apps.events.models_broadcasts import EventBroadcast
    from apps.integrations.models import EmailLog
    # Remove only this domain's source outboxes, including deferred digest inputs.
    EmailLog.objects.filter(makerspace=makerspace, source_kind__in=["event_broadcast", "event_invitation"]).delete()
    broadcasts, broadcast_labels = _delete(EventBroadcast.objects.filter(makerspace=makerspace))
    from apps.events.models_website import EventPage
    pages, page_labels = _delete(EventPage.objects.filter(makerspace=makerspace))
    from apps.events.models import (
        Event, EventCategory, EventStaffGrant, EventStaffGrantInvite,
        EventAttendanceCertificate,
        EventCertificateArtwork, EventCertificateTemplateRevision,
        EventCheckInEvent,
        EventCollaborator,
        EventFeedbackResponse,
        EventFeedbackSurvey,
        EventRegistration,
        EventSeries,
        EventSeriesCollaborator,
        EventStationBinding,
        MemberCalendarFeed,
    )
    from apps.makerspaces.models import Station, StationCredential

    grants, grant_labels = _delete(EventStaffGrant.objects.filter(makerspace=makerspace))
    invites, invite_labels = _delete(EventStaffGrantInvite.objects.filter(makerspace=makerspace))
    feeds, feed_labels = _delete(
        MemberCalendarFeed.objects.filter(membership__makerspace=makerspace)
    )
    projected_collaborations, projected_collaboration_labels = _delete(
        EventCollaborator.objects.filter(
            source_series_collaboration__makerspace=makerspace
        ).exclude(event__makerspace=makerspace)
    )
    series_collaborations, series_collaboration_labels = _delete(
        EventSeriesCollaborator.objects.filter(makerspace=makerspace)
    )
    collaborations, collaboration_labels = _delete(
        EventCollaborator.objects.filter(makerspace=makerspace)
    )
    # Clearing activity provenance is the point. Payment routing is left intact in both places
    # holding it (`Payment.via_makerspace`, and the registration's `payment_via_makerspace` for
    # a charge raised later at promotion), so a receipt stays visible and a pending charge payable.
    provenance_cleared = EventRegistration.objects.filter(
        registered_via_makerspace=makerspace,
    ).exclude(event__makerspace=makerspace).update(registered_via_makerspace=None)
    station_ids = list(
        EventStationBinding.objects.select_for_update()
        .filter(event__makerspace=makerspace)
        .values_list("station_id", flat=True)
    )
    station_credentials, station_credential_labels = _delete(
        StationCredential.objects.filter(station_id__in=station_ids)
    )
    station_bindings, station_binding_labels = _delete(
        EventStationBinding.objects.filter(station_id__in=station_ids)
    )
    stations, station_labels = _delete(
        Station.objects.filter(pk__in=station_ids)
    )
    certificates, certificate_labels = _delete(
        EventAttendanceCertificate.objects.filter(
            registration__event__makerspace=makerspace
        )
    )
    revisions, revision_labels = _delete(
        EventCertificateTemplateRevision.objects.filter(event__makerspace=makerspace)
    )
    artwork, artwork_labels = _delete(
        EventCertificateArtwork.objects.filter(event__makerspace=makerspace)
    )
    responses, response_labels = _delete(
        EventFeedbackResponse.objects.filter(survey__event__makerspace=makerspace)
    )
    surveys, survey_labels = _delete(
        EventFeedbackSurvey.objects.filter(event__makerspace=makerspace)
    )
    checkins, checkin_labels = _delete(
        EventCheckInEvent.objects.filter(makerspace=makerspace)
    )
    registrations, registration_labels = _delete(
        EventRegistration.objects.filter(event__makerspace=makerspace)
    )
    events, event_labels = _delete(Event.objects.filter(makerspace=makerspace))
    series, series_labels = _delete(EventSeries.objects.filter(makerspace=makerspace))
    categories, category_labels = _delete(EventCategory.objects.filter(makerspace=makerspace))
    return _counts(
        model_labels=(
            page_labels | collaboration_labels | certificate_labels | response_labels
            | revision_labels | artwork_labels
            | survey_labels | checkin_labels | registration_labels | event_labels
            | projected_collaboration_labels | series_collaboration_labels | series_labels
            | feed_labels | station_credential_labels | station_binding_labels
            | station_labels | category_labels | grant_labels | invite_labels | broadcast_labels
        ),
        event_series_collaboration_projections=projected_collaborations,
        event_series_collaborations=series_collaborations,
        event_collaborations=collaborations,
        event_certificates=certificates,
        event_certificate_template_revisions=revisions,
        event_certificate_artwork=artwork,
        event_feedback_responses=responses,
        event_feedback_surveys=surveys,
        event_check_in_events=checkins,
        event_check_in_station_credentials=station_credentials,
        event_station_bindings=station_bindings,
        event_stations=stations,
        event_registration_provenance_cleared=provenance_cleared,
        event_registrations=registrations,
        events=events,
        event_series=series,
        event_categories=categories,
        event_calendar_feeds=feeds,
        event_staff_grants=grants,
        event_staff_grant_invites=invites,
        event_broadcasts=broadcasts,
        event_website_rows=pages,
    )


def events_public_images(makerspace):
    from apps.events.models import Event, EventSeries

    return [
        *Event.objects.filter(makerspace=makerspace).values_list("image_key", flat=True),
        *EventSeries.objects.filter(makerspace=makerspace).values_list("image_key", flat=True),
    ]


def events_private_keys(makerspace, add):
    from apps.events.models import EventAttendanceCertificate, EventCertificateArtwork
    from apps.events.models_website import EventPageAsset
    for key in EventPageAsset.objects.filter(page__makerspace=makerspace).values_list("object_key", flat=True):
        add(key)

    for key in EventAttendanceCertificate.objects.filter(
        registration__event__makerspace=makerspace
    ).values_list("object_key", flat=True):
        add(key)
    for key in EventCertificateArtwork.objects.filter(
        event__makerspace=makerspace
    ).values_list("object_key", flat=True):
        add(key)
        add(f"staging/{key}")


def events_private_key_sizes(makerspace):
    from apps.events.models import EventAttendanceCertificate, EventCertificateArtwork

    from apps.events.models_website import EventPageAsset

    sizes = {
        key: size
        for key, size in EventAttendanceCertificate.objects.filter(
            registration__event__makerspace=makerspace
        ).values_list("object_key", "size_bytes")
        if key
    }
    sizes.update({
        key: size for key, size in EventCertificateArtwork.objects.filter(
            event__makerspace=makerspace,
        ).values_list("object_key", "size_bytes") if key
    })
    sizes.update({
        key: size for key, size in EventPageAsset.objects.filter(
            page__makerspace=makerspace,
        ).values_list("object_key", "size_bytes") if key
    })
    return sizes
