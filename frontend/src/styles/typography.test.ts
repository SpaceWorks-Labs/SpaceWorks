/// <reference types="node" />
import { existsSync, readdirSync, readFileSync } from "node:fs";
import { expect, it } from "vitest";

it("keeps native machine strings on the Outfit text face instead of the browser monospace", () => {
  const css = readFileSync("src/index.css", "utf8");
  const declarations = css.match(/code, kbd, samp, pre\s*\{([^}]+)\}/)![1];
  const pre = css.match(/(?:^|\n)\s*pre \{([^}]+)\}/)![1];
  const sheet = document.createElement("style");
  // Exercise the actual declarations in jsdom; Vite strips CSS imports in tests.
  sheet.textContent = `code, kbd, samp, pre {${declarations}} pre {${pre}}`;
  document.head.append(sheet);
  try {
    for (const tag of ["code", "kbd", "samp", "pre"]) {
      const element = document.createElement(tag);
      element.textContent = "00O01Il JSON recovery-code";
      document.body.append(element);
      const style = getComputedStyle(element);
      expect(style.fontFamily).toMatch(/^"?Outfit/);
      expect(style.fontVariantNumeric).toBe("tabular-nums slashed-zero");
      expect(style.letterSpacing).toBe("0.02em");
      if (tag === "pre") expect(style.whiteSpace).toBe("pre-wrap");
      element.remove();
    }
  } finally { sheet.remove(); }
});

// AGPL repo (owner decision 2026-11-09): only Gilroy's free Light/ExtraBold may ship.
const COMMERCIAL_GILROY = /Gilroy-(Regular|Medium|SemiBold|Bold)\./;

it("ships only the free Gilroy weights, Outfit and Unbounded, each with its licence", () => {
  expect(readdirSync("public/fonts").filter((name) => name.endsWith(".woff2")).sort()).toEqual(
    ["Gilroy-ExtraBold.woff2", "Gilroy-Light.woff2", "Outfit-Variable.woff2", "Unbounded-Variable.woff2"]);
  for (const licence of ["Gilroy-Free-Font-EULA.txt", "OFL-Outfit.txt", "OFL-Unbounded.txt"]) {
    expect(existsSync(`public/fonts/LICENSES/${licence}`)).toBe(true);
  }
  for (const file of ["src/index.css", "index.html", "public/member-pwa/offline.css", "public/member-pwa/offline.html"]) {
    expect(readFileSync(file, "utf8")).not.toMatch(COMMERCIAL_GILROY);
  }
});

it("declares only real faces so no weight is synthesised", () => {
  const css = readFileSync("src/index.css", "utf8");
  const faces = [...css.matchAll(/@font-face\s*\{([^}]+)\}/g)].map(([, body]) => ({
    family: body.match(/font-family:\s*"([^"]+)"/)![1],
    src: body.match(/url\("([^"]+)"\)/)![1],
    weight: body.match(/font-weight:\s*([^;]+);/)![1].trim(),
  }));
  expect(faces).toEqual([
    { family: "Gilroy", src: "/fonts/Gilroy-Light.woff2", weight: "300" },
    { family: "Gilroy", src: "/fonts/Gilroy-ExtraBold.woff2", weight: "800" },
    { family: "Outfit", src: "/fonts/Outfit-Variable.woff2", weight: "100 900" },
    { family: "Unbounded", src: "/fonts/Unbounded-Variable.woff2", weight: "500 600" },
  ]);
  expect(css).toMatch(/body \{[^}]*font-family: "Outfit"[^}]*font-synthesis: none;/);
  expect(css).toMatch(/h1, h2, h3, h4, h5, h6 \{\s*font-family: "Gilroy", "Outfit"[^}]*font-weight: 800;/);
  const html = readFileSync("index.html", "utf8");
  expect([...html.matchAll(/rel="preload" href="([^"]+)"/g)].map(([, href]) => href))
    .toEqual(["/fonts/Outfit-Variable.woff2", "/fonts/Gilroy-ExtraBold.woff2"]);
});
