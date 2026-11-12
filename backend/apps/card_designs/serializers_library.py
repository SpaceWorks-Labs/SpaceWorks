"""OpenAPI shapes for the artwork library and the brand kit (decision 344(b))."""
from rest_framework import serializers


class CardLibraryAssetSerializer(serializers.Serializer):
    asset_id = serializers.UUIDField()
    kind = serializers.ChoiceField(choices=("background", "watermark", "image"))
    width_px = serializers.IntegerField()
    height_px = serializers.IntegerField()
    mean_colour = serializers.CharField(allow_blank=True)
    size_bytes = serializers.IntegerField()
    created_at = serializers.DateTimeField()


class CardBrandColourSerializer(serializers.Serializer):
    label = serializers.CharField()
    hex = serializers.RegexField(r"^#[0-9A-F]{6}$")


class CardBrandLogoSerializer(serializers.Serializer):
    source = serializers.ChoiceField(choices=("space", "organisation", "event", "symbol"))
    label = serializers.CharField()


class CardBrandKitSerializer(serializers.Serializer):
    colours = CardBrandColourSerializer(many=True)
    logos = CardBrandLogoSerializer(many=True)
    fonts = serializers.ListField(child=serializers.CharField(), help_text="The Card Studio font allow-list.")


class CardCsvMergeSerializer(serializers.Serializer):
    csv = serializers.CharField(trim_whitespace=False, max_length=256 * 1024,
                                help_text="CSV text: a header row of data tags (name, role, number, valid_until, "
                                          "field:<key> ...), then up to 200 rows.")
    dry_run = serializers.BooleanField(default=True, help_text="Check the file and preview the first rows; no PDF.")
    paper = serializers.ChoiceField(choices=("a4", "letter", "per_card"), default="a4")
    order = serializers.ChoiceField(choices=("duplex", "fronts_then_backs"), default="duplex")
    crop_marks = serializers.BooleanField(default=True)


class CardCsvMergeReportSerializer(serializers.Serializer):
    columns = serializers.ListField(child=serializers.CharField(), help_text="Columns that fill a data tag.")
    unknown_columns = serializers.ListField(child=serializers.CharField(), help_text="Ignored columns.")
    rows = serializers.IntegerField()
    preview = serializers.ListField(child=serializers.DictField(child=serializers.CharField(allow_blank=True)))
    published = serializers.BooleanField(help_text="False: publish the design before printing.")
    images = serializers.ListField(child=serializers.CharField(), help_text="The first cards drawn from the PUBLISHED "
                                   "version (PNG data URIs, front), exactly as the PDF prints them; empty if unpublished.")


class CardBarcodeRequestSerializer(serializers.Serializer):
    symbology = serializers.ChoiceField(choices=("code128", "code39", "ean13", "upca", "pdf417", "datamatrix", "aztec"))
    value = serializers.CharField(max_length=80, trim_whitespace=False,
                                  help_text="What the designer previews (a sample card number or a placeholder desk code).")


class CardBarcodeSerializer(serializers.Serializer):
    symbology = serializers.CharField()
    kind = serializers.ChoiceField(choices=("linear", "matrix"))
    bars = serializers.CharField(required=False, help_text="Linear: modules, 1 = dark.")
    quiet = serializers.ListField(child=serializers.IntegerField(), required=False, help_text="Linear: quiet modules left, right.")
    text = serializers.CharField(required=False, help_text="Linear: the human-readable line.")
    rows = serializers.ListField(child=serializers.CharField(), required=False, help_text="Matrix: rows of 0/1, quiet zone included.")
