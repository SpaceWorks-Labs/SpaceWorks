"""No-cloud settings, route table and beat remain independent of every free knob."""
import json
import os
from pathlib import Path
import subprocess
import sys

BACKEND = Path(__file__).resolve().parents[3]
SNAPSHOT = r"""
import json, django
django.setup()
from django.conf import settings
from django.urls import get_resolver, URLPattern

def routes(patterns, prefix=""):
    result=[]
    for entry in patterns:
        path=prefix+str(entry.pattern)
        if isinstance(entry, URLPattern):
            result.append([path, entry.name])
        else:
            result.extend(routes(entry.url_patterns, path))
    return result
keys=("CELERY_BROKER_URL", "CELERY_TASK_ALWAYS_EAGER", "CELERY_RESULT_BACKEND",
      "LIVE_REDIS_URL", "CACHES", "MANAGED_POSTGRES", "ALLOWED_HOSTS",
      "REST_FRAMEWORK", "STORAGES", "CELERY_BEAT_SCHEDULER")
print(json.dumps({"settings": {k:getattr(settings,k) for k in keys},
 "routes":routes(get_resolver().url_patterns),
 "beat":{k:{**v,"schedule":str(v["schedule"])} for k,v in settings.CELERY_BEAT_SCHEDULE.items()}},
 sort_keys=True,default=str))
"""


def snapshot(extra):
    environment = {k:v for k,v in os.environ.items() if not k.startswith(("FREE_", "CLOUD_", "SPACEWORKS_DEPLOYMENT_"))}
    environment.update(DJANGO_SETTINGS_MODULE="config.settings", EMAIL_PROVIDER_WEBHOOKS_ENABLED="False")
    environment.update(extra)
    # A cold full boot plus URL import measured 75-85 s in the isolated Docker runner;
    # the bound guards against a hang, not against a slow host.
    result=subprocess.run([sys.executable,"-c",SNAPSHOT],cwd=BACKEND,env=environment,
                          capture_output=True,text=True,timeout=300,check=True)
    return json.loads(result.stdout.strip().splitlines()[-1])


def test_no_cloud_and_explicit_full_preserve_settings_routes_and_beat():
    baseline=snapshot({})
    full=snapshot({"SPACEWORKS_DEPLOYMENT_MODE":"host", "SPACEWORKS_DEPLOYMENT_PROFILE":"full", "FREE_TICK_SECRET":"inert",
        "FREE_TICK_BUDGET_SECONDS":"invalid", "FREE_TICK_INTERVAL_SECONDS":"invalid",
        "FREE_EMAIL_DAILY_CAP":"invalid", "FREE_EMAIL_MONTHLY_CAP":"invalid",
        "FREE_EMAIL_ACCOUNTS":"invalid", "FREE_MAX_PROMOTION_BYTES":"invalid",
        "FREE_DB_CAP_BYTES":"invalid", "FREE_OBJECT_CAP_BYTES":"invalid",
        "MANAGED_UPLOAD_TRANSFER_BOUND_SECONDS":"invalid"})
    assert full == baseline
    assert not any("internal/free/" in path or "email-provider-webhook" in path
                   for path,name in baseline["routes"])
    assert baseline["beat"]


def test_explicit_host_task_profiles_ignore_every_free_cap():
    for profile, scheduler, broker in (("redis", "beat", "redis://redis:6379/0"),
                                        ("brokerless", "loop", "")):
        selected = {"SPACEWORKS_DEPLOYMENT_MODE": "host", "SPACEWORKS_DEPLOYMENT_PROFILE": "full",
                    "CLOUD_TASK_PROFILE": profile, "CLOUD_SCHEDULER": scheduler,
                    "CELERY_BROKER_URL": broker, "CACHE_URL": "", "LIVE_REDIS_URL": "",
                    "CELERY_RESULT_BACKEND": "", "CELERY_TASK_ALWAYS_EAGER": str(not broker)}
        assert snapshot(selected) == snapshot({**selected, "FREE_TICK_SECRET": "irrelevant",
            "FREE_EMAIL_ACCOUNTS": "malformed", "FREE_EMAIL_DAILY_CAP": "malformed",
            "FREE_MAX_PROMOTION_BYTES": "malformed", "FREE_OBJECT_CAP_BYTES": "malformed"})
