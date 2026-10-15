import { PublicLayout } from "../components/layouts";
import { ThemeToggle } from "../components/ThemeToggle";
import { ListRow } from "../components/ui";

export function AboutPage() {
  return <PublicLayout makerspace={{ name: "Space Works", slug: "", homeHref: "/" }}
    nav={[{ label: "Browse spaces", href: "/" }]} headerAction={{ label: "Sign in", href: "/member" }}
    liveStatus={<ThemeToggle />} width="narrow" state={{ status: "ready" }}
    header={{ eyebrow: "About", title: "Open-source makerspace management", subtitle: "Tools to run a community workshop, with care for every handover.", primary: { label: "Browse spaces", href: "/" } }}
    footer={{ credit: "Space Works · Made for shared workshops", links: [{ label: "Staff sign-in", href: "/admin" }] }}>
    <div className="space-y-5 text-base leading-7 text-muted">
      <p>Space Works brings public equipment catalogues, traceable hardware loans, 3D-print requests, and makerspace operations together.</p>
      <p>Each space controls its inventory, branding, team, and notifications. Members browse and request tools; staff review requests and record every issue and return with evidence.</p>
      <p>Free and open source under the <a className="underline decoration-line underline-offset-4 hover:text-ink focus-visible:outline-2 focus-visible:outline-focus" href="https://github.com/SpaceWorks-HQ/SpaceWorks/blob/main/LICENSE" target="_blank" rel="noreferrer">GNU Affero General Public License v3 ↗</a>. Use, study, share, and modify it under the licence terms.</p>
    </div>
    <div className="mt-8 grid gap-4">
      <ListRow title="Browse spaces" meta="Find a community workshop and explore its catalogue." href="/" right={<span aria-hidden="true">→</span>} />
      <ListRow title="Staff sign-in" meta="Open the console for your makerspace." href="/admin" right={<span aria-hidden="true">→</span>} />
    </div>
  </PublicLayout>;
}
