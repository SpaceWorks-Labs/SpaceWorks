"""The same pre-settings hook is used by image startup and finite setup tools."""
import os


def materialize():
    if os.environ.get("SPACEWORKS_SECRET_FILE_MODE", "native") == "native":
        return
    if os.environ.get("SPACEWORKS_SECRET_FILE_MODE") != "inline":
        raise ValueError("SPACEWORKS_SECRET_FILE_MODE must be native or inline.")
    if len(os.environ.get("SPACEWORKS_EMAIL_PROVIDER_CONFIG_B64", "")) > 21848 or len(os.environ.get("SPACEWORKS_STORAGE_CAPABILITIES_B64", "")) > 131072:
        raise ValueError("Inline secret file exceeds its bound.")
    from cloud_setup.secret_files import materialize_secret_files
    materialize_secret_files(os.environ)
