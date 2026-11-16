/** A project row in the profile form. `id` is absent until the first save. Links are https-only (the server returns 400 otherwise). */
export type ProjectDraft = {
  id?: number;
  title: string;
  subtitle?: string;
  tags?: string[];
  public_visible?: boolean;
  description: string;
  links: { label: string; url: string }[];
};
