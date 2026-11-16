import { describe, expect, it } from "vitest";
import { linkedInUrl, type HolderCertificate } from "./certificateApi";
import { sha256Hex, shortFingerprint } from "../../events/eventPresentation/CertificateFileCheck";

const row: HolderCertificate = { id: 1, event_id: 2, event_title: "Spring Build Night", event_date: "2026-10-18T10:00:00Z",
  issuer_name: "Tinkerspace", kind: "winner", kind_title: "Winner's certificate", award: "1st place · Best design",
  status: "active", issued_at: "2026-10-20T10:00:00Z", revision: 1, serial: "6f1c2a9e-1b2c-4d5e-8f90-123456789abc",
  verifiable: true, verify_url: "https://spaceworks.example/certificates/verify/6f1c2a9e-1b2c-4d5e-8f90-123456789abc", holder_name_public: false };

describe("sharing", () => {
  it("builds LinkedIn's add-to-profile link from the certificate", () => {
    const url = new URL(linkedInUrl(row));
    expect(url.origin + url.pathname).toBe("https://www.linkedin.com/profile/add");
    expect(Object.fromEntries(url.searchParams)).toMatchObject({ startTask: "CERTIFICATION_NAME", organizationName: "Tinkerspace",
      issueYear: "2026", issueMonth: "10", certId: row.serial, certUrl: row.verify_url, name: "Winner's certificate · Spring Build Night" });
  });
  it("hashes a file in the browser and shortens the fingerprint", async () => {
    const hex = await sha256Hex(new Blob(["abc"]));
    expect(hex).toBe("ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    expect(shortFingerprint(hex)).toBe("BA78 16BF 8F01 CFEA");
  });
});
