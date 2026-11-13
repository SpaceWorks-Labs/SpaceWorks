// Device adapter media and data (decision 321): artifacts, detections, telemetry history, diagnostics, offline cache
// status and config versions. Staff routes of `apps/devices/urls_adapter.py`; each needs its child switch of
// `machines.integrations` (404 while off). Nothing here ever carries an object key or a credential digest.
import { memberRequest, staffRequest } from "../../../../../lib/api";
import type { Page } from "./adaptersApi";

export type ArtifactKind = "timelapse" | "thumbnail" | "preview" | "failure_snapshot" | "log_bundle" | "audio_recording";
export type Artifact = { id: string; binding: string; kind: ArtifactKind; content_type: string; size_bytes: number; status: "pending" | "ready" | "purged";
  service_request_id: number | null; session_id: number | null; captured_at: string; created_at: string; expires_at: string };
export type DetectionKind = "failure" | "spaghetti" | "fire" | "smoke" | "person" | "other";
export type Detection = { id: string; binding?: string; kind: DetectionKind; confidence: number; artifact_id: string | null; note?: string; observed_at: string; received_at?: string };
export type TelemetryPoint = { ts: string; avg: number; min: number; max: number; n: number };
export type Telemetry = { binding_id: string; series: string[]; selected: string; resolution: 0 | 60 | 900; points: TelemetryPoint[] };
export type ConfigVersion = { id: string; version: number; config: Record<string, unknown>; created_at: string; ack_outcome: "" | "applied" | "rejected"; ack_detail: string; acked_at: string | null };
export type OfflineCache = { version: number; entry_count: number; issued_at: string; expires_at: string; reconciled_at: string | null };
export type ArtifactUrl = { url: string; content_type: string; kind: ArtifactKind };

const send = (method: string, body?: unknown) => ({ method, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });

export const mediaKeys = {
  artifacts: (binding: string, kind: string) => ["device-adapters", "artifacts", binding, kind] as const,
  detections: (binding: string) => ["device-adapters", "detections", binding] as const,
  telemetry: (binding: string, series: string, since: string) => ["device-adapters", "telemetry", binding, series, since] as const,
  configs: (adapter: string) => ["device-adapters", "configs", adapter] as const,
  jobArtifacts: (job: number) => ["adapter-job-media", "artifacts", job] as const,
  jobDetections: (job: number) => ["adapter-job-media", "detections", job] as const,
};

export const mediaApi = {
  artifacts: (binding: string, kind: string) => staffRequest<Page<Artifact>>(`/admin/adapter-bindings/${binding}/artifacts${kind ? `?kind=${kind}` : ""}`),
  artifactUrl: (id: string) => staffRequest<ArtifactUrl>(`/admin/adapter-artifacts/${id}/url`),
  detections: (binding: string) => staffRequest<Page<Detection>>(`/admin/adapter-bindings/${binding}/detections`),
  telemetry: (binding: string, series: string, since: string) =>
    staffRequest<Telemetry>(`/admin/adapter-bindings/${binding}/telemetry?${new URLSearchParams({ ...(series ? { series } : {}), since })}`),
  requestLogBundle: (binding: string) => staffRequest<{ command_id: string; status: string }>(`/admin/adapter-bindings/${binding}/log-bundle`, send("POST")),
  configVersions: (adapter: string) => staffRequest<ConfigVersion[]>(`/admin/adapters/${adapter}/config-versions`),
  pushConfig: (adapter: string, config: Record<string, unknown>) => staffRequest<ConfigVersion>(`/admin/adapters/${adapter}/config-versions`, send("POST", { config })),
  talk: (watch: string, active: boolean) => staffRequest<{ n: number; active: boolean }>(`/member/adapter-watch/${watch}/talk`, send("POST", { active })),
  // The job owner's own routes (member session).
  jobArtifacts: (job: number) => memberRequest<Page<Artifact>>(`/member/adapter-artifacts/requests/${job}`),
  jobArtifactUrl: (id: string) => memberRequest<ArtifactUrl>(`/member/adapter-artifacts/${id}/url`),
  jobDetections: (job: number) => memberRequest<Page<Detection>>(`/member/adapter-detections/requests/${job}`),
};

/** Retention notices shown next to the data (`LIMITS` in `caps/artifact_upload.py`). */
export const ARTIFACT_DAYS: Record<ArtifactKind, number> = { timelapse: 30, thumbnail: 90, preview: 90, failure_snapshot: 30, log_bundle: 7, audio_recording: 3 };
export const AUDIO_RECORDING_DAYS = ARTIFACT_DAYS.audio_recording;

/** The extra child switches of the media/data area; all optional so older callers keep compiling. */
export type MediaSwitches = { audio?: boolean; talk?: boolean; audioRecording?: boolean; artifacts?: boolean; detections?: boolean;
  history?: boolean; diagnostics?: boolean; offlineCache?: boolean };
export const mediaSwitches = (features: string[]): MediaSwitches => {
  const on = (key: string) => features.includes(`machines.integrations.${key}`);
  return { audio: on("audio") && on("video"), talk: on("talk") && on("audio") && on("video"), audioRecording: on("audio_recording") && on("audio") && on("video") && on("recording"),
    artifacts: on("artifacts"), detections: on("detections"), history: on("telemetry_history"), diagnostics: on("diagnostics"), offlineCache: on("offline_cache") };
};
