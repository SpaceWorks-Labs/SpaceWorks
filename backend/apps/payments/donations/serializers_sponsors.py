"""Staff shapes for sponsors, tiers, perks, sponsorship charges and event links."""

from django.utils.translation import gettext
from rest_framework import serializers
from apps.payments.money_fields import MoneyField

from apps.accounts.pii_presentation import PiiMaskingSerializerMixin

from .models import Sponsor, SponsorEventLink, SponsorPerk, SponsorshipCharge, SponsorTier


class TierSerializer(serializers.ModelSerializer):
    class Meta:
        model = SponsorTier
        fields = ("id", "name", "rank", "amount", "currency", "description", "created_at")
        read_only_fields = ("id", "currency", "created_at")


class PerkSerializer(serializers.ModelSerializer):
    tier = serializers.PrimaryKeyRelatedField(queryset=SponsorTier.objects.all(), required=False, allow_null=True)
    sponsor = serializers.PrimaryKeyRelatedField(queryset=Sponsor.objects.all(), required=False, allow_null=True)
    fulfilled_by_name = serializers.SerializerMethodField()

    class Meta:
        model = SponsorPerk
        fields = ("id", "tier", "sponsor", "source_perk", "description", "due_on", "fulfilled_at", "fulfilled_by",
                  "fulfilled_by_name", "note", "created_at")
        read_only_fields = ("id", "source_perk", "fulfilled_at", "fulfilled_by", "created_at")
        # The copied-once rule is a database constraint the service keeps; DRF's generated
        # unique-together check would demand `source_perk`, which callers never send.
        validators = []

    def get_fulfilled_by_name(self, obj) -> str:
        user = obj.fulfilled_by
        return (getattr(user, "display_name", "") or user.username) if user else ""


class SponsorSerializer(PiiMaskingSerializerMixin, serializers.ModelSerializer):
    tier = serializers.PrimaryKeyRelatedField(queryset=SponsorTier.objects.all(), required=False, allow_null=True)
    tier_name = serializers.CharField(source="tier.name", default="", read_only=True)
    logo_url = serializers.SerializerMethodField()
    perks_open = serializers.SerializerMethodField()

    class Meta:
        model = Sponsor
        fields = ("id", "name", "organization", "tier", "tier_name", "logo_url", "website_url", "blurb",
                  "contact_name", "contact_email", "contact_phone", "starts_on", "ends_on", "show_on_wall",
                  "perks_open", "created_at", "updated_at", "archived_at")
        read_only_fields = ("id", "logo_url", "created_at", "updated_at", "archived_at")

    def get_logo_url(self, obj) -> str:
        from apps.inventory.public_image_storage import public_url

        return public_url(obj.logo_key) if obj.logo_key else ""

    def get_perks_open(self, obj) -> int:
        return obj.perks.filter(fulfilled_at__isnull=True).count()

    def validate(self, data):
        start, end = data.get("starts_on"), data.get("ends_on")
        if start and end and end < start:
            raise serializers.ValidationError({"ends_on": gettext("A sponsorship must end after it starts.")})
        return data


class ChargeCreateSerializer(serializers.Serializer):
    amount = MoneyField(max_digits=13, decimal_places=3, min_value=1)
    description = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    # Hack-money G8: the payment may be for one event of this space, and earmarked for its prize pool.
    event_id = serializers.IntegerField(min_value=1, required=False, allow_null=True, default=None)
    earmark = serializers.ChoiceField(choices=("general", "prize_pool"), required=False, default="general",
                                      help_text="prize_pool needs event_id: the money funds that event's prizes.")

    def validate(self, attrs):
        if attrs["earmark"] == "prize_pool" and not attrs.get("event_id"):
            raise serializers.ValidationError({"event_id": gettext("Choose the event whose prize pool this funds.")})
        return attrs


class ChargeSerializer(serializers.ModelSerializer):
    payment_id = serializers.SerializerMethodField()
    payment_status = serializers.SerializerMethodField()

    class Meta:
        model = SponsorshipCharge
        fields = ("id", "sponsor", "amount", "currency", "description", "event", "earmark", "payment_id",
                  "payment_status", "created_at")

    def _payment(self, obj):
        from apps.payments.models import Payment

        return Payment.objects.filter(makerspace_id=obj.makerspace_id, subject_type="sponsorship",
                                      subject_id=obj.pk).first()

    def get_payment_id(self, obj) -> int | None:
        payment = self._payment(obj)
        return payment.pk if payment else None

    def get_payment_status(self, obj) -> str:
        payment = self._payment(obj)
        return payment.status if payment else ""


class EventLinkCreateSerializer(serializers.Serializer):
    event_sponsor = serializers.IntegerField()


class EventLinkSerializer(serializers.ModelSerializer):
    event_id = serializers.IntegerField(source="event_sponsor.event_id", read_only=True)
    event_title = serializers.CharField(source="event_sponsor.event.title", read_only=True)
    label = serializers.CharField(source="event_sponsor.label", read_only=True)

    class Meta:
        model = SponsorEventLink
        fields = ("id", "sponsor", "event_sponsor", "event_id", "event_title", "label", "created_at")


class EventSponsorChoiceSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    label = serializers.CharField()
    event_id = serializers.IntegerField()
    event_title = serializers.CharField()
    active = serializers.BooleanField()
    linked_sponsor_id = serializers.IntegerField(allow_null=True)


class FulfilSerializer(serializers.Serializer):
    fulfilled = serializers.BooleanField(default=True)
    note = serializers.CharField(required=False, allow_blank=True, max_length=300, default="")
