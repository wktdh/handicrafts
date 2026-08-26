import { useEffect, useState } from "react";

const API_BASE =
  (import.meta as ImportMeta & { env?: { VITE_API_BASE?: string } }).env
    ?.VITE_API_BASE ?? "";

function ServiceAutomationOperations() {
  type Rule = {
    id: string;
    name: string;
    keywords: string[];
    priority: "low" | "normal" | "high" | "urgent";
    route: "shop" | "platform";
    replyTemplate?: string;
    enabled: boolean;
    sortOrder: number;
  };
  const [rules, setRules] = useState<Rule[]>([]);
  const [draft, setDraft] = useState({
    id: "",
    name: "",
    keywords: "",
    priority: "normal" as Rule["priority"],
    route: "shop" as Rule["route"],
    replyTemplate: "",
    sortOrder: "100",
  });
  const [notice, setNotice] = useState("");
  const load = async () => {
    const response = await fetch(`${API_BASE}/api/admin/service-automation`, {
      credentials: "include",
    });
    const payload = (await response.json().catch(() => ({}))) as {
      rules?: Rule[];
      error?: string;
    };
    if (!response.ok)
      return setNotice(payload.error || "客服自动化规则加载失败");
    setRules(payload.rules || []);
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
    const issue = (await request.json().catch(() => ({}))) as {
      developmentCode?: string;
      error?: string;
    };
    if (!request.ok) return setNotice(issue.error || "无法请求二次验证");
    const code = window.prompt(
      `请输入二次验证码${issue.developmentCode ? `（开发验证码：${issue.developmentCode}）` : ""}`,
    );
    if (!code) return;
    const confirmation = await fetch(
      `${API_BASE}/api/auth/confirm-admin-step-up`,
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code }),
      },
    );
    const verified = (await confirmation.json().catch(() => ({}))) as {
      ticket?: string;
      error?: string;
    };
    if (!confirmation.ok || !verified.ticket)
      return setNotice(verified.error || "二次验证失败");
    await action(verified.ticket);
  };
  const save = (enabled = true, value = draft) =>
    void stepUp(async (ticket) => {
      const keywords = value.keywords
        .split(/[，,\n]/)
        .map((item) => item.trim())
        .filter(Boolean);
      const response = await fetch(`${API_BASE}/api/admin/service-automation`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-Admin-Step-Up": ticket,
        },
        body: JSON.stringify({
          ...value,
          keywords,
          sortOrder: Number(value.sortOrder),
          enabled,
        }),
      });
      const payload = (await response.json().catch(() => ({}))) as {
        id?: string;
        error?: string;
      };
      if (!response.ok) return setNotice(payload.error || "规则保存失败");
      setNotice("客服自动化规则已保存");
      setDraft({
        id: "",
        name: "",
        keywords: "",
        priority: "normal",
        route: "shop",
        replyTemplate: "",
        sortOrder: "100",
      });
      void load();
    });
  return (
    <section className="studio-panel search-operations">
      <div className="panel-head">
        <h2>客服自动化</h2>
        <button className="secondary" onClick={() => void load()}>
          刷新
        </button>
      </div>
      {notice && <p className="auth-error">{notice}</p>}
      <div className="admin-operation-grid">
        <div>
          <h3>{draft.id ? "编辑自动化规则" : "新建自动化规则"}</h3>
          <input
            value={draft.name}
            maxLength={80}
            onChange={(event) =>
              setDraft({ ...draft, name: event.target.value })
            }
            placeholder="规则名称"
          />
          <input
            value={draft.keywords}
            maxLength={600}
            onChange={(event) =>
              setDraft({ ...draft, keywords: event.target.value })
            }
            placeholder="命中关键词，使用逗号分隔"
          />
          <div className="campaign-rule">
            <select
              value={draft.priority}
              onChange={(event) =>
                setDraft({
                  ...draft,
                  priority: event.target.value as Rule["priority"],
                })
              }
            >
              <option value="low">低优先级</option>
              <option value="normal">普通</option>
              <option value="high">高优先级</option>
              <option value="urgent">紧急</option>
            </select>
            <select
              value={draft.route}
              onChange={(event) =>
                setDraft({
                  ...draft,
                  route: event.target.value as Rule["route"],
                })
              }
            >
              <option value="shop">优先路由店铺</option>
              <option value="platform">路由平台客服</option>
            </select>
            <input
              type="number"
              min="1"
              max="9999"
              value={draft.sortOrder}
              onChange={(event) =>
                setDraft({ ...draft, sortOrder: event.target.value })
              }
              placeholder="优先顺序"
            />
          </div>
          <textarea
            value={draft.replyTemplate}
            maxLength={1000}
            onChange={(event) =>
              setDraft({ ...draft, replyTemplate: event.target.value })
            }
            placeholder="自动回复（可选，可使用 {subject}）"
          />
          <button
            className="primary"
            disabled={!draft.name.trim() || !draft.keywords.trim()}
            onClick={() => save()}
          >
            保存规则
          </button>
        </div>
        <div>
          <h3>已配置规则</h3>
          <div className="admin-operation-list">
            {rules.map((rule) => {
              const value = {
                id: rule.id,
                name: rule.name,
                keywords: rule.keywords.join("，"),
                priority: rule.priority,
                route: rule.route,
                replyTemplate: rule.replyTemplate || "",
                sortOrder: String(rule.sortOrder),
              };
              return (
                <div key={rule.id}>
                  <span>
                    <b>{rule.name}</b> · {rule.keywords.join("、")}
                    <small>
                      {rule.priority} ·{" "}
                      {rule.route === "platform" ? "平台客服" : "店铺客服"} ·
                      顺序 {rule.sortOrder}
                      {rule.replyTemplate ? " · 自动回复" : ""}
                    </small>
                  </span>
                  <button className="secondary" onClick={() => setDraft(value)}>
                    编辑
                  </button>
                  <button
                    className="secondary"
                    onClick={() => save(!rule.enabled, value)}
                  >
                    {rule.enabled ? "停用" : "启用"}
                  </button>
                </div>
              );
            })}
            {!rules.length && <p>暂无自动化规则</p>}
          </div>
        </div>
      </div>
    </section>
  );
}


