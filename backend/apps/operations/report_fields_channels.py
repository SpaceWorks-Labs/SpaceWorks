"""Web-and-app-use report schema; importable with every source app tombstoned."""

CHANNEL_USAGE_FIELDS = ("period", "measure", "channel", "area", "value", "share_percent")
CHANNELS = ("web", "ios", "android", "api_client")
MEASURES = ("session_days", "active_accounts", "new_accounts", "returning_accounts", "app_versions",
            "flow_completions", "api_calls")
