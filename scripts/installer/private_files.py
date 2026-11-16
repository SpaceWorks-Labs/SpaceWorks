#!/usr/bin/env python3
"""Private-file checks use POSIX ownership/modes or an explicit Windows ACL."""
import os
from pathlib import Path
import re
import stat
import subprocess
import sys


def _run(command, **options):
    try:
        return subprocess.run(command, **options)
    except (OSError, subprocess.SubprocessError):
        raise ValueError("Private-file authority could not be verified.") from None


def windows_sid():
    result = _run(["whoami", "/user", "/fo", "csv", "/nh"], check=True,
                            capture_output=True, timeout=10)
    match = re.search(rb'"(S-1-[0-9-]+)"', result.stdout)
    if match is None:
        raise ValueError("Cannot prove Windows operator identity.")
    return match[1].decode("ascii")


def make_private(path, directory=False):
    path = Path(path)
    if path.is_symlink() or not (path.is_dir() if directory else path.is_file()):
        raise ValueError("Expected a regular private file.")
    if os.name == "nt":
        _run(["icacls", str(path), "/inheritance:r", "/grant:r", f"*{windows_sid()}:" + ("(OI)(CI)(F)" if directory else "(F)")],
                       check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    else:
        path.chmod(0o700 if directory else 0o600)


def check_private(path, directory=False):
    path = Path(path)
    info = path.lstat()
    if not (stat.S_ISDIR(info.st_mode) if directory else stat.S_ISREG(info.st_mode)):
        raise ValueError("Expected a regular private file.")
    if os.name != "nt":
        if info.st_uid != os.getuid() or info.st_mode & 0o077:
            raise ValueError("Private file has unsafe ownership or permissions.")
        return info
    # Use a fixed script and environment transport; paths are never PowerShell code.
    script = r'''
$ErrorActionPreference = 'Stop'
$acl = Get-Acl -LiteralPath $env:SPACEWORKS_PRIVATE_PATH
$sid = $env:SPACEWORKS_PRIVATE_SID
$owner = (New-Object System.Security.Principal.NTAccount($acl.Owner)).Translate([System.Security.Principal.SecurityIdentifier]).Value
if ($owner -ne $sid) { exit 1 }
foreach ($rule in $acl.GetAccessRules($true, $true, [System.Security.Principal.SecurityIdentifier])) {
  if ($rule.AccessControlType -eq 'Allow' -and $rule.IdentityReference.Value -notin @($sid, 'S-1-5-18', 'S-1-5-32-544')) { exit 1 }
}
'''
    _run(["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script], check=True,
                   env={**os.environ, "SPACEWORKS_PRIVATE_PATH": str(path.absolute()), "SPACEWORKS_PRIVATE_SID": windows_sid()},
                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=10)
    return info


if __name__ == "__main__":
    try:
        if sys.argv[1] not in {"secure", "secure-directory", "check"}:
            raise ValueError("Unknown private-file action.")
        is_directory = sys.argv[1] == "secure-directory"
        if sys.argv[1] != "check":
            make_private(sys.argv[2], directory=is_directory)
        check_private(sys.argv[2], directory=is_directory)
    except (ValueError, OSError, subprocess.SubprocessError, IndexError):
        sys.exit("Cannot prove private file permissions; installation was not completed.")
