import { forwardRef, type MouseEvent } from "react";
import { Link, useHref, useNavigate, type LinkProps } from "react-router-dom";
import { canTransitionRoute, navigateWithTransition } from "./routeTransition";

const plain = (event: MouseEvent<HTMLAnchorElement>, target?: string) =>
  event.button === 0 && (!target || target === "_self") && !(event.metaKey || event.altKey || event.ctrlKey || event.shiftKey);

/** `Link` whose plain left-click navigates inside a View Transition. Everything else is the stock Link. */
export const TransitionLink = forwardRef<HTMLAnchorElement, LinkProps>(function TransitionLink({ onClick, replace, to, target, ...props }, ref) {
  const navigate = useNavigate();
  const href = useHref(to);
  return <Link ref={ref} to={to} replace={replace} target={target} {...props} onClick={event => {
    onClick?.(event);
    if (event.defaultPrevented || replace || !plain(event, target)) return;
    const from = `${window.location.pathname}${window.location.search}`;
    if (!canTransitionRoute(from, href)) return;
    event.preventDefault();
    navigateWithTransition(() => navigate(to, { state: props.state, preventScrollReset: props.preventScrollReset }), from, href);
  }} />;
});
