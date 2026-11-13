"""Where an import's rows come from: an uploaded file or a public Google Sheet (L13).

Both importers -- the member import (L4, G18) and the ID-programme import (L3, SPEC
§5.2) -- keep their own parser, mapping, preview, de-duplication and apply. This module
only answers "which bytes?": the upload, or the CSV export of a public sheet fetched by
`import_sources_sheets`. Each sheet source sits behind its own capability, off by
default; while it is off a sheet request answers 404 and file uploads are unchanged.

The preview returns the fetched sheet's SHA-256. When the apply sends it back, a sheet
edited in between is refused with `sheet_changed`, so what is written is what staff saw.
"""
from django.utils.translation import gettext
from drf_spectacular.utils import OpenApiResponse
from rest_framework import serializers

from apps.admin_api import import_sources_sheets as sheets

MEMBER_SHEETS = "membership.import_sheets"
PROGRAMME_SHEETS = "membership.id_programmes_import_sheets"
# A 400 carries `sheet_url_invalid`, `sheet_not_public`, `sheet_too_large` or `sheet_changed`.
SHEET_ERRORS = {502: OpenApiResponse(description="`sheet_unreachable`: Google Sheets did not answer in time.")}


class ImportSourceSerializer(serializers.Serializer):
    """Mixed into an importer's request serializer; `upload_field` names its file field."""

    upload_field = "file"
    source = serializers.ChoiceField(
        choices=(sheets.SOURCE_FILE, sheets.SOURCE_SHEET), default=sheets.SOURCE_FILE,
        help_text="`file` (the upload) or `google_sheet` (a public sheet's link in `url`).")
    url = serializers.CharField(
        required=False, allow_blank=True, max_length=2048,
        help_text="With `google_sheet`: the sheet's share link. It must be shared as "
                  "“Anyone with the link can view”; SpaceWorks reads it once per request.")
    sheet_sha256 = serializers.RegexField(
        r"^[0-9a-f]{64}$", required=False,
        help_text="With `google_sheet` on apply: the `sheet_sha256` the preview returned. "
                  "A sheet changed since then is refused with `sheet_changed`.")

    def validate(self, attrs):
        attrs = super().validate(attrs)
        if attrs.get("source", sheets.SOURCE_FILE) == sheets.SOURCE_FILE and not attrs.get(self.upload_field):
            raise serializers.ValidationError({self.upload_field: gettext("Choose a file to import.")})
        return attrs


def read_source(validated, makerspace, capability, *, max_bytes, max_rows):
    """The fetched sheet for a `google_sheet` request, or None for a file upload."""
    if validated.get("source") != sheets.SOURCE_SHEET:
        return None
    from apps.makerspaces.guards import feature_off
    from apps.makerspaces.platform import feature_enabled
    if not feature_enabled(makerspace, capability):
        raise feature_off(capability)
    fetched = sheets.fetch_sheet(validated.get("url", ""), max_bytes=max_bytes, max_rows=max_rows)
    expected = validated.get("sheet_sha256")
    if expected and expected != fetched.sha256:
        raise sheets.SheetImportError("sheet_changed")
    return fetched


def source_of(fetched):
    return sheets.SOURCE_SHEET if fetched else sheets.SOURCE_FILE
