/// <reference types="vite/client" />

interface ImportMetaEnv {
  readonly VITE_API_URL?: string;
  readonly VITE_TENANT_TOKEN?: string;
  readonly VITE_PUBLIC_API_KEY?: string;
  readonly VITE_PUBLIC_CLIENT_ID?: string;
}

interface ImportMeta {
  readonly env: ImportMetaEnv;
}

// Lingui catalogues are imported as .po files and compiled by @lingui/vite-plugin.
declare module "*.po" {
  export const messages: import("@lingui/core").Messages;
}
