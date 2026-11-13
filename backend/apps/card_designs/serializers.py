"""Card-engine serializers. A design document is validated by `layout.normalize_document`,
not field by field here; these shapes only carry it."""
from rest_framework import serializers

from .default_templates import LABELS as TEMPLATE_LABELS
from .models import CardDesign, CardDesignApproval, CardJob


class CardDesignApprovalSerializer(serializers.ModelSerializer):
    class Meta:
        model = CardDesignApproval
        fields = ("id", "revision", "decision", "note", "created_at", "decided_at")
        read_only_fields = fields


class CardDesignSerializer(serializers.ModelSerializer):
    plan_id = serializers.IntegerField(read_only=True, allow_null=True)
    title_id = serializers.IntegerField(read_only=True, allow_null=True)
    programme_id = serializers.IntegerField(read_only=True, allow_null=True)
    organization_id = serializers.IntegerField(read_only=True, allow_null=True)
    event_id = serializers.IntegerField(read_only=True, allow_null=True)
    ticket_type_id = serializers.IntegerField(read_only=True, allow_null=True)
    has_unpublished_changes = serializers.SerializerMethodField()
    pending_approval = serializers.SerializerMethodField()
    last_review = serializers.SerializerMethodField()
    needs_approval = serializers.SerializerMethodField()
    can_approve = serializers.SerializerMethodField()
    can_edit = serializers.SerializerMethodField()
    target_label = serializers.SerializerMethodField()
    answer_fields = serializers.SerializerMethodField(
        help_text="Answers this design may place as {{field:<key>}}: a programme's printed questions.")
    badge_format = serializers.SerializerMethodField(
        help_text="`badge_v1` while the design is edited in the badge designer (its layers are compiled); else null.")

    class Meta:
        model = CardDesign
        fields = ("id", "domain", "name", "plan_id", "title_id", "programme_id", "organization_id", "event_id",
                  "ticket_type_id", "target_label", "status", "document", "revision", "published_revision",
                  "published_at", "archived_at", "has_unpublished_changes", "pending_approval", "last_review", "needs_approval",
                  "can_approve", "can_edit", "answer_fields", "card_role", "badge_format",
                  "updated_at")
        read_only_fields = fields

    def _actor(self):
        request = self.context.get("request")
        return getattr(request, "user", None)

    def get_has_unpublished_changes(self, obj) -> bool:
        return obj.published_revision != obj.revision

    def get_pending_approval(self, obj) -> dict | None:
        row = obj.approvals.filter(decision="pending").first()
        return CardDesignApprovalSerializer(row).data if row else None

    def get_last_review(self, obj) -> dict | None:
        """The latest approval or send-back, so the editor sees the approver's note."""
        row = obj.approvals.filter(decision__in=("approved", "rejected")).first()
        return CardDesignApprovalSerializer(row).data if row else None

    def get_needs_approval(self, obj) -> bool:
        from .approval import needs_approval
        return needs_approval(self._actor(), obj)

    def get_can_approve(self, obj) -> bool:
        from .approval import can_approve
        return can_approve(self._actor(), obj)

    def get_can_edit(self, obj) -> bool:
        from .authority import can_edit
        actor = self._actor()
        return bool(actor and actor.is_authenticated and can_edit(actor, obj))

    def get_badge_format(self, obj) -> str | None:
        return "badge_v1" if isinstance(obj.document, dict) and obj.document.get("source") else None

    def get_answer_fields(self, obj) -> list[dict]:
        """Only questions the programme prints (front or back); hidden answers never reach a card."""
        if obj.domain != "id_programme" or not obj.programme_id:
            return []
        return [{"key": f"field:{row['key']}", "label": str(row.get("label") or row["key"])[:80]}
                for row in obj.programme.form_schema or ()
                if isinstance(row, dict) and row.get("key") and row.get("placement") in ("front", "back")]

    def get_target_label(self, obj) -> str:
        if obj.title_id:
            return f"Title: {obj.title.name}"
        if obj.plan_id:
            return f"Plan: {obj.plan.name}"
        if obj.ticket_type_id:
            return f"Ticket type: {obj.ticket_type.name}"
        if obj.event_id:
            return "This event"
        if obj.organization_id:
            return f"{obj.organization.name} library"
        if obj.programme_id:
            return obj.programme.name
        return "Space default"


class CardDesignCreateSerializer(serializers.Serializer):
    domain = serializers.ChoiceField(choices=CardDesign.Domain.choices, default="member_cards")
    plan_id = serializers.IntegerField(required=False, allow_null=True)
    title_id = serializers.IntegerField(required=False, allow_null=True)
    template = serializers.ChoiceField(choices=tuple(TEMPLATE_LABELS), required=False)
    theme = serializers.ChoiceField(choices=("light", "dark"), default="light")


class CardDesignSaveSerializer(serializers.Serializer):
    document = serializers.JSONField()
    revision = serializers.IntegerField(min_value=1)
    name = serializers.CharField(max_length=80, required=False, allow_blank=True)


class CardDesignDecisionSerializer(serializers.Serializer):
    note = serializers.CharField(max_length=300, required=False, allow_blank=True)


