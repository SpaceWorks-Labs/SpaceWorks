import { t } from "@lingui/core/macro";
import { Search, X } from "lucide-react";
import { forwardRef, useCallback, useRef, useState, type CSSProperties, type InputHTMLAttributes, type KeyboardEvent, type Ref } from "react";
import { BoxSpinner } from "../BoxSpinner";
import "./SearchField.css";

export type SearchFieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "size"> & {
  /** A query is in flight: the magnifier crossfades to the box-open spinner and back. */
  loading?: boolean;
  loadingLabel?: string;
  /** Shortcut hint chip (e.g. "Ctrl K"); fades out while the field has focus or text. */
  shortcut?: string;
  /** Grows to its slot's full width on focus; the slot keeps its width so neighbours never shift. */
  expand?: boolean;
  /** Escape clears a non-empty field (default). Off for fields where Escape closes a popup. */
  clearOnEscape?: boolean;
  /** Colour classes for the magnifier and the clear button, for fields on a filled surface. */
  adornmentClassName?: string;
  /** Keep the magnifier colour on focus (fields on a filled surface). */
  fixedIcon?: boolean;
  clearLabel?: string;
  /** Borderless, transparent input for fields that sit in a bar that supplies its own frame (command palettes). */
  bare?: boolean;
};

/* Layout utilities belong to the wrapper (the field sits inside it); everything else stays on the input. */
const LAYOUT = /^(?:[\w-]+:)*-?(?:w|min-w|max-w|flex|basis|grow|shrink|m|mt|mb|ml|mr|mx|my|ms|me|self|order|col-span)(?:-|$)/;
const PADDING_START = /^(?:[\w-]+:)*(?:pl|ps)-/;

function split(className: string) {
  const wrapper: string[] = [];
  const input: string[] = [];
  for (const token of className.split(/\s+/).filter(Boolean)) {
    if (LAYOUT.test(token)) wrapper.push(token);
    else if (!PADDING_START.test(token) && token !== "desk-input") input.push(token);
  }
  return { wrapper: wrapper.join(" "), input: input.join(" ") };
}

/** Inline style for the n-th suggestion row: the first six stagger 20 ms apart. */
export function searchItemStyle(index: number): CSSProperties {
  return { "--sw-i": Math.min(index, 5) } as CSSProperties;
}

/** The one search input in the app: magnifier, focus easing, loading swap, clear button, Escape. */
export const SearchField = forwardRef<HTMLInputElement, SearchFieldProps>(function SearchField({
  loading = false, loadingLabel, shortcut, expand = false, clearOnEscape = true, adornmentClassName = "", fixedIcon = false,
  clearLabel, bare = false, className = "", value, defaultValue, onChange, onKeyDown, disabled, readOnly, ...rest
}, forwarded: Ref<HTMLInputElement>) {
  const inner = useRef<HTMLInputElement | null>(null);
  const [local, setLocal] = useState(String(defaultValue ?? ""));
  const text = value !== undefined ? String(value) : local;
  const parts = split(className);
  const setRef = useCallback((node: HTMLInputElement | null) => {
    inner.current = node;
    if (typeof forwarded === "function") forwarded(node);
    else if (forwarded) (forwarded as { current: HTMLInputElement | null }).current = node;
  }, [forwarded]);

  const clear = () => {
    const input = inner.current;
    if (!input) return;
    // Drive the native setter + an input event so React fires the call site's own onChange (controlled or not).
    Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, "value")?.set?.call(input, "");
    input.dispatchEvent(new Event("input", { bubbles: true }));
    input.focus();
  };
  const keyDown = (event: KeyboardEvent<HTMLInputElement>) => {
    onKeyDown?.(event);
    if (event.defaultPrevented || event.key !== "Escape" || !clearOnEscape || !text || disabled || readOnly) return;
    event.preventDefault();
    event.stopPropagation();
    clear();
  };
  const canClear = text.length > 0 && !disabled && !readOnly;
  const field = <span className={`sw-search ${expand ? "" : parts.wrapper}`} data-expand={expand ? "" : undefined} data-bare={bare ? "" : undefined} data-loading={loading ? "" : undefined}>
    <span className={`sw-search-icon ${adornmentClassName}`} data-loading={loading ? "" : undefined} data-fixed={fixedIcon ? "" : undefined}>
      <Search aria-hidden="true" size={18} className="sw-search-glyph" />
      {loading ? <span className="sw-search-spin"><BoxSpinner label={loadingLabel ?? t`Searching…`} size={16} mono /></span> : null}
    </span>
    <input {...rest} ref={setRef} type="search" className={`${bare ? "sw-search-bare" : "desk-input"} sw-search-input w-full min-w-0 ${parts.input}`} value={value} defaultValue={defaultValue}
      disabled={disabled} readOnly={readOnly}
      onChange={event => { setLocal(event.target.value); onChange?.(event); }} onKeyDown={keyDown} />
    {canClear ? <button type="button" tabIndex={-1} aria-label={clearLabel ?? t`Clear search`} className={`sw-search-clear ${adornmentClassName}`}
      onMouseDown={event => event.preventDefault()} onClick={clear}><X aria-hidden="true" size={16} /></button> : null}
    {shortcut ? <kbd className="sw-search-kbd code-text text-xs text-muted" data-text={text ? "" : undefined} aria-hidden="true">{shortcut}</kbd> : null}
  </span>;
  return expand ? <span className={`sw-search-slot ${parts.wrapper}`}>{field}</span> : field;
});
