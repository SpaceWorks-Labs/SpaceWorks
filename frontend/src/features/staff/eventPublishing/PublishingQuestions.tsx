import { EyeOff, Globe, Lock, Users } from "lucide-react";
import type { ReactNode } from "react";

export type Listing = "listed" | "unlisted";
export type PageState = "live" | "offline";
export type PublishingAnswers = {
  is_public: boolean;
  listing: Listing;
  page_state: PageState;
  registration_audience: string;
};

type Option<T> = { value: T; label: string; detail: string; icon?: ReactNode };

const AUDIENCES: Option<string>[] = [
  { value: "accounts", label: "Signed-in accounts", detail: "Anyone with an account here can sign up." },
  { value: "members", label: "Members", detail: "Only active members of this space." },
  { value: "participating_organizations", label: "Selected organizations", detail: "People in the organizations you pick." },
  { value: "invite", label: "Invitation only", detail: "Only people you invite." },
];

function RadioCards<T extends string>({ name, legend, options, value, onChange, disabled, hint }: {
  name: string; legend: string; options: Option<T>[]; value: T; onChange: (value: T) => void; disabled?: boolean; hint?: string;
}) {
  return <fieldset className="grid gap-2" disabled={disabled}>
    <legend className="mb-1 text-sm font-semibold">{legend}</legend>
    {hint ? <p className="text-sm text-muted">{hint}</p> : null}
    <div className="grid gap-2 sm:grid-cols-2">{options.map(option => <label key={option.value}
      className="flex min-h-11 cursor-pointer items-start gap-3 rounded-control border border-line p-3 text-sm has-checked:border-brand-boundary has-checked:bg-brand-soft has-disabled:cursor-not-allowed has-disabled:opacity-60">
      <input type="radio" className="mt-1" name={name} value={option.value} checked={value === option.value} onChange={() => onChange(option.value)} />
      <span className="grid gap-0.5">
        <span className="flex items-center gap-1.5 font-semibold">{option.icon}{option.label}</span>
        <span className="text-muted">{option.detail}</span>
      </span>
    </label>)}</div>
  </fieldset>;
}

/** One sentence that says who sees what, in the same words the questions use. */
export function publishingSummary(answers: PublishingAnswers, published: boolean) {
  if (!answers.is_public) return "Only your team can open this event. It is not on any public page.";
  if (published && answers.page_state === "offline") return "The public page is taken down: the link shows 'not found' until you put it back.";
  const find = answers.listing === "listed"
    ? "It is listed on the events page, Discover, organisation pages and search engines."
    : "It is hidden from every listing and from search engines; only people with the link can open it.";
  const audience = AUDIENCES.find(row => row.value === answers.registration_audience)?.label ?? answers.registration_audience;
  return `Anyone with the link can open it. ${find} Who can sign up: ${audience.toLowerCase()}.`;
}

/** The three publishing questions ("who can see / find / sign up") plus the page state. */
export function PublishingQuestions({ answers, onChange, published, idPrefix = "publishing" }: {
  answers: PublishingAnswers; onChange: (patch: Partial<PublishingAnswers>) => void; published: boolean; idPrefix?: string;
}) {
  return <div className="grid gap-5">
    <RadioCards<"private" | "public"> name={`${idPrefix}-see`} legend="1. Who can see it?" value={answers.is_public ? "public" : "private"}
      onChange={value => onChange({ is_public: value === "public" })} options={[
        { value: "private", label: "Only your team", detail: "Staff working on the event.", icon: <Lock aria-hidden="true" size={16} /> },
        { value: "public", label: "Anyone with the link", detail: "The event page is public.", icon: <Globe aria-hidden="true" size={16} /> },
      ]} />
    <RadioCards<Listing> name={`${idPrefix}-find`} legend="2. Who can find it?" value={answers.listing} disabled={!answers.is_public}
      hint={answers.is_public ? undefined : "A private event is never listed. Make it visible first."}
      onChange={listing => onChange({ listing })} options={[
        { value: "listed", label: "Listed", detail: "Events page, Discover, organisation and space pages, calendars and search engines.", icon: <Globe aria-hidden="true" size={16} /> },
        { value: "unlisted", label: "Unlisted", detail: "Only people you send the link to. Hidden from listings and search engines.", icon: <EyeOff aria-hidden="true" size={16} /> },
      ]} />
    <RadioCards<string> name={`${idPrefix}-signup`} legend="3. Who can sign up?" value={answers.registration_audience}
      onChange={registration_audience => onChange({ registration_audience })}
      options={AUDIENCES.map(row => ({ ...row, icon: <Users aria-hidden="true" size={16} /> }))} />
    {published ? <RadioCards<PageState> name={`${idPrefix}-page`} legend="Public page" value={answers.page_state}
      onChange={page_state => onChange({ page_state })} options={[
        { value: "live", label: "Up", detail: "The page and its links work." },
        { value: "offline", label: "Taken down", detail: "Hide the page without cancelling or unpublishing the event." },
      ]} /> : null}
    <p className="rounded-control bg-surface p-3 text-sm" aria-live="polite">{publishingSummary(answers, published)}</p>
  </div>;
}
