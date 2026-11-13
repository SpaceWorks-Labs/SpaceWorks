/**
 * A skip link to the next section, hidden until focused (the app's `.skip-link`). It moves focus as
 * well as scroll, so the next Tab continues from the section it lands on. `onJump` lets the pinned hero
 * land at the end of its own scroll distance; it returns false when the page is static, and the link
 * then scrolls the target into view itself.
 */
export function SkipAhead({ target, label, onJump }: { target: string; label: string; onJump?: () => boolean }) {
  return <a href={`#${target}`} className="skip-link" onClick={event => {
    const node = document.getElementById(target);
    if (!node) return;
    event.preventDefault();
    if (!onJump?.()) node.scrollIntoView?.({ block: "start" });
    if (!node.hasAttribute("tabindex")) node.setAttribute("tabindex", "-1");
    node.focus({ preventScroll: true });
  }}>{label}</a>;
}
