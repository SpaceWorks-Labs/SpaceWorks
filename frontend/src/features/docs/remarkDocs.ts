import type { Blockquote, Code, Nodes, Parent, Root } from "mdast";
import { createSlugger } from "./docsSource";

// One pass over the parsed Markdown before it becomes React:
//   - every heading gets the anchor the build-time index computed for it (same slugger, same order);
//   - "> **Note** …", "> **Warning:** …", "> **Tip** …" and GitHub "> [!NOTE]" quotes become callouts;
//   - adjacent shell blocks in different languages (bash + powershell…) become one tabbed block.

export const CALLOUT_KINDS = ["note", "tip", "important", "warning", "caution"] as const;
export type CalloutKind = (typeof CALLOUT_KINDS)[number];

const SHELLS = new Set(["bash", "sh", "shell", "zsh", "console", "powershell", "ps1", "pwsh", "cmd", "bat", "batch"]);

function textOf(node: Nodes): string {
  if ("value" in node && typeof node.value === "string" && node.type !== "html") return node.value;
  return "children" in node ? (node.children as Nodes[]).map(textOf).join("") : "";
}

function calloutKind(word: string): CalloutKind | null {
  const value = word.toLowerCase().replace(/[:.!]$/, "").trim();
  if (value === "danger") return "caution";
  return (CALLOUT_KINDS as readonly string[]).includes(value) ? value as CalloutKind : null;
}

function markCallout(quote: Blockquote) {
  const first = quote.children[0];
  if (first?.type !== "paragraph" || !first.children.length) return;
  const lead = first.children[0];
  let kind: CalloutKind | null = null;
  if (lead.type === "strong") {
    kind = calloutKind(textOf(lead));
    if (kind) {
      first.children.shift();
      const after = first.children[0];
      if (after?.type === "text") after.value = after.value.replace(/^\s*:?\s*/, "");
    }
  } else if (lead.type === "text") {
    const alert = /^\[!(\w+)\]\s*/.exec(lead.value);
    kind = alert ? calloutKind(alert[1]) : null;
    if (kind && alert) lead.value = lead.value.slice(alert[0].length);
  }
  if (!kind) return;
  if (first.children.length === 0 || (first.children.length === 1 && textOf(first).trim() === "")) quote.children.shift();
  quote.data = { ...quote.data, hProperties: { ...(quote.data?.hProperties ?? {}), dataCallout: kind } };
}

function groupShellTabs(parent: Parent) {
  const children = parent.children as Nodes[];
  for (let start = 0; start < children.length; start++) {
    const run: Code[] = [];
    for (let index = start; index < children.length; index++) {
      const node = children[index];
      if (node.type !== "code" || !SHELLS.has((node.lang ?? "").toLowerCase())) break;
      if (run.some(code => code.lang?.toLowerCase() === node.lang?.toLowerCase())) break;
      run.push(node);
    }
    if (run.length < 2) continue;
    const group = { type: "codeTabs", children: run, data: { hName: "div", hProperties: { dataCodeTabs: "" } } };
    children.splice(start, run.length, group as unknown as Nodes);
  }
}

export function remarkDocs() {
  return (tree: Root) => {
    const slug = createSlugger();
    const visit = (node: Nodes) => {
      if (node.type === "heading") {
        const id = slug(textOf(node));
        node.data = { ...node.data, hProperties: { ...(node.data?.hProperties ?? {}), id } };
      }
      if (node.type === "blockquote") markCallout(node);
      if ("children" in node && (node.type as string) !== "codeTabs") {
        groupShellTabs(node as Parent);
        for (const child of node.children as Nodes[]) visit(child);
      }
    };
    visit(tree);
  };
}

