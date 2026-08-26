import { useEffect, useState } from "react";

const API_BASE =
  (import.meta as ImportMeta & { env?: { VITE_API_BASE?: string } }).env
    ?.VITE_API_BASE ?? "";

function ActivityOperations() {
  type ActivityProduct = {
    id: string;
    productId: string;
    title: string;
    shop: string;
    quotaStock: number;
    reservedStock: number;
    availableStock: number;
    status: string;
    reviewNote?: string;
  };
  type Activity = {
    id: string;
    name: string;
    description: string;
    status: "draft" | "open" | "active" | "ended";
    startsAt?: string;
    endsAt?: string;
    page: { banner?: string; theme?: { accent?: string }; modules?: string[] };
    applications: {
      id: string;
      shop: string;
      status: string;
      note: string;
      reviewNote?: string;
    }[];
    products: ActivityProduct[];
  };
  const [activities, setActivities] = useState<Activity[]>([]);
  const [draft, setDraft] = useState({
    id: "",
    name: "",
    description: "",
    status: "draft" as Activity["status"],
    startsAt: "",
    endsAt: "",
    banner: "",
    accent: "#e66020",
    modules: "作品墙,报名说明",
  });
  const [notice, setNotice] = useState("");
  const load = async () => {
    const response = await fetch(`${API_BASE}/api/admin/activities`, {
      credentials: "include",
    });
    const payload = (await response.json().catch(() => ({}))) as {
      activities?: Activity[];
      error?: string;
    };
    if (!response.ok) return setNotice(payload.error || "活动加载失败");
    setActivities(payload.activities || []);
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
  const save = () =>
    void stepUp(async (ticket) => {
      const response = await fetch(`${API_BASE}/api/admin/activities`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-Admin-Step-Up": ticket,
        },
        body: JSON.stringify({
          id: draft.id || undefined,
          name: draft.name,
          description: draft.description,
          status: draft.status,
          startsAt: draft.startsAt || undefined,
          endsAt: draft.endsAt || undefined,
          page: {
            banner: draft.banner || undefined,
            theme: { accent: draft.accent },
            modules: draft.modules
              .split(/[，,]/)
              .map((item) => item.trim())
              .filter(Boolean)
              .slice(0, 8),
          },
        }),
      });
      const payload = (await response.json().catch(() => ({}))) as {
        error?: string;
      };
      if (!response.ok) return setNotice(payload.error || "活动保存失败");
      setNotice("活动与页面配置已保存");
      setDraft({
        id: "",
        name: "",
        description: "",
        status: "draft",
        startsAt: "",
        endsAt: "",
        banner: "",
        accent: "#e66020",
        modules: "作品墙,报名说明",
      });
      void load();
    });
  const reviewApplication = (
    activityId: string,
    applicationId: string,
    decision: "approved" | "rejected",
  ) =>
    void stepUp(async (ticket) => {
      const note = decision === "rejected" ? window.prompt("驳回原因") : "";
      if (decision === "rejected" && !note) return;
      const response = await fetch(
        `${API_BASE}/api/admin/activities/${encodeURIComponent(activityId)}/applications`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "X-Admin-Step-Up": ticket,
          },
          body: JSON.stringify({ applicationId, decision, note }),
        },
      );
      if (!response.ok) return setNotice("报名审核失败");
      void load();
    });
  const reviewProduct = (
    activityId: string,
    activityProductId: string,
    decision: "active" | "rejected" | "disabled",
  ) =>
    void stepUp(async (ticket) => {
      const note = decision === "rejected" ? window.prompt("驳回原因") : "";
      const response = await fetch(
        `${API_BASE}/api/admin/activities/${encodeURIComponent(activityId)}/products`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "X-Admin-Step-Up": ticket,
          },
          body: JSON.stringify({ activityProductId, decision, note }),
        },
      );
      if (!response.ok) return setNotice("活动作品处理失败");
      void load();
    });
  return (
    <section className="studio-panel activity-operations">
      <div className="panel-head">
        <h2>活动运营</h2>
        <button className="secondary" onClick={() => void load()}>
          刷新
        </button>
      </div>
      {notice && <p className="auth-error">{notice}</p>}
      <div className="admin-operation-grid">
        <div>
          <h3>{draft.id ? "编辑活动" : "创建活动"}</h3>
          <input
            value={draft.name}
            maxLength={80}
            onChange={(event) =>
              setDraft({ ...draft, name: event.target.value })
            }
            placeholder="活动名称"
          />
          <textarea
            value={draft.description}
            maxLength={500}
            onChange={(event) =>
              setDraft({ ...draft, description: event.target.value })
            }
            placeholder="活动说明"
          />
          <div className="campaign-rule">
            <select
              value={draft.status}
              onChange={(event) =>
                setDraft({
                  ...draft,
                  status: event.target.value as Activity["status"],
                })
              }
            >
              <option value="draft">草稿</option>
              <option value="open">开放报名</option>
              <option value="active">活动中</option>
              <option value="ended">已结束</option>
            </select>
            <input
              type="datetime-local"
              value={draft.startsAt}
              onChange={(event) =>
                setDraft({ ...draft, startsAt: event.target.value })
              }
            />
            <input
              type="datetime-local"
              value={draft.endsAt}
              onChange={(event) =>
                setDraft({ ...draft, endsAt: event.target.value })
              }
            />
          </div>
          <h3>活动页装修</h3>
          <input
            value={draft.banner}
            onChange={(event) =>
              setDraft({ ...draft, banner: event.target.value })
            }
            placeholder="横幅图片 URL"
          />
          <input
            value={draft.accent}
            onChange={(event) =>
              setDraft({ ...draft, accent: event.target.value })
            }
            placeholder="主题色"
          />
          <input
            value={draft.modules}
            onChange={(event) =>
              setDraft({ ...draft, modules: event.target.value })
            }
            placeholder="页面模块，逗号分隔"
          />
          <button className="primary" disabled={!draft.name} onClick={save}>
            保存活动
          </button>
        </div>
        <div>
          <h3>活动与审核队列</h3>
          <div className="admin-operation-list">
            {activities.map((activity) => (
              <div key={activity.id}>
                <span>
                  <b>{activity.name}</b>
                  <small>
                    {activity.status} · 报名 {activity.applications.length} ·
                    作品 {activity.products.length}
                  </small>
                </span>
                <button
                  className="secondary"
                  onClick={() =>
                    setDraft({
                      id: activity.id,
                      name: activity.name,
                      description: activity.description,
                      status: activity.status,
                      startsAt: activity.startsAt?.slice(0, 16) || "",
                      endsAt: activity.endsAt?.slice(0, 16) || "",
                      banner: activity.page.banner || "",
                      accent: activity.page.theme?.accent || "#e66020",
                      modules: (activity.page.modules || []).join(","),
                    })
                  }
                >
                  编辑
                </button>
                {activity.applications
                  .filter((item) => item.status === "pending")
                  .map((item) => (
                    <span key={item.id}>
                      报名：{item.shop} · {item.note}
                      <button
                        className="secondary"
                        onClick={() =>
                          reviewApplication(activity.id, item.id, "approved")
                        }
                      >
                        通过
                      </button>
                      <button
                        className="danger"
                        onClick={() =>
                          reviewApplication(activity.id, item.id, "rejected")
                        }
                      >
                        驳回
                      </button>
                    </span>
                  ))}
                {activity.products.map((item) => (
                  <span key={item.id}>
                    作品：{item.title} · 配额 {item.quotaStock} · 已占{" "}
                    {item.reservedStock} · {item.status}
                    {item.status === "pending" && (
                      <>
                        <button
                          className="secondary"
                          onClick={() =>
                            reviewProduct(activity.id, item.id, "active")
                          }
                        >
                          启用
                        </button>
                        <button
                          className="danger"
                          onClick={() =>
                            reviewProduct(activity.id, item.id, "rejected")
                          }
                        >
                          驳回
                        </button>
                      </>
                    )}
                    {item.status === "active" && (
                      <button
                        className="secondary"
                        onClick={() =>
                          reviewProduct(activity.id, item.id, "disabled")
                        }
                      >
                        停用
                      </button>
                    )}
                  </span>
                ))}
              </div>
            ))}
            {!activities.length && <p>暂无活动</p>}
          </div>
        </div>
      </div>
    </section>
  );
}


