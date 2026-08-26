import { useEffect, useState } from "react";

export default function SellerActivityOperations({ shopId, apiBase }: { shopId: string; apiBase: string }) {
  type Activity = {
    id: string;
    name: string;
    description: string;
    status: string;
    application?: {
      id: string;
      status: string;
      note: string;
      reviewNote?: string;
    } | null;
    myProducts?: {
      id: string;
      productId: string;
      title: string;
      quotaStock: number;
      reservedStock: number;
      productStock: number;
      status: string;
      reviewNote?: string;
    }[];
  };
  const [activities, setActivities] = useState<Activity[]>([]);
  const [notes, setNotes] = useState<Record<string, string>>({});
  const [productIds, setProductIds] = useState<Record<string, string>>({});
  const [quotas, setQuotas] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");
  const load = async () => {
    const response = await fetch(
      `${apiBase}/api/seller/activities?shopId=${encodeURIComponent(shopId)}`,
      { credentials: "include" },
    );
    const payload = (await response.json().catch(() => ({}))) as {
      activities?: Activity[];
      error?: string;
    };
    if (!response.ok) return setNotice(payload.error || "活动加载失败");
    setActivities(payload.activities || []);
  };
  useEffect(() => {
    void load();
  }, [shopId]);
  const apply = async (activity: Activity) => {
    const response = await fetch(
      `${apiBase}/api/seller/activity-applications`,
      {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          activityId: activity.id,
          shopId,
          note: notes[activity.id] || "",
        }),
      },
    );
    const payload = (await response.json().catch(() => ({}))) as {
      error?: string;
    };
    if (!response.ok) return setNotice(payload.error || "报名提交失败");
    setNotice("报名已提交，等待平台审核");
    void load();
  };
  const saveProduct = async (activity: Activity) => {
    const response = await fetch(`${apiBase}/api/seller/activity-products`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        applicationId: activity.application?.id,
        productId: productIds[activity.id],
        quotaStock: Number(quotas[activity.id]),
      }),
    });
    const payload = (await response.json().catch(() => ({}))) as {
      error?: string;
    };
    if (!response.ok) return setNotice(payload.error || "活动作品提交失败");
    setNotice("活动作品已提交，等待平台审核");
    void load();
  };
  return (
    <section className="studio-panel seller-activity-operations">
      <div className="panel-head">
        <h2>活动报名与作品配额</h2>
        <button className="secondary" onClick={() => void load()}>
          刷新
        </button>
      </div>
      {notice && <p className="auth-error">{notice}</p>}
      <div className="governance-task-list">
        {activities.map((activity) => (
          <div key={activity.id}>
            <span>
              <b>{activity.name}</b>
              <small>
                {activity.status} · {activity.description}
              </small>
              {activity.application && (
                <small>
                  报名状态：{activity.application.status}
                  {activity.application.reviewNote
                    ? ` · ${activity.application.reviewNote}`
                    : ""}
                </small>
              )}
            </span>
            {!activity.application && activity.status === "open" && (
              <>
                <input
                  value={notes[activity.id] || ""}
                  maxLength={500}
                  onChange={(event) =>
                    setNotes({ ...notes, [activity.id]: event.target.value })
                  }
                  placeholder="报名说明"
                />
                <button
                  className="primary"
                  onClick={() => void apply(activity)}
                >
                  报名
                </button>
              </>
            )}
            {activity.application?.status === "approved" && (
              <div className="campaign-rule">
                <input
                  value={productIds[activity.id] || ""}
                  onChange={(event) =>
                    setProductIds({
                      ...productIds,
                      [activity.id]: event.target.value,
                    })
                  }
                  placeholder="作品 ID"
                />
                <input
                  type="number"
                  min="0"
                  value={quotas[activity.id] || ""}
                  onChange={(event) =>
                    setQuotas({ ...quotas, [activity.id]: event.target.value })
                  }
                  placeholder="活动配额"
                />
                <button
                  className="secondary"
                  disabled={!productIds[activity.id] || !quotas[activity.id]}
                  onClick={() => void saveProduct(activity)}
                >
                  提交作品
                </button>
              </div>
            )}
            <div className="admin-operation-list">
              {activity.myProducts?.map((item) => (
                <span key={item.id}>
                  {item.title} · 配额 {item.quotaStock} · 已占{" "}
                  {item.reservedStock} · 作品库存 {item.productStock} ·{" "}
                  {item.status}
                  {item.reviewNote ? ` · ${item.reviewNote}` : ""}
                </span>
              ))}
            </div>
          </div>
        ))}
        {!activities.length && <p>暂无可报名或已报名活动</p>}
      </div>
    </section>
  );
}


