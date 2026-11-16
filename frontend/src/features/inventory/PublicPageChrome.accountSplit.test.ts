import { expect, it } from "vitest";
import { publicPageChrome } from "./PublicPageChrome";

it.each(["central", "single"])("links staff to the correct tenant console in %s mode", mode => {
  const path = (part = "") => mode === "central" ? `/m/forge${part ? `/${part}` : ""}` : `/${part}`;
  const chrome = publicPageChrome("forge", "Forge", path);
  expect(chrome.footer.links.find(link => link.label === "Staff sign-in")?.href).toBe(mode === "central" ? "/m/forge/admin" : "/admin");
  expect(chrome.headerAction.href).toBe(path("member"));
});
