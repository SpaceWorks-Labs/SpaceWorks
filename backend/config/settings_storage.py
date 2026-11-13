"""Storage, uploads and evidence retention."""

from config.settings_runtime import ImproperlyConfigured, assert_distinct_storage_buckets, env

AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default="")
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default="")
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="evidence")
AWS_S3_ENDPOINT_URL = env("AWS_S3_ENDPOINT_URL", default="http://localhost:9000")
AWS_S3_PUBLIC_ENDPOINT_URL = env(
    "AWS_S3_PUBLIC_ENDPOINT_URL",
    default=AWS_S3_ENDPOINT_URL,
)
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="us-east-1")
AWS_S3_ADDRESSING_STYLE = "path"
AWS_S3_SIGNATURE_VERSION = "s3v4"
AWS_DEFAULT_ACL = None
AWS_QUERYSTRING_AUTH = True

STORAGES = {
    "default": {"BACKEND": "storages.backends.s3boto3.S3Boto3Storage"},
    # Match prior behavior: plain static storage (whitenoise serves it via middleware).
    # Manifest storage would require collectstatic before runserver, breaking host dev.
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}

EVIDENCE_URL_TTL_SECONDS = env.int("EVIDENCE_URL_TTL_SECONDS", default=300)
# Signed download links for scheduled report deliveries; the stored file is swept once
# this window has passed. Longer than an evidence presign because the link lands in an
# inbox or a chat room and is read later, but still bounded and never a public URL.
REPORT_DELIVERY_URL_TTL_SECONDS = env.int("REPORT_DELIVERY_URL_TTL_SECONDS", default=6 * 60 * 60)
EVIDENCE_MAX_BYTES = env.int("EVIDENCE_MAX_BYTES", default=10485760)
EVIDENCE_ALLOWED_MIME = ["image/jpeg", "image/png", "image/webp"]
EVIDENCE_OBJECT_RETENTION_DAYS = env.int(
    "EVIDENCE_OBJECT_RETENTION_DAYS", default=365
)
EVIDENCE_OBJECT_EXPIRY_ENABLED = env.bool(
    "EVIDENCE_OBJECT_EXPIRY_ENABLED", default=False
)
EVIDENCE_RETENTION_BATCH_SIZE = env.int("EVIDENCE_RETENTION_BATCH_SIZE", default=100)
# Abandoned-upload cleanup DELETES rows (only post-marker presigns proven unconsumed);
# independent of object expiry and default off. Existing receipts still reconcile.
EVIDENCE_ABANDONED_UPLOAD_CLEANUP_ENABLED = env.bool(
    "EVIDENCE_ABANDONED_UPLOAD_CLEANUP_ENABLED", default=False
)
EVIDENCE_ABANDONED_UPLOAD_RETENTION_DAYS = env.int(
    "EVIDENCE_ABANDONED_UPLOAD_RETENTION_DAYS", default=7
)
# Event travel support: private receipts and payee documents (core payouts), and
# stage-form uploads. Retention counts from the financial/terminal anchor; quotas are
# per member and per event. Values outside these bounds refuse to start.
EVENT_REIMBURSEMENT_RECEIPT_RETENTION_DAYS = env.int("EVENT_REIMBURSEMENT_RECEIPT_RETENTION_DAYS", default=2555)
EVENT_REIMBURSEMENT_PAYEE_PURGE_DAYS = env.int("EVENT_REIMBURSEMENT_PAYEE_PURGE_DAYS", default=30)
EVENT_REIMBURSEMENT_FILE_MAX_BYTES = env.int("EVENT_REIMBURSEMENT_FILE_MAX_BYTES", default=10485760)
EVENT_REIMBURSEMENT_MEMBER_STORAGE_BYTES = env.int("EVENT_REIMBURSEMENT_MEMBER_STORAGE_BYTES", default=104857600)
EVENT_REIMBURSEMENT_EVENT_STORAGE_BYTES = env.int("EVENT_REIMBURSEMENT_EVENT_STORAGE_BYTES", default=1073741824)
EVENT_STAGE_FILE_RETENTION_DAYS = env.int("EVENT_STAGE_FILE_RETENTION_DAYS", default=365)
EVENT_STAGE_MEMBER_QUOTA_BYTES = env.int("EVENT_STAGE_MEMBER_QUOTA_BYTES", default=104857600)
EVENT_STAGE_EVENT_QUOTA_BYTES = env.int("EVENT_STAGE_EVENT_QUOTA_BYTES", default=1073741824)
for _name, _low, _high in (
    ("EVENT_REIMBURSEMENT_RECEIPT_RETENTION_DAYS", 1, 36500), ("EVENT_REIMBURSEMENT_PAYEE_PURGE_DAYS", 1, 36500),
    ("EVENT_REIMBURSEMENT_FILE_MAX_BYTES", 1, 10485760), ("EVENT_STAGE_FILE_RETENTION_DAYS", 1, 36500),
    ("EVENT_REIMBURSEMENT_MEMBER_STORAGE_BYTES", 1, 2 ** 40), ("EVENT_REIMBURSEMENT_EVENT_STORAGE_BYTES", 1, 2 ** 40),
    ("EVENT_STAGE_MEMBER_QUOTA_BYTES", 1, 2 ** 40), ("EVENT_STAGE_EVENT_QUOTA_BYTES", 1, 2 ** 40),
):
    if not _low <= globals()[_name] <= _high:
        raise ImproperlyConfigured(f"{_name} must be between {_low} and {_high}.")
