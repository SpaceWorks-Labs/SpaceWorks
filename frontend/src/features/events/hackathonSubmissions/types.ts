export type SubmissionScope = { makerspaceId: number; eventId: number; teamId: number; accountId: number };
export type Declaration = { used: boolean; details: string };
export type ProjectLink = { kind: "repo" | "demo" | "video" | "slides" | "cad" | "pcb" | "firmware" | "other"; url: string; public_requested: boolean };
export type Project = {
  title: string; tagline: string; problem: string; description: string; challenges: string;
  tech_tags: string[]; ai_declaration: Declaration; reuse_declaration: Declaration;
  public_requested: boolean; track_ids: number[]; prize_ids: number[]; asset_ids: number[]; public_asset_ids: number[];
  form_answers: Record<string, unknown>; links: ProjectLink[];
};
/** The server's JSON project has a domain-specific validated editor projection. */
export type Submission = Omit<import('../../../generated/api').ProjectResponse, 'project'> & { project: Partial<Project> };
export type Asset = import('../../../generated/api').AssetResponse;
export type UploadSpec = { group: string; subtype: string };
export type UploadDescriptor = import('../../../generated/api').UploadDescriptor;
export type UploadResult = import('../../../generated/api').UploadResponse;
export type PreviewMesh = { positions: Float32Array; normals?: Float32Array };
export type PreviewResult = { kind: "mesh"; meshes: PreviewMesh[] } | { kind: "svg"; svg: string };
