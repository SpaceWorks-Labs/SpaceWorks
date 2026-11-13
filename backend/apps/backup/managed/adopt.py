"""Explicit existing-installation adoption, using the same finite release checks."""

import sys


def main():
    from .profile import deployment_profile
    from .release import run_release

    try:
        if deployment_profile().mode != "managed" or len(sys.argv) != 1:
            raise ValueError("Managed adoption takes no arguments and requires managed mode.")
        run_release(adopt=True)
    except Exception:
        print("Managed adoption refused; verify recovery, identity, role and transport prerequisites.", file=sys.stderr)
        return 78
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