del _name, _low, _high
WARRANTY_DOC_MAX_BYTES = env.int("WARRANTY_DOC_MAX_BYTES", default=10485760)
WARRANTY_DOC_ALLOWED_MIME = env.list(
    "WARRANTY_DOC_ALLOWED_MIME",
    default=["application/pdf", "image/jpeg", "image/png", "image/webp"],
)
MACHINE_DOC_MAX_BYTES = env.int("MACHINE_DOC_MAX_BYTES", default=10485760)
MACHINE_DOC_ALLOWED_EXT = env.list(
    "MACHINE_DOC_ALLOWED_EXT",
    default=[
        "pdf", "jpg", "jpeg", "png", "webp", "stl", "3mf", "step", "stp",
        "obj", "amf", "ply", "gcode", "gco", "iges", "igs", "dxf",
    ],
)
MACHINE_DOC_ALLOWED_MIME = env.list(
    "MACHINE_DOC_ALLOWED_MIME",
    default=[
        "application/pdf", "image/jpeg", "image/png", "image/webp",
        "application/octet-stream", "model/stl", "application/sla",
        "application/vnd.ms-pki.stl", "model/3mf",
        "application/vnd.ms-package.3dmanufacturing-3dmodel+xml",
        "application/vnd.ms-3mfdocument", "application/step", "model/step",
        "model/obj", "application/xml", "text/xml", "application/x-amf",
        "model/amf", "application/x-ply", "model/ply", "text/x.gcode",
        "application/x-gcode", "application/iges", "model/iges",
        "image/vnd.dxf", "application/dxf", "application/x-dxf", "text/plain",
    ],
)
PROCUREMENT_RECEIPT_MAX_BYTES = env.int("PROCUREMENT_RECEIPT_MAX_BYTES", default=10485760)
PROCUREMENT_RECEIPT_ALLOWED_MIME = env.list(
    "PROCUREMENT_RECEIPT_ALLOWED_MIME",
    default=["application/pdf", "image/jpeg", "image/png", "image/webp"],
)
PUBLIC_IMAGE_BUCKET = env("PUBLIC_IMAGE_BUCKET", default="public-images")
assert_distinct_storage_buckets(AWS_STORAGE_BUCKET_NAME, PUBLIC_IMAGE_BUCKET)
PUBLIC_IMAGE_BASE_URL = env("PUBLIC_IMAGE_BASE_URL", default="")
PUBLIC_IMAGE_MAX_BYTES = env.int("PUBLIC_IMAGE_MAX_BYTES", default=10485760)
PUBLIC_IMAGE_URL_TTL_SECONDS = env.int("PUBLIC_IMAGE_URL_TTL_SECONDS", default=300)
PUBLIC_IMAGE_ALLOWED_MIME = {
    "image/jpeg": [".jpg", ".jpeg"],
    "image/png": [".png"],
    "image/webp": [".webp"],
}
PRINT_UPLOAD_MAX_BYTES = env.int("PRINT_UPLOAD_MAX_BYTES", default=104857600)  # 100 MB
PRINT_ALLOWED_MODEL_EXT = env.list(
    "PRINT_ALLOWED_MODEL_EXT",
    default=[
        "stl", "3mf", "step", "stp", "obj", "amf", "ply", "gcode", "gco",
        "iges", "igs", "dxf",
    ],
)
PRINT_ALLOWED_MODEL_MIME = env.list(
    "PRINT_ALLOWED_MODEL_MIME",
    default=[
        "application/octet-stream", "model/stl", "application/sla",
        "application/vnd.ms-pki.stl", "model/3mf",
        "application/vnd.ms-package.3dmanufacturing-3dmodel+xml",
        "application/vnd.ms-3mfdocument", "application/step", "model/step",
        "model/obj", "application/xml", "text/xml", "application/x-amf",
        "model/amf", "application/x-ply", "model/ply", "text/x.gcode",
        "application/x-gcode", "application/iges", "model/iges",
        "image/vnd.dxf", "application/dxf", "application/x-dxf", "text/plain",
    ],
)
PRINT_ALLOWED_SCREENSHOT_EXT = ["png", "jpg", "jpeg", "webp", "pdf"]
PRINT_ALLOWED_SCREENSHOT_MIME = [
    "image/png",
    "image/jpeg",
    "image/webp",
    "application/pdf",
]
