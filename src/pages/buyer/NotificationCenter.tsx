import { useState } from "react";

type NotificationItem = {
  id: string;
  type: string;
  title: string;
  content: string;
  read: boolean;
  createdAt: string;
  relatedType?: string;
  relatedId?: string;
};

export default function NotificationCenter({
  notifications,
  onRead,
  onReadAll,
  onOpen,
  onOpenMessages,
  conversationUnread,
}: {
  notifications: NotificationItem[];
  onRead: (ids: string[]) => void;
  onReadAll: () => void;
  onOpen: (item: NotificationItem) => void;
  onOpenMessages: () => void;
  conversationUnread: number;
}) {
  const [filter, setFilter] = useState<
    "all" | "unread" | "orders" | "after_sale" | "governance"
  >("all");
  const visible = notifications.filter(
    (item) =>
      !["buyer_message", "seller_message"].includes(item.type) &&
      (filter === "all" ||
        (filter === "unread" && !item.read) ||
        (filter === "orders" &&
          [
            "order_paid",
            "order_shipped",
            "order_completed",
            "review_reminder",
          ].includes(item.type)) ||
        (filter === "after_sale" && item.type.includes("sale")) ||
        item.type.includes("refund") ||
        item.type.includes("return") ||
        (filter === "governance" &&
          ["report_result", "appeal_result", "enforcement"].includes(
            item.type,
          ))),
  );
  return (
    <div className="container page section">
      <div className="page-title">
        <div>
          <h1>Notifications</h1>
          <p>Platform updates and conversations are kept separate.</p>
        </div>
        <div className="notification-page-actions">
          <button className="secondary" onClick={onOpenMessages}>
            Messages{conversationUnread ? ` (${conversationUnread})` : ""}
          </button>
          <button className="secondary" onClick={onReadAll}>
            Mark all as read
          </button>
        </div>
      </div>
      <div className="order-filters">
        {[
          ["all", "All"],
          ["unread", "Unread"],
          ["orders", "Orders"],
          ["after_sale", "Support"],
          ["governance", "Platform"],
        ].map(([id, label]) => (
          <button
            key={id}
            className={filter === id ? "selected" : ""}
            onClick={() => setFilter(id as typeof filter)}
          >
            {label}
          </button>
        ))}
      </div>
      <section className="messages-panel">
        {visible.map((item) => (
          <button
            className={`message-item ${item.read ? "" : "unread"}`}
            key={item.id}
            onClick={() => {
              if (!item.read) onRead([item.id]);
              onOpen(item);
            }}
          >
            <b>{item.title}</b>
            <span>{item.content}</span>
            <small>{item.createdAt}</small>
          </button>
        ))}
        {!visible.length && <p>No notifications yet.</p>}
      </section>
    </div>
  );
}


