import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(cleanup);
// Phase 8 i18n: activate the English catalogue before any component renders.
import "../lib/i18n";

// The app renders under one I18nProvider (lib/I18nRoot.tsx), and a `<Trans>` message throws
// without it. Every render/renderHook in a test therefore gets the same provider around the
// test's own wrapper, so a component that moves a sentence into `<Trans>` needs no test edits.
vi.mock("@testing-library/react", async (importOriginal) => {
  const actual = await importOriginal<typeof import("@testing-library/react")>();
  const { createElement } = await import("react");
  const { I18nProvider } = await import("@lingui/react");
  const { i18n } = await import("../lib/i18n");
  type Wrapper = import("react").JSXElementConstructor<{ children: import("react").ReactNode }>;
  const withI18n = (Inner?: Wrapper): Wrapper => function I18nTestWrapper({ children }) {
    return createElement(I18nProvider, { i18n }, Inner ? createElement(Inner, null, children) : children);
  };
  return {
    ...actual,
    render: ((ui: Parameters<typeof actual.render>[0], options?: Parameters<typeof actual.render>[1]) =>
      actual.render(ui, { ...options, wrapper: withI18n(options?.wrapper as Wrapper | undefined) })) as typeof actual.render,
    renderHook: ((callback: (props: unknown) => unknown, options?: Parameters<typeof actual.renderHook>[1]) =>
      actual.renderHook(callback, { ...options, wrapper: withI18n(options?.wrapper as Wrapper | undefined) })) as typeof actual.renderHook,
  };
});
