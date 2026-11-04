import type { ReactNode } from "react";
import type { EmptyProps, QueryState } from "../ui";

/** Callers own server state; layouts only decide how to display it. */
export type LayoutStateProps = {
  state: QueryState;
  isEmpty?: boolean;
  empty?: EmptyProps;
};

export type LayoutProps = LayoutStateProps & {
  /** true outside a shell; false uses the shell's main landmark. */
  standalone?: boolean;
  /** Default content is capped at 1120px; wide uses the available width. */
  width?: "default" | "wide";
};

export type ContentSection = { id: string; label: string; content: ReactNode };
