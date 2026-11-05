"""Distinct OpenAPI component names for serializers whose class names collide.

drf-spectacular names a component after its serializer class, and when two different
classes share a name it keeps the first and points the second's operations at it, so
those operations silently document the wrong shape (the guard now fails on that).
Keyed on the EXACT class (`module.Class`), not inherited the way `Meta.ref_name` is,
so a base serializer's subclasses keep their own names.
"""

COMPONENT_NAMES = {
    "apps.events.contributions.serializers.AggregateSerializer": "EventRoleAggregate",
    "apps.event_reimbursements.serializers.Command": "ReimbursementCommand",
    "apps.events.hackathons.admission_inputs.CommandInput": "HackathonAdmissionCommandInput",
    "apps.events.hackathons.api_schema.CommentSerializer": "HackathonComment",
    "apps.events.hackathons.serializers_commands.CommentInput": "HackathonCommentInput",
    "apps.payments.event_payouts.serializers_snapshot.Decision": "PayoutDecision",
    "apps.events.contributions.serializers.ErrorSerializer": "EventRoleError",
    "apps.payments.event_payouts.serializers.ErrorSerializer": "PayoutError",
    "apps.events.programme.serializers.ErrorSerializer": "EventProgrammeError",
    "apps.procurement.serializers.ErrorSerializer": "ProcurementError",
    "apps.bookings.views_feed.FeedIssuedSerializer": "BookingFeedIssued",
    "apps.bookings.views_feed.FeedStateSerializer": "BookingFeedState",
    "apps.events.hackathons.api_schema_details.HostWaiverSerializer": "HackathonHostWaiver",
    "apps.id_programmes.serializers.ImportCommitSerializer": "IdProgrammeImportCommit",
    "apps.id_programmes.serializers.ImportPreviewSerializer": "IdProgrammeImportPreview",
    "apps.events.hackathons.api_schema.InviteSerializer": "HackathonInvite",
    "apps.events.hackathons.serializers_commands.InviteInput": "HackathonInviteInput",
    "apps.events.serializers_participation.PublicCrewSerializer": "EventPublicCrew",
    "apps.makerspaces.public_profile_serializers.PublicEventSerializer": "ProfilePublicEvent",
    "apps.makerspaces.public_profile_serializers.PublicProfileSerializer": "MakerProfile",
    "apps.operations.serializers_health.ReadinessSerializer": "HealthReadiness",
    "apps.accounts.views_mobile_readiness.ReadinessItemSerializer": "MobileReadinessItem",
    "apps.admin_api.serializers_roles.RoleSerializer": "MakerspaceRoleDefinition",
    "apps.events.views_short_links_admin.VisitDaySerializer": "ShortLinkVisitDay",
    "apps.operations.platform_insights.WindowSerializer": "PlatformInsightsWindow",
}
