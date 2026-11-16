import { BoxSpinner } from "../BoxSpinner";

/** Kept for existing callers: the inline loading state is now the Space Works box. */
export function Spinner({ label, size = 24 }: { label?: string; size?: number }) {
  return <BoxSpinner label={label} size={size} className="text-muted" />;
}
