/** Hand-typed shapes for the #177-#180 stage routes (backend submissions/serializers_stages.py). */
export type ContentMode = "files_and_links" | "files_only" | "links_only" | "presentation";
export type FieldType = "short_text" | "long_text" | "choice" | "url";
export type FieldVisibility = "staff_and_judges" | "staff_only" | "public";

export type CustomField = { key: string; label: string; type: FieldType; required: boolean; choices: string[];
  help: string; visible_to: FieldVisibility };

export type StageRules = {
  name: string; description: string; opens_at: string | null; deadline: string | null; grace_minutes: number;
  late_policy: "reject" | "accept_flagged"; resubmission: "until_deadline" | "once"; requires_previous: boolean;
  content_mode: ContentMode; required_link_kinds: string[]; min_files: number; max_files: number | null;
  max_links: number | null; accepted_families: string[]; max_bytes_per_file: number | null; video_hosts: string[];
  custom_fields: CustomField[]; shortlist_after: boolean; shortlist_label: string;
  /** S18: show this stage's work in the gallery once published (only teams that passed it). */
  public_after_publish?: boolean;
};

/** A row in the editor. `id` is null for a stage that is not saved yet; `key` is a local React key. */
export type StageDraft = StageRules & { id: number | null; key: string };

export type Extension = { id: number; team_id: number; team_name?: string; until: string; reason: string; created_at: string };

export type SavedStage = StageRules & {
  id: number | null; position: number; version: number; submissions?: number; pending_triage?: number;
  shortlist?: { applied_id: number | null; published: boolean; count: number }; extensions?: Extension[]; warnings?: string[];
};

export type Preset = { key: string; name: string; description: string; requires_admission: boolean; stages: Partial<StageRules>[] };

export type StagePlan = {
  event_id: number; fingerprint: string; stages: SavedStage[]; timezone: string; event_ends_at: string;
  presets: Preset[]; families: string[]; link_kinds: string[]; video_hosts: string[]; field_types: FieldType[];
  field_visibility: FieldVisibility[]; max_stages: number; answer_limits: Record<string, number>; admission_enabled: boolean;
};

export type ShortlistEntry = { submission_id: number; team_id: number; snapshot_id: number; title: string; source_rank: number | null };
export type ShortlistPlan = { stage_id: number; source_round_id: number | null; selection: "top_n" | "manual"; top_n: number | null;
  tied_at_cutoff: boolean; fingerprint: string; entries: ShortlistEntry[]; candidates: number; not_shortlisted: number; email_enabled: boolean };
export type StageEntryRead = { submission_id: number; team_id: number; team_name: string; snapshot_id: number; triage: string;
  submitted_at: string | null };
export type Shortlist = { stage_id: number; label: string; pending_triage: number; candidates: number; email_enabled: boolean;
  stage_entries: StageEntryRead[];
  current: { id: number; selection: string; top_n: number | null; source_round_id: number | null; created_at: string;
    published_at: string | null; entries: ShortlistEntry[] } | null; allowed_actions: string[] };
export type ShortlistSelection = { selection: "top_n" | "manual"; top_n?: number; source_round_id?: number | null; submission_ids?: number[] };
