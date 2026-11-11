"""Standalone host checks: python backend/tests/test_host_setup_areas_behavior.py."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
BASH = shutil.which("bash")
AREAS = ["inventory", "machines", "events", "bookings", "membership", "payments", "reports", "chat"]


def default_area_answers():
    # Everything shortcut; Inventory + its policies/charges/access; Machines + its reminder policy;
    # the other six areas; organization, notifications, MFA.
    return [""] * 31


def run_questionnaire(directory, area_answers=None, prefix=None, cancel=False, edition="makerspace", payments=False):
    scripts = directory / "scripts"
    scripts.mkdir(exist_ok=True)
    shutil.copytree(ROOT / "scripts/installer", scripts / "installer", dirs_exist_ok=True, ignore=shutil.ignore_patterns("__pycache__"))
    for name in ("setup-questions.sh", "setup-question-input.sh", "setup-area-questions.sh", "setup-areas-json.sh"):
        source = (ROOT / "scripts" / name).read_text(encoding="utf-8")
        source = source.replace("exec 3</dev/tty", "exec 3<&0")
        source = source.replace('[[ "$(uname -s)" == Linux ]] && command -v systemctl >/dev/null 2>&1', "true")
        source = source.replace("[[ -d /run/systemd/system ]]", "true")
        (scripts / name).write_text(source, encoding="utf-8", newline="\n")
    # "n" answers "Use quick setup?" so the full questionnaire runs.
    answers = ["n"] + (prefix or ["", "", "", "", "", "", "", "Test Organization", "", ""]) + (area_answers if area_answers is not None else default_area_answers())
    answers += ["", "owner@example.org", "private-password"]
    if payments:
        answers += ["", ""]
    answers += ["", "", "n" if cancel else ""]
    return subprocess.run([BASH, "-c", '''set -euo pipefail
source scripts/setup-questions.sh
ask_setup_questions || exit 0
save_setup_answers "$PWD/.spaceworks-answers"
setup_areas_json > areas.json
'''], cwd=directory, input="\n".join(answers) + "\n", text=True,
        capture_output=True, env={**os.environ, "SPACEWORKS_EDITION": edition}, timeout=30)


@unittest.skipUnless(BASH, "requires Bash")
class SetupAreaHostTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)

    def tearDown(self):
        self.temporary.cleanup()

    def test_default_flow_summary_and_private_answers(self):
        result = run_questionnaire(self.root)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / "areas.json").exists(), result.stdout)
        answers = json.loads((self.root / "areas.json").read_text())
        self.assertEqual(answers["areas"], ["inventory", "machines", "reports"])
        self.assertEqual(answers["request_access"], "accounts")
        self.assertEqual(answers["settings"]["loan_policy"]["loan_renewal_mode"], "auto")
        self.assertEqual(answers["settings"]["machine_policy"]["cert_reminder_days"], 14)
        self.assertNotIn("security.staff_mfa_required", answers["settings"].get("features", {}))
        self.assertIn("Areas: inventory,machines,reports; edition: makerspace", result.stdout)
        self.assertIn("Maximum active loans per borrower: 0", result.stdout)
        self.assertNotIn("private-password", result.stdout)
        saved = (self.root / ".spaceworks-answers").read_text()
        self.assertIn("AREA_SETTINGS_JSON=", saved)
        self.assertNotIn("MSPROFILE=", saved)

    def test_no_areas_skip_followups_and_preserve_core(self):
        # Everything, eight area answers, organization, timezone/quiet window, digest, MFA.
        result = run_questionnaire(self.root, ["n"] * 10 + ["", "", "", "n", "n"])
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads((self.root / "areas.json").read_text())
        self.assertEqual(data["areas"], [])
        self.assertNotIn("request_access", data)
        self.assertNotIn("Maximum active loans", result.stdout)
        self.assertNotIn("How people join", result.stdout)
        self.assertNotIn("Stripe secret key", result.stdout)

    def test_membership_vouches_plan_and_json_escaping(self):
        area = ["n", "n", "n", "n", "n", "y", "vouch", "2", "30", "3", "30", "y", "y",
                "y", 'Standard "friends"', "custom_days", "45", "12.50", "inr", "y",
                "10", "2", "1", "14,7,1", "1,3", "n", "n", "n", "n", "", "", "", "y", "09:00", "y"]
        result = run_questionnaire(self.root, area)
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads((self.root / "areas.json").read_text())
        self.assertEqual(data["areas"], ["membership"])
        self.assertEqual(data["settings"]["admission"]["vouches_required"], 2)
        self.assertTrue(data["settings"]["admission"]["vouch_replaces_approval"])
        self.assertIsInstance(data["settings"]["admission"]["application_schema"], list)
        self.assertEqual(data["settings"]["plan"]["name"], 'Standard "friends"')
        self.assertEqual(data["settings"]["plan"]["reminder_days_after"], [1, 3])

    def test_cancellation_has_no_effects(self):
        result = run_questionnaire(self.root, cancel=True)
        self.assertIn("Cancelled", result.stdout)
        self.assertFalse((self.root / ".spaceworks-answers").exists())

    def test_events_edition_keeps_account_checkout_and_report_defaults(self):
        result = run_questionnaire(self.root, [""] * 20, edition="events", payments=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads((self.root / "areas.json").read_text())
        self.assertEqual(data["areas"], ["events", "membership", "payments", "reports"])
        self.assertIn("Use Inventory? [y/N]", result.stdout)
        self.assertIn("Use Online payments? [Y/n]", result.stdout)
        self.assertIn("edition: events", result.stdout)

    def test_shared_charge_ticket_and_checkout_currency_is_not_overwritten(self):
        areas = default_area_answers()
        areas[13] = "inr"
        areas[19] = "y"
        areas.insert(20, "accounts")
        areas[23] = "y"
        result = run_questionnaire(self.root, areas, payments=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads((self.root / "areas.json").read_text())
        self.assertEqual(data["settings"]["currency"], "inr")
        self.assertIn("Ticket prices use the shared default currency: inr", result.stdout)
        self.assertIn("Online checkout uses the shared default currency: inr", result.stdout)
        self.assertIn("STRIPE_DEFAULT_CURRENCY=inr", (self.root / ".spaceworks-answers").read_text())

    def test_everything_selects_all_areas_and_keeps_followups_in_order(self):
        # All shortcut; 13 inventory, 3 machine, 1 event, 4 membership,
        # then organization and the five always-on setting answers.
        result = run_questionnaire(self.root, ["yes"] + [""] * 27, payments=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads((self.root / "areas.json").read_text())
        self.assertEqual(data["areas"], AREAS)
        self.assertEqual(data["request_access"], "members")
        self.assertEqual(data["settings"]["loan_policy"]["default_loan_days"], 7)
        self.assertEqual(data["settings"]["machine_policy"]["cert_reminder_days"], 14)
        self.assertEqual(data["settings"]["space"]["event_default_registration_audience"], "accounts")
        self.assertEqual(data["settings"]["admission"]["join_mode"], "approval")
        self.assertNotIn("security.staff_mfa_required", data["settings"].get("features", {}))
        prompts = ["Maximum active loans per borrower", "Enforce machine certification gating?",
                   "Default registration audience", "Bookings and recurring bookings are enabled",
                   "How people join", "Online payments enable checkout", "Reports and saved report views",
                   "Telegram, Slack, Mattermost", "Label this as an organization", "Quiet hours start"]
        positions = [result.stdout.index(prompt) for prompt in prompts]
        self.assertEqual(positions, sorted(positions))
        for label in ("Inventory", "Machines", "Events", "Bookings", "Membership",
                      "Online payments", "Reports", "Chat alerts"):
            self.assertNotIn(f"Use {label}?", result.stdout)

    def test_edition_derivation(self):
        helper = (ROOT / "scripts/setup-area-questions.sh").as_posix()
        for areas, edition in [("events,membership,payments,chat", "events"), ("bookings,reports", "bookings"),
                               ("events,bookings", "makerspace"), ("inventory", "makerspace"), ("", "makerspace")]:
            result = subprocess.run([BASH, "-c", 'source "$HELPER"; SETUP_SELECTED_AREAS="$AREAS"; derive_setup_edition; echo "$SPACEWORKS_EDITION"'],
                env={**os.environ, "HELPER": helper, "AREAS": areas}, text=True, capture_output=True)
            self.assertEqual(result.stdout.strip(), edition, result.stderr)

    def test_native_windows_resume_keeps_inherited_area_answers(self):
        helper = (ROOT / "scripts/setup-questions.sh").as_posix()
        settings = {"space": {"event_default_registration_audience": "accounts"}, "currency": "inr"}
        result = subprocess.run([BASH, "-c", 'source "$HELPER"; setup_areas_json'],
            env={**os.environ, "HELPER": helper, "ANSWERS_CONFIRMED": "yes", "SETUP_SELECTED_AREAS": "events,reports",
                 "AREA_SETTINGS_JSON": json.dumps(settings)}, text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"areas": ["events", "reports"], "settings": settings})

    def menu(self, states, mode="interactive", selected="", input_text="", active=None, without=""):
        helper = (ROOT / "scripts/module-selection.sh").as_posix()
        script = '''set -euo pipefail
say() { echo "$*"; }; warn() { echo "$*" >&2; }
compose() {
  printf '%s\n' "$*" >> "$COMMANDS"
  case "$*" in
    *--status*) printf '%s\n' "$STATES" ;;
    *--answers-json*) cat > "$DOCUMENT" ;;
    *list_modules*) printf '+ telegram Chat alerts\n' ;;
    *) return 99 ;;
  esac
}
COMPOSE=(compose)
source "$HELPER"
module_change_one test-space
'''
        env = {**os.environ, "HELPER": helper, "MODULE_MODE": mode,
               "MODULE_INTERACTIVE": "1" if mode == "interactive" else "0", "MODULE_AREAS": selected,
               "STATES": json.dumps({"areas": states, "active": active or {}}),
               "COMMANDS": (self.root / "commands").as_posix(), "MODULE_WITHOUT": without,
               "DOCUMENT": (self.root / "document").as_posix(), "MODULE_CONFIRM_REMOVALS": "1"}
        result = subprocess.run([BASH, "-c", script], env=env, text=True, input=input_text,
                                capture_output=True, timeout=30)
        return result

    def test_menu_new_area_followups_and_no_answers_on_argv(self):
        states = dict.fromkeys(["inventory", "machines", "events", "bookings", "membership", "payments", "reports", "chat"], "off")
        result = self.menu(states, input_text="3\n\naccounts\ninr\n\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        document = json.loads((self.root / "document").read_text())
        self.assertEqual(document["areas"], ["events"])
        self.assertEqual(document["configure_areas"], ["events"])
        self.assertEqual(document["settings"]["currency"], "inr")
        self.assertIn("current off", result.stdout)
        self.assertNotIn("Maximum active loans", result.stdout)
        commands = (self.root / "commands").read_text()
        self.assertIn("--answers-json -", commands)
        self.assertNotIn("inr", commands)
        self.assertNotIn("purge", commands)

    def test_menu_disable_inventory_no_core_uninstall_or_followups(self):
        states = dict.fromkeys(["inventory", "machines", "events", "bookings", "membership", "payments", "reports", "chat"], "off")
        states["inventory"] = states["machines"] = "on"
        result = self.menu(states, input_text="1\n\n\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        document = json.loads((self.root / "document").read_text())
        self.assertEqual(document["areas"], ["machines"])
        self.assertEqual(document["configure_areas"], [])
        self.assertEqual(document["settings"], {})
        self.assertNotIn("Certification expiry reminder lead", result.stdout)

    def test_menu_scripting_areas_and_unknown_area_refusal(self):
        states = dict.fromkeys(["inventory", "machines", "events", "bookings", "membership", "payments", "reports", "chat"], "off")
        result = self.menu(states, mode="areas", selected="events,reports,payments")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((self.root / "document").read_text())["areas"], ["events", "payments", "reports"])
        result = self.menu(states, mode="areas", selected="unknown")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unknown area", result.stderr)

    def test_partial_existing_area_keeps_configuration(self):
        states = dict.fromkeys(["inventory", "machines", "events", "bookings", "membership", "payments", "reports", "chat"], "off")
        states["inventory"] = "partial"
        result = self.menu(states, input_text="\n\n")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads((self.root / "document").read_text())
        self.assertEqual(data["areas"], ["inventory"])
        self.assertEqual(data["configure_areas"], [])
        self.assertNotIn("Maximum active loans per borrower", result.stdout)

    def test_menu_all_and_none_presets(self):
        for preset in ("a", "A", "n", "N"):
            with self.subTest(preset=preset):
                selecting_all = preset.lower() == "a"
                # All starts from none, then answers 21 follow-ups and confirmation.
                # None starts from all and needs only confirmation after review.
                states = dict.fromkeys(AREAS, "off" if selecting_all else "on")
                input_text = f"{preset}\n\n" + "\n" * (22 if selecting_all else 1)
                result = self.menu(states, input_text=input_text)
                self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
                data = json.loads((self.root / "document").read_text())
                self.assertEqual(data["areas"], AREAS if selecting_all else [])
                self.assertEqual(data["configure_areas"], AREAS if selecting_all else [])
                if selecting_all:
                    self.assertIn("loan_policy", data["settings"])
                    self.assertIn("admission", data["settings"])
                    self.assertEqual(data["request_access"], "members")
                else:
                    self.assertEqual(data["settings"], {})
                self.assertNotIn("enable_area_features", data)

    def test_all_mode_selects_chat_and_configures_only_new_areas(self):
        states = dict.fromkeys(AREAS, "off")
        states.update(inventory="partial", machines="partial", events="on")
        active = dict.fromkeys(AREAS, False)
        active.update(inventory=True, events=True)
        result = self.menu(states, mode="all", active=active)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads((self.root / "document").read_text())
        self.assertEqual(data["areas"], AREAS)
        self.assertIs(data["enable_area_features"], True)
        self.assertEqual(data["configure_areas"], [area for area in AREAS if not active[area]])
        self.assertEqual(data["settings"], {})

    def test_all_mode_keeps_telegram_exclusion_and_confirms_removal(self):
        result = self.menu(dict.fromkeys(AREAS, "on"), mode="all", without="telegram")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads((self.root / "document").read_text())
        self.assertEqual(data["areas"], AREAS)
        self.assertEqual(data["without"], ["telegram"])
        self.assertIs(data["enable_area_features"], True)
        self.assertEqual(data["configure_areas"], [])
        self.assertIn("Confirmed: disabling 1 module(s)", result.stdout)
        self.assertIn("list_modules", (self.root / "commands").read_text())


if __name__ == "__main__":
    unittest.main()
