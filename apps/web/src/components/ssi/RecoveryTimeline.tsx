import React from "react";
import type { RecoveryTimelineEvent } from "../../api/recovery.ts";
import { IdentifierText } from "../ui/IdentifierText.tsx";
import { formatDateTime, humanize } from "../../lib/format.ts";

/** Audit events of one recovery request, oldest first; actor identities are not included. */
export const RecoveryTimeline: React.FC<{ events: RecoveryTimelineEvent[] }> = ({ events }) => (
  events.length === 0 ? <p className="text-secondary mb-0">No events recorded.</p> : (
    <ul className="timeline timeline-simple mb-0" aria-label="Recovery audit timeline">
      {events.map((event) => (
        <li key={event.eventId} className="timeline-event">
          <div className="card timeline-event-card">
            <div className="card-body py-2">
              <div className="text-secondary small">{formatDateTime(event.occurredAt)}</div>
              <div>{humanize(event.eventType.replace(/^RECOVERY_/, ""))}{event.decision ? ` · ${humanize(event.decision)}` : ""}</div>
              {event.guardianId && <div className="small"><IdentifierText value={event.guardianId} label="guardian ID" copy={false} /></div>}
            </div>
          </div>
        </li>
      ))}
    </ul>
  )
);
