import type { ComponentType } from "react";
import { privateKey, type EventScope } from "./privateQueries";

/** Route exports discard private local drafts when identity or event changes. */
export function withEventSession<P extends { scope: EventScope }>(Component: ComponentType<P>) {
  return function EventSessionBoundary(props: P) {
    return <Component key={JSON.stringify(privateKey("event-draft", props.scope))} {...props} />;
  };
}
