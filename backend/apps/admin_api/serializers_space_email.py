"""Sender name, Reply-To and SMTP-test state on the makerspace settings payload (parity E-B8)."""

from rest_framework import serializers


class SpaceEmailSenderFields(serializers.Serializer):
    smtp_verified = serializers.SerializerMethodField(
        help_text="True once a test message through the space's own SMTP account was accepted with the CURRENT "
                  "settings; editing any SMTP setting makes it false until the test passes again.")

    def get_smtp_verified(self, obj) -> bool:
        from apps.integrations.space_smtp_gate import smtp_verified
        return smtp_verified(obj)
