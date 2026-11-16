"""Shared, PII-free ETA and machine-summary shapes for every machine-service surface."""

from rest_framework import serializers

from apps.machines.service_queue_eta_core import ESTIMATED, REASONS, ROUGH, UNAVAILABLE

CONFIDENCE_CHOICES = (ESTIMATED, ROUGH, UNAVAILABLE)


class ServiceRequestEtaSerializer(serializers.Serializer):
    """A derived forecast, never a promise: continuous processing time, staff permitting.

    ``unavailable`` always carries null timestamps and minutes; counts and reasons stay.
    """

    calculated_at = serializers.DateTimeField()
    estimated_start_at = serializers.DateTimeField(allow_null=True)
    estimated_finish_at = serializers.DateTimeField(allow_null=True)
    start_in_minutes = serializers.IntegerField(min_value=0, allow_null=True)
    finish_in_minutes = serializers.IntegerField(min_value=0, allow_null=True)
    confidence = serializers.ChoiceField(choices=CONFIDENCE_CHOICES)
    reasons = serializers.ListField(child=serializers.ChoiceField(choices=REASONS))
    approved_ahead = serializers.IntegerField(min_value=0)
    awaiting_review_ahead = serializers.IntegerField(min_value=0)
    active_machine_count = serializers.IntegerField(min_value=0)
    missing_estimate_count = serializers.IntegerField(min_value=0)


class MachineQueueSummarySerializer(serializers.Serializer):
    """Per-machine workload: approved/running jobs and the machine's final free-at offset."""

    length = serializers.IntegerField(min_value=0)
    eta_minutes = serializers.IntegerField(min_value=0, allow_null=True)
    estimated_clear_at = serializers.DateTimeField(allow_null=True)
    calculated_at = serializers.DateTimeField()
    confidence = serializers.ChoiceField(choices=CONFIDENCE_CHOICES)
    reasons = serializers.ListField(child=serializers.ChoiceField(choices=REASONS))


def eta_for(serializer, row):
    """Serializer helper: read the response's batched snapshot from context, never query."""
    snapshot = serializer.context.get("queue_snapshot")
    payload = snapshot.eta(row) if snapshot is not None else None
    return ServiceRequestEtaSerializer(payload).data if payload is not None else None


def counts_for(serializer, row):
    snapshot = serializer.context.get("queue_snapshot")
    return snapshot.counts(row) if snapshot is not None else None
