import type { KeyAction, KeyJob } from "./spaceKeysApi";

export const KEY_ACTIONS: { action: KeyAction; label: string; message: string; needsPii?: boolean }[] = [
  { action: "rotate_dek", label: "Rotate the data key", needsPii: true,
    message: "A new data key is used for every write at once; older records are re-encrypted in the background, then the old key is retired." },
  { action: "emergency_rekey", label: "Emergency re-key", needsPii: true,
    message: "For a suspected key leak: the same rotation, and the space's managers are told when it starts and finishes." },
  { action: "rotate_search_key", label: "Rotate the search key", needsPii: true,
    message: "A new search key is used at once and the space's search index is rebuilt in the background." },
  { action: "rotate_publishable_key", label: "Rotate the browser key",
    message: "The public site gets a new browser key now. The old one keeps working for the grace period so the site can be redeployed." },
];

export const JOB_LABELS: Record<KeyJob["kind"], string> = {
  rotation: "Key rotation", emergency_rekey: "Emergency re-key", search_reindex: "Search key rotation",
};
