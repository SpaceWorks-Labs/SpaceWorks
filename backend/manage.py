#!/usr/bin/env python
import os
import sys


def main() -> None:
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
    from django.core.management import execute_from_command_line

    from apps.backup.managed.commands import execute
    execute(sys.argv, execute_from_command_line)


if __name__ == "__main__":
    main()
