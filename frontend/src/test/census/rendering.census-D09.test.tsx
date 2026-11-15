import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it } from "vitest";
import { RestrictedMarkdown } from "../../components/RestrictedMarkdown";
import { LogoLoader } from "../../components/LogoLoader";
import { BoxSpinner } from "../../components/BoxSpinner";
import { DocsMarkdown } from "../../features/docs/DocsMarkdown";
import { LegalMarkdown } from "../../features/legal/LegalMarkdown";
import { safeSvg } from "../../features/events/hackathonSubmissions/AssetPreview";
import { sanitizeSvg } from "../../features/staff/panels/machine/filePreview/svgFile";
import { PreviewPane } from "../../features/staff/panels/EmailTemplateEditorParts";

const MARKUP = '<script>alert("D09")</script><img src=x onerror=alert("D09")>';
const UNICODE = "\u202e\u2066\u200b\u200d\u0645\u0631\u062d\u0628\u0627\u{1f527}";
const TEXT = [
  { name: "markup", value: MARKUP }, { name: "nul", value: "before\0after" },
  { name: "unicode", value: UNICODE }, { name: "posix", value: "../../etc/passwd" },
  { name: "windows", value: "..\\..\\Windows\\system.ini" },
  { name: "megabyte", value: "X".repeat(1_048_576) },
];

function expectNoExecutableContent(container: HTMLElement) {
  expect(container.querySelectorAll("script,img,iframe,object,embed,foreignObject")).toHaveLength(0);
  expect(Array.from(container.querySelectorAll("*")).flatMap(node => Array.from(node.attributes)
    .filter(attr => /^on/i.test(attr.name) || /^(?:javascript|data):/i.test(attr.value)))).toEqual([]);
}

describe("D09 actual text renderers", () => {
  for (const mode of ["restricted", "legacy_literal"] as const) {
    it.each(TEXT)(`keeps hostile $name literal in ${mode} markdown`, ({ value }) => {
      const { container } = render(<RestrictedMarkdown text={value} mode={mode} />);
      expectNoExecutableContent(container);
      expect(container.textContent).toBe(value);
    });
  }

  // Decision 575 requires raw HTML source to be omitted as well as inert.
  // Keep the security, Unicode and presentation regressions independently asserted.
  for (const [kind, defect] of [["legal", "CENSUS-D09-5"], ["docs", "CENSUS-D09-6"]] as const) {
    it(`keeps ${kind} markdown inert and preserves Unicode`, () => {
      const { container } = render(<MemoryRouter>{kind === "legal"
        ? <LegalMarkdown body={`${MARKUP}\n\n${UNICODE}`} />
        : <DocsMarkdown body={`${MARKUP}\n\n${UNICODE}`} source="D09.md" index={[]} />}</MemoryRouter>);
      expectNoExecutableContent(container);
      expect(container.textContent).toContain(UNICODE);
    });
    it(`${defect}: does not display raw HTML source in ${kind} markdown (decision 575)`, () => {
      const { container } = render(<MemoryRouter>{kind === "legal"
        ? <LegalMarkdown body={`${MARKUP}\n\n${UNICODE}`} />
        : <DocsMarkdown body={`${MARKUP}\n\n${UNICODE}`} source="D09.md" index={[]} />}</MemoryRouter>);
      expect(container.textContent).not.toContain(MARKUP);
    });
  }

  it.each(["loader", "spinner"])("keeps %s labels outside the constant SVG HTML sink", kind => {
    const { container } = render(kind === "loader" ? <LogoLoader label={MARKUP} showLabel /> : <BoxSpinner label={MARKUP} />);
    expectNoExecutableContent(container);
    expect(screen.getByRole("status").getAttribute("aria-label")).toBe(MARKUP);
    expect(screen.getByText(MARKUP).textContent).toBe(MARKUP);
  });

  it("isolates accepted email HTML in a sandbox and keeps subject/plain text literal", () => {
    const { container } = render(<PreviewPane loading={false} error={null}
      preview={{ subject: MARKUP, text_body: MARKUP, html_body: MARKUP }} />);
    const frame = container.querySelector("iframe");
    expect(frame?.getAttribute("sandbox")).toBe("");
    expect(frame?.getAttribute("srcdoc")).toBe(MARKUP);
    expect(container.querySelectorAll("script,img")).toHaveLength(0);
    expect(Array.from(container.querySelectorAll("pre"), node => node.textContent)).toEqual([MARKUP, MARKUP]);
  });
});

const SVG_ATTACKS = [
  '<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script></svg>',
  '<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"><path onmouseover="alert(1)"/></svg>',
  '<svg xmlns="http://www.w3.org/2000/svg"><use href="javascript:alert(1)"/></svg>',
  '<svg xmlns="http://www.w3.org/2000/svg"><foreignObject><iframe/></foreignObject></svg>',
  '<svg xmlns="http://www.w3.org/2000/svg"><path fill="url(https://evil.example/x)"/></svg>',
];

describe("D09 every SVG parser identified by the source census", () => {
  it.each(SVG_ATTACKS)("refuses hostile preview SVG exactly: %s", value => {
    expect(() => safeSvg(value)).toThrow("Unsafe preview output.");
  });

  it.each(SVG_ATTACKS)("removes active content from member SVG: %s", value => {
    const output = sanitizeSvg(value);
    const doc = new DOMParser().parseFromString(output, "image/svg+xml");
    expect(doc.querySelectorAll("parsererror,script,foreignObject,iframe")).toHaveLength(0);
    expect(Array.from(doc.querySelectorAll("*")).flatMap(node => Array.from(node.attributes)
      .filter(attr => /^on/i.test(attr.name) || /javascript:|https:\/\/evil|url\(https:/i.test(attr.value)))).toEqual([]);
  });

  it.each(["strict", "sanitized"])("preserves allowed Unicode SVG text through the %s parser", kind => {
    const value = `<svg xmlns="http://www.w3.org/2000/svg"><title>${UNICODE}</title><path d="M0 0"/></svg>`;
    const output = kind === "strict" ? safeSvg(value) : sanitizeSvg(value);
    const doc = new DOMParser().parseFromString(output, "image/svg+xml");
    expect(doc.querySelector("title")?.textContent).toBe(UNICODE);
    expect(Array.from(doc.querySelectorAll("*"), node => node.localName)).toEqual(["svg", "title", "path"]);
  });
});
