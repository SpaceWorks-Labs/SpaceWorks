"""Request and response shapes of the account-merge API (U-C; U-B renders the flow)."""

from rest_framework import serializers

from apps.accounts.account_merge_eligibility import ERROR_CODES
from apps.accounts.models_account_merge import AccountMergeIntent
from apps.accounts.passkeys.serializers import PasskeyVerifyRequestSerializer

METHODS = AccountMergeIntent.Method.choices


class MergeStartRequestSerializer(serializers.Serializer):
    identifier = serializers.CharField(max_length=254, trim_whitespace=True,
                                       help_text="The other account's username, email or held email.")
    method = serializers.ChoiceField(choices=METHODS)


class MergeIntentSerializer(serializers.Serializer):
    intent_id = serializers.UUIDField(source="pk")
    method = serializers.ChoiceField(choices=METHODS)
    state = serializers.ChoiceField(choices=AccountMergeIntent.State.choices)
    expires_at = serializers.DateTimeField()


class MergeProveRequestSerializer(serializers.Serializer):
    password = serializers.CharField(required=False, allow_blank=True, max_length=4096, trim_whitespace=False,
                                     help_text="credentials: the other account's password.")
    otp = serializers.CharField(required=False, allow_blank=True, max_length=64,
                                help_text="credentials: a code from the other account's authenticator, or one of "
                                          "its recovery codes. Or send `passkey` instead.")
    passkey = PasskeyVerifyRequestSerializer(
        required=False, help_text="credentials: the other account's passkey answering the ceremony from "
                                  "`passkey-options`, sent with the same password instead of `otp`.")
    survivor_code = serializers.CharField(required=False, allow_blank=True, max_length=16,
                                          help_text="email_codes: the code sent to this account's email.")
    source_code = serializers.CharField(required=False, allow_blank=True, max_length=16,
                                        help_text="email_codes: the code sent to the other account's email.")


class MergePasskeyOptionsRequestSerializer(serializers.Serializer):
    password = serializers.CharField(max_length=4096, trim_whitespace=False,
                                     help_text="The other account's password; its passkeys are offered only after it matches.")


class _Makerspace(serializers.Serializer):
    id = serializers.IntegerField()
    slug = serializers.CharField()
    name = serializers.CharField()


class _RoleEntry(serializers.Serializer):
    makerspace = _Makerspace()
    roles = serializers.ListField(child=serializers.CharField())


class _PrivilegeDiff(serializers.Serializer):
    roles_gained = _RoleEntry(many=True, help_text="Staff roles this account gains, per makerspace.")
    duplicate_staff_rows = _RoleEntry(many=True, help_text="Spaces where both accounts are staff: this account's "
                                                           "roles win; the other account's stay behind, revoked.")


class _Rows(serializers.Serializer):
    rows = serializers.IntegerField()


class _UniqueRows(_Rows):
    kept_on_shell = serializers.IntegerField()


class _Moves(serializers.Serializer):
    repoint = _Rows(help_text="Records that move to this account.")
    keep_on_shell = _Rows(help_text="History that stays on the linked account's id (still shown as yours).")
    unique_resolve = _UniqueRows(help_text="One-per-person records: they move unless this account already has one.")


class _Conflict(serializers.Serializer):
    model = serializers.CharField()
    field = serializers.CharField()
    kept_on_shell = serializers.IntegerField()


class _Source(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    display_name = serializers.CharField()


class MergePreviewSerializer(serializers.Serializer):
    source = _Source()
    privilege_diff = _PrivilegeDiff()
    grace_opens = serializers.BooleanField(help_text="This account becomes staff without a second factor: a "
                                                     "3-day grace to enrol starts at confirm (#128 C-1).")
    moves = _Moves()
    conflicts = _Conflict(many=True)
    preview_sha256 = serializers.CharField(help_text="Send back to confirm exactly what you reviewed.")
    expires_at = serializers.DateTimeField()


class MergeConfirmRequestSerializer(serializers.Serializer):
    preview_sha256 = serializers.CharField(max_length=64, min_length=64)


class _Counts(serializers.Serializer):
    repointed = serializers.IntegerField()
    kept_on_shell = serializers.IntegerField()
    unique_moved = serializers.IntegerField()
    unique_kept = serializers.IntegerField()
    revoked = serializers.IntegerField()


class MergeConfirmResponseSerializer(serializers.Serializer):
    merged = serializers.BooleanField()
    record_id = serializers.UUIDField()
    roles_gained = _RoleEntry(many=True)
    grace_opened = serializers.BooleanField()
    counts = _Counts()


class MergeErrorSerializer(serializers.Serializer):
    code = serializers.ChoiceField(choices=[*ERROR_CODES, "recent_reauth_required"])
    detail = serializers.CharField()
