import { useEffect, useState } from "react";

const API_BASE =
  (import.meta as ImportMeta & { env?: { VITE_API_BASE?: string } }).env
    ?.VITE_API_BASE ?? "";

function money(value: number) {
  return `$${value.toFixed(2)}`;
}

function Metric({ label, value, trend }: { label: string; value: string; trend: string }) {
  return <div className="metric"><span>{label}</span><b>{value}</b><small>{trend}</small></div>;
}

export default function AdminFinanceOperations() {
  type Withdrawal = {
    id: string;
    shop: string;
    applicant: string;
    amount: number;
    recipientType: string;
    recipient: string;
    status: string;
    note?: string;
    createdAt: string;
  };
  const [finance, setFinance] = useState<{
    feeRateBps: number;
    summary: {
      available: number;
      pending: number;
      withdrawing: number;
      withdrawn: number;
      refundDebt: number;
      platformFees: number;
    };
    withdrawals: Withdrawal[];
  } | null>(null);
  const [feeRate, setFeeRate] = useState("");
  const [notice, setNotice] = useState("");
  const load = async () => {
    const response = await fetch(`${API_BASE}/api/admin/finance`, {
      credentials: "include",
    });
    const payload = (await response
      .json()
      .catch(() => ({}))) as typeof finance & { error?: string };
    if (!response.ok || !payload)
      return setNotice(payload?.error || "资金数据加载失败");
    setFinance(payload);
    setFeeRate(String(payload.feeRateBps / 100));
  };
  useEffect(() => {
    void load();
  }, []);
  const stepUp = async (action: (ticket: string) => Promise<void>) => {
    const requested = await fetch(
      `${API_BASE}/api/auth/request-admin-step-up`,
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: "{}",
      },
    );
    const issue = (await requested.json().catch(() => ({}))) as {
      developmentCode?: string;
      error?: string;
    };
    if (!requested.ok) return setNotice(issue.error || "无法请求二次验证");
    const code = window.prompt(
      `请输入二次验证码${issue.developmentCode ? `（开发验证码：${issue.developmentCode}）` : ""}`,
    );
    if (!code) return;
    const confirmed = await fetch(
      `${API_BASE}/api/auth/confirm-admin-step-up`,
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
      },
    );
    const verified = (await confirmed.json().catch(() => ({}))) as {
      ticket?: string;
      error?: string;
    };
    if (!confirmed.ok || !verified.ticket)
      return setNotice(verified.error || "二次验证失败");
    await action(verified.ticket);
  };
  const updateWithdrawal = (
    id: string,
    decision: "approved" | "rejected" | "paid",
  ) =>
    void stepUp(async (ticket) => {
      const note = decision === "rejected" ? window.prompt("驳回原因") : "";
      if (decision === "rejected" && !note) return;
      const response = await fetch(
        `${API_BASE}/api/admin/withdrawals/${encodeURIComponent(id)}`,
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
      if (!response.ok) return setNotice(payload.error || "提现处理失败");
      setNotice("提现状态已更新");
      void load();
    });
  return (
    <section className="studio-panel admin-operations finance-admin">
      <div className="panel-head">
        <h2>结算与商家资金</h2>
        <button className="secondary" onClick={() => void load()}>
          刷新
        </button>
      </div>
      {notice && <p className="auth-error">{notice}</p>}
      <div className="metric-grid">
        <Metric
          label="商家可提现"
          value={money(finance?.summary.available || 0)}
          trend="未发起提现"
        />
        <Metric
          label="待结算"
          value={money(finance?.summary.pending || 0)}
          trend="等待收货"
        />
        <Metric
          label="提现中"
          value={money(finance?.summary.withdrawing || 0)}
          trend="待审核或打款"
        />
        <Metric
          label="平台服务费"
          value={money(finance?.summary.platformFees || 0)}
          trend="未冲回订单"
        />
      </div>
      <div className="admin-operation-grid">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void stepUp(async (ticket) => {
              const response = await fetch(
                `${API_BASE}/api/admin/finance/settings`,
                {
                  method: "POST",
                  credentials: "include",
                  headers: {
                    "Content-Type": "application/json",
                    "X-Admin-Step-Up": ticket,
                  },
                  body: JSON.stringify({
                    serviceFeeBps: Math.round(Number(feeRate) * 100),
                  }),
                },
              );
              const payload = (await response.json().catch(() => ({}))) as {
                error?: string;
              };
              if (!response.ok)
                return setNotice(payload.error || "费率保存失败");
              setNotice("新订单服务费率已保存");
              void load();
            });
          }}
        >
          <h3>平台服务费率</h3>
          <label className="fee-rate-input">
            <input
              required
              type="number"
              min="0"
              max="30"
              step="0.01"
              value={feeRate}
              onChange={(event) => setFeeRate(event.target.value)}
              aria-label="平台服务费率"
            />
            <span>%</span>
          </label>
          <small>仅影响之后支付的订单，历史结算单费率保持不变。</small>
          <button className="primary">保存费率</button>
        </form>
        <div>
          <h3>提现审核队列</h3>
          <div className="finance-list">
            {finance?.withdrawals.map((item) => (
              <div key={item.id}>
                <span>
                  <b>
                    {item.shop} · {money(item.amount)}
                  </b>
                  <small>
                    {item.applicant} ·{" "}
                    {item.recipientType === "bank" ? "银行卡" : "电子钱包"} ·{" "}
                    {item.recipient}
                  </small>
                </span>
                <span>
                  <b>{item.status}</b>
                  {item.status === "pending" && (
                    <button
                      className="secondary"
                      onClick={() => updateWithdrawal(item.id, "approved")}
                    >
                      通过
                    </button>
                  )}
                  {item.status === "pending" && (
                    <button
                      className="danger"
                      onClick={() => updateWithdrawal(item.id, "rejected")}
                    >
                      驳回
                    </button>
                  )}
                  {item.status === "approved" && (
                    <button
                      className="primary"
                      onClick={() => updateWithdrawal(item.id, "paid")}
                    >
                      标记已打款
                    </button>
                  )}
                </span>
              </div>
            )) || <p>暂无提现申请。</p>}
          </div>
        </div>
      </div>
    </section>
  );
}


