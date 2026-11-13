// Thin re-export barrel. The implementation lives in ./api/*; every existing
// `import { X } from ".../lib/api"` keeps resolving through here, and the module-level
// context-keyed sessions and tenant publishable keys live in the api submodules,
// so importing either the barrel or a submodule sees the same
// state. Exports are listed explicitly so the barrel's surface stays exactly what it was:
// ./api/client's internal helpers (publicHeaders, staffFetch, getTenantPublishableKey) are
// deliberately NOT re-exported.
export {
  API_URL,
  API_V1_URL,
  addAuthExpiredListener,
  authHeaders,
  cacheTenantPublishableKey,
  cleanupLegacyAccessToken,
  clearAccessToken,
  expireStaffAuthSession,
  getAccessToken,
  logout,
  refreshAccessToken,
  setAccessToken,
  setRuntimePublishableKey,
} from "./api/client";

export { StructuredApiError, isSurfaceOff } from "./api/errors";
export type { ApiErrorBody } from "./api/errors";

export {
  apiGet,
  downloadStaffFile,
  fetchJson,
  fetchMe,
  memberRequest,
  memberRequestBlob,
  publicV1Request,
  staffRequest,
  staffRequestBlob,
} from "./api/requests";

export {
  bootstrapTenant,
  tenantMemberRequest,
  tenantPublicRequest,
  tenantPublicRequestBlob,
} from "./api/tenant";

export type {
  PasswordLoginRequest,
  PasswordLoginRequestedSurface,
  PasswordLoginResponse,
  PasswordLoginSurface,
  StaffAuthUser,
  TenantBootstrap,
} from "./api/types";
