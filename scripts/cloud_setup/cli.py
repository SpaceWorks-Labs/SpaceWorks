"""Managed setup actions; parser/help need only Python's standard library."""

import argparse
import hashlib
import json
from pathlib import Path
import sys

from .answers import validate_answers
from .environment import effective_environment
from .errors import SetupError
from .free_profile import FREE_NOTICE
from .private_files import read_json, setup_lock, sync_directory, write_json


def parser():
    value = argparse.ArgumentParser(description="Space Works managed setup. No root, Docker daemon or provider account creation. Run in a Linux setup job with backend requirements and age installed.")
    value.add_argument("action", choices=("wizard", "validate", "render", "bootstrap"))
    value.add_argument("--answers-file", help="Owned 0600 version-1 JSON; no credential arguments")
    value.add_argument("--secrets-file", help="Owned 0600 version-1 values JSON, or - for protected stdin")
    value.add_argument("--state-dir", required=True, help="Owned 0700 persistent setup directory")
    value.add_argument("--non-interactive", action="store_true")
    value.add_argument("--send-test", action="store_true", help="Bootstrap only: send to the recipient explicitly selected in answers")
    value.add_argument("--inbox-confirmed", action="store_true", help="Operator confirms actual receipt separately from provider acceptance")
    value.add_argument("--acceptance-file", help="Private deployment/image/config-bound live harness receipt; see deploy/cloud/acceptance-contract.json")
    value.add_argument("--release-only", action="store_true", help="Bootstrap: finite initial release only, before residents deploy; never marks setup complete")
    return value


def interactive():
    from .interactive import interactive as collect
    return collect()


def supplied_secrets(path):
    if not path:
        return {"version": 1, "values": {}}
    if path != "-":
        return read_json(path)
    if sys.stdin.isatty():
        raise SetupError("secret_stdin_pipe", "Pipe a protected file to stdin; do not type secrets into an echoed terminal.")
    try:
        raw = sys.stdin.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError
        return json.loads(raw)
    except ValueError:
        raise SetupError("secret_stdin_json", "Supply bounded version-1 JSON through protected stdin.") from None


def run(argv=None):
    args = parser().parse_args(argv)
    if args.action != "bootstrap" and (args.send_test or args.inbox_confirmed or args.release_only or args.acceptance_file):
        raise SetupError("send_only_bootstrap", "validate/render never send mail; select bootstrap explicitly.")
    if not args.answers_file and (args.non_interactive or args.action != "wizard"):
        raise SetupError("answers_required", "Noninteractive setup requires --answers-file with every required choice.")
    answers = validate_answers(read_json(args.answers_file) if args.answers_file else interactive())
    if args.action == "bootstrap" and "setup" not in answers:
        raise SetupError("setup_required", "Bootstrap requires explicit version-1 setup account, organization and makerspace choices.")
    if args.release_only and (args.send_test or args.inbox_confirmed or args.acceptance_file):
        raise SetupError("release_only_choices", "Separate finite initial release from post-deploy acceptance and test mail.")
    if answers["profile"] == "free":
        print(FREE_NOTICE, file=sys.stderr)
    with setup_lock(args.state_dir):
        root = Path(args.state_dir)
        digest = hashlib.sha256(json.dumps(answers, sort_keys=True).encode()).hexdigest()
        state = root / "state.json"
        previous = read_json(state) if state.exists() else {}
        owns_answers = previous.get("owns_answers", False)
        if previous and previous.get("answers_sha256") != digest:
            raise SetupError("answers_changed", "Use a new setup directory for a reviewed configuration change; retain existing continuity secrets.")
        if args.action != "validate":
            write_json(state, {"version": 1, "answers_sha256": digest, "status": "incomplete", "owns_answers": owns_answers})
        if args.action == "wizard":
            write_json(root / "answers.json", answers)
            owns_answers = True
        from .secrets import ensure_secrets, validate_secrets
        supplied = supplied_secrets(args.secrets_file)
        if not isinstance(supplied, dict) or set(supplied) != {"version", "values"} or supplied["version"] != 1:
            raise SetupError("secret_version", "Use secret file version 1 with a values mapping.")
        validate_secrets(supplied["values"], free=answers["profile"] == "free")
        if args.action == "validate":
            # Read-only action: no secret generation, provider writes or send.
            secrets = read_json(root / "secrets.json")["values"] if (root / "secrets.json").exists() else supplied.get("values", {})
            if any(key in secrets and secrets[key] != value for key, value in supplied["values"].items()):
                raise SetupError("secret_change_refused", "Supplied secrets differ from saved state; use a reviewed rotation instead of silently validating old credentials.")
            secrets = {**secrets, **supplied["values"]}
            validate_secrets(secrets, free=answers["profile"] == "free")
            from .validation import validate
            report = validate(effective_environment(answers, secrets), answers)
            write_json(root / "validation.json", report)
        else:
            secrets = ensure_secrets(root, supplied, free=answers["profile"] == "free")
            values = effective_environment(answers, secrets)
            from .render import render
            report = render(root, values, answers)
            if args.action == "bootstrap":
                from .bootstrap import bootstrap
                report = bootstrap(root, values, answers, send_test=args.send_test, inbox_confirmed=args.inbox_confirmed, acceptance_file=args.acceptance_file, release_only=args.release_only)
            if report["status"] == "complete" and args.non_interactive and owns_answers:
                path = root / "answers.json"
                saved = read_json(path)
                if hashlib.sha256(json.dumps(saved, sort_keys=True).encode()).hexdigest() != digest:
                    raise SetupError("owned_answers_changed", "Owned answer material changed; preserve it for explicit review instead of deleting.")
                path.unlink()
                sync_directory(root)
                owns_answers = False
            write_json(state, {"version": 1, "answers_sha256": digest, "status": report["status"], "owns_answers": owns_answers})
        print(json.dumps(report, sort_keys=True))
        return 0 if report["status"] in {"passed", "rendered", "released", "complete"} else 78


def main(argv=None):
    try:
        return run(argv)
    except KeyboardInterrupt:
        print(json.dumps({"status": "cancelled", "code": "cancelled", "action": "Private state retained; resume with the same answers."}), file=sys.stderr)
        return 130
    except SetupError as exc:
        print(json.dumps(exc.report()), file=sys.stderr)
        return 78
    except Exception:
        print(json.dumps({"status": "failed", "code": "setup_failed", "action": "Check private setup files and dependencies; no raw provider or credential error is printed."}), file=sys.stderr)
        return 78
