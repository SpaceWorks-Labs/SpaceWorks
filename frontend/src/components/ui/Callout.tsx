import { ActionControl } from "./ActionControl";
import { Icon } from "./icon";
import { toneSurfaceClasses } from "./tones";
import type { CalloutProps } from "./types";
const sizes = { banner: "min-h-13 flex-wrap items-center p-4", panel: "min-h-26 flex-wrap items-start p-5", card: "flex-col p-5", inline: "flex-wrap items-center p-3" };
export function Callout({ size, tone, lead, body, action }: CalloutProps) {
  return <div className={`relative flex min-w-0 gap-3 rounded-xl border ${toneSurfaceClasses[tone]} ${sizes[size]}`}>
    <Icon name={tone === "success" ? "CheckCircle" : tone === "danger" ? "CircleAlert" : "TriangleAlert"} />
    <div className={`min-w-0 flex-1 ${size === "panel" ? "basis-64" : ""}`}>
      <p className="text-sm"><strong>{lead}</strong>{body ? <> {body}</> : null}</p>
    </div>
    {action ? <ActionControl action={{ ...action, label: `${action.label} →` }}
      className={`border-transparent bg-transparent underline ${size === "card" ? "after:absolute after:inset-0 after:rounded-xl" : ""}`} /> : null}
  </div>;
}
