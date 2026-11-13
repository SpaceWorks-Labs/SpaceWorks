// The language switcher (phase 8 i18n, #75g): a compact menu in the public header and the
// staff/member shells, and a plain select in member account settings. It lists the locale
// registry, so an English-only deployment shows one "English" entry and no dead affordance.
// A choice is stored in this browser as the explicit locale; where `onPersist` is given (a
// signed-in account) it is also saved as the account preference. With more than one locale,
// signed-in people can return to the space default (null).
import { t } from "@lingui/core/macro";
import { Languages } from "lucide-react";
import { useEffect, useId, useRef, useState, useSyncExternalStore, type KeyboardEvent } from "react";
import { SUPPORTED_LOCALES, type LocaleCode } from "../../generated/locales";
import { activeLocale, localeSource, onLocaleChange, setExplicitLocale } from "../../lib/i18n";
import { focusRing } from "./types";

type Choice = { code: LocaleCode | null; label: string };
type Props = { variant?: "menu" | "select"; onPersist?: (code: LocaleCode | null) => Promise<unknown> };

const snapshot = () => `${activeLocale()}|${localeSource()}`;

function useLocaleState() {
  const value = useSyncExternalStore(onLocaleChange, snapshot, snapshot);
  const [code, source] = value.split("|") as [LocaleCode, string];
  return { code, source };
}

export function LanguageSwitcher({ variant = "menu", onPersist }: Props) {
  const { code, source } = useLocaleState();
  const [error, setError] = useState("");
  const choices: Choice[] = [
    ...SUPPORTED_LOCALES.map((locale) => ({ code: locale.code as LocaleCode, label: locale.label })),
    ...(onPersist && SUPPORTED_LOCALES.length > 1 ? [{ code: null, label: t`Use the space's default` }] : []),
  ];
  const selected = source === "explicit" || !onPersist || SUPPORTED_LOCALES.length === 1 ? code : null;
  const choose = async (next: LocaleCode | null) => {
    setError("");
    setExplicitLocale(next);
    try {
      await onPersist?.(next);
    } catch {
      setError(t`Your language could not be saved to your account. It still applies in this browser.`);
    }
  };
  const current = SUPPORTED_LOCALES.find((locale) => locale.code === code)?.label ?? code;
  if (variant === "select") {
    return <div className="grid gap-1">
      <label className="grid gap-1 text-sm font-semibold text-ink">{t`Language`}
        <select className={`min-h-11 rounded-control border border-line bg-panel px-3 text-ink ${focusRing}`}
          value={selected ?? ""} onChange={(event) => void choose(event.target.value ? event.target.value as LocaleCode : null)}>
          {choices.map((choice) => <option key={choice.code ?? "default"} value={choice.code ?? ""} lang={choice.code ?? undefined}>{choice.label}</option>)}
        </select>
      </label>
      {error ? <p role="alert" className="text-sm text-danger">{error}</p> : null}
    </div>;
  }
  return <LanguageMenu choices={choices} selected={selected} current={current} onChoose={choose} error={error} />;
}

function LanguageMenu({ choices, selected, current, onChoose, error }: {
  choices: Choice[]; selected: LocaleCode | null; current: string; error: string;
  onChoose: (code: LocaleCode | null) => Promise<void>;
}) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const trigger = useRef<HTMLButtonElement>(null);
  const items = useRef<(HTMLButtonElement | null)[]>([]);
  const id = useId();
  useEffect(() => {
    if (!open) return;
    const index = Math.max(0, choices.findIndex((choice) => choice.code === selected));
    items.current[index]?.focus();
    const outside = (event: PointerEvent) => { if (event.target instanceof Node && !root.current?.contains(event.target)) setOpen(false); };
    document.addEventListener("pointerdown", outside);
    return () => document.removeEventListener("pointerdown", outside);
  }, [open, choices, selected]);
  const close = () => { setOpen(false); trigger.current?.focus(); };
  const onKeyDown = (event: KeyboardEvent) => {
    const focused = items.current.findIndex((item) => item === document.activeElement);
    const move = (index: number) => { event.preventDefault(); items.current[(index + choices.length) % choices.length]?.focus(); };
    if (event.key === "Escape") { event.preventDefault(); close(); }
    else if (event.key === "ArrowDown") move(focused + 1);
    else if (event.key === "ArrowUp") move(focused - 1);
    else if (event.key === "Home") move(0);
    else if (event.key === "End") move(choices.length - 1);
    else if (event.key === "Tab") setOpen(false);
  };
  return <div ref={root} className="relative inline-flex" onKeyDown={open ? onKeyDown : undefined}>
    <button ref={trigger} type="button" aria-haspopup="menu" aria-expanded={open} aria-controls={id}
      className={`desk-button min-h-11 min-w-11 justify-center gap-2 px-2 ${focusRing}`} title={t`Language: ${current}`}
      onClick={() => setOpen(!open)}
      onKeyDown={(event) => { if (event.key === "ArrowDown" && !open) { event.preventDefault(); setOpen(true); } }}>
      <Languages aria-hidden="true" size={18} />
      <span className="sr-only">{t`Language: ${current}`}</span>
    </button>
    {open ? <div id={id} role="menu" aria-label={t`Choose a language`}
      className="absolute right-0 top-full z-40 mt-2 grid w-56 max-w-[calc(100vw-2rem)] gap-1 rounded-xl border border-line bg-panel p-2 text-ink shadow-overlay">
      {choices.map((choice, index) => <button key={choice.code ?? "default"} ref={(node) => { items.current[index] = node; }}
        type="button" role="menuitemradio" aria-checked={choice.code === selected} lang={choice.code ?? undefined}
        className={`flex min-h-11 w-full items-center justify-between rounded-control px-3 text-left hover:bg-surface ${focusRing}`}
        onClick={() => { void onChoose(choice.code); close(); }}>
        <span>{choice.label}</span>{choice.code === selected ? <span aria-hidden="true">✓</span> : null}
      </button>)}
    </div> : null}
    {error ? <p role="alert" className="sr-only">{error}</p> : null}
  </div>;
}
