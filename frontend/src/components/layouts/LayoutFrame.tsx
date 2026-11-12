import { t } from "@lingui/core/macro";
import { createContext, useContext, type ReactNode } from "react";
import { EmptyState, ErrorBlock } from "../ui";
import type { LayoutStateProps } from "./types";
import "./layouts.css";
import { LogoLoader } from "../LogoLoader";

export const ContentTarget = createContext(false);
export const PublicQueryState = createContext<LayoutStateProps | undefined>(undefined);

/** Nested public layouts share one landmark and one skip destination. Inside the shell, a narrow
 * layout keeps its reading width; the shell itself caps everything else for wide monitors. */
export function LayoutFrame({ standalone = false, width = "default", children, className = "" }: {
  standalone?: boolean;
  width?: "default" | "wide" | "narrow";
  children: ReactNode;
  className?: string;
}) {
  const nested = useContext(ContentTarget);
  const ownsTarget = standalone && !nested;
  const Root = ownsTarget ? "main" : "div";
  return <ContentTarget.Provider value={true}>
    {standalone && !nested ? <a href="#main-content" className="skip-link">{t`Skip to main content`}</a> : null}
    <Root id={ownsTarget ? "main-content" : undefined} tabIndex={ownsTarget ? -1 : undefined}
      className={`${nested ? `min-w-0 ${width === "narrow" ? "mx-auto w-full max-w-[792px]" : ""}` : `sw-layout sw-layout-${width}`} ${className}`}>
      {children}
    </Root>
  </ContentTarget.Provider>;
}

export function useLayoutQuery(query: LayoutStateProps): LayoutStateProps {
  const inherited = useContext(PublicQueryState);
  return {
    state: inherited && inherited.state.status !== "ready" ? inherited.state : query.state,
    isEmpty: inherited?.isEmpty || query.isEmpty,
    empty: inherited?.isEmpty ? inherited.empty : query.empty,
  };
}

export function QueryContent({ children, ...props }: LayoutStateProps & { children: ReactNode }) {
  const { state, isEmpty, empty } = useLayoutQuery(props);
  if (state.status === "loading") return <LogoLoader label={t`Loading content`} size={48} className="min-h-24 py-3" />;
  if (state.status === "error") return <ErrorBlock error={new Error(state.error || t`Couldn't load this page. Try again.`)}
    onRetry={state.onRetry} />;
  if (isEmpty) return <EmptyState {...empty ?? { message: t`Nothing here yet.` }} />;
  return <>{children}</>;
}
