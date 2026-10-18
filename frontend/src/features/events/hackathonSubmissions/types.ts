export type SubmissionScope = { makerspaceId: number; eventId: number; teamId: number; accountId: number };
export type Declaration = { used: boolean; details: string };
export type ProjectLink = { kind: "repo" | "demo" | "video" | "slides" | "cad" | "pcb" | "firmware" | "other"; url: string; public_requested: boolean };
export type Project = {
  title: string; tagline: string; problem: string; description: string; challenges: string;
  tech_tags: string[]; ai_declaration: Declaration; reuse_declaration: Declaration;
  public_requested: boolean; track_ids: number[]; prize_ids: number[]; asset_ids: number[]; public_asset_ids: number[];
  form_answers: Record<string, unknown>; links: ProjectLink[];
};
export type Submission = { id: number | null; event_id: number; version: number; state: string;
  snapshot_id: number | null; project: Partial<Project>; allowed_actions: string[] };
export type Asset = { asset_id: number; event_id: number; version: number; generation: number;
  state: string; bytes: number; mime: string; sha256: string; expires_at: string | null; allowed_actions: string[];
  filename?: string; extension?: string; kind?: string; media_metadata?: { browser_playable?: boolean } };
export type UploadSpec = { group: string; subtype: string };
export type UploadDescriptor = { method: "POST"; url: string; fields: Record<string, string>; expires_at: string }
  | { method: "MULTIPART"; part_size: number; part_count: number; expires_at?: string };
export type UploadResult = Asset & { upload?: UploadDescriptor };
export type PreviewMesh = { positions: Float32Array; normals?: Float32Array };
export type PreviewResult = { kind: "mesh"; meshes: PreviewMesh[] } | { kind: "svg"; svg: string };
