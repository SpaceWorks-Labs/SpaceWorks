"""A fresh value each time prevents cross-request mutation."""


def defaults():
    return {
        "pageview": {"provider": "none", "site_id": "", "endpoint": ""},
        "replay": {"provider": "none", "site_id": "", "endpoint": ""},
        "diagnostics": {"sentry": {"enabled": False, "dsn": "", "sample_rate": 1.0},
                        "firebase_performance": {"enabled": False, "sample_rate": 0.1}},
        "firebase": {"api_key": "", "auth_domain": "", "project_id": "", "app_id": "",
                     "messaging_sender_id": "", "measurement_id": "", "vapid_public_key": ""},
    }
