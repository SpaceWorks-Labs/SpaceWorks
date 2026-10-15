import { useId, type ReactNode } from "react";
import { ActionControl } from "./ActionControl";
import { Icon } from "./icon";
import type { Action } from "./types";

export type ResultPanelProps = {
  tone: "success" | "warn" | "danger";
  title: string;
  summary?: ReactNode;
  children?: ReactNode;
  next: Action;
  undo?: Action;
};
const colours = { success: "border-transparent bg-success text-on-success", warn: "border-transparent bg-warn text-on-warn",
  danger: "border-danger-line bg-danger text-on-danger" };
const icons = { success: "CheckCircle", warn: "TriangleAlert", danger: "CircleAlert" } as const;
export function ResultPanel({ tone, title, summary, children, next, undo }: ResultPanelProps) {
  const id = useId();
  return <section aria-labelledby={id} className={`grid min-w-0 gap-6 rounded-xl border p-6 md:p-8 ${colours[tone]}`}>
    <div role={tone === "danger" ? "alert" : "status"} aria-atomic="true" className="grid gap-4">
      <Icon name={icons[tone]} className="h-16 w-16" /><h2 id={id} className="break-words font-display text-3xl md:text-4xl">{title}</h2>
      {summary ? <div className="text-lg">{summary}</div> : null}
    </div>
    {children}
    <div className="flex flex-wrap gap-3"><ActionControl action={next} className="flex-1" />
      {undo ? <ActionControl action={undo} /> : null}</div>
  </section>;
}
