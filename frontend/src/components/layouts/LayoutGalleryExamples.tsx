import type { ReactNode } from "react";
import { Card, Field, ScanWorkbench, StatusPill } from "../ui";
import type { QueryState } from "../ui";
import { AuthLayout, CenteredCardLayout, DashboardLayout, DetailLayout, FlowLayout, FormPageLayout,
  KioskLayout, ListLayout, PublicDetailLayout, PublicLayout, SettingsLayout } from "./index";

export const layoutGalleryExamples = ["Dashboard", "List", "Detail", "Detail drawer", "Settings", "Form", "Flow", "Flow dialog",
  "Auth", "Centered card", "Centered wide", "Public", "Public detail", "Kiosk", "Kiosk PIN", "Scan workbench"] as const;
export type LayoutGalleryExampleName = typeof layoutGalleryExamples[number];
const noop = () => {};
const identity = { kind: "icon", icon: "Wrench", tone: "accent" } as const;
const sample = <p>Sample content</p>;
const actionCard = { title: "Join the workshop", summary: "5 / 20 makers registered", primary: { label: "Register", onClick: noop },
  state: "open", mobileBar: { summary: "15 places available", label: "Join workshop" } } as const;

/** Route-free fixtures. This file is only imported by the dev gallery and tests. */
export function LayoutGalleryExample({ example, state = { status: "ready" }, isEmpty, onDismiss = noop }: {
  example: LayoutGalleryExampleName; state?: QueryState; isEmpty?: boolean; onDismiss?: () => void;
}) {
  const base = { state, isEmpty, empty: { message: "Nothing here yet. Add your first item." }, standalone: true };
  const header = { title: example, subtitle: "Everything your community needs to make." };
  const form = <Field label="Name"><input className="desk-input" defaultValue="Community workshop" required /></Field>;
  const publicDetail = <PublicDetailLayout {...base} standalone={false} title="Community workshop" tagline="Find it. Use it. Make something."
    cover={{ src: "/brand/og-1200x630.png", alt: "" }} chips={[{ label: "In person", tone: "accent" }]}
    facts={[{ identity: { kind: "date", date: "2026-10-16" }, primary: "Friday, 16 October", secondary: "9:30 AM" }]}
    sections={[{ id: "gallery-about", label: "About", content: sample }]} actionCard={actionCard}
    host={{ identity, name: "Community makerspace", href: "#host" }} />;
  let content: ReactNode;
  switch (example) {
    case "Dashboard": return <DashboardLayout {...base} header={{ ...header, eyebrow: "Good morning, Meera" }}
      progress={<Card>Finish setting up your space</Card>} stats={[{ label: "Ready for handover", value: 5 }, { label: "Tools out", value: 37 }]}
      overflowStats={{ label: "Everything else", stats: [{ label: "Members", value: 120 }] }}
      main={[{ title: "Coming up", content: sample, empty: base.empty, action: { label: "See all", href: "#all" } }]}
      rail={{ title: "Recent activity", items: [{ key: "issue", actor: "Meera", children: "issued a drill", date: "2026-10-15T10:00:00Z" }], seeAll: { label: "See all activity", href: "#activity" } }} />;
    case "List": return <ListLayout {...base} header={header} body={{ kind: "rows", rows: sample }}
      tabs={[{ key: "active", label: "Active", href: "#active", count: 5 }, { key: "history", label: "History", href: "#history" }]}
      filters={{ search: { label: "Search items", value: "", onChange: noop }, controls: <Field label="Sort"><select className="desk-input"><option>Name</option></select></Field> }}
      pagination={{ page: 1, pageSize: 24, count: 48, onChange: noop }} rail={<Card>Activity rail</Card>} />;
    case "Detail": case "Detail drawer": {
      const detail = { ...base, identity, title: "Request #1042", main: sample, aside: <Card>At a glance</Card>,
        tabs: [{ key: "overview", label: "Overview", href: "#overview" }, { key: "history", label: "History", href: "#history" }],
        status: <StatusPill label="Accepted" tone="accent" />, meta: ["Meera Nair", "5 tools"],
        danger: [{ title: "Archive request", consequence: "This request will leave the active list.", action: { label: "Archive", onClick: noop } }] };
      return example === "Detail drawer" ? <DetailLayout {...detail} presentation="drawer" open onClose={onDismiss} drawerWidth={720}
        footer={{ primary: { label: "Issue tools", onClick: noop } }} /> : <DetailLayout {...detail} back={{ label: "All requests", href: "#requests" }} />;
    }
    case "Settings": return <SettingsLayout {...base} header={header} sections={["General", "Public page", "Loans", "Notifications", "Evidence"].map((title, index) => ({
      id: `gallery-settings-${index}`, title, description: index === 0 ? "Sample content" : undefined, rows: [{ label: `${title} name`, htmlFor: `gallery-field-${index}`, children: <input id={`gallery-field-${index}`} className="desk-input w-full" defaultValue={title} /> }],
    }))} actions={{ dirty: true, onSave: noop, onDiscard: noop }}
      danger={[{ title: "Archive makerspace", consequence: "New requests will stop. Existing records remain.", action: { label: "Archive makerspace", onClick: noop } }]} />;
    case "Form": return <FormPageLayout {...base} header={header} form={<>{sample}{form}</>}
      preview={{ label: "Public page preview", content: <Card>Live preview</Card> }} submit={{ label: "Create workshop", onClick: noop }} cancel={{ label: "Cancel", href: "#cancel" }} />;
    case "Flow": case "Flow dialog": {
      const flow = { ...base, title: "Issue request #1042", subject: "Meera Nair", work: sample, current: "photo", onStepSelect: noop,
        steps: [{ key: "scan", label: "Scan box", state: "done", summary: "BOX-0042" }, { key: "photo", label: "Issue photo", state: "current", required: true }],
        footer: { back: { label: "Back", onClick: noop }, next: { label: "Issue tools", disabled: true, disabledReason: "Upload an issue photo first." } }, onCancel: onDismiss,
        leaveGuard: "Your captured evidence will be left unfinished." } as const;
      return example === "Flow dialog" ? <FlowLayout {...flow} steps={[...flow.steps]} presentation="dialog" open /> : <FlowLayout {...flow} steps={[...flow.steps]} />;
    }
    case "Auth": return <AuthLayout {...base} title="Welcome back." brand={{ showcase: <><Card>16 Oct · Community workshop</Card><Card>Meera checked in</Card></> }}
      modeSwitch={{ label: "Account access", value: "signin", options: [{ value: "signin", label: "Sign in" }, { value: "signup", label: "Create account" }], onChange: noop }}
      social={<button type="button" className="desk-button">Continue with your provider</button>} form={<>{sample}{form}</>} legal="By continuing, you agree to the terms." />;
    case "Centered card": case "Centered wide": return <CenteredCardLayout {...base} title="Confirm your email" body={sample}
      media={{ icon: "User", tone: "accent" }} width={example === "Centered wide" ? "wide" : 440}
      content={<p>Confirming meera@example.test activates your account.</p>} primary={{ label: "Confirm email", onClick: noop }} escape={{ label: "Back to sign in", href: "#signin" }} footer="Signed in as Meera" />;
    case "Public detail": return <PublicLayout {...base} makerspace={{ name: "Community makerspace", slug: "makerspace" }}
      nav={[{ label: "Tools", href: "#tools" }, { label: "Events", href: "#events" }]} width="wide" footer={{ links: [{ label: "Privacy", href: "#privacy" }] }}>{publicDetail}</PublicLayout>;
    case "Public": content = sample; break;
    case "Kiosk": return <KioskLayout {...base} context={{ identity, title: "Door check-in", subtitle: "Community workshop · Station 1" }}
      connection={{ online: false, queued: 2 }} progress={{ done: 3, of: 5, label: "checked in" }} headerActions={[{ label: "Lock station", onClick: noop }]}
      mode="work" work={{ capture: <Card>Camera capture</Card>, panel: sample, recent: <Card>Recent check-ins</Card> }} />;
    case "Kiosk PIN": return <KioskLayout {...base} context={{ identity, title: "Door check-in", subtitle: "Station 1" }}
      connection={{ online: true }} headerActions={[{ label: "Exit station", onClick: noop }]} mode="lock"
      lock={{ title: "Enter the station PIN", helper: "Ask an organiser for the PIN.", pinLength: 8, pending: false, onSubmit: noop }} />;
    case "Scan workbench": return <ListLayout {...base} header={header} body={{ kind: "rows", rows: <ScanWorkbench onFind={noop}
      result={{ tone: "success", title: "Ready to issue", summary: "Drill · BOX-0042", next: { label: "Next", onClick: noop }, undo: { label: "Undo", onClick: noop } }}
      recent={[{ key: "drill", label: "Drill found", meta: "Just now · QR", tone: "success" }]} /> }} />;
  }
  return <PublicLayout {...base} header={header} makerspace={{ name: "Community makerspace", slug: "makerspace" }}
    nav={[{ label: "Tools", href: "#tools" }, { label: "Events", href: "#events" }]} footer={{ links: [{ label: "Privacy", href: "#privacy" }] }}>{content}</PublicLayout>;
}
