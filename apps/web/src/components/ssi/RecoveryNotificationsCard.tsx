import React from "react";
import { fetchRecoveryNotifications, markRecoveryNotificationRead } from "../../api/recovery.ts";
import { Card } from "../ui/Card.tsx";
import { Button } from "../ui/Button.tsx";
import { Badge } from "../ui/StatusBadge.tsx";
import { EmptyState, ErrorState, LoadingState } from "../ui/States.tsx";
import { useAsync } from "../../lib/useAsync.ts";
import { formatDateTime, humanize } from "../../lib/format.ts";

/** In-app notices only: no e-mail provider is configured, and this never says otherwise. */
export const RecoveryNotificationsCard: React.FC = () => {
  const items = useAsync(() => fetchRecoveryNotifications(), []);
  const onRead = async (id: string) => {
    await markRecoveryNotificationRead(id);
    items.reload();
  };
  return (
    <Card title="Recovery notices" subtitle="Shown here only. E-mail delivery is not configured." flush>
      {items.status === "loading" && <LoadingState label="Loading notices" rows={2} />}
      {items.status === "error" && <ErrorState error={items.error} title="Notices are unavailable" onRetry={items.reload} />}
      {items.status === "success" && items.data.length === 0 && <EmptyState title="No notices" />}
      {items.status === "success" && items.data.length > 0 && (
        <ul className="list-group list-group-flush" aria-label="Recovery notices">
          {items.data.slice(0, 8).map((item) => (
            <li key={item.notificationId} className="list-group-item">
              <div className="row align-items-center g-2">
                <div className="col min-w-0">
                  <div className="fw-medium">{humanize(item.eventType)}</div>
                  <div className="small text-secondary">{formatDateTime(item.createdAt)}</div>
                </div>
                <div className="col-auto">
                  {item.readAt ? <Badge tone="neutral">Read</Badge> : <Button size="sm" variant="ghost" onClick={() => onRead(item.notificationId)}>Mark read</Button>}
                </div>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
};
