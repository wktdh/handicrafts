import { useEffect, useState } from "react";
import { ArrowRight, LoaderCircle } from "lucide-react";

type AdvisorOverview = {
  exposureUv: number;
  clickUv: number;
  ctr: number;
  favoriteAdds: number;
  addCartUv: number;
  orders: number;
  revenue: number;
  clickToOrderRate: number;
};

type AdvisorProduct = AdvisorOverview & {
  id: string | number;
  title: string;
};

type AdvisorInsight = {
  id?: string | number;
  title?: string;
  name?: string;
  reason?: string;
  description?: string;
  recommendation?: string;
  suggestion?: string;
  priority?: "high" | "medium" | "low" | string;
  actionTab?: "products" | "promotions" | "inventory" | string;
  actionTarget?: "products" | "promotions" | "inventory" | string;
  actionLabel?: string;
};

type AdvisorReport = {
  current: {
    startDate?: string;
    endDate?: string;
    overview?: Partial<AdvisorOverview>;
    funnel?: Partial<AdvisorOverview>;
    products?: AdvisorProduct[];
    insights?: AdvisorInsight[];
  };
  previous?: { overview?: Partial<AdvisorOverview> };
};

const apiBase =
  (import.meta as ImportMeta & { env?: { VITE_API_BASE?: string } }).env
    ?.VITE_API_BASE ?? "";

const advisorNumber = (value: unknown) =>
  typeof value === "number" && Number.isFinite(value) ? value : Number(value) || 0;

const advisorOverview = (value?: Partial<AdvisorOverview>): AdvisorOverview => ({
  exposureUv: advisorNumber(value?.exposureUv),
  clickUv: advisorNumber(value?.clickUv),
  ctr: advisorNumber(value?.ctr),
  favoriteAdds: advisorNumber(value?.favoriteAdds),
  addCartUv: advisorNumber(value?.addCartUv),
  orders: advisorNumber(value?.orders),
  revenue: advisorNumber(value?.revenue),
  clickToOrderRate: advisorNumber(value?.clickToOrderRate),
});

const advisorPercent = (value: number) => `${value.toFixed(1)}%`;
const advisorInteger = (value: number) => value.toLocaleString("zh-CN");
const advisorMoney = (value: number) =>
  `¥${value.toLocaleString("zh-CN", { maximumFractionDigits: 2 })}`;

function advisorChange(current: number, previous: number, percentage = false) {
  if (!previous) return "对比周期暂无数据";
  if (percentage) {
    const delta = current - previous;
    return `较上期${delta >= 0 ? "+" : ""}${delta.toFixed(1)} 个百分点`;
  }
  const rate = ((current - previous) / previous) * 100;
  return `较上期${rate >= 0 ? "+" : ""}${rate.toFixed(1)}%`;
}

