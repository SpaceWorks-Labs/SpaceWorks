"""Guided terminal choices. Credentials are never requested in an echoed prompt."""

from datetime import date

from .errors import SetupError
from .free_profile import FREE_NOTICE
from .private_files import read_json


def ask(label, default=None):
    suffix = f" [{default}]" if default is not None else ""
    try:
        answer = input(label + suffix + ": ").strip()
    except EOFError:
        raise SetupError("wizard_eof", "Input ended before setup choices were complete; use --answers-file for unattended jobs.") from None
    value = answer or default
    if value is None:
        raise SetupError("answer_required", "A required setup answer is missing; no completion was recorded.")
    return value


def choose(label, values, default):
    answer = ask(label + " (" + "/".join(values) + ")", default)
    if answer not in values:
        raise SetupError("invalid_choice", "Select one of the displayed choices; no resource has been provisioned.")
    return answer


def number(label, default=None):
    try:
        return int(ask(label, str(default) if default is not None else None))
    except ValueError:
        raise SetupError("invalid_number", "Supply a positive integer; setup choices remain incomplete.") from None


def interactive():
    print("Space Works cloud setup. No provider account or paid resource is created automatically.")
    print("Full uses a worker and singleton scheduler. Full VM alternative: Oracle Always Free uses the existing host/full installer; capacity and off-VM recovery need verification.")
    print(FREE_NOTICE)
    existing = ask("Existing protected answers JSON (blank for guided choices)", "")
    if existing:
        return read_json(existing)
    profile = choose("Deployment profile: free means Free (best effort)", ("full", "free"), "full")
    providers = ("render", "cloud-run", "docker", "northflank") if profile == "free" else ("render", "railway", "fly", "koyeb", "digitalocean", "cloud-run", "docker", "kubernetes")
    provider = choose("Compute provider", providers, "render")
    if provider == "northflank":
        print("Northflank Sandbox: verify on signup. This recipe is not certified one-click or guaranteed $0.")
    answer = {
        "version": 1, "provider": provider, "profile": profile,
        "backend_image": ask("Verified same-build backend OCI image@sha256:digest (free target if selected)"),
        "database_provider": choose("Database provider", ("generic", "supabase", "neon", "rds", "digitalocean", "aiven"), "supabase" if profile == "free" else "generic"),
    }
    default_mode = "session" if answer["database_provider"] == "supabase" else "direct"
    answer.update(
        database_connection_mode=choose("Runtime DB transport (transaction pooling is refused)", ("direct", "session"), default_mode),
        maintenance_connection_mode=choose("Separate maintenance DB transport", ("direct", "session"), default_mode),
        database_documentation_url=ask("Official provider connection-mode documentation HTTPS URL"),
        connection_limit=number("Account DB connection allowance, including extra guard/release connections", 20),
        trusted_proxy_count=number("Exact verified ingress proxy count (include static proxy hops)"),
        task_profile="brokerless" if profile == "free" else choose("Task topology", ("redis", "brokerless"), "redis"),
        public_origin=ask("Exact public frontend HTTPS origin"), api_origin=ask("Exact API HTTPS origin"),
        allowed_hosts=ask("Exact API infrastructure hosts, comma separated; no wildcards").split(","),
        email_provider=choose("Verified email provider", ("resend", "brevo", "smtp", "postmark", "ses", "mailgun", "sendgrid"), "resend"),
        from_email=ask("Verified sender mailbox"), presign_method=choose("Verified storage upload method", ("put", "post"), "put"),
        scan_policy=choose("Malware policy (external means private ClamAV)", ("none", "external"), "none"),
        storage_capabilities_file=ask("Absolute private storage-capabilities JSON path", "/tmp/spaceworks-secrets/storage.json" if provider in {"digitalocean", "koyeb", "railway", "cloud-run"} else "/secrets/storage/config.json"),
    )
    answer["allowed_hosts"] = [host.strip() for host in answer["allowed_hosts"]]
    environment = {
        "AWS_STORAGE_BUCKET_NAME": ask("Existing private bucket (all uploads stage privately)"),
        "PUBLIC_IMAGE_BUCKET": ask("Distinct public-final image bucket"),
        "AWS_S3_REGION_NAME": ask("Storage signing region", "auto"),
        "AWS_S3_ENDPOINT_URL": ask("Backend S3 HTTPS API endpoint"),
        "AWS_S3_PUBLIC_ENDPOINT_URL": ask("Browser S3 HTTPS API endpoint (not r2.dev)"),
        "PUBLIC_IMAGE_BASE_URL": ask("Public-final image HTTPS delivery base URL"),
    }
    if answer["email_provider"] != "smtp":
        environment["EMAIL_PROVIDER_CONFIG_FILE"] = ask("Absolute private HTTP mail config JSON path", "/tmp/spaceworks-secrets/email.json" if provider in {"digitalocean", "koyeb", "railway", "cloud-run"} else "/secrets/email/config.json")
    else:
        environment.update(EMAIL_HOST=ask("SMTP host"), EMAIL_PORT=str(number("SMTP port", 587)), EMAIL_USE_TLS="True")
    if answer["scan_policy"] == "external":
        environment.update(CLAMD_HOST=ask("Private ClamAV host"), CLAMD_PORT=str(number("Private ClamAV port", 3310)))
    answer["environment"] = environment
    answer["setup"] = {
        "username": ask("Initial platform admin username"), "email": ask("Initial platform admin real email"),
        "makerspace_name": ask("Makerspace name"), "makerspace_slug": ask("Makerspace lowercase slug"),
        "organization_name": ask("Owner organization name"),
        "module_profile": choose("Initial module set (separate from deployment profile)", ("cloud", "recommended", "minimal", "full", "lending", "workshop", "everything", "events", "bookings"), "cloud"),
    }
    recipient = ask("Optional explicit test email recipient (sent only by bootstrap --send-test)", "")
    if recipient:
        answer["send_test_recipient"] = recipient
    if profile == "free":
        print(FREE_NOTICE)
        answer["free"] = {
            "db_cap_bytes": number("Verified DB cap in bytes"), "object_cap_bytes": number("Verified aggregate object cap in bytes"),
            "email_daily_cap": number("Verified provider-account daily recipient allowance"),
            "email_monthly_cap": number("Verified provider-account monthly recipient allowance"),
            "email_account_key": ask("Stable non-secret mail account budget key shared by every sender/tenant"),
            "email_reset_timezone": ask("Provider daily reset IANA timezone", "UTC"),
            "source_url": ask("Official allowance source HTTPS URL"), "checked_on": ask("Date all provider allowances were checked (YYYY-MM-DD)", date.today().isoformat()),
            "tick_interval_seconds": number("External tick interval seconds", 1800 if answer["database_provider"] == "neon" else 600),
            "acknowledge_limits": choose("Acknowledge cold starts, caps, costs and recovery limits", ("yes", "no"), "no") == "yes",
        }
    print("Credentials must come from --secrets-file or protected stdin. They are never prompted or printed.")
    return answer