class CardDesignResetSerializer(serializers.Serializer):
    template = serializers.ChoiceField(choices=("classic", "bold", "minimal", "community", "student", "event_pass"))
    theme = serializers.ChoiceField(choices=("light", "dark"), default="light")


class CardDesignImportSerializer(serializers.Serializer):
    file = serializers.JSONField(help_text="The parsed design file: {kind, version, document}.")


class CardDesignImportResultSerializer(serializers.Serializer):
    design = CardDesignSerializer()
    notes = serializers.ListField(child=serializers.CharField())


class CardPreviewSerializer(serializers.Serializer):
    document = serializers.JSONField()
    side = serializers.ChoiceField(choices=("front", "back"), default="front")
    format = serializers.ChoiceField(choices=("png", "pdf"), default="png")
    long_names = serializers.BooleanField(default=False)
    holder_id = serializers.IntegerField(required=False, min_value=1,
                                         help_text="Preview as this real holder (see the design's holders list).")
    bleed_mm = serializers.FloatField(default=0, min_value=0, max_value=5,
                                      help_text="Print-ready: mirror bleed around the trim (0 = trim only).")
    crop_marks = serializers.BooleanField(default=False, help_text="Print-ready PDF: crop marks in a 7 mm slug.")
    dpi = serializers.ChoiceField(choices=(150, 300), default=150, help_text="PNG resolution.")


class CardTemplateSerializer(serializers.Serializer):
    key = serializers.CharField()
    label = serializers.CharField()
    theme = serializers.ChoiceField(choices=("light", "dark"))
    document = serializers.JSONField()


class CardAssetPresignSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=("background", "watermark", "image"))
    content_type = serializers.ChoiceField(choices=("image/png", "image/jpeg", "image/webp"))


class CardAssetSerializer(serializers.Serializer):
    asset_id = serializers.UUIDField()
    kind = serializers.CharField()
    width_px = serializers.IntegerField()
    height_px = serializers.IntegerField()
    mean_colour = serializers.CharField()
    ready = serializers.BooleanField()


class CardAssetFinalizeSerializer(serializers.Serializer):
    asset_id = serializers.UUIDField()


class CardJobSerializer(serializers.ModelSerializer):
    progress = serializers.SerializerMethodField()
    download_ready = serializers.SerializerMethodField()
    save_url = serializers.SerializerMethodField()

    class Meta:
        model = CardJob
        fields = ("id", "kind", "scope", "scope_id", "state", "total", "done", "failed", "progress", "error_code",
                  "download_ready", "result_expires_at", "save_url", "created_at", "started_at", "finished_at")
        read_only_fields = fields

    def get_progress(self, obj) -> int:
        return round(100 * (obj.done + obj.failed) / obj.total) if obj.total else 0

    def get_download_ready(self, obj) -> bool:
        return bool(obj.state == "succeeded" and obj.result_key)

    def get_save_url(self, obj) -> str:
        return (obj.params or {}).get("save_url", "") if obj.kind == "wallet_issue" else ""


EVENT_CARD_ROLES = ("attendee", "speaker", "mentor", "judge", "volunteer", "crew", "organiser")


class CardJobCreateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=("bulk_sheet", "bulk_per_person", "zip", "email"))
    card_ids = serializers.ListField(child=serializers.IntegerField(min_value=1), required=False, max_length=1000)
    status = serializers.ChoiceField(choices=("active", "all"), default="active")
    plan_id = serializers.IntegerField(required=False)
    expiring_within_days = serializers.IntegerField(required=False, min_value=1, max_value=90)
    roles = serializers.ListField(child=serializers.ChoiceField(choices=EVENT_CARD_ROLES), required=False,
                                  max_length=7, help_text="Event cards only: print these roles.")
    checked_in = serializers.BooleanField(required=False, allow_null=True, default=None,
                                          help_text="Event cards only: true = checked in, false = not yet.")
    status_set = serializers.ChoiceField(
        choices=("confirmed", "attendees_without_crew", "crew", "role", "checked_in", "not_checked_in", "all"),
        required=False, help_text="Event cards only (E-B2): a ready-made audience; combines with roles and checked_in.")
    filter = serializers.DictField(child=serializers.CharField(allow_blank=True), required=False,
                                   help_text="Member cards only: the member register filter (q, role, standing, plan, "
                                             "status, title, ...) instead of card_ids. Resolved server side in your "
                                             "scope and frozen when the job is queued.")
    paper = serializers.ChoiceField(choices=("a4", "letter", "per_card"), default="a4")
    order = serializers.ChoiceField(choices=("duplex", "fronts_then_backs"), default="duplex")
    crop_marks = serializers.BooleanField(default=True)


class CardJobLinkSerializer(serializers.Serializer):
    url = serializers.URLField()


class CardFontSerializer(serializers.Serializer):
    family = serializers.CharField()
    category = serializers.CharField()
    weights = serializers.ListField(child=serializers.IntegerField())
    scripts = serializers.ListField(child=serializers.CharField())
    bundled = serializers.BooleanField()
    state = serializers.CharField()


class CardFontPageSerializer(serializers.Serializer):
    count = serializers.IntegerField()
    results = CardFontSerializer(many=True)


class CardApprovalSettingSerializer(serializers.Serializer):
    membership_required = serializers.BooleanField()
    event_required = serializers.BooleanField()
