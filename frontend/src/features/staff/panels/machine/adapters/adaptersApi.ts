// Device adapters (decision 312): the staff routes of `apps/devices/urls_adapter_admin.py`.
// Everything needs MANAGE_DEVICES and `machines.integrations`; the credentials routes also need
// `.access` and the watch routes `.video`. Typed refusal codes are translated in adapterErrors.ts.
import { staffRequest } from "../../../../../lib/api";
import type { Device, EnrollmentGrant } from "../../../devicesApi";
import { mediaSwitches } from "./adaptersMediaApi";

export type Capability = { name: string; version?: string | number };
export type BindingState = "idle" | "preparing" | "running" | "paused" | "finished" | "failed" | "error" | "offline" | "maintenance";
/** The normalised status of `status.item.json`: `telemetry` carries temperatures and metrics, `observed_at` is an ISO time or epoch seconds. */
/** The normalised status of `status.item.json`: `telemetry` carries temperatures and metrics; `observed_at` is an ISO time or epoch seconds. */
export type BindingStatus = { state: BindingState; observed_at: string | number; progress_percent?: number | null; eta_seconds?: number | null;
  power?: "on" | "off" | "unknown"; busy?: boolean | null; error_codes?: string[]; error_detail?: string;
  interlocks?: { enclosure_closed?: boolean | null; estop_ok?: boolean | null; filter_ok?: boolean | null }; area_clear?: boolean | null;
  telemetry?: { temperatures?: Record<string, number>; metrics?: Record<string, number> } };
export type TargetType = "machine" | "machine_type" | "storage_location" | "item" | "box" | "door" | "space";
export type EffectiveConfig = Record<string, { value: number | boolean; source: "type" | "binding" }>;
export type Page<T> = { count: number; next: string | null; previous: string | null; results: T[] };
export type Binding = { id: string; config?: SafetyConfig; effective_config?: EffectiveConfig; target_type: TargetType; machine_id: number | null; target_id: string; external_ref: string;
  capabilities: string[]; enabled: boolean; status: BindingStatus | null;
  offline_cache?: { version: number; entry_count: number; issued_at: string; expires_at: string; reconciled_at: string | null } | null };
export type AdapterSummary = { online: boolean; offline_since: string | null; id: string; name: string; status: Device["status"]; last_seen_at: string | null; adapter_kind: string | null;
  vendor: string; software_version: string; capabilities: Capability[]; config_version: number; hello_at: string | null; bindings: Binding[];
  firmware?: string; health?: "" | "ok" | "degraded" | "failing"; health_at?: string | null;
  /** Telemetry samples not stored in the last 7 days because the space reached its limit (decision 328a). */
  telemetry_dropped_7d?: number };
export type AdapterCommand = { id: string; binding: string | null; capability: string; command: string;
  status: "queued" | "leased" | "succeeded" | "failed" | "expired"; attempts: number; result_code: string; created_by: unknown;
  created_at: string; completed_at: string | null; expires_at: string | null };
export type AdapterEvent = { id: string; binding: string | null; operation_id: string; event_type: string; capability: string;
  data: Record<string, unknown>; observed_at: string; received_at: string };
export type AccessDecision = { id: string; binding: string | null; member: number | null; credential_type: string; allowed: boolean; reason: string; session_id: number | null; created_at: string };
export type UsageRecord = { id: string; binding: string | null; operation_id: string; session_id: number | null; started_at: string; ended_at: string | null;
  active_minutes: number | null; idle_minutes: number | null; outcome: string; error_code: string; consumptions: unknown; created_at: string };
export type BindingJob = { id: string; service_request_id: number | null; service_request_name: string; machine_name: string; state: "awaiting" | "reported" | "applied" | "needs_review" | "cancelled";
  telemetry_state: string; progress_percent: number | null; outcome: string | null; actual_minutes: number | null; percent_complete: number | null; failure_reason: string;
  reported_at: string | null; applied_at: string | null; created_at: string; command_status: string; command_attempts: number; command_error: string };
export type Pose = { id: string; binding: string; target_type: string; target_id: string; pose: Record<string, number | string | boolean>; note: string;
  saved_by: unknown; updated_at: string };
export type Credential = { id: string; user: unknown; kind: "nfc" | "pin"; label: string; locked_until: string | null; last_used_at: string | null;
  disabled_at: string | null; created_at: string };
export type Watch = { id: string; binding: string; status: string; record?: boolean; audio?: boolean; talk?: boolean; audio_notice_ack?: boolean; expires_at: string; created_at: string; ended_at: string | null };
export type Signal = { n: number; from: string; kind: "offer" | "answer" | "candidate" | "bye" | "ptt_on" | "ptt_off"; sdp: string; candidate: string };
export type IceServer = { urls: string[]; username?: string; credential?: string };
export type SafetyConfig = { laser_max_power_pct?: number; max_on_seconds?: number; auto_off_idle_minutes?: number; require_area_clear?: boolean; max_session_minutes?: number; require_filter_ok?: boolean; auto_apply_terminal?: boolean };
/** Defaults for every adapter binding on a machine type (`safety.profile.json`); a binding's own config overrides them. */
export type TypeProfile = Omit<SafetyConfig, "auto_apply_terminal">;
export type Webhook = { url: string; enabled: boolean; include_data: boolean; secret_version: number; consecutive_failures: number;
  disabled_at: string | null; disabled_reason: string; last_success_at: string | null; secret?: string };
