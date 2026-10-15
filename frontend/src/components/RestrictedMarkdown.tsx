import { Fragment } from "react";

/** Deliberately small Markdown vocabulary. React escapes HTML; no HTML parser runs. */
export function RestrictedMarkdown({ text }: { text: string }) {
  const inline = (line: string) => line.split(/(\[[^\]\n]{1,200}\]\(https?:\/\/[^\s)]+\)|\*\*[^*\n]+\*\*)/g).map((part, index) => {
    const link = /^\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)$/.exec(part);
    if (link) return <a className="underline" key={index} href={link[2]} rel="noopener noreferrer">{link[1]}</a>;
    if (part.startsWith("**") && part.endsWith("**")) return <strong key={index}>{part.slice(2, -2)}</strong>;
    return <Fragment key={index}>{part}</Fragment>;
  });
  return <div className="grid gap-2">{text.split(/\n\s*\n/).map((paragraph, index) => {
    const lines = paragraph.split("\n");
    if (lines.every((line) => line.startsWith("- "))) return <ul key={index} className="list-disc pl-5">{lines.map((line, n) => <li key={n}>{inline(line.slice(2))}</li>)}</ul>;
    return <p key={index} className="whitespace-pre-wrap">{inline(paragraph)}</p>;
  })}</div>;
}
