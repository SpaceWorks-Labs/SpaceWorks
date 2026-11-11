import { t } from "@lingui/core/macro";
import { Check, Copy } from "lucide-react";
import { lazy, Suspense, useEffect, useId, useRef, useState } from "react";
import "./docs.css";

const MermaidDiagram = lazy(() => import("./MermaidDiagram").then(m => ({ default: m.MermaidDiagram })));

// Code-block language names are technical product names, the same in every locale.
// i18n-ignore: language names (Bash, PowerShell, JSON…) are not translated
const LANGUAGE_LABELS: Record<string, string> = Object.fromEntries("sh=Shell|bash=Bash|shell=Shell|zsh=Zsh|console=Console|powershell=PowerShell|ps1=PowerShell|pwsh=PowerShell|cmd=Command Prompt|bat=Batch|batch=Batch|js=JavaScript|javascript=JavaScript|ts=TypeScript|typescript=TypeScript|tsx=TSX|json=JSON|yaml=YAML|yml=YAML|toml=TOML|py=Python|python=Python|sql=SQL|http=HTTP|nginx=nginx|ini=INI|env=.env|dotenv=.env|dockerfile=Dockerfile|caddyfile=Caddyfile|html=HTML|css=CSS|xml=XML|text=Text|txt=Text".split("|").map(pair => pair.split("=") as [string, string]));

export function languageLabel(language: string) {
  return LANGUAGE_LABELS[language.toLowerCase()] ?? (language ? language : t`Code`);
}

export function CopyButton({ text, label = t`Copy code` }: { text: string; label?: string }) {
  const [copied, setCopied] = useState(false);
  const timer = useRef<number | undefined>(undefined);
  useEffect(() => () => window.clearTimeout(timer.current), []);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      window.clearTimeout(timer.current);
      timer.current = window.setTimeout(() => setCopied(false), 2000);
    } catch { setCopied(false); }
  };
  return <button type="button" className="sw-doc-copy" onClick={() => { void copy(); }} aria-label={copied ? t`Copied` : label}>
    {copied ? <Check size={16} aria-hidden="true" /> : <Copy size={16} aria-hidden="true" />}
    <span aria-live="polite">{copied ? t`Copied` : t`Copy`}</span>
  </button>;
}

export function CodeBlock({ language, code }: { language: string; code: string }) {
  if (language.toLowerCase() === "mermaid") {
    return <Suspense fallback={<pre className="sw-doc-pre"><code>{code}</code></pre>}><MermaidDiagram code={code} /></Suspense>;
  }
  return <figure className="sw-doc-code">
    <figcaption className="sw-doc-code-bar">
      <span className="sw-doc-code-lang">{languageLabel(language)}</span>
      <CopyButton text={code} />
    </figcaption>
    <pre className="sw-doc-pre" tabIndex={0}><code className={language ? `language-${language}` : undefined}>{code}</code></pre>
  </figure>;
}

export type CodeTab = { language: string; title?: string; code: string };

/** Adjacent shell blocks (bash + PowerShell…) as one block with a tab per language (WAI-ARIA tabs). */
export function CodeTabs({ tabs }: { tabs: CodeTab[] }) {
  const [active, setActive] = useState(0);
  const base = useId();
  const refs = useRef<(HTMLButtonElement | null)[]>([]);
  const move = (index: number) => { const next = (index + tabs.length) % tabs.length; setActive(next); refs.current[next]?.focus(); };
  const current = tabs[active];
  return <figure className="sw-doc-code">
    <figcaption className="sw-doc-code-bar">
      <div role="tablist" aria-label={t`Code language`} className="flex min-w-0 gap-1 overflow-x-auto">
        {tabs.map((tab, index) => <button key={`${tab.language}-${index}`} ref={node => { refs.current[index] = node; }} type="button" role="tab"
          id={`${base}-tab-${index}`} aria-selected={index === active} aria-controls={`${base}-panel`} tabIndex={index === active ? 0 : -1}
          className="sw-doc-tab" onClick={() => setActive(index)}
          onKeyDown={event => {
            if (event.key === "ArrowRight") { event.preventDefault(); move(index + 1); }
            if (event.key === "ArrowLeft") { event.preventDefault(); move(index - 1); }
            if (event.key === "Home") { event.preventDefault(); move(0); }
            if (event.key === "End") { event.preventDefault(); move(tabs.length - 1); }
          }}>{tab.title || languageLabel(tab.language)}</button>)}
      </div>
      <CopyButton text={current.code} />
    </figcaption>
    <pre className="sw-doc-pre" id={`${base}-panel`} role="tabpanel" aria-labelledby={`${base}-tab-${active}`} tabIndex={0}>
      <code className={`language-${current.language}`}>{current.code}</code></pre>
  </figure>;
}