function CouponOperations() {
  type Campaign = {
    id: string;
    name: string;
    type: string;
    status: string;
    claimUsers: number;
    claimedQuantity: number;
    usedQuantity: number;
    directIssuedQuantity: number;
    codeTotal: number;
    codeIssued: number;
    codeRedeemed: number;
    codeExpired: number;
    claimToRedeemRate: number;
  };
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [campaignId, setCampaignId] = useState("");
  const [userIds, setUserIds] = useState("");
  const [segment, setSegment] = useState("");
  const [quantity, setQuantity] = useState("1");
  const [codeCount, setCodeCount] = useState("20");
  const [prefix, setPrefix] = useState("HC");
  const [expiresAt, setExpiresAt] = useState("");
  const [assignedUserIds, setAssignedUserIds] = useState("");
  const [generatedCodes, setGeneratedCodes] = useState<string[]>([]);
  const [notice, setNotice] = useState("");
  const couponCampaigns = campaigns.filter((item) => item.type === "coupon");
  const selected = couponCampaigns.find((item) => item.id === campaignId);
  const load = async () => {
    const response = await fetch(`${API_BASE}/api/admin/operations`, {
      credentials: "include",
    });
    const payload = (await response.json().catch(() => ({}))) as {
      campaigns?: Campaign[];
    };
    if (!response.ok) return;
    const next = payload.campaigns || [];
    setCampaigns(next);
    setCampaignId((current) =>
      current &&
      next.some((item) => item.id === current && item.type === "coupon")
        ? current
        : next.find((item) => item.type === "coupon")?.id || "",
    );
  };
  useEffect(() => {
    void load();
  }, []);
  const withStepUp = async (action: (ticket: string) => Promise<void>) => {
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
  const parsedIds = (value: string) =>
    Array.from(
      new Set(
        value
          .split(/[\s,，]+/)
          .map((item) => item.trim())
          .filter(Boolean),
      ),
    );
  return (
    <section className="studio-panel coupon-operations">
      <div className="panel-head">
        <h2>优惠券运营</h2>
        <button className="secondary" onClick={() => void load()}>
          刷新
        </button>
      </div>
      {notice && <p className="auth-error">{notice}</p>}
      {!couponCampaigns.length ? (
        <p>请先创建平台券活动。</p>
      ) : (
        <>
          <div className="campaign-rule">
            <select
              value={campaignId}
              onChange={(event) => setCampaignId(event.target.value)}
            >
              {couponCampaigns.map((item) => (
                <option value={item.id} key={item.id}>
                  {item.name} · {item.status}
                </option>
              ))}
            </select>
            <button
              className="secondary"
              onClick={() =>
                void withStepUp(async (ticket) => {
                  const response = await fetch(
                    `${API_BASE}/api/admin/coupons/reminders/run`,
                    {
                      method: "POST",
                      credentials: "include",
                      headers: {
                        "Content-Type": "application/json",
                        "X-Admin-Step-Up": ticket,
                      },
                      body: "{}",
                    },
                  );
                  const payload = (await response.json().catch(() => ({}))) as {
                    reminders?: number;
                    error?: string;
                  };
                  if (!response.ok)
                    return setNotice(payload.error || "失效提醒扫描失败");
                  setNotice(`已发送 ${payload.reminders || 0} 条临期提醒`);
                })
              }
            >
              扫描临期券
            </button>
          </div>
          {selected && (
            <div className="coupon-operation-stats">
              <span>
                领券用户 <b>{selected.claimUsers}</b>
              </span>
              <span>
                已发放 <b>{selected.claimedQuantity}</b>
              </span>
              <span>
                已使用 <b>{selected.usedQuantity}</b>
              </span>
              <span>
                使用转化 <b>{selected.claimToRedeemRate}%</b>
              </span>
              <span>
                券码 {selected.codeRedeemed}/{selected.codeTotal}
              </span>
              <span>失效券码 {selected.codeExpired}</span>
            </div>
          )}
          <div className="admin-operation-grid">
            <div>
              <h3>定向发券</h3>
              <textarea
                value={userIds}
                maxLength={12000}
                onChange={(event) => setUserIds(event.target.value)}
                placeholder="买家账号 ID，使用逗号或换行分隔"
              />
              <select
                value={segment}
                onChange={(event) => setSegment(event.target.value)}
              >
                <option value="">不选择人群</option>
                <option value="all_buyers">全部买家</option>
                <option value="new_buyers">新买家</option>
                <option value="repeat_buyers">复购买家</option>
                <option value="inactive_30d">30 天未活跃买家</option>
              </select>
              <div className="campaign-rule">
                <input
                  type="number"
                  min="1"
                  max="20"
                  value={quantity}
                  onChange={(event) => setQuantity(event.target.value)}
                />
                <button
                  className="primary"
                  disabled={!campaignId || (!userIds.trim() && !segment)}
                  onClick={() =>
                    void withStepUp(async (ticket) => {
                      const response = await fetch(
                        `${API_BASE}/api/admin/campaigns/${encodeURIComponent(campaignId)}/issue`,
                        {
                          method: "POST",
                          credentials: "include",
                          headers: {
                            "Content-Type": "application/json",
                            "X-Admin-Step-Up": ticket,
                          },
                          body: JSON.stringify({
                            userIds: parsedIds(userIds),
                            segment: segment || undefined,
                            quantity: Number(quantity),
                          }),
                        },
                      );
                      const payload = (await response
                        .json()
                        .catch(() => ({}))) as {
                        users?: number;
                        quantity?: number;
                        skipped?: number;
                        error?: string;
                      };
                      if (!response.ok)
                        return setNotice(payload.error || "定向发券失败");
                      setNotice(
                        `已向 ${payload.users || 0} 位买家发放 ${payload.quantity || 0} 张券，跳过 ${payload.skipped || 0} 位`,
                      );
                      setUserIds("");
                      void load();
                    })
                  }
                >
                  发放
                </button>
              </div>
            </div>
            <div>
              <h3>批量生成券码</h3>
              <div className="campaign-rule">
                <input
                  type="number"
                  min="1"
                  max="500"
                  value={codeCount}
                  onChange={(event) => setCodeCount(event.target.value)}
                  placeholder="数量"
                />
                <input
                  value={prefix}
                  maxLength={8}
                  onChange={(event) =>
                    setPrefix(event.target.value.toUpperCase())
                  }
                  placeholder="前缀"
                />
              </div>
              <input
                type="date"
                value={expiresAt}
                onChange={(event) => setExpiresAt(event.target.value)}
              />
              <textarea
                value={assignedUserIds}
                maxLength={12000}
                onChange={(event) => setAssignedUserIds(event.target.value)}
                placeholder="专属买家账号 ID，可选；填写后每人生成一张"
              />
              <button
                className="primary"
                disabled={!campaignId}
                onClick={() =>
                  void withStepUp(async (ticket) => {
                    const ids = parsedIds(assignedUserIds);
                    const response = await fetch(
                      `${API_BASE}/api/admin/campaigns/${encodeURIComponent(campaignId)}/codes`,
                      {
                        method: "POST",
                        credentials: "include",
                        headers: {
                          "Content-Type": "application/json",
                          "X-Admin-Step-Up": ticket,
                        },
                        body: JSON.stringify({
                          count: Number(codeCount),
                          prefix,
                          expiresAt: expiresAt || undefined,
                          assignedUserIds: ids,
                        }),
                      },
                    );
                    const payload = (await response
                      .json()
                      .catch(() => ({}))) as {
                      codes?: string[];
                      error?: string;
                    };
                    if (!response.ok)
                      return setNotice(payload.error || "券码生成失败");
                    setGeneratedCodes(payload.codes || []);
                    setNotice(`已生成 ${(payload.codes || []).length} 个券码`);
                    void load();
                  })
                }
              >
                生成券码
              </button>
              {generatedCodes.length > 0 && (
                <textarea
                  readOnly
                  value={generatedCodes.join("\n")}
                  aria-label="已生成券码"
                />
              )}
            </div>
          </div>
        </>
      )}
    </section>
  );
}


export default function AdminCampaignOperations() {
  return <><CouponOperations /><ActivityOperations /></>;
}

