import { useEffect, useState } from "react";

const API_BASE =
  (import.meta as ImportMeta & { env?: { VITE_API_BASE?: string } }).env
    ?.VITE_API_BASE ?? "";

export default function RiskControlOperations() {
  type RiskCase = {
    id: string;
    category: string;
    severity: "low" | "medium" | "high";
    status: string;
    reasonCode: string;
    subject?: string | null;
    orderNo?: string | null;
    productTitle?: string | null;
    occurrences: number;
    lastSeenAt: string;
  };
  const [cases, setCases] = useState<RiskCase[]>([]);
  const [notice, setNotice] = useState("");
  const load = async () => {
    const response = await fetch(`${API_BASE}/api/admin/risk-cases`, {
      credentials: "include",
    });
    const payload = (await response.json().catch(() => ({}))) as {
      riskCases?: RiskCase[];
      error?: string;
    };
    if (!response.ok) return setNotice(payload.error || "风险队列加载失败");
    setCases(payload.riskCases || []);
    setNotice("");
  };
  useEffect(() => {
    void load();
  }, []);
  const labels: Record<string, string> = {
    coupon_abuse: "优惠滥用",
    order_anomaly: "异常下单",
    wash_trading: "疑似刷单",
    refund_dispute: "退款争议",
    image_duplicate: "重复图片",
  };
  return (
    <section className="studio-panel">
      <div className="panel-head">
        <div>
          <h2>交易风险队列</h2>
          <small>自动拦截高风险操作，其他信号进入人工复核。</small>
        </div>
        <button className="secondary" onClick={() => void load()}>
          刷新
        </button>
      </div>
      {notice && <p className="auth-error">{notice}</p>}
      <div className="admin-operation-list">
        {cases.slice(0, 20).map((item) => (
          <div key={item.id}>
            <span>
              <b>
                {labels[item.category] || item.category} · {item.reasonCode}
              </b>
              <small>
                {item.subject || "未关联用户"}
                {item.orderNo ? ` · 订单 ${item.orderNo}` : ""}
                {item.productTitle ? ` · ${item.productTitle}` : ""}
              </small>
              <small>
                {item.status} · 命中 {item.occurrences} 次 · 最近 {item.lastSeenAt}
              </small>
            </span>
            <em className={`risk-severity ${item.severity}`}>
              {item.severity}
            </em>
          </div>
        ))}
        {!cases.length && <p>暂无待复核风险。</p>}
      </div>
    </section>
  );
}


