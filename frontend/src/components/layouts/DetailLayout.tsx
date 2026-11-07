import { t } from "@lingui/core/macro";
import type { ReactNode } from "react";
import { ActionControl, Callout, DangerZone, DetailDrawer, PageHeader, Tabs } from "../ui";
import type { Action, CalloutProps, DangerZoneProps, Identity, SecondaryAction, Tab } from "../ui";
import { LayoutFrame, QueryContent } from "./LayoutFrame";
import type { LayoutProps } from "./types";

type Presentation = { presentation?: "page"; open?: never; onClose?: never; drawerWidth?: never }
  | { presentation: "drawer"; open: boolean; onClose: () => void; drawerWidth?: 640 | 720 };
export type DetailLayoutProps = LayoutProps & Presentation & {
  back?: Action;
  identity?: Identity;
  title: string;
  status?: ReactNode;
  meta?: ReactNode[];
  actions?: { primary?: Action & { targetsTab?: string }; secondary?: SecondaryAction; overflow?: Action[] };
  banner?: CalloutProps;
  tabs?: Tab[];
  activeTab?: string;
  onTabChange?: (key: string) => void;
  main: ReactNode;
  aside?: ReactNode;
  asideSide?: "start" | "end";
  footer?: { primary?: Action; secondary?: Action[] };
  danger?: DangerZoneProps[];
};

export function DetailLayout(props: DetailLayoutProps) {
  const { presentation = "page", back, identity, title, status, meta, actions, banner, tabs, activeTab, onTabChange,
    main, aside, asideSide = "end", footer, danger = [], standalone, width, state, isEmpty, empty } = props;
  const primary = actions?.primary?.targetsTab && actions.primary.targetsTab === activeTab ? undefined : actions?.primary;
  const panel = <>
    <QueryContent state={state} isEmpty={isEmpty} empty={empty}>
      <div className="grid min-w-0 gap-6">
        {banner ? <Callout {...banner} /> : null}
        <div className={aside ? `sw-detail-columns ${asideSide === "start" ? "sw-detail-start" : ""}` : "min-w-0"}>
          <div className="min-w-0">{main}{danger.map(zone => <DangerZone key={zone.title} {...zone} />)}</div>
          {aside ? <aside aria-label={t`At a glance`} className="min-w-0">{aside}</aside> : null}
        </div>
      </div>
      {presentation === "drawer" && footer ? <div className="sw-sticky-footer mt-6 flex flex-wrap justify-end gap-2 border-t border-line bg-panel pt-4">
        {footer.secondary?.map(action => <ActionControl key={action.label} action={action} />)}
        {footer.primary ? <ActionControl action={footer.primary} primary /> : null}
      </div> : null}
    </QueryContent>
  </>;
  const content = <LayoutFrame standalone={presentation === "page" && standalone} width={width} className={presentation === "drawer" ? "sw-overlay-content" : ""}>
    <PageHeader headingLevel={presentation === "drawer" ? 2 : 1} title={title} identity={identity} status={status} back={presentation === "page" ? back : undefined}
      meta={meta?.map((part, index) => <span key={index}>{index ? <span aria-hidden="true"> · </span> : null}{part}</span>)}
      primary={primary} secondary={actions?.secondary} overflow={actions?.overflow} />
    {tabs?.length ? <Tabs tabs={tabs} activeKey={activeTab ?? tabs[0].key} onChange={onTabChange}>{panel}</Tabs> : panel}
  </LayoutFrame>;
  return props.presentation === "drawer" ? <div className={`sw-detail-drawer sw-detail-drawer-${props.drawerWidth ?? 640}`}>
    <DetailDrawer open={props.open} title={title} onClose={props.onClose}>{content}</DetailDrawer>
  </div> : content;
}
