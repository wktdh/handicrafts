import { useEffect, useState } from "react";

const API_BASE =
  (import.meta as ImportMeta & { env?: { VITE_API_BASE?: string } }).env
    ?.VITE_API_BASE ?? "";

export default function AdminServiceManagement() {
  type Application = {
    id: string;
    seller: string;
    legalName: string;
    contactPhone: string;
    status: string;
    reviewNote?: string;
    evidence: string[];
    expiresAt?: string | null;
    supplementDueAt?: string | null;
    documents?: {
      id: string;
      type: string;
      url: string;
      status: string;
      reviewNote?: string;
    }[];
  };
  type Ticket = {
    id: string;
    subject: string;
    status: string;
    priority: string;
    buyer: string;
    assignee?: string;
  };
  type Report = {
    id: string;
    reason: string;
    status: string;
    reporter: string;
    targetType: string;
    targetId: string;
  };
  const [applications, setApplications] = useState<Application[]>([]);
  const [tickets, setTickets] = useState<Ticket[]>([]);
  const [reports, setReports] = useState<Report[]>([]);
  const [caseDetail, setCaseDetail] = useState<{
    case: { type: string; id: string; title: string; status: string };
    timeline: {
      type: string;
      content: string;
      actor: string;
      createdAt: string;
    }[];
  } | null>(null);
  const [note, setNote] = useState("");
  const [notice, setNotice] = useState("");
  const load = async () => {
    const [applicationsResponse, ticketsResponse, reportsResponse] =
      await Promise.all([
        fetch(`${API_BASE}/api/admin/seller-verifications`, {
          credentials: "include",
        }),
        fetch(`${API_BASE}/api/admin/support/tickets`, {
          credentials: "include",
        }),
        fetch(`${API_BASE}/api/admin/reports`, { credentials: "include" }),
      ]);
    if (applicationsResponse.ok)
      setApplications(
        ((await applicationsResponse.json()) as { applications: Application[] })
          .applications || [],
      );
    if (ticketsResponse.ok)
      setTickets(
        ((await ticketsResponse.json()) as { tickets: Ticket[] }).tickets || [],
      );
    if (reportsResponse.ok)
      setReports(
        ((await reportsResponse.json()) as { reports: Report[] }).reports || [],
      );
  };
  useEffect(() => {
    void load();
  }, []);
  const stepUp = async (action: (ticket: string) => Promise<void>) => {
    const request = await fetch(`${API_BASE}/api/auth/request-admin-step-up`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    const issued = (await request.json().catch(() => ({}))) as {
      developmentCode?: string;
      error?: string;
    };
    if (!request.ok) return setNotice(issued.error || "无法请求二次验证");
    const code = window.prompt(
      `请输入二次验证码${issued.developmentCode ? `（开发验证码：${issued.developmentCode}）` : ""}`,
    );
    if (!code) return;
    const confirm = await fetch(`${API_BASE}/api/auth/confirm-admin-step-up`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    });
    const verified = (await confirm.json().catch(() => ({}))) as {
      ticket?: string;
      error?: string;
    };
    if (!confirm.ok || !verified.ticket)
      return setNotice(verified.error || "二次验证失败");
    await action(verified.ticket);
  };
  const reviewVerification = (
    item: Application,
    decision: "approved" | "rejected" | "supplement_required",
  ) =>
    void stepUp(async (ticket) => {
      const note =
        decision === "approved"
          ? ""
          : window.prompt(
              decision === "supplement_required" ? "补件要求" : "拒绝原因",
            );
      if (decision !== "approved" && !note?.trim()) return;
      const response = await fetch(
        `${API_BASE}/api/admin/seller-verifications/${encodeURIComponent(item.id)}`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "X-Admin-Step-Up": ticket,
          },
          body: JSON.stringify({ decision, note }),
        },
      );
      const payload = (await response.json().catch(() => ({}))) as {
        error?: string;
      };
      if (!response.ok) return setNotice(payload.error || "认证审核失败");
      void load();
    });
  return (
    <section className="studio-panel governance-operations admin-service-management">
      <div className="panel-head">
        <h2>案件、认证与客服工单</h2>
        <button className="secondary" onClick={() => void load()}>
          刷新
        </button>
      </div>
      {notice && <p className="auth-error">{notice}</p>}
      <div className="admin-operation-grid">
        <div>
          <h3>卖家认证审核</h3>
          <div className="admin-operation-list">
            {applications.slice(0, 12).map((item) => (
              <div key={item.id}>
                <b>{item.seller}</b> · {item.legalName} · {item.status}
                {item.supplementDueAt
                  ? ` · 补件截止 ${item.supplementDueAt}`
                  : ""}
                <small>{item.reviewNote || ""}</small>
                <div className="verification-review-documents">
                  {item.documents?.map((document) => (
                    <a
                      key={document.id}
                      href={document.url}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {document.type} · {document.status}
                    </a>
                  ))}
                  {item.evidence.map((url) => (
                    <a key={url} href={url} target="_blank" rel="noreferrer">
                      凭证
                    </a>
                  ))}
                </div>
                {item.status === "pending" && (
                  <>
                    <button
                      className="secondary"
                      onClick={() => reviewVerification(item, "approved")}
                    >
                      通过
                    </button>
                    <button
                      className="secondary"
                      onClick={() =>
                        reviewVerification(item, "supplement_required")
                      }
                    >
                      要求补件
                    </button>
                    <button
                      className="danger"
                      onClick={() => reviewVerification(item, "rejected")}
                    >
                      拒绝
                    </button>
                  </>
                )}
              </div>
            ))}
            {!applications.length && <p>暂无认证申请</p>}
          </div>
        </div>
        <div>
          <h3>平台客服工单</h3>
          <div className="admin-operation-list">
            {tickets.slice(0, 12).map((item) => (
              <span key={item.id}>
                <b>{item.subject}</b> · {item.buyer} · {item.priority} ·{" "}
                {item.status}
                <button
                  className="secondary"
                  onClick={async () => {
                    await fetch(
                      `${API_BASE}/api/admin/support/tickets/${encodeURIComponent(item.id)}/status`,
                      {
                        method: "POST",
                        credentials: "include",
                        headers: { "Content-Type": "application/json" },
                        body: JSON.stringify({ status: "resolved" }),
                      },
                    );
                    void load();
                  }}
                >
                  解决
                </button>
              </span>
            ))}
            {!tickets.length && <p>暂无平台工单</p>}
          </div>
        </div>
      </div>
      <div className="governance-task-list">
        <h3>治理案件时间线</h3>
        {reports.slice(0, 8).map((report) => (
          <div key={report.id}>
            <span>
              <b>{report.reason}</b>
              <small>
                {report.reporter} · {report.status}
              </small>
            </span>
            <button
              className="secondary"
              onClick={async () => {
                const response = await fetch(
                  `${API_BASE}/api/admin/governance/cases/report/${encodeURIComponent(report.id)}`,
                  { credentials: "include" },
                );
                const payload = await response.json().catch(() => null);
                if (!response.ok) return setNotice("案件加载失败");
                setCaseDetail(payload);
              }}
            >
              查看案件
            </button>
          </div>
        ))}
        {caseDetail && (
          <div className="governance-case">
            <b>
              {caseDetail.case.title} · {caseDetail.case.status}
            </b>
            {caseDetail.timeline.map((item, index) => (
              <small key={`${item.createdAt}-${index}`}>
                {item.createdAt} · {item.actor} · {item.content}
              </small>
            ))}
            <textarea
              value={note}
              onChange={(event) => setNote(event.target.value)}
              maxLength={1000}
              placeholder="内部案件备注"
            />
            <button
              className="secondary"
              disabled={!note.trim()}
              onClick={async () => {
                const response = await fetch(
                  `${API_BASE}/api/admin/governance/cases/${encodeURIComponent(caseDetail.case.type)}/${encodeURIComponent(caseDetail.case.id)}/notes`,
                  {
                    method: "POST",
                    credentials: "include",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({
                      content: note,
                      visibility: "internal",
                    }),
                  },
                );
                if (!response.ok) return setNotice("案件备注保存失败");
                setNote("");
                const refreshed = await fetch(
                  `${API_BASE}/api/admin/governance/cases/${encodeURIComponent(caseDetail.case.type)}/${encodeURIComponent(caseDetail.case.id)}`,
                  { credentials: "include" },
                );
                if (refreshed.ok) setCaseDetail(await refreshed.json());
              }}
            >
              添加备注
            </button>
          </div>
        )}
      </div>
    </section>
  );
}


