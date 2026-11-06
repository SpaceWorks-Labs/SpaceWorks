import { useState } from "react";
import { CollapsibleSection } from "../../components/ui";
import { ChatTemplateList } from "./platformParity/ChatTemplatesSection";

/** A Space Manager's own chat message templates: one message per event, shared by every chat room (#190 follow-up). */
export function SpaceChatTemplates({ makerspace }: { makerspace: { id: number; name: string } }) {
  const [open, setOpen] = useState(false);
  return <div className="py-4">
    <CollapsibleSection title="Chat message templates" open={open} onToggle={() => setOpen(!open)}>
      <div className="grid gap-3">
        <p className="text-sm text-muted">Change what your chat rooms (Telegram, Slack, Mattermost, Discord) are told for an event. Chat is a staff
          room, so never put member-facing details in it. Messages use Django template syntax; removing one goes back to the built-in text.</p>
        {open ? <ChatTemplateList space={{ id: makerspace.id, name: makerspace.name }} surface="space" /> : null}
      </div>
    </CollapsibleSection>
  </div>;
}