export default function DataAdvisor({
  onOpenTab,
}: {
  onOpenTab: (tab: "products" | "promotions" | "inventory") => void;
}) {
  const [days, setDays] = useState<1 | 7 | 30>(1);
  const [report, setReport] = useState<AdvisorReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [sort, setSort] = useState<keyof AdvisorProduct>("exposureUv");
  const [sortDescending, setSortDescending] = useState(true);

  const load = async () => {
    setLoading(true);
    setError("");
    try {
      const response = await fetch(
        `${apiBase}/api/analytics/seller/business?days=${days}`,
        { credentials: "include" },
      );
      if (!response.ok) throw new Error("request failed");
      const payload = (await response.json()) as {
        analytics?: AdvisorReport;
      } & AdvisorReport;
      const next = payload.analytics ?? payload;
      if (!next?.current) throw new Error("invalid response");
      setReport(next);
    } catch {
      setReport(null);
      setError("经营数据暂时无法加载，请稍后重试。");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load();
  }, [days]);

  const current = advisorOverview(report?.current.overview);
  const previous = advisorOverview(report?.previous?.overview);
  const funnel = advisorOverview(report?.current.funnel);
  const products = [...(report?.current.products || [])].sort((left, right) => {
    const a = typeof left[sort] === "number" ? (left[sort] as number) : 0;
    const b = typeof right[sort] === "number" ? (right[sort] as number) : 0;
    return sortDescending ? b - a : a - b;
  });
  const dateRange = report?.current.startDate && report?.current.endDate
    ? `${report.current.startDate} 至 ${report.current.endDate}`
    : "数据持续积累中";
  const funnelItems = [
    ["曝光", funnel.exposureUv],
    ["点击", funnel.clickUv],
    ["收藏", funnel.favoriteAdds],
    ["加购", funnel.addCartUv],
    ["下单", funnel.orders],
  ] as const;
  const updateSort = (key: keyof AdvisorProduct) => {
    if (sort === key) setSortDescending((value) => !value);
    else {
      setSort(key);
      setSortDescending(true);
    }
  };
  const resolveActionTab = (insight: AdvisorInsight) => {
    if (
      insight.actionTarget === "products" ||
      insight.actionTarget === "promotions" ||
      insight.actionTarget === "inventory"
    )
      return insight.actionTarget;
    if (
      insight.actionTab === "products" ||
      insight.actionTab === "promotions" ||
      insight.actionTab === "inventory"
    )
      return insight.actionTab;
    const text = `${insight.title || ""}${insight.name || ""}${insight.reason || ""}${insight.description || ""}`;
    if (/库存|补货|缺货/.test(text)) return "inventory";
    if (/优惠|折扣|促销|活动/.test(text)) return "promotions";
    return "products";
  };

  return (
    <div className="data-advisor" data-testid="data-advisor">
      <div className="studio-title">
        <div>
          <h1>数据参谋</h1>
          <p>查看作品流量和转化，找到下一步最值得处理的经营机会。</p>
        </div>
      </div>
      <div className="advisor-toolbar">
        <div className="order-filters" aria-label="数据周期">
          {(
            [
              [1, "今日"],
              [7, "近 7 天"],
              [30, "近 30 天"],
            ] as const
          ).map(([value, label]) => (
            <button
              key={value}
              className={days === value ? "selected" : ""}
              onClick={() => setDays(value)}
            >
              {label}
            </button>
          ))}
        </div>
        <span>{dateRange}</span>
      </div>

      {loading && !report && (
        <section className="studio-panel advisor-state" aria-live="polite">
          <LoaderCircle size={24} className="advisor-spinner" />
          <b>正在汇总经营数据…</b>
        </section>
      )}
      {!loading && error && (
        <section className="studio-panel advisor-state" role="alert">
          <b>{error}</b>
          <button className="secondary" onClick={() => void load()}>
            重新加载
          </button>
        </section>
      )}
      {!error && report && (
        <>
          <section className="advisor-metric-grid" aria-label="经营总览">
            <AdvisorMetric label="曝光人数" value={advisorInteger(current.exposureUv)} trend={advisorChange(current.exposureUv, previous.exposureUv)} />
            <AdvisorMetric label="点击人数" value={advisorInteger(current.clickUv)} trend={advisorChange(current.clickUv, previous.clickUv)} />
            <AdvisorMetric label="点击率" value={advisorPercent(current.ctr)} trend={advisorChange(current.ctr, previous.ctr, true)} />
            <AdvisorMetric label="新增收藏" value={advisorInteger(current.favoriteAdds)} trend={advisorChange(current.favoriteAdds, previous.favoriteAdds)} />
            <AdvisorMetric label="加购人数" value={advisorInteger(current.addCartUv)} trend={advisorChange(current.addCartUv, previous.addCartUv)} />
            <AdvisorMetric label="支付订单" value={advisorInteger(current.orders)} trend={advisorChange(current.orders, previous.orders)} />
            <AdvisorMetric label="成交金额" value={advisorMoney(current.revenue)} trend={advisorChange(current.revenue, previous.revenue)} />
            <AdvisorMetric label="点击成交率" value={advisorPercent(current.clickToOrderRate)} trend={advisorChange(current.clickToOrderRate, previous.clickToOrderRate, true)} />
          </section>

          <section className="studio-panel advisor-funnel">
            <div className="panel-head">
              <div>
                <h3>转化漏斗</h3>
                <p>按去重访客统计，帮助定位流失环节。</p>
              </div>
            </div>
            <div className="advisor-funnel-steps">
              {funnelItems.map(([label, value], index) => {
                const before = index ? funnelItems[index - 1][1] : 0;
                const rate = index && before > 0 ? (value / before) * 100 : null;
                return (
                  <div className="advisor-funnel-step" key={label}>
                    <span>{label}</span>
                    <b>{advisorInteger(value)}</b>
                    <small>{index ? (rate === null ? "暂无可计算的转化率" : `转化 ${advisorPercent(rate)}`) : "起始流量"}</small>
                  </div>
                );
              })}
            </div>
          </section>

          <section className="studio-panel advisor-products">
            <div className="panel-head">
              <div>
                <h3>单品表现</h3>
                <p>点击表头可按关键指标排序。</p>
              </div>
            </div>
            {!products.length ? (
              <div className="advisor-empty">暂无足够的单品数据，作品被浏览后会逐步显示在这里。</div>
            ) : (
              <div className="advisor-table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>作品</th>
                      {(
                        [
                          ["exposureUv", "曝光"],
                          ["clickUv", "点击"],
                          ["ctr", "CTR"],
                          ["favoriteAdds", "收藏"],
                          ["addCartUv", "加购"],
                          ["orders", "订单"],
                          ["revenue", "成交额"],
                          ["clickToOrderRate", "点击成交率"],
                        ] as [keyof AdvisorProduct, string][]
                      ).map(([key, label]) => (
                        <th key={key}>
                          <button onClick={() => updateSort(key)}>
                            {label}{sort === key ? (sortDescending ? " ↓" : " ↑") : ""}
                          </button>
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody>
                    {products.map((product) => (
                      <tr key={product.id}>
                        <td>{product.title || "未命名作品"}</td>
                        <td>{advisorInteger(advisorNumber(product.exposureUv))}</td>
                        <td>{advisorInteger(advisorNumber(product.clickUv))}</td>
                        <td>{advisorPercent(advisorNumber(product.ctr))}</td>
                        <td>{advisorInteger(advisorNumber(product.favoriteAdds))}</td>
                        <td>{advisorInteger(advisorNumber(product.addCartUv))}</td>
                        <td>{advisorInteger(advisorNumber(product.orders))}</td>
                        <td>{advisorMoney(advisorNumber(product.revenue))}</td>
                        <td>{advisorPercent(advisorNumber(product.clickToOrderRate))}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </section>

          <section className="studio-panel advisor-insights">
            <div className="panel-head">
              <div>
                <h3>优化任务</h3>
                <p>根据表现自动排序，先处理影响更大的问题。</p>
              </div>
            </div>
            {!(report.current.insights || []).length ? (
              <div className="advisor-empty">暂未发现需要优先处理的问题，继续积累数据后会生成诊断建议。</div>
            ) : (
              <div className="advisor-insight-list">
                {(report.current.insights || []).map((insight, index) => {
                  const actionTab = resolveActionTab(insight);
                  const priority = insight.priority === "high" ? "高优先级" : insight.priority === "low" ? "低优先级" : "中优先级";
                  const title = insight.title || insight.name || "经营优化建议";
                  const reason = insight.reason || insight.description || "系统根据近期经营数据发现该项需要关注。";
                  const recommendation = insight.recommendation || insight.suggestion;
                  const actionLabel = insight.actionLabel || (actionTab === "inventory" ? "管理库存" : actionTab === "promotions" ? "设置优惠" : "优化作品");
                  return (
                    <article key={insight.id || `${title}-${index}`}>
                      <span className={`advisor-priority ${insight.priority || "medium"}`}>{priority}</span>
                      <div>
                        <b>{title}</b>
                        <p>{reason}</p>
                        {recommendation && <small>建议：{recommendation}</small>}
                      </div>
                      <button className="secondary" onClick={() => onOpenTab(actionTab)}>
                        {actionLabel} <ArrowRight size={15} />
                      </button>
                    </article>
                  );
                })}
              </div>
            )}
          </section>
        </>
      )}
    </div>
  );
}

function AdvisorMetric({
  label,
  value,
  trend,
}: {
  label: string;
  value: string;
  trend: string;
}) {
  return (
    <div className="advisor-metric">
      <span>{label}</span>
      <b>{value}</b>
      <small>{trend}</small>
    </div>
  );
}
