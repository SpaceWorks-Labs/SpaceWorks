#!/usr/bin/env python3
"""Read-only proof that missing legacy key material is unused, never guessed."""
import os
import sys


def main():
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    import django
    django.setup()
    from apps.encryption.models import MakerspaceEncryptionKey, SearchKeyGeneration
    master_unused = not MakerspaceEncryptionKey.objects.exclude(broker_backend="aws_kms").exists()
    search_unused = not SearchKeyGeneration.objects.exists()
    print(f"{int(master_unused)}|{int(search_unused)}")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        sys.exit("Cannot prove unused legacy encryption keys; recover the original keys before proceeding.")
