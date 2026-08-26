import { useEffect, useState, type FormEvent } from "react";

type SupportTicket = {
  id: string;
  subject: string;
  status: string;
  priority: string;
  createdAt: string;
  updatedAt: string;
};

export default function SupportDialog({
  apiBase,
  onClose,
}: {
  apiBase: string;
  onClose: () => void;
}) {
  const [subject, setSubject] = useState("");
  const [content, setContent] = useState("");
  const [priority, setPriority] = useState("normal");
  const [tickets, setTickets] = useState<SupportTicket[]>([]);
  const [notice, setNotice] = useState("");

  const loadTickets = async () => {
    const response = await fetch(`${apiBase}/api/support/tickets`, {
      credentials: "include",
    });
    const payload = (await response.json().catch(() => ({}))) as {
      tickets?: SupportTicket[];
      error?: string;
    };
    if (!response.ok) {
      setNotice(payload.error || "Support requests could not be loaded");
      return;
    }
    setTickets(payload.tickets || []);
  };

  useEffect(() => {
    void loadTickets();
  }, []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    const trimmedSubject = subject.trim();
    const trimmedContent = content.trim();
    if (!trimmedSubject || !trimmedContent) {
      setNotice("Please provide a subject and a detailed description");
      return;
    }
    const response = await fetch(`${apiBase}/api/support/tickets`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        subject: trimmedSubject,
        content: trimmedContent,
        priority,
      }),
    });
    const payload = (await response.json().catch(() => ({}))) as {
      error?: string;
    };
    if (!response.ok) {
      setNotice(payload.error || "Support request could not be submitted");
      return;
    }
    setSubject("");
    setContent("");
    setPriority("normal");
    setNotice("Your support request has been submitted. We will get back to you soon.");
    void loadTickets();
  };

  return (
    <div
      className="support-dialog-backdrop"
      role="presentation"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget) onClose();
      }}
    >
      <section
        className="support-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="support-dialog-title"
      >
        <header>
          <div>
            <p className="eyebrow">PLATFORM SUPPORT</p>
            <h2 id="support-dialog-title">Contact support</h2>
          </div>
          <button type="button" className="community-dialog-close" onClick={onClose}>
            Close
          </button>
        </header>
        <p className="support-dialog-intro">
          Have a question about the platform, an order, or your account? Send us a support request.
        </p>
        {notice && <p className="support-dialog-notice">{notice}</p>}
        <form onSubmit={submit}>
          <label>
            Subject
            <input
              value={subject}
              maxLength={120}
              onChange={(event) => setSubject(event.target.value)}
              placeholder="e.g. I need help with an order payment"
            />
          </label>
          <label>
            How can we help?
            <textarea
              value={content}
              maxLength={1000}
              onChange={(event) => setContent(event.target.value)}
              placeholder="Tell us what happened"
            />
          </label>
          <label>
            Priority
            <select value={priority} onChange={(event) => setPriority(event.target.value)}>
              <option value="low">Low</option>
              <option value="normal">Normal</option>
              <option value="high">High</option>
              <option value="urgent">Urgent</option>
            </select>
          </label>
          <footer>
            <button type="button" className="secondary" onClick={onClose}>
              Cancel
            </button>
            <button className="primary">Submit request</button>
          </footer>
        </form>
        <div className="support-ticket-history">
          <h3>My support requests</h3>
          {tickets.length ? (
            tickets.slice(0, 8).map((ticket) => (
              <div key={ticket.id}>
                <span>
                  <b>{ticket.subject}</b>
                  <small>{ticket.createdAt}</small>
                </span>
                <em>{ticket.status}</em>
              </div>
            ))
          ) : (
            <p>No support requests yet.</p>
          )}
        </div>
      </section>
    </div>
  );
}