function SearchOperations() {
  type Kind = "synonym" | "correction" | "recommendation" | "zero_result";
  type Rule = {
    id: string;
    source: string;
    target?: string | string[];
    message?: string;
    productId?: string | null;
    productTitle?: string | null;
    weight?: number;
    enabled: boolean;
  };
  type Payload = {
    days: number;
    rules: {
      synonyms: Rule[];
      corrections: Rule[];
      recommendations: Rule[];
      zeroResults: Rule[];
    };
    summary: {
      searches: number;
      zeroResults: number;
      corrections: number;
      zeroRate: number;
    };
    terms: {
      keyword: string;
      searches: number;
      zeroResults: number;
      corrections: number;
    }[];
    zeroTerms: { keyword: string; searches: number }[];
  };
  const [data, setData] = useState<Payload | null>(null);
  const [days, setDays] = useState<7 | 30>(30);
  const [kind, setKind] = useState<Kind>("synonym");
  const [source, setSource] = useState("");
  const [target, setTarget] = useState("");
  const [productId, setProductId] = useState("");
  const [weight, setWeight] = useState("100");
  const [notice, setNotice] = useState("");
  const load = async () => {
    const response = await fetch(
      `${API_BASE}/api/admin/search-operations?days=${days}`,
      { credentials: "include" },
    );
    const payload = (await response.json().catch(() => ({}))) as Payload & {
      error?: string;
    };
    if (!response.ok) return setNotice(payload.error || "搜索运营数据加载失败");
    setData(payload);
  };
  useEffect(() => {
    void load();
  }, [days]);
  const withStepUp = async (action: (ticket: string) => Promise<void>) => {
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
  const save = () =>
    void withStepUp(async (ticket) => {
      const body = {
        kind,
        source,
        target:
          kind === "synonym"
            ? target
                .split(/[，,]/)
                .map((item) => item.trim())
                .filter(Boolean)
            : kind === "zero_result"
              ? { message: target, productId: productId || undefined }
              : target,
        weight: Number(weight),
      };
      const response = await fetch(`${API_BASE}/api/admin/search-operations`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-Admin-Step-Up": ticket,
        },
        body: JSON.stringify(body),
      });
      const payload = (await response.json().catch(() => ({}))) as {
        error?: string;
      };
      if (!response.ok) return setNotice(payload.error || "规则保存失败");
      setSource("");
      setTarget("");
      setProductId("");
      setNotice("搜索规则已保存");
      void load();
    });
  const update = (rule: Rule, enabled: boolean) =>
    void withStepUp(async (ticket) => {
      const response = await fetch(
        `${API_BASE}/api/admin/search-operations/${kind}/${encodeURIComponent(rule.id)}`,
        {
          method: "PUT",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "X-Admin-Step-Up": ticket,
          },
          body: JSON.stringify({ enabled, weight: rule.weight }),
        },
      );
      if (!response.ok) return setNotice("规则更新失败");
      void load();
    });
  const remove = (rule: Rule) =>
    void withStepUp(async (ticket) => {
      if (!window.confirm(`删除“${rule.source}”规则？`)) return;
      const response = await fetch(
        `${API_BASE}/api/admin/search-operations/${kind}/${encodeURIComponent(rule.id)}`,
        {
          method: "DELETE",
          credentials: "include",
          headers: { "X-Admin-Step-Up": ticket },
        },
      );
      if (!response.ok) return setNotice("规则删除失败");
      void load();
    });
  const rules: Rule[] =
    kind === "synonym"
      ? data?.rules.synonyms || []
      : kind === "correction"
        ? data?.rules.corrections || []
        : kind === "recommendation"
          ? data?.rules.recommendations || []
          : data?.rules.zeroResults || [];
  return (
    <section className="studio-panel search-operations">
      <div className="panel-head">
        <h2>搜索运营</h2>
        <div className="analytics-toolbar">
          <div>
            <button
              className={days === 7 ? "active" : ""}
              onClick={() => setDays(7)}
            >
              近 7 天
            </button>
            <button
              className={days === 30 ? "active" : ""}
              onClick={() => setDays(30)}
            >
              近 30 天
            </button>
          </div>
          <button className="secondary" onClick={() => void load()}>
            刷新
          </button>
        </div>
      </div>
      {notice && <p className="auth-error">{notice}</p>}
      {data && (
        <>
          <div className="coupon-operation-stats">
            <span>
              搜索次数 <b>{data.summary.searches}</b>
            </span>
            <span>
              零结果 <b>{data.summary.zeroResults}</b>
            </span>
            <span>
              零结果率 <b>{data.summary.zeroRate}%</b>
            </span>
            <span>
              纠错使用 <b>{data.summary.corrections}</b>
            </span>
          </div>
          <div className="admin-operation-grid">
            <div>
              <h3>配置搜索规则</h3>
              <select
                value={kind}
                onChange={(event) => setKind(event.target.value as Kind)}
              >
                <option value="synonym">同义词扩展</option>
                <option value="correction">纠错词</option>
                <option value="recommendation">搜索推荐</option>
                <option value="zero_result">无结果运营</option>
              </select>
              <input
                value={source}
                maxLength={50}
                onChange={(event) => setSource(event.target.value)}
                placeholder="触发搜索词"
              />
              <input
                value={target}
                maxLength={kind === "zero_result" ? 200 : 100}
                onChange={(event) => setTarget(event.target.value)}
                placeholder={
                  kind === "synonym"
                    ? "同义词，使用逗号分隔"
                    : kind === "correction"
                      ? "正确搜索词"
                      : kind === "recommendation"
                        ? "推荐给买家的搜索词"
                        : "无结果时的运营提示"
                }
              />
              {kind === "recommendation" && (
                <input
                  type="number"
                  min="1"
                  max="10000"
                  value={weight}
                  onChange={(event) => setWeight(event.target.value)}
                  placeholder="推荐权重"
                />
              )}
              {kind === "zero_result" && (
                <input
                  value={productId}
                  onChange={(event) => setProductId(event.target.value)}
                  placeholder="推荐作品 ID（可选）"
                />
              )}
              <button
                className="primary"
                disabled={!source.trim() || !target.trim()}
                onClick={save}
              >
                保存规则
              </button>
            </div>
            <div>
              <h3>规则列表</h3>
              <div className="admin-operation-list">
                {rules.map((rule) => (
                  <div key={rule.id}>
                    <span>
                      <b>{rule.source}</b> →{" "}
                      {Array.isArray(rule.target)
                        ? rule.target.join("、")
                        : rule.target || rule.message}
                      {rule.productTitle && ` · 推荐：${rule.productTitle}`}
                      {rule.weight && ` · 权重 ${rule.weight}`}
                    </span>
                    <button
                      className="secondary"
                      onClick={() => update(rule, !rule.enabled)}
                    >
                      {rule.enabled ? "停用" : "启用"}
                    </button>
                    <button className="danger" onClick={() => remove(rule)}>
                      删除
                    </button>
                  </div>
                ))}
                {!rules.length && <p>暂无此类规则</p>}
              </div>
            </div>
          </div>
          <div className="admin-analytics-grid search-term-analytics">
            <div className="studio-panel analytics-ranking">
              <div className="panel-head">
                <h3>高频搜索词</h3>
                <span>搜索 / 零结果 / 纠错</span>
              </div>
              {data.terms.map((item) => (
                <p key={item.keyword}>
                  <span>
                    {item.keyword} · {item.searches} / {item.zeroResults} /{" "}
                    {item.corrections}
                  </span>
                  <b>{item.searches}</b>
                </p>
              ))}
              {!data.terms.length && (
                <p>
                  <span>暂无搜索记录</span>
                </p>
              )}
            </div>
            <div className="studio-panel analytics-ranking">
              <div className="panel-head">
                <h3>待运营零结果词</h3>
                <span>优先配置引导</span>
              </div>
              {data.zeroTerms.map((item) => (
                <p key={item.keyword}>
                  <span>{item.keyword}</span>
                  <b>{item.searches} 次</b>
                </p>
              ))}
              {!data.zeroTerms.length && (
                <p>
                  <span>暂无零结果词</span>
                </p>
              )}
            </div>
          </div>
        </>
      )}
    </section>
  );
}


export default function AdminToolsOperations() {
  return <><SearchOperations /><ServiceAutomationOperations /></>;
}

