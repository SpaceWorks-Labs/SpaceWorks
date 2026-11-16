import { describe, expect, it } from "vitest";

import { lookDocument } from "./certificateLooks";
import { certificateStudioValues, compileCertificateV2, LEGACY_ARTWORK, stockForSize } from "./certificateLayout";
import type { LayerDocument } from "./layout";

const v2: LayerDocument = { version: 2, page_width_mm: 297, page_height_mm: 210, layers: [
  { id: "b", order: 1, type: "certificate_qr", x_mm: 250, y_mm: 170, width_mm: 24, height_mm: 24, rotation: 0 },
  { id: "a", order: 0, type: "text", x_mm: 20, y_mm: 20, width_mm: 100, height_mm: 12, rotation: 0, opacity: 0.5, font_family: "Gilroy",
    text: "{{name}} at {{event}} on {{eventDate}} ({{crewRole}})", colour_token: "teal", font_size_pt: 20, font_weight: 700 },
  { id: "s", order: 2, type: "signature", x_mm: 40, y_mm: 140, width_mm: 60, height_mm: 24, rotation: 0, signature_slot: 2 },
  { id: "i", order: 3, type: "image", x_mm: 10, y_mm: 10, width_mm: 30, height_mm: 30, rotation: 0, resource_id: "r-1" },
] };

describe("compileCertificateV2 (twin of certificate_compile.compile_v2)", () => {
  const document = compileCertificateV2(v2, true);
  it("makes a v3 certificate document marked as compiled from v2", () => {
    expect(document.version).toBe(3);
    expect(document.kind).toBe("certificate");
    expect(document.source).toEqual({ kind: "certificate_v2" });
    expect(document.stock).toBe("a4-landscape");
  });
  it("orders layers by their v2 order and maps units and tags", () => {
    expect(document.front.layers.map((layer) => layer.id)).toEqual(["a", "b", "s", "i"]);
    const text = document.front.layers[0];
    expect(text.w_mm).toBe(100);
    expect(text.opacity).toBe(50);
    expect(text.colour).toBe("#006E63");
    expect(text.font_family).toBe("Outfit");
    expect(text.text).toBe("{{name}} at {{event}} on {{event_date}} ({{role}})");
  });
  it("maps signatures, the verify QR and resource images", () => {
    const [, qr, signature, image] = document.front.layers;
    expect(qr.kind).toBe("verify_qr");
    expect([signature.kind, signature.signatory_slot]).toEqual(["signature", 2]);
    expect([image.kind, image.asset_id]).toEqual(["image", "r-1"]);
  });
  it("shows the legacy artwork as the background only when there is one", () => {
    expect(document.front.background).toMatchObject({ kind: "image", asset_id: LEGACY_ARTWORK });
    expect(compileCertificateV2(v2, false).front.background.kind).toBe("colour");
  });
  it("keeps a custom page size", () => {
    const custom = compileCertificateV2({ ...v2, page_width_mm: 250, page_height_mm: 180 });
    expect([custom.stock, custom.page_width_mm, custom.page_height_mm]).toEqual(["custom", 250, 180]);
    expect(stockForSize(215.9, 279.4)).toBe("letter-portrait");
  });
});

describe("built-in certificate looks (server-owned)", () => {
  it("unwraps a template detail row or a bare document and always marks it a v3 certificate", () => {
    const document = { version: 3, kind: "certificate", stock: "a4-landscape" } as never;
    expect(lookDocument({ document })).toBe(document);
    expect(lookDocument(document)).toBe(document);
  });
});

describe("certificateStudioValues", () => {
  it("carries the certificate tags and only the signatories that exist", () => {
    const values = certificateStudioValues("Priya Raman", "winner", { 1: { name: "A. Director", title: "Director" } });
    expect(values.recipient).toBe("Priya Raman");
    expect([values.first_name, values.last_name]).toEqual(["Priya", "Raman"]);
    expect(values.serial_short).toHaveLength(8);
    expect(values.signatory_1_name).toBe("A. Director");
    expect(values.signatory_2_name).toBe("");
  });
});
