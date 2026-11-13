import { readFileSync, readdirSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { describe, expect, it } from "vitest";

// A stylesheet imported from a component module can be injected before src/index.css. If it opens an
// `@layer`, the browser fixes the layer order from that first sheet (components before base), so Tailwind's
// base reset beats every component class: buttons lose padding, colour and radius site-wide (decision 421).
const SRC = join(process.cwd(), "src");

function files(dir: string): string[] {
  return readdirSync(dir).flatMap(name => {
    const path = join(dir, name);
    return statSync(path).isDirectory() ? (name === "generated" ? [] : files(path)) : [path];
  });
}

describe("CSS layer order", () => {
  it("no component module imports a stylesheet that opens a CSS layer", () => {
    const offenders: string[] = [];
    for (const file of files(SRC).filter(f => /\.(ts|tsx)$/.test(f) && !/\.test\.tsx?$/.test(f))) {
      const source = readFileSync(file, "utf8");
      for (const match of source.matchAll(/^\s*import\s+["']([^"']+\.css)["'];?/gm)) {
        const css = resolve(dirname(file), match[1]);
        if (css === join(SRC, "index.css")) continue; // the entry stylesheet itself declares the order
        if (/@layer\b/.test(readFileSync(css, "utf8"))) offenders.push(`${file.slice(SRC.length + 1)} -> ${match[1]}`);
      }
    }
    expect(offenders).toEqual([]);
  });

  it("index.css declares the Tailwind layers before importing layered component CSS", () => {
    const index = readFileSync(join(SRC, "index.css"), "utf8");
    expect(index.indexOf('@import "tailwindcss"')).toBeGreaterThanOrEqual(0);
    expect(index.indexOf('@import "./components/ui/SearchField.css"')).toBeGreaterThan(index.indexOf('@import "tailwindcss"'));
  });
});