export type WebhookDelivery = { id: string; type: string; status: string; attempts: number; last_status_code: number | null; last_error: string; created_at: string; delivered_at: string | null };
export type ControlCommand = "pause" | "resume" | "cancel" | "power";
export type IndicateMode = "point" | "light" | "clear";
export type BindingCreate = { target_type: TargetType; machine_id?: number; target_id?: string; external_ref?: string; capabilities: string[] };

const send = (method: string, body?: unknown) => ({ method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
const space = (id: number) => `/admin/makerspace/${id}`;

export const adapterKeys = {
  root: (space: number) => ["device-adapters", space] as const,
  list: (space: number) => ["device-adapters", space, "list"] as const,
  detail: (space: number, id: string) => ["device-adapters", space, "detail", id] as const,
  commands: (space: number, id: string) => ["device-adapters", space, "commands", id] as const,
  events: (space: number, id: string) => ["device-adapters", space, "events", id] as const,
  poses: (space: number, binding: string) => ["device-adapters", space, "poses", binding] as const,
  position: (space: number, binding: string) => ["device-adapters", space, "position", binding] as const,
  credentials: (space: number) => ["device-adapters", space, "credentials"] as const,
  webhook: (space: number, id: string) => ["device-adapters", space, "webhook", id] as const,
  deliveries: (space: number, id: string) => ["device-adapters", space, "deliveries", id] as const,
  bindingJobs: (space: number, binding: string, query: string) => ["device-adapters", space, "binding-jobs", binding, query] as const,
  access: (space: number, id: string, query: string) => ["device-adapters", space, "access", id, query] as const,
  usage: (space: number, id: string, query: string) => ["device-adapters", space, "usage", id, query] as const,
  profile: (space: number, type: number) => ["device-adapters", space, "profile", type] as const,
};

export const adaptersApi = {
  list: (makerspace: number) => staffRequest<{ results: AdapterSummary[] }>(`${space(makerspace)}/adapters`),
  detail: (id: string) => staffRequest<AdapterSummary>(`/admin/adapters/${id}`),
  enroll: (makerspace: number, name: string) => staffRequest<{ device: Device; enrollment: EnrollmentGrant }>(
    `${space(makerspace)}/devices`, send("POST", { kind: "adapter", name })),
  revoke: (id: string) => staffRequest<Device>(`/admin/devices/${id}/revoke`, send("POST")),
  bind: (adapter: string, body: BindingCreate) => staffRequest<Binding>(`/admin/adapters/${adapter}/bindings`, send("POST", body)),
  unbind: (binding: string) => staffRequest<undefined>(`/admin/adapter-bindings/${binding}`, send("DELETE")),
  commands: (id: string) => staffRequest<AdapterCommand[]>(`/admin/adapters/${id}/commands`),
  events: (id: string) => staffRequest<AdapterEvent[]>(`/admin/adapters/${id}/events`),
  command: (binding: string, capability: string, command: string, params: Record<string, unknown> = {}) =>
    staffRequest<AdapterCommand>(`/admin/adapter-bindings/${binding}/commands`, send("POST", { capability, command, params })),
  control: (binding: string, command: ControlCommand, params: Record<string, unknown> = {}) =>
    staffRequest<AdapterCommand>(`/admin/adapter-bindings/${binding}/commands`, send("POST", { capability: "control", command, params })),
  setConfig: (binding: string, config: SafetyConfig) => staffRequest<{ id: string; config: SafetyConfig; effective_config: EffectiveConfig }>(`/admin/adapter-bindings/${binding}/config`, send("PUT", config)),
  accessDecisions: (id: string, query: string) => staffRequest<Page<AccessDecision>>(`/admin/adapters/${id}/access-decisions?${query}`),
  usage: (id: string, query: string) => staffRequest<Page<UsageRecord>>(`/admin/adapters/${id}/usage?${query}`),
  bindingJobs: (binding: string, query: string) => staffRequest<Page<BindingJob>>(`/admin/adapter-bindings/${binding}/jobs?${query}`),
  dispatchJob: (binding: string, serviceRequestId: number) => staffRequest<{ job_id: string; state: string }>(`/admin/adapter-bindings/${binding}/jobs`, send("POST", { service_request_id: serviceRequestId })),
  poses: (binding: string) => staffRequest<Pose[]>(`/admin/adapter-bindings/${binding}/poses`),
  savePose: (binding: string, body: { target_type: string; target_id: string; pose: Pose["pose"]; note?: string }) =>
    staffRequest<Pose>(`/admin/adapter-bindings/${binding}/poses`, send("PUT", body)),
  clearPose: (binding: string, body: { target_type: string; target_id: string }) =>
    staffRequest<undefined>(`/admin/adapter-bindings/${binding}/poses`, send("DELETE", body)),
  aim: (binding: string, pose: Pose["pose"]) => staffRequest<AdapterCommand>(`/admin/adapter-bindings/${binding}/aim`, send("POST", { pose })),
  jog: (binding: string, body: { dx?: number; dy?: number }) => staffRequest<AdapterCommand>(`/admin/adapter-bindings/${binding}/jog`, send("POST", body)),
  position: (binding: string) => staffRequest<{ pose: Pose["pose"] | null }>(`/admin/adapter-bindings/${binding}/position`),
  indicate: (binding: string, body: { mode: IndicateMode; target_type: string; target_id: string; duration_seconds?: number }) =>
    staffRequest<AdapterCommand>(`/admin/adapter-bindings/${binding}/indicate`, send("POST", body)),
  credentials: (makerspace: number) => staffRequest<Credential[]>(`${space(makerspace)}/adapter-credentials`),
  addCredential: (makerspace: number, body: { user_id: number; kind: "nfc" | "pin"; secret: string; label?: string }) =>
    staffRequest<Credential>(`${space(makerspace)}/adapter-credentials`, send("POST", body)),
  disableCredential: (id: string) => staffRequest<Credential>(`/admin/adapter-credentials/${id}`, send("DELETE")),
  startWatch: (binding: string, reason: string, record = false, audio: WatchAudio = {}) => staffRequest<Watch>(`/admin/adapter-bindings/${binding}/watch`, send("POST", { ...(reason ? { reason } : {}), ...(record ? { record: true } : {}),
    ...(audio.listen || audio.talk ? { audio: true } : {}), ...(audio.talk ? { talk: true } : {}), ...(audio.noticeAck ? { notice_ack: true } : {}) })),
  snapshot: (watch: string) => staffRequest<AdapterCommand>(`/admin/adapter-watches/${watch}/snapshot`, send("POST")),
  endWatch: (watch: string) => staffRequest<Watch>(`/admin/adapter-watches/${watch}`, send("DELETE")),
  // The viewer routes serve whoever opened the watch: staff here, a job owner on the member job page (`memberRequest`, see MemberJobWatch).
  webhook: (id: string) => staffRequest<Webhook>(`/admin/adapters/${id}/webhook`),
  setWebhook: (id: string, body: { url: string; include_data: boolean }) => staffRequest<Webhook>(`/admin/adapters/${id}/webhook`, send("PUT", body)),
  rotateWebhook: (id: string) => staffRequest<Webhook>(`/admin/adapters/${id}/webhook/rotate`, send("POST")),
  removeWebhook: (id: string) => staffRequest<undefined>(`/admin/adapters/${id}/webhook`, send("DELETE")),
  deliveries: (id: string) => staffRequest<{ results: WebhookDelivery[] }>(`/admin/adapters/${id}/webhook/deliveries`),
  profile: (makerspace: number, type: number) => staffRequest<{ machine_type_id: number; config: TypeProfile; updated_at: string | null }>(`${space(makerspace)}/machine-types/${type}/adapter-profile`),
  setProfile: (makerspace: number, type: number, body: TypeProfile) => staffRequest<{ machine_type_id: number; config: TypeProfile }>(`${space(makerspace)}/machine-types/${type}/adapter-profile`, send("PUT", body)),
  poll: (watch: string, after: number) => staffRequest<{ signals: Signal[]; ice_servers: IceServer[]; audio?: boolean; talk?: boolean }>(`/member/adapter-watch/${watch}/signal?after=${after}`),
  signal: (watch: string, body: { kind: Signal["kind"]; sdp?: string; candidate?: string }) => staffRequest<{ n: number }>(`/member/adapter-watch/${watch}/signal`, send("POST", body)),
  frame: (watch: string) => staffRequest<{ content_type: string | null; data: string | null }>(`/member/adapter-watch/${watch}/frame`),
};

/** The child switches of `machines.integrations` that gate parts of the console. */
/** Audio choices on a watch (decision 321a): listening is receive-only; talk is staff push-to-talk; recording audio needs the notice acknowledged. */
export type WatchAudio = { listen?: boolean; talk?: boolean; noticeAck?: boolean };
export type AdapterSwitches = { access: boolean; video: boolean; recording: boolean; kiosk: boolean } & import("./adaptersMediaApi").MediaSwitches;
export const adapterSwitches = (features: string[]): AdapterSwitches => ({ access: features.includes("machines.integrations.access"),
  video: features.includes("machines.integrations.video"), kiosk: features.includes("machines.integrations.kiosk"),
  recording: features.includes("machines.integrations.video") && features.includes("machines.integrations.recording"), ...mediaSwitches(features) });
/** Recordings are deleted this many days after the watch (`RECORDING_DAYS` in the backend). */
export const RECORDING_DAYS = 7;
