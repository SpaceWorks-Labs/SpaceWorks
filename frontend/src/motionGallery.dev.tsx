// Dev-only entry for /motion-gallery.html (`npm run dev`): AppShell, a Modal and toasts without a login,
// for checking motion by eye. Like gallery.html it is not an entry of the production build.
import "./lib/i18n";
import { t } from "@lingui/core/macro";
import { useState } from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Route, Routes, useLocation } from "react-router-dom";
import { Boxes, ClipboardList, Cog, Home, Package, Users } from "lucide-react";
import { AppShell } from "./components/shell";
import type { ShellSection } from "./components/shell/types";
import { Modal } from "./components/ui/Modal";
import { ToastHost } from "./components/ui/ToastHost";
import { toast } from "./components/ui/toastStore";
import { ActionControl } from "./components/ui/ActionControl";
import { BoxArt, BoxSpinner } from "./components/BoxSpinner";
import { LogoLoader } from "./components/LogoLoader";
import { RouteTransitionGate } from "./lib/motion";
import { initializeTheme } from "./lib/theme";
import "./index.css";
initializeTheme();

const item = (key: string, label: string, icon: typeof Home) => ({ key, label, icon, href: `/${key}` });
const nav: ShellSection[] = [{ key: "main", label: t`Workspace`, items: [item("home", t`Home`, Home), item("inventory", t`Inventory`, Package), item("requests", t`Requests`, ClipboardList), item("members", t`Members`, Users)],
  more: [item("machines", t`Machines`, Cog), item("kits", t`Kits`, Boxes), item("reports", t`Reports`, Package)] }];

function Page() {
  const { pathname } = useLocation();
  const [open, setOpen] = useState(false);
  return <div className="grid gap-4">
    <h1 className="text-heading">{pathname.replace("/", "") || "home"}</h1>
    <p className="max-w-prose text-muted">{t`Content for ${pathname}. Open the dialog or raise a toast to see their motion.`}</p>
    <div className="flex gap-2"><button type="button" className="desk-button" onClick={() => setOpen(true)}>{t`Open dialog`}</button>
      <button type="button" className="desk-button" onClick={() => toast(t`Saved the change`, { duration: 2500 })}>{t`Raise toast`}</button></div>
    <Modal open={open} onClose={() => setOpen(false)} title={t`Example dialog`} footer={<button type="button" className="desk-button-primary" onClick={() => setOpen(false)}>{t`Done`}</button>}>
      <p>{t`Dialog body.`}</p></Modal>
    <Loaders />
  </div>;
}

const BUTTONS = ["desk-button", "desk-button-primary", "desk-button-brand", "desk-button-success", "desk-button-danger", "desk-button-emphasis", "desk-button-warn"];
/** Pending states on every button style, plus the page and inline loaders (shown on every page). */
function Loaders() {
  return <div className="grid gap-4" data-testid="loaders">
    <div className="grid gap-2">{BUTTONS.map(style => <div key={style} className="flex flex-wrap items-center gap-3">
      <ActionControl className={style} action={{ label: style, pending: true, pendingLabel: t`Saving…` }} />
      <button type="button" className={style}><BoxArt size={16} mono />{t`Saving…`}</button>
    </div>)}</div>
    <div className="flex items-center gap-4"><BoxSpinner size={16} /><BoxSpinner size={24} /></div>
    <LogoLoader label={t`Loading`} showLabel />
  </div>;
}

function Gallery() {
  const { pathname } = useLocation();
  const activeKey = pathname.split("/")[1] || "home";
  return <AppShell variant="staff" compactNav="drawer" nav={nav} activeKey={activeKey}
    workspace={{ name: t`Demo Makerspace`, subtitle: t`Dev gallery`, avatar: { kind: "avatar", name: "Demo Makerspace", seed: "dm" } }}
    search={{ label: t`Search`, shortcut: "mod+k", onOpen: () => undefined }}
    user={{ name: t`Demo Admin`, role: t`Space Manager`, menu: [] }}>
    <Routes><Route path="*" element={<Page />} /></Routes>
  </AppShell>;
}

ReactDOM.createRoot(document.getElementById("root") as HTMLElement).render(
  <BrowserRouter basename="/motion-gallery.html"><RouteTransitionGate /><ToastHost /><Gallery /></BrowserRouter>,
);
