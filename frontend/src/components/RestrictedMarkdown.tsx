import { Fragment } from "react";
import { markdownInlineTokens } from "./restrictedMarkdownTokens";

/** Deliberately small Markdown vocabulary. React escapes HTML; no HTML parser runs. */
export function RestrictedMarkdown({ text, mode }: { text: string; mode?: "restricted" | "legacy_literal" }) {
  if (mode === "legacy_literal") return <div className="whitespace-pre-wrap [overflow-wrap:anywhere]">{text}</div>;
  const inline = (line: string) => markdownInlineTokens(line).map((part, index) => {
    if (part.kind === "link") return <a className="rounded-control underline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-focus" key={index} href={part.url} rel="noopener noreferrer">{part.text}</a>;
    if (part.kind === "strong") return <strong key={index}>{part.text}</strong>;
    return <Fragment key={index}>{part.text}</Fragment>;
  });
  return <div className="grid gap-2">{text.replace(/\r\n?/g, "\n").split(/\n\s*\n/).map((paragraph, index) => {
    const lines = paragraph.split("\n");
    if (lines.every((line) => line.startsWith("- "))) return <ul key={index} className="list-disc pl-5">{lines.map((line, n) => <li key={n}>{inline(line.slice(2))}</li>)}</ul>;
    return <p key={index} className="whitespace-pre-wrap">{inline(paragraph)}</p>;
  })}</div>;
}
