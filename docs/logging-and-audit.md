# Logging and audit

Use the audit log to see who changed a record and when. Use application logs to investigate a failed request, a background task, or a service outage.

## Find an audit entry

1. Open **Audit log** in the staff console for the relevant makerspace. Access follows your role in that space.
2. Filter by time, action, actor, or target. For a loan, the request timeline also shows events linked to that request.
3. As a superadmin, open **Platform settings → Audit log** to search across spaces. Filter by makerspace ID or select **Platform-level rows only** for actions recorded at deployment scope.

The [audit action reference](audit-action-reference.md) lists action keys and the labels shown in the console. Screens and exports use a shared metadata policy. Each action exposes only its reviewed fields, when present. Unknown actions and some actions emitted through shared services withhold metadata.

Audit rows are append-only during normal operation. Archiving a space keeps its audit trail. A break-glass tenant purge removes the space's audit rows under the purge workflow and records the purge in the platform audit trail. Row attestation and Merkle batch retention have their own settings. See [operator environment settings](environment-operations.md) and the [audit and evidence rules](INVARIANTS.md).

## Trace a request or worker task

1. Copy the response's `X-Request-ID`. Keep the time, route and status code if you are reporting an incident.
2. Search the backend or live service logs for the ID. In JSON logs, filter on `request_id`.
3. If the request queued work, search the worker logs for the same ID. Celery copies the ID into task headers and binds it for the duration of the task.

Production defaults to JSON lines. Each record includes the UTC timestamp, severity, logger, message and request ID. `LOG_JSON` changes the format and `LOG_LEVEL` sets the minimum level, which defaults to `INFO`. A line without request context uses `-` for the request ID.

On a full VPS installation, the production Compose file rotates application container logs at 10 MB per file and keeps up to five files. The TLS Caddy overlay uses up to three 10 MB files. Cloud and Kubernetes installations use their provider's logging and retention settings. Export any incident evidence you need before it rotates.

## Keep sensitive data out of logs

Use record IDs, action keys, allowed field names and outcomes to diagnose a problem. Keep passwords, API keys, bearer tokens, provider credentials, contact details, payment routing data, and free-text member remarks out of application log messages and extra fields. The request logger redacts calendar capabilities, confirmation credentials and notification-media links. Audit projections apply their action-specific metadata rules before staff can view or export an entry.
