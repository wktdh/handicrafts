import { useEffect, useState } from "react";

const API_BASE =
  (import.meta as ImportMeta & { env?: { VITE_API_BASE?: string } }).env
    ?.VITE_API_BASE ?? "";

export function GovernanceDeepOperations() {
  type RuleCondition = {
    field:
      "content" | "title" | "description" | "material" | "category" | "tags";
    operator: "contains" | "equals" | "not_contains";
    value: string;
  };
  type Rule = {
    id: string;
    name: string;
    action: "manual_review" | "reject";
    priority: number;
    conditions: RuleCondition[];
    conditionLogic: "all" | "any";
    rolloutPercent: number;
    releaseStatus: "draft" | "active" | "paused";
    version: number;
    hits: number;
    lastHitAt?: string;
  };
  type Task = {
    id: string;
    type: "product_moderation" | "report" | "appeal";
    targetId: string;
    status: string;
    priority: "low" | "normal" | "high" | "urgent";
    dueAt?: string;
    sla: "met" | "on_track" | "warning" | "overdue";
    assigneeId?: string;
    assignee?: string;
  };
  type Template = {
    id: string;
    name: string;
    targetType: "product" | "shop" | "user";
    action: string;
    reason: string;
    enabled: boolean;
  };
  const [rules, setRules] = useState<Rule[]>([]);
  const [tasks, setTasks] = useState<Task[]>([]);
  const [templates, setTemplates] = useState<Template[]>([]);
  const [admins, setAdmins] = useState<{ id: string; name: string }[]>([]);
  const [filters, setFilters] = useState({ status: "", priority: "", sla: "" });
  const [rule, setRule] = useState({
    id: "",
    name: "",
    action: "manual_review" as Rule["action"],
    priority: "100",
    conditionLogic: "all" as Rule["conditionLogic"],
    rolloutPercent: "100",
    releaseStatus: "draft" as Rule["releaseStatus"],
    conditions: [
      {
        field: "content" as RuleCondition["field"],
        operator: "contains" as RuleCondition["operator"],
        value: "",
      },
    ],
  });
  const [targetId, setTargetId] = useState("");
  const [selectedTemplateId, setSelectedTemplateId] = useState("");
  const [taskNotes, setTaskNotes] = useState<Record<string, string>>({});
  const [caseDetail, setCaseDetail] = useState<{
    case: { type: string; id: string; title: string; status: string };
    task?: { priority: string; dueAt?: string; sla: string };
    timeline: {
      type: string;
      content: string;
      actor: string;
      createdAt: string;
    }[];
  } | null>(null);
  const [notice, setNotice] = useState("");
  const stepUp = async (action: (ticket: string) => Promise<void>) => {
    const request = await fetch(`${API_BASE}/api/auth/request-admin-step-up`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    const issued = (await request.json().catch(() => ({}))) as {
      error?: string;
      developmentCode?: string;
    };
    if (!request.ok) return setNotice(issued.error || "无法请求二次验证");
    const code = window.prompt(
      `请输入二次验证码${issued.developmentCode ? `（开发验证码：${issued.developmentCode}）` : ""}`,
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
      error?: string;
      ticket?: string;
    };
    if (!confirmation.ok || !verified.ticket)
      return setNotice(verified.error || "二次验证失败");
    await action(verified.ticket);
  };
  const load = async () => {
    const query = new URLSearchParams(
      Object.entries(filters).filter(([, value]) => value),
    );
    const [operationsResponse, tasksResponse] = await Promise.all([
      fetch(`${API_BASE}/api/admin/governance`, { credentials: "include" }),
      fetch(`${API_BASE}/api/admin/governance/tasks?${query.toString()}`, {
        credentials: "include",
      }),
    ]);
    if (operationsResponse.ok) {
      const payload = (await operationsResponse.json()) as {
        rules: Rule[];
        templates: Template[];
        admins: { id: string; name: string }[];
      };
      setRules(payload.rules || []);
      setTemplates(payload.templates || []);
      setAdmins(payload.admins || []);
    }
    if (tasksResponse.ok)
      setTasks(((await tasksResponse.json()) as { tasks: Task[] }).tasks || []);
  };
  useEffect(() => {
    void load();
  }, [filters.status, filters.priority, filters.sla]);
  const openCase = async (task: Task) => {
    const type = task.type === "product_moderation" ? "product" : task.type;
    const response = await fetch(
      `${API_BASE}/api/admin/governance/cases/${type}/${encodeURIComponent(task.targetId)}`,
      { credentials: "include" },
    );
    const payload = (await response
      .json()
      .catch(() => ({}))) as typeof caseDetail & { error?: string };
    if (!response.ok) return setNotice(payload.error || "案件加载失败");
    setCaseDetail(payload);
  };
  return (
    <section className="studio-panel governance-deep-operations">
      <div className="panel-head">
        <h2>深度治理</h2>
        <button className="secondary" onClick={() => void load()}>
          刷新队列
        </button>
      </div>
      {notice && <p className="auth-error">{notice}</p>}
      <div className="admin-operation-grid">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            void stepUp(async (ticket) => {
              const response = await fetch(
                `${API_BASE}/api/admin/governance/rules`,
                {
                  method: "POST",
                  credentials: "include",
                  headers: {
                    "Content-Type": "application/json",
                    "X-Admin-Step-Up": ticket,
                  },
                  body: JSON.stringify({
                    ...rule,
                    id: rule.id || undefined,
                    priority: Number(rule.priority),
                    rolloutPercent: Number(rule.rolloutPercent),
                  }),
                },
              );
              const payload = (await response.json().catch(() => ({}))) as {
                error?: string;
              };
              if (!response.ok)
                return setNotice(payload.error || "规则保存失败");
              setRule({
                id: "",
                name: "",
                action: "manual_review",
                priority: "100",
                conditionLogic: "all",
                rolloutPercent: "100",
                releaseStatus: "draft",
                conditions: [
                  { field: "content", operator: "contains", value: "" },
                ],
              });
              void load();
            });
          }}
        >
          <h3>{rule.id ? "编辑规则新版本" : "版本化审核规则"}</h3>
          <input
            required
            value={rule.name}
            maxLength={80}
            onChange={(event) => setRule({ ...rule, name: event.target.value })}
            placeholder="规则名称"
          />
          <div className="campaign-rule">
            <select
              value={rule.action}
              onChange={(event) =>
                setRule({
                  ...rule,
                  action: event.target.value as Rule["action"],
                })
              }
            >
              <option value="manual_review">转人工审核</option>
              <option value="reject">自动驳回</option>
            </select>
            <input
              type="number"
              min="1"
              max="999"
              value={rule.priority}
              onChange={(event) =>
                setRule({ ...rule, priority: event.target.value })
              }
              placeholder="优先级"
            />
            <input
              type="number"
              min="0"
              max="100"
              value={rule.rolloutPercent}
              onChange={(event) =>
                setRule({ ...rule, rolloutPercent: event.target.value })
              }
              placeholder="灰度比例"
            />
          </div>
          <select
            value={rule.conditionLogic}
            onChange={(event) =>
              setRule({
                ...rule,
                conditionLogic: event.target.value as Rule["conditionLogic"],
              })
            }
          >
            <option value="all">全部条件满足</option>
            <option value="any">任一条件满足</option>
          </select>
          {rule.conditions.map((condition, index) => (
            <div className="campaign-rule" key={index}>
              <select
                value={condition.field}
                onChange={(event) =>
                  setRule({
                    ...rule,
                    conditions: rule.conditions.map((item, itemIndex) =>
                      itemIndex === index
                        ? {
                            ...item,
                            field: event.target.value as RuleCondition["field"],
                          }
                        : item,
                    ),
                  })
                }
              >
                <option value="content">全内容</option>
                <option value="title">标题</option>
                <option value="description">描述</option>
                <option value="material">材质</option>
                <option value="category">分类</option>
                <option value="tags">标签</option>
              </select>
              <select
                value={condition.operator}
                onChange={(event) =>
                  setRule({
                    ...rule,
                    conditions: rule.conditions.map((item, itemIndex) =>
                      itemIndex === index
                        ? {
                            ...item,
                            operator: event.target
                              .value as RuleCondition["operator"],
                          }
                        : item,
                    ),
                  })
                }
              >
                <option value="contains">包含</option>
                <option value="equals">等于</option>
                <option value="not_contains">不包含</option>
              </select>
              <input
                required
                value={condition.value}
                maxLength={80}
                onChange={(event) =>
                  setRule({
                    ...rule,
                    conditions: rule.conditions.map((item, itemIndex) =>
                      itemIndex === index
                        ? { ...item, value: event.target.value }
                        : item,
                    ),
                  })
                }
                placeholder="条件值"
              />
              {rule.conditions.length > 1 && (
                <button
                  type="button"
                  className="remove"
                  onClick={() =>
                    setRule({
                      ...rule,
                      conditions: rule.conditions.filter(
                        (_, itemIndex) => itemIndex !== index,
                      ),
                    })
                  }
                >
                  ×
                </button>
              )}
            </div>
          ))}
          <div>
            <button
              type="button"
              className="secondary"
              disabled={rule.conditions.length >= 8}
              onClick={() =>
                setRule({
                  ...rule,
                  conditions: [
                    ...rule.conditions,
                    { field: "content", operator: "contains", value: "" },
                  ],
                })
              }
            >
              添加条件
            </button>
            <select
              value={rule.releaseStatus}
              onChange={(event) =>
                setRule({
                  ...rule,
                  releaseStatus: event.target.value as Rule["releaseStatus"],
                })
              }
            >
              <option value="draft">草稿</option>
              <option value="active">启用</option>
              <option value="paused">暂停</option>
            </select>
            <button className="primary">保存版本</button>
          </div>
        </form>
        <div>
          <h3>命中统计与模板执行</h3>
          <div className="admin-operation-list">
            {rules.slice(0, 8).map((item) => (
              <span key={item.id}>
                <b>{item.name}</b> · v{item.version} · 优先级 {item.priority} ·
                灰度 {item.rolloutPercent}% · 命中 {item.hits}
                {item.lastHitAt ? ` · 最近 ${item.lastHitAt}` : ""}
                <button
                  className="secondary"
                  onClick={() =>
                    setRule({
                      id: item.id,
                      name: item.name,
                      action: item.action,
                      priority: String(item.priority),
                      conditionLogic: item.conditionLogic,
                      rolloutPercent: String(item.rolloutPercent),
                      releaseStatus: item.releaseStatus,
                      conditions: item.conditions,
                    })
                  }
                >
                  编辑
                </button>
              </span>
            ))}
          </div>
          <div className="campaign-rule">
            <select
              value={selectedTemplateId}
              onChange={(event) => setSelectedTemplateId(event.target.value)}
            >
              <option value="">选择处罚模板</option>
              {templates.map((item) => (
                <option key={item.id} value={item.id}>
                  {item.name} · {item.action}
                </option>
              ))}
            </select>
            <input
              value={targetId}
              onChange={(event) => setTargetId(event.target.value)}
              placeholder="目标 ID"
            />
            <button
              className="danger"
              disabled={!selectedTemplateId || !targetId}
              onClick={() =>
                void stepUp(async (ticket) => {
                  const response = await fetch(
                    `${API_BASE}/api/admin/enforcement/templates/${encodeURIComponent(selectedTemplateId)}/apply`,
                    {
                      method: "POST",
                      credentials: "include",
                      headers: {
                        "Content-Type": "application/json",
                        "X-Admin-Step-Up": ticket,
                      },
                      body: JSON.stringify({ targetId }),
                    },
                  );
                  const payload = (await response.json().catch(() => ({}))) as {
                    error?: string;
                  };
                  if (!response.ok) setNotice(payload.error || "模板执行失败");
                  else {
                    setTargetId("");
                    setNotice("已套用处罚模板");
                  }
                })
              }
            >
              一键处罚
            </button>
          </div>
        </div>
      </div>
      <div className="governance-task-list">
        <div className="panel-head">
          <h3>任务队列与 SLA</h3>
          <span>
            <select
              value={filters.status}
              onChange={(event) =>
                setFilters({ ...filters, status: event.target.value })
              }
            >
              <option value="">全部状态</option>
              <option value="pending">待处理</option>
              <option value="in_progress">处理中</option>
              <option value="completed">已完成</option>
            </select>
            <select
              value={filters.priority}
              onChange={(event) =>
                setFilters({ ...filters, priority: event.target.value })
              }
            >
              <option value="">全部优先级</option>
              <option value="urgent">紧急</option>
              <option value="high">高</option>
              <option value="normal">普通</option>
              <option value="low">低</option>
            </select>
            <select
              value={filters.sla}
              onChange={(event) =>
                setFilters({ ...filters, sla: event.target.value })
              }
            >
              <option value="">全部 SLA</option>
              <option value="warning">即将超时</option>
              <option value="overdue">已超时</option>
            </select>
          </span>
        </div>
        {tasks.map((task) => (
          <div key={task.id}>
            <span>
              <b>
                {task.type} · {task.priority}
              </b>
              <small>
                {task.targetId} · 截止 {task.dueAt || "未设置"} · SLA {task.sla}
              </small>
            </span>
            <select
              value={task.assigneeId || ""}
              onChange={(event) =>
                void stepUp(async (ticket) => {
                  await fetch(
                    `${API_BASE}/api/admin/governance/tasks/${encodeURIComponent(task.id)}/assign`,
                    {
                      method: "POST",
                      credentials: "include",
                      headers: {
                        "Content-Type": "application/json",
                        "X-Admin-Step-Up": ticket,
                      },
                      body: JSON.stringify({
                        assigneeId: event.target.value || null,
                        note: "工作台转派",
                      }),
                    },
                  );
                  void load();
                })
              }
            >
              <option value="">未分派</option>
              {admins.map((admin) => (
                <option key={admin.id} value={admin.id}>
                  {admin.name}
                </option>
              ))}
            </select>
            <select
              value={task.priority}
              onChange={(event) =>
                void stepUp(async (ticket) => {
                  await fetch(
                    `${API_BASE}/api/admin/governance/tasks/${encodeURIComponent(task.id)}/config`,
                    {
                      method: "POST",
                      credentials: "include",
                      headers: {
                        "Content-Type": "application/json",
                        "X-Admin-Step-Up": ticket,
                      },
                      body: JSON.stringify({ priority: event.target.value }),
                    },
                  );
                  void load();
                })
              }
            >
              <option value="urgent">紧急</option>
              <option value="high">高</option>
              <option value="normal">普通</option>
              <option value="low">低</option>
            </select>
            <button className="secondary" onClick={() => void openCase(task)}>
              案件
            </button>
            <input
              value={taskNotes[task.id] || ""}
              onChange={(event) =>
                setTaskNotes({ ...taskNotes, [task.id]: event.target.value })
              }
              placeholder="处理备注"
            />
            <button
              className="secondary"
              disabled={!taskNotes[task.id]?.trim()}
              onClick={async () => {
                const response = await fetch(
                  `${API_BASE}/api/admin/governance/tasks/${encodeURIComponent(task.id)}/notes`,
                  {
                    method: "POST",
                    credentials: "include",
                    headers: { "Content-Type": "application/json" },
                    body: JSON.stringify({ content: taskNotes[task.id] }),
                  },
                );
                if (!response.ok) return setNotice("任务备注保存失败");
                setTaskNotes({ ...taskNotes, [task.id]: "" });
              }}
            >
              记录
            </button>
          </div>
        ))}
        {!tasks.length && <p>没有符合筛选条件的任务。</p>}
      </div>
      {caseDetail && (
        <div className="governance-case">
          <div className="panel-head">
            <h3>{caseDetail.case.title}</h3>
            <span>
              {caseDetail.case.status}
              {caseDetail.task
                ? ` · ${caseDetail.task.priority} · ${caseDetail.task.sla}`
                : ""}
            </span>
          </div>
          {caseDetail.timeline.map((item, index) => (
            <small key={`${item.createdAt}-${index}`}>
              {item.createdAt} · {item.actor} · {item.type} · {item.content}
            </small>
          ))}
        </div>
      )}
    </section>
  );
}


