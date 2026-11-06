import { t } from "@lingui/core/macro";
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
const sample = <p>{t`Sample content`}</p>;
const actionCard = { title: t`Join the workshop`, summary: t`5 / 20 makers registered`, primary: { label: t`Register`, onClick: noop },
  state: "open", mobileBar: { summary: t`15 places available`, label: t`Join workshop` } } as const;

/** Route-free fixtures. This file is only imported by the dev gallery and tests. */
export function LayoutGalleryExample({ example, state = { status: "ready" }, isEmpty, onDismiss = noop }: {
  example: LayoutGalleryExampleName; state?: QueryState; isEmpty?: boolean; onDismiss?: () => void;
}) {
  const base = { state, isEmpty, empty: { message: t`Nothing here yet. Add your first item.` }, standalone: true };
  const header = { title: example, subtitle: t`Everything your community needs to make.` };
  const form = <Field label={t`Name`}><input className="desk-input" defaultValue="Community workshop" required /></Field>;
  const publicDetail = <PublicDetailLayout {...base} standalone={false} title={t`Community workshop`} tagline="Find it. Use it. Make something."
    cover={{ src: "/brand/og-1200x630.png", alt: "" }} chips={[{ label: t`In person`, tone: "accent" }]}
    facts={[{ identity: { kind: "date", date: "2026-10-16" }, primary: "Friday, 16 October", secondary: "9:30 AM" }]}
    sections={[{ id: "gallery-about", label: t`About`, content: sample }]} actionCard={actionCard}
    host={{ identity, name: "Community makerspace", href: "#host" }} />;
  let content: ReactNode;
  switch (example) {
    case "Dashboard": return <DashboardLayout {...base} header={{ ...header, eyebrow: t`Good morning, Meera` }}
      progress={<Card>{t`Finish setting up your space`}</Card>} stats={[{ label: t`Ready for handover`, value: 5 }, { label: t`Tools out`, value: 37 }]}
      overflowStats={{ label: t`Everything else`, stats: [{ label: t`Members`, value: 120 }] }}
      main={[{ title: t`Coming up`, content: sample, empty: base.empty, action: { label: t`See all`, href: "#all" } }]}
      rail={{ title: t`Recent activity`, items: [{ key: "issue", actor: "Meera", children: "issued a drill", date: "2026-10-15T10:00:00Z" }], seeAll: { label: t`See all activity`, href: "#activity" } }} />;
    case "List": return <ListLayout {...base} header={header} body={{ kind: "rows", rows: sample }}
      tabs={[{ key: "active", label: t`Active`, href: "#active", count: 5 }, { key: "history", label: t`History`, href: "#history" }]}
      filters={{ search: { label: t`Search items`, value: "", onChange: noop }, controls: <Field label={t`Sort`}><select className="desk-input"><option>{t`Name`}</option></select></Field> }}
      pagination={{ page: 1, pageSize: 24, count: 48, onChange: noop }} rail={<Card>{t`Activity rail`}</Card>} />;
    case "Detail": case "Detail drawer": {
      const detail = { ...base, identity, title: t`Request #1042`, main: sample, aside: <Card>{t`At a glance`}</Card>,
        tabs: [{ key: "overview", label: t`Overview`, href: "#overview" }, { key: "history", label: t`History`, href: "#history" }],
        status: <StatusPill label={t`Accepted`} tone="accent" />, meta: ["Meera Nair", "5 tools"],
        danger: [{ title: t`Archive request`, consequence: "This request will leave the active list.", action: { label: t`Archive`, onClick: noop } }] };
      return example === "Detail drawer" ? <DetailLayout {...detail} presentation="drawer" open onClose={onDismiss} drawerWidth={720}
        footer={{ primary: { label: t`Issue tools`, onClick: noop } }} /> : <DetailLayout {...detail} back={{ label: t`All requests`, href: "#requests" }} />;
    }
    case "Settings": return <SettingsLayout {...base} header={header} sections={["General", "Public page", "Loans", "Notifications", "Evidence"].map((title, index) => ({
      id: `gallery-settings-${index}`, title, description: index === 0 ? t`Sample content` : undefined, rows: [{ label: `${title} name`, htmlFor: `gallery-field-${index}`, children: <input id={`gallery-field-${index}`} className="desk-input w-full" defaultValue={title} /> }],
    }))} actions={{ dirty: true, onSave: noop, onDiscard: noop }}
      danger={[{ title: t`Archive makerspace`, consequence: "New requests will stop. Existing records remain.", action: { label: t`Archive makerspace`, onClick: noop } }]} />;
    case "Form": return <FormPageLayout {...base} header={header} form={<>{sample}{form}</>}
      preview={{ label: t`Public page preview`, content: <Card>{t`Live preview`}</Card> }} submit={{ label: t`Create workshop`, onClick: noop }} cancel={{ label: t`Cancel`, href: "#cancel" }} />;
    case "Flow": case "Flow dialog": {
      const flow = { ...base, title: t`Issue request #1042`, subject: "Meera Nair", work: sample, current: "photo", onStepSelect: noop,
        steps: [{ key: "scan", label: t`Scan box`, state: "done", summary: t`BOX-0042` }, { key: "photo", label: t`Issue photo`, state: "current", required: true }],
        footer: { back: { label: t`Back`, onClick: noop }, next: { label: t`Issue tools`, disabled: true, disabledReason: "Upload an issue photo first." } }, onCancel: onDismiss,
        leaveGuard: "Your captured evidence will be left unfinished." } as const;
      return example === "Flow dialog" ? <FlowLayout {...flow} steps={[...flow.steps]} presentation="dialog" open /> : <FlowLayout {...flow} steps={[...flow.steps]} />;
    }
    case "Auth": return <AuthLayout {...base} title={t`Welcome back.`} brand={{ showcase: <><Card>{t`16 Oct · Community workshop`}</Card><Card>{t`Meera checked in`}</Card></> }}
      modeSwitch={{ label: t`Account access`, value: "signin", options: [{ value: "signin", label: t`Sign in` }, { value: "signup", label: t`Create account` }], onChange: noop }}
      social={<button type="button" className="desk-button">{t`Continue with your provider`}</button>} form={<>{sample}{form}</>} legal="By continuing, you agree to the terms." />;
    case "Centered card": case "Centered wide": return <CenteredCardLayout {...base} title={t`Confirm your email`} body={sample}
      media={{ icon: "User", tone: "accent" }} width={example === "Centered wide" ? "wide" : 440}
      content={<p>{t`Confirming meera@example.test activates your account.`}</p>} primary={{ label: t`Confirm email`, onClick: noop }} escape={{ label: t`Back to sign in`, href: "#signin" }} footer="Signed in as Meera" />;
    case "Public detail": return <PublicLayout {...base} makerspace={{ name: "Community makerspace", slug: "makerspace" }}
      nav={[{ label: t`Tools`, href: "#tools" }, { label: t`Events`, href: "#events" }]} width="wide" footer={{ links: [{ label: t`Privacy`, href: "#privacy" }] }}>{publicDetail}</PublicLayout>;
    case "Public": content = sample; break;
    case "Kiosk": return <KioskLayout {...base} context={{ identity, title: t`Door check-in`, subtitle: t`Community workshop · Station 1` }}
      connection={{ online: false, queued: 2 }} progress={{ done: 3, of: 5, label: t`checked in` }} headerActions={[{ label: t`Lock station`, onClick: noop }]}
      mode="work" work={{ capture: <Card>{t`Camera capture`}</Card>, panel: sample, recent: <Card>{t`Recent check-ins`}</Card> }} />;
    case "Kiosk PIN": return <KioskLayout {...base} context={{ identity, title: t`Door check-in`, subtitle: t`Station 1` }}
      connection={{ online: true }} headerActions={[{ label: t`Exit station`, onClick: noop }]} mode="lock"
      lock={{ title: t`Enter the station PIN`, helper: "Ask an organiser for the PIN.", pinLength: 8, pending: false, onSubmit: noop }} />;
    case "Scan workbench": return <ListLayout {...base} header={header} body={{ kind: "rows", rows: <ScanWorkbench onFind={noop}
      result={{ tone: "success", title: t`Ready to issue`, summary: t`Drill · BOX-0042`, next: { label: t`Next`, onClick: noop }, undo: { label: t`Undo`, onClick: noop } }}
      recent={[{ key: "drill", label: t`Drill found`, meta: "Just now · QR", tone: "success" }]} /> }} />;
  }
  return <PublicLayout {...base} header={header} makerspace={{ name: "Community makerspace", slug: "makerspace" }}
    nav={[{ label: t`Tools`, href: "#tools" }, { label: t`Events`, href: "#events" }]} footer={{ links: [{ label: t`Privacy`, href: "#privacy" }] }}>{content}</PublicLayout>;
}
