import { useId } from "react";
import { CenteredCardLayout, type CenteredCardLayoutProps } from "../../components/layouts";
import { ActionControl } from "../../components/ui";

/**
 * One sign-in step (email verification, two-step code, recovery codes). On its own it is a whole
 * page; embedded inside another page's card it keeps the same body and actions but drops the page
 * chrome — no logo, no h1 — so the host page keeps its single page heading.
 */
export function AuthStepCard({ embedded = false, ...props }: CenteredCardLayoutProps & { embedded?: boolean }) {
  const titleId = useId();
  if (!embedded) return <CenteredCardLayout {...props} />;
  const { title, body, content, primary, escape, footer } = props;
  return <section aria-labelledby={titleId} className="grid gap-4">
    <h3 id={titleId} className="title-section">{title}</h3>
    <div className="text-sm text-muted">{body}</div>
    {content}
    <ActionControl action={primary} primary className="w-full" />
    {escape ? <ActionControl action={escape} className="w-full border-transparent underline" /> : null}
    {footer ? <div className="border-t border-line pt-4 text-sm text-muted">{footer}</div> : null}
  </section>;
}
