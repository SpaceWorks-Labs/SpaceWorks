/** Wire projection from backend/cloud_contracts/usage.py. Authorized and scoped by the server. */
export type UsageSample = {
  used: number | null;
  cap: number | null;
  unit: "bytes" | "recipients";
  state: "ok" | "warning" | "critical" | "reached" | "unknown" | "stale";
  source: string;
  cap_source: string;
  cap_verified_on: string | null;
  scope: "deployment" | "tenant" | "provider_account";
  sampled_at: string | null;
  uncertain: number;
  reason_code: string;
};
export type FreeUsage = {
  profile: "free";
  visibility: "deployment" | "tenant";
  database: UsageSample | null;
  objects: UsageSample;
  email: UsageSample;
  email_pending: number | null;
  email_uncertain: number | null;
  notification_uncertain?: number;
  email_accounts?: Array<{
    label: string; provider: string; accepted: number; reserved: number; uncertain: number;
    daily_cap: number | null; monthly_cap: number | null; monthly_charged: number;
    reset_timezone: string; provider_usage_known: boolean;
  }>;
  tick: {
    last_completed_at: string | null;
    last_contact_at: string | null;
    age_seconds: number | null;
    interval_seconds: number;
    state: "ok" | "late" | "never" | "failed" | "unknown";
    failed_tasks: number;
  };
  notices: string[];
};
export type DeploymentNoticeData = {
  mode: "host" | "managed";
  profile: "full" | "free";
  scanner: "none" | "clamav";
  media_validation_available: boolean;
};
export type DeploymentSummary = DeploymentNoticeData & {
  scope: "deployment";
  topology: string;
  database_transport: string;
  database_major: number;
  storage: Array<{ label: string; upload: "put" | "post"; versioned: boolean; object_lock: boolean }>;
  last_worker_success_at: string | null;
  last_scheduler_success_at: string | null;
  portable_dump_available: boolean;
  portable_dump_reason?: string;
  provider_recovery?: {
    database_status: "verified" | "unavailable" | "unknown";
    object_status: "verified" | "unavailable" | "unknown";
    drill_status: "verified" | "failed" | "never" | "unknown";
    last_drill_at: string | null;
    reason: string;
    runbook_url?: string;
  };
  free_usage?: FreeUsage;
};
export type TenantDeploymentSummary = DeploymentNoticeData & {
  scope: "tenant";
  objects?: UsageSample;
  deployment_warning: boolean;
};