export function GovernanceServiceInsights() {
  type Admin = { id: string; name: string };
  type Task = {
    id: string;
    type: string;
    targetId: string;
    status: string;
    priority: string;
    sla: string;
    assignee?: string;
    assigneeId?: string;
  };
  type Ticket = {
    id: string;
    subject: string;
    buyer: string;
    priority: string;
    status: string;
    assignee?: string;
  };
  type Payload = {
    governance: {
      sla: {
        backlog: number;
        unassigned: number;
        warning: number;
        overdue: number;
        completed: number;
        onTimeCompleted: number;
        breachedCompleted: number;
        averageResolutionHours: number;
      };
      rules: {
        id: string;
        name: string;
        version: number;
        rolloutPercent: number;
        releaseStatus: string;
        hits: number;
        autoRejected: number;
        approved: number;
        rejected: number;
        pending: number;
        reviewPassRate: number;
      }[];
    };
    support: {
      total: number;
      open: number;
      inProgress: number;
      resolved: number;
      overdue: number;
      warning: number;
      unassigned: number;
      averageFirstResponseHours: number;
      averageResolutionHours: number;
    };
    tasks: Task[];
    tickets: Ticket[];
    admins: Admin[];
  };
  const [data, setData] = useState<Payload | null>(null);
  const [selectedTasks, setSelectedTasks] = useState<string[]>([]);
  const [selectedTickets, setSelectedTickets] = useState<string[]>([]);
  const [assigneeId, setAssigneeId] = useState("");
  const [priority, setPriority] = useState("normal");
  const [ticketStatus, setTicketStatus] = useState("in_progress");
  const [notice, setNotice] = useState("");
  const load = async () => {
    const response = await fetch(`${API_BASE}/api/admin/operations/insights`, {
      credentials: "include",
    });
    const payload = (await response.json().catch(() => ({}))) as Payload & {
      error?: string;
    };
    if (!response.ok)
      return setNotice(payload.error || "治理与客服洞察加载失败");
    setData(payload);
    setSelectedTasks((ids) =>
      ids.filter((id) => payload.tasks.some((item) => item.id === id)),
    );
    setSelectedTickets((ids) =>
      ids.filter((id) => payload.tickets.some((item) => item.id === id)),
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
    const issue = (await request.json().catch(() => ({}))) as {
      developmentCode?: string;
      error?: string;
    };
    if (!request.ok) return setNotice(issue.error || "无法请求二次验证");
    const code = window.prompt(
      `请输入二次验证码${issue.developmentCode ? `（开发验证码：${issue.developmentCode}）` : ""}`,
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
  const bulkTasks = (action: "assign" | "priority") =>
    void stepUp(async (ticket) => {
      const response = await fetch(
        `${API_BASE}/api/admin/governance/tasks/bulk`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "X-Admin-Step-Up": ticket,
          },
          body: JSON.stringify({
            taskIds: selectedTasks,
            action,
            ...(action === "assign" ? { assigneeId: assigneeId || null } : {}),
            ...(action === "priority" ? { priority } : {}),
          }),
        },
      );
      const payload = (await response.json().catch(() => ({}))) as {
        count?: number;
        error?: string;
      };
      if (!response.ok)
        return setNotice(payload.error || "批量治理任务处理失败");
      setSelectedTasks([]);
      setNotice(`已处理 ${payload.count || 0} 项治理任务`);
      void load();
    });
  const bulkTickets = (action: "assign" | "status") =>
    void stepUp(async (ticket) => {
      const response = await fetch(
        `${API_BASE}/api/admin/support/tickets/bulk`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "X-Admin-Step-Up": ticket,
          },
          body: JSON.stringify({
            ticketIds: selectedTickets,
            action,
            ...(action === "assign"
              ? { assigneeId: assigneeId || null }
              : { status: ticketStatus }),
          }),
        },
      );
      const payload = (await response.json().catch(() => ({}))) as {
        count?: number;
        error?: string;
      };
      if (!response.ok) return setNotice(payload.error || "批量工单处理失败");
      setSelectedTickets([]);
      setNotice(`已处理 ${payload.count || 0} 张工单`);
      void load();
    });
  const toggle = (
    ids: string[],
    id: string,
    setIds: (value: string[]) => void,
  ) =>
    setIds(ids.includes(id) ? ids.filter((item) => item !== id) : [...ids, id]);
  if (!data) return null;
  return (
    <section className="studio-panel governance-service-insights">
      <div className="panel-head">
        <h2>治理与客服效能</h2>
        <button className="secondary" onClick={() => void load()}>
          刷新
        </button>
      </div>
      {notice && <p className="auth-error">{notice}</p>}
      <div className="coupon-operation-stats">
        <span>
          治理待办 <b>{data.governance.sla.backlog}</b>
        </span>
        <span>
          治理超时 / 预警{" "}
          <b>
            {data.governance.sla.overdue} / {data.governance.sla.warning}
          </b>
        </span>
        <span>
          治理按时完成 <b>{data.governance.sla.onTimeCompleted}</b>
        </span>
        <span>
          平均治理时长 <b>{data.governance.sla.averageResolutionHours}h</b>
        </span>
        <span>
          未分派工单 <b>{data.support.unassigned}</b>
        </span>
        <span>
          工单超时 / 预警{" "}
          <b>
            {data.support.overdue} / {data.support.warning}
          </b>
        </span>
        <span>
          首响 / 解决{" "}
          <b>
            {data.support.averageFirstResponseHours}h /{" "}
            {data.support.averageResolutionHours}h
          </b>
        </span>
      </div>
      <div className="admin-analytics-grid">
        <div className="studio-panel analytics-ranking">
          <div className="panel-head">
            <h3>规则灰度效果</h3>
            <span>命中后的审核结果</span>
          </div>
          {data.governance.rules.map((rule) => (
            <p key={rule.id}>
              <span>
                {rule.name} v{rule.version} · 灰度 {rule.rolloutPercent}% · 命中{" "}
                {rule.hits} · 自动拦截 {rule.autoRejected} · 通过率{" "}
                {rule.reviewPassRate}%
              </span>
              <b>
                通过 {rule.approved} / 驳回 {rule.rejected}
              </b>
            </p>
          ))}
          {!data.governance.rules.length && (
            <p>
              <span>暂无规则命中数据</span>
            </p>
          )}
        </div>
        <div className="studio-panel analytics-ranking">
          <div className="panel-head">
            <h3>客服工单统计</h3>
            <span>总计 {data.support.total}</span>
          </div>
          <p>
            <span>待受理</span>
            <b>{data.support.open}</b>
          </p>
          <p>
            <span>处理中</span>
            <b>{data.support.inProgress}</b>
          </p>
          <p>
            <span>已解决</span>
            <b>{data.support.resolved}</b>
          </p>
          <p>
            <span>未分派</span>
            <b>{data.support.unassigned}</b>
          </p>
        </div>
      </div>
      <div className="governance-batch-workspace">
        <div>
          <div className="panel-head">
            <h3>批量治理任务</h3>
            <span>{selectedTasks.length} 项已选</span>
          </div>
          <div className="governance-bulk">
            <label>
              <input
                type="checkbox"
                checked={
                  data.tasks.length > 0 &&
                  data.tasks.every((item) => selectedTasks.includes(item.id))
                }
                onChange={(event) =>
                  setSelectedTasks(
                    event.target.checked
                      ? data.tasks.map((item) => item.id)
                      : [],
                  )
                }
              />
              全选
            </label>
            <select
              value={assigneeId}
              onChange={(event) => setAssigneeId(event.target.value)}
            >
              <option value="">选择管理员</option>
              {data.admins.map((admin) => (
                <option key={admin.id} value={admin.id}>
                  {admin.name}
                </option>
              ))}
            </select>
            <button
              className="secondary"
              disabled={!selectedTasks.length || !assigneeId}
              onClick={() => bulkTasks("assign")}
            >
              批量分派
            </button>
            <select
              value={priority}
              onChange={(event) => setPriority(event.target.value)}
            >
              <option value="urgent">紧急</option>
              <option value="high">高</option>
              <option value="normal">普通</option>
              <option value="low">低</option>
            </select>
            <button
              className="secondary"
              disabled={!selectedTasks.length}
              onClick={() => bulkTasks("priority")}
            >
              改优先级
            </button>
          </div>
          <div className="admin-operation-list">
            {data.tasks.slice(0, 30).map((task) => (
              <div key={task.id}>
                <label>
                  <input
                    type="checkbox"
                    checked={selectedTasks.includes(task.id)}
                    onChange={() =>
                      toggle(selectedTasks, task.id, setSelectedTasks)
                    }
                  />
                  {task.type}
                </label>
                <span>
                  {task.targetId} · {task.priority} · {task.sla} ·{" "}
                  {task.assignee || "未分派"}
                </span>
              </div>
            ))}
          </div>
        </div>
        <div>
          <div className="panel-head">
            <h3>批量客服工单</h3>
            <span>{selectedTickets.length} 张已选</span>
          </div>
          <div className="governance-bulk">
            <label>
              <input
                type="checkbox"
                checked={
                  data.tickets.length > 0 &&
                  data.tickets.every((item) =>
                    selectedTickets.includes(item.id),
                  )
                }
                onChange={(event) =>
                  setSelectedTickets(
                    event.target.checked
                      ? data.tickets.map((item) => item.id)
                      : [],
                  )
                }
              />
              全选
            </label>
            <button
              className="secondary"
              disabled={!selectedTickets.length || !assigneeId}
              onClick={() => bulkTickets("assign")}
            >
              批量分派
            </button>
            <select
              value={ticketStatus}
              onChange={(event) => setTicketStatus(event.target.value)}
            >
              <option value="in_progress">处理中</option>
              <option value="resolved">已解决</option>
              <option value="closed">已关闭</option>
            </select>
            <button
              className="secondary"
              disabled={!selectedTickets.length}
              onClick={() => bulkTickets("status")}
            >
              更新状态
            </button>
          </div>
          <div className="admin-operation-list">
            {data.tickets.slice(0, 30).map((item) => (
              <div key={item.id}>
                <label>
                  <input
                    type="checkbox"
                    checked={selectedTickets.includes(item.id)}
                    onChange={() =>
                      toggle(selectedTickets, item.id, setSelectedTickets)
                    }
                  />
                  {item.subject}
                </label>
                <span>
                  {item.buyer} · {item.priority} · {item.status} ·{" "}
                  {item.assignee || "未分派"}
                </span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}


