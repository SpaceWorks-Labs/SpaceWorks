import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(cleanup);
// Phase 8 i18n: activate the English catalogue before any component renders.
import "../lib/i18n";
