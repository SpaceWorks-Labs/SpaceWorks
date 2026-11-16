// Parses mermaid blocks for scripts/ci/check_docs.py --mermaid.
// stdin: JSON [{f, l, t}] (file, line, text). stdout: "OK file:line" or "ERR file:line message" per block.
// Run with cwd = a folder where `npm install mermaid@11 jsdom` was run (MERMAID_DIR).
import { JSDOM } from "jsdom";

const dom = new JSDOM("<!doctype html><html><body></body></html>");
globalThis.window = dom.window;
globalThis.document = dom.window.document;
try { globalThis.navigator = dom.window.navigator; } catch { /* node already defines navigator */ }
const { default: mermaid } = await import("mermaid");
mermaid.initialize({ startOnLoad: false });

let raw = "";
for await (const chunk of process.stdin) raw += chunk;
let failed = false;
for (const { f, l, t } of JSON.parse(raw)) {
  try {
    await mermaid.parse(t);
    console.log(`OK ${f}:${l}`);
  } catch (error) {
    failed = true;
    console.log(`ERR ${f}:${l} ${String(error?.message ?? error).split("\n")[0]}`);
  }
}
process.exit(failed ? 1 : 0);
