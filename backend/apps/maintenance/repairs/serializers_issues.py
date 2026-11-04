"""Issue payloads for staff, Technicians and reporters.

What each viewer sees about the REPORTER (Q-T2): a manager sees the name and email (to
relay with them; masked for a superadmin without a PII window); a Technician sees the
first name only; nobody else sees anyone. Contractors' contact details never appear on
an issue -- dispatch rows name the technician and the channel only.
"""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.accounts.pii_presentation import PiiMaskingSerializerMixin

from .models_issues import IssueReport
from .models_records import IssueEvent, IssuePhoto, RepairPart, TechnicianDispatch
from .notify import subject_label


def _manager(context, row):
    """Per row: the same person may manage one area and be a Technician in another."""
    from .authority import manages_issue
    cache = context.setdefault("_manages", {})
    if row.pk not in cache:
        actor = context.get("actor")
        cache[row.pk] = bool(actor is not None and manages_issue(actor, row))
    return cache[row.pk]


class IssueEventSerializer(serializers.ModelSerializer):
    actor_name = serializers.SerializerMethodField()
    contact_name = serializers.SerializerMethodField()

    class Meta:
        model = IssueEvent
        fields = ["id", "kind", "actor_name", "contact_name", "note", "occurred_on", "amount", "currency",
                  "created_at"]

    def get_actor_name(self, row) -> str:
        actor = row.actor
        return (actor.display_name or actor.first_name or "Staff") if actor else ""

    def get_contact_name(self, row) -> str:
        return row.contact.name if row.contact_id else ""


class IssuePhotoSerializer(serializers.ModelSerializer):
    url = serializers.SerializerMethodField()

    class Meta:
        model = IssuePhoto
        fields = ["id", "stage", "content_type", "size_bytes", "created_at", "url"]

    def get_url(self, row) -> str:
        from apps.evidence.storage import StorageUnavailable
        from . import storage
        try:
            return storage.signed_url(row.object_key)
        except StorageUnavailable:
            return ""


class TechnicianDispatchSerializer(serializers.ModelSerializer):
    contact_name = serializers.CharField(source="contact.name", read_only=True)

    class Meta:
        model = TechnicianDispatch
        fields = ["id", "contact_id", "contact_name", "channel", "status", "failure_code", "sent_at"]


class RepairPartSerializer(serializers.ModelSerializer):
    class Meta:
        model = RepairPart
        fields = ["id", "kind", "product_id", "name", "quantity", "to_buy_item_id", "created_at"]


class IssueAssignmentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    contact_id = serializers.IntegerField(allow_null=True)
    person_id = serializers.IntegerField(allow_null=True)
    name = serializers.CharField()


class IssueReportListSerializer(PiiMaskingSerializerMixin, serializers.ModelSerializer):
    subject_id = serializers.SerializerMethodField()
    subject_label = serializers.SerializerMethodField()
    reporter_name = serializers.SerializerMethodField()
    assignees = serializers.SerializerMethodField()

    class Meta:
        model = IssueReport
        fields = ["id", "area", "subject_type", "subject_id", "subject_label", "source", "title", "state",
                  "priority", "quote_state", "reporter_name", "assignees", "work_order_id", "created_at",
                  "updated_at", "fixed_at", "closed_at"]

    def get_subject_id(self, row) -> int:
        return row.machine_id or row.asset_id or row.product_id or row.room_id

    def get_subject_label(self, row) -> str:
        return subject_label(row)

    def get_reporter_name(self, row) -> str:
        name = row.reporter_name or ""
        if _manager(self.context, row):
            return name
        return name.split()[0] if name.split() else ""  # Q-T2: the first name only

    @extend_schema_field(IssueAssignmentSerializer(many=True))
    def get_assignees(self, row):
        return [{"id": item.pk, "contact_id": item.contact_id, "person_id": item.person_id,
                 "name": item.contact.name if item.contact_id else (item.person.display_name or item.person.username)}
                for item in row.assignments.all()]


class IssueReportDetailSerializer(IssueReportListSerializer):
    reporter_email = serializers.SerializerMethodField()
    events = IssueEventSerializer(many=True, read_only=True)
    photos = IssuePhotoSerializer(many=True, read_only=True)
    dispatches = TechnicianDispatchSerializer(many=True, read_only=True)
    parts = RepairPartSerializer(many=True, read_only=True)
    viewer_role = serializers.SerializerMethodField()
    default_contact_ids = serializers.SerializerMethodField()

    class Meta(IssueReportListSerializer.Meta):
        fields = [*IssueReportListSerializer.Meta.fields, "description", "resolution", "reporter_email", "quote_amount",
                  "quote_currency", "quote_note", "quote_contact_id", "payout_entry_id", "loan_id", "booking_id",
                  "machine_job_id", "reporter_notified_at", "events", "photos", "dispatches", "parts",
                  "viewer_role", "default_contact_ids"]

    def get_reporter_email(self, row) -> str:
        return row.reporter_email if _manager(self.context, row) else ""

    def get_viewer_role(self, row) -> str:
        return "manager" if _manager(self.context, row) else "technician"

    def get_default_contact_ids(self, row) -> list[int]:
        if not _manager(self.context, row):
            return []
        from .services_contacts import defaults_for
        return defaults_for(row)


class MemberIssueReportSerializer(serializers.ModelSerializer):
    subject_label = serializers.SerializerMethodField()

    class Meta:
        model = IssueReport
        fields = ["id", "area", "subject_label", "source", "title", "state", "created_at", "fixed_at"]

    def get_subject_label(self, row) -> str:
        return subject_label(row)


class IssueReportCreatedSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    state = serializers.CharField()
