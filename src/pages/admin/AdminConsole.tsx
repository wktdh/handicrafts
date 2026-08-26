import {
  lazy,
  Suspense,
  useEffect,
  useState,
  type FormEvent,
} from "react";
import { ImagePlus } from "lucide-react";

const API_BASE =
  (import.meta as ImportMeta & { env?: { VITE_API_BASE?: string } }).env
    ?.VITE_API_BASE ?? "";

const LazyRiskControlOperations = lazy(
  () => import("./RiskControlOperations"),
);
const LazyAdminCommunityOperations = lazy(
  () => import("./AdminCommunityOperations"),
);
const LazyAdminToolsOperations = lazy(
  () => import("./AdminToolsOperations"),
);
const LazyAdminFinanceOperations = lazy(
  () => import("./AdminFinanceOperations"),
);
const LazyGovernanceDeepOperations = lazy(
  () =>
    import("./GovernanceOperations").then((module) => ({
      default: module.GovernanceDeepOperations,
    })),
);
const LazyGovernanceServiceInsights = lazy(
  () =>
    import("./GovernanceOperations").then((module) => ({
      default: module.GovernanceServiceInsights,
    })),
);
const LazyAdminServiceManagement = lazy(
  () => import("./AdminServiceManagement"),
);
const LazyAdminCampaignOperations = lazy(
  () => import("./AdminCampaignOperations"),
);

function money(value: number) {
  return `$${value.toFixed(2)}`;
}

function Metric({ label, value, trend }: { label: string; value: string; trend: string }) {
  return <div className="metric"><span>{label}</span><b>{value}</b><small>{trend}</small></div>;
}

type Account = { name: string };

export default function AdminConsole({
  account,
  onLogout,
  compressImageForUpload,
  setDocumentTitle,
}: {
  account: Account;
  onLogout: () => void;
  compressImageForUpload: (file: File) => Promise<string>;
  setDocumentTitle: (page: string) => void;
}) {
  const [reports, setReports] = useState<
    {
      id: string;
      targetType: string;
      targetId: string;
      reason: string;
      detail: string;
      status: string;
      reporter: string;
      createdAt: string;
    }[]
  >([]);
  const [products, setProducts] = useState<
    {
      id: string;
      title: string;
      shop: string;
      status: string;
      moderationStatus: string;
      reason?: string;
    }[]
  >([]);
  const [notice, setNotice] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [lastSyncedAt, setLastSyncedAt] = useState<Date | null>(null);
  const [activeAdminSection, setActiveAdminSection] = useState<
    "overview" | "operations" | "governance" | "tools" | "finance"
  >(() => {
    const section = new URLSearchParams(window.location.search).get("adminSection");
    return ["overview", "operations", "governance", "tools", "finance"].includes(section || "")
      ? (section as "overview" | "operations" | "governance" | "tools" | "finance")
      : "overview";
  });
  useEffect(() => {
    const titles = {
      overview: "管理后台",
      operations: "运营管理",
      governance: "平台治理",
      tools: "运营工具",
      finance: "平台财务",
    };
    setDocumentTitle(titles[activeAdminSection]);
  }, [activeAdminSection]);
  const [stepUp, setStepUp] = useState<{
    action: (ticket: string) => Promise<void>;
    developmentCode?: string;
  } | null>(null);
  const [stepUpCode, setStepUpCode] = useState("");
  const [stepUpError, setStepUpError] = useState("");
  const [analyticsDays, setAnalyticsDays] = useState<1 | 7 | 30 | 90>(1);
  const [analytics, setAnalytics] = useState<{
    days: number;
    revenue: number;
    orders: number;
    activeShops: number;
    pendingReports: number;
    pendingAppeals: number;
    appealHours: number;
    orderStatuses: Record<string, number>;
    activeCampaigns: number;
    daily: { date: string; revenue: number; orders: number }[];
    categories: { name: string; sales: number; revenue: number }[];
    topShops: { name: string; orders: number; revenue: number }[];
    campaignPerformance: CampaignSummary[];
    funnel: {
      visitors: number;
      views: number;
      addCarts: number;
      checkouts: number;
      paidBuyers: number;
      viewToCartRate: number;
      cartToCheckoutRate: number;
      checkoutToPaidRate: number;
      cartDropOff: number;
      checkoutDropOff: number;
      paymentDropOff: number;
    };
    channels: {
      channel: string;
      visitors: number;
      addCarts: number;
      checkouts: number;
      paidOrders: number;
      revenue: number;
      visitorToCartRate: number;
      checkoutToPaidRate: number;
    }[];
    repeatCustomers: number;
    repeatRate: number;
    quality: {
      paidOrders: number;
      averageOrderValue: number;
      averageItemValue: number;
      refundOrders: number;
      refundAmount: number;
      refundRate: number;
      afterSaleRate: number;
      fulfillmentHours: number;
    };
    customers: {
      new: number;
      repeat: number;
      repeatOrders: number;
      repeatRevenue: number;
      repeatRate: number;
    };
    productPerformance: {
      id: string;
      title: string;
      views: number;
      sales: number;
      revenue: number;
      conversionRate: number;
    }[];
  } | null>(null);
  const [announcements, setAnnouncements] = useState<
    {
      id: string;
      title: string;
      content: string;
      imageUrl?: string | null;
      audience: string;
      status: string;
      publishedAt?: string;
    }[]
  >([]);
  type CampaignSummary = {
    id: string;
    name: string;
    type: "coupon" | "full_reduction";
    status: string;
    rule: { threshold?: number; discount?: number };
    budget: number | null;
    budgetRemaining: number | null;
    totalUsageLimit: number | null;
    perUserUsageLimit: number;
    reserved: number;
    redemptions: number;
    reversed: number;
    spent: number;
    attributedRevenue: number;
    attributedOrders: number;
    redemptionRate: number;
    averageOrderValue: number;
    roi: number | null;
    usageRemaining: number | null;
  };
  const [campaigns, setCampaigns] = useState<CampaignSummary[]>([]);
  const [governanceTasks, setGovernanceTasks] = useState<
    {
      id: string;
      type: string;
      targetId: string;
      status: string;
      assigneeId?: string;
      assignee?: string;
      createdAt: string;
    }[]
  >([]);
  const [governanceAdmins, setGovernanceAdmins] = useState<
    { id: string; name: string }[]
  >([]);
  const [governanceRules, setGovernanceRules] = useState<
    {
      id: string;
      name: string;
      keyword: string;
      action: "manual_review" | "reject";
      enabled: boolean;
    }[]
  >([]);
  const [enforcementTemplates, setEnforcementTemplates] = useState<
    {
      id: string;
      name: string;
      targetType: "product" | "shop" | "user";
      action: string;
      reason: string;
      enabled: boolean;
    }[]
  >([]);
  const [selectedProducts, setSelectedProducts] = useState<string[]>([]);
  const [ruleDraft, setRuleDraft] = useState({
    name: "",
    keyword: "",
    action: "manual_review" as "manual_review" | "reject",
  });
  const [templateDraft, setTemplateDraft] = useState({
    name: "",
    targetType: "product" as "product" | "shop" | "user",
    action: "unlist_product",
    reason: "",
  });
  const [announcementDraft, setAnnouncementDraft] = useState({
    title: "",
    content: "",
    imageUrl: "",
    audience: "all",
    status: "draft",
  });
  const [announcementModalOpen, setAnnouncementModalOpen] = useState(false);
  const [uploadingAnnouncementImage, setUploadingAnnouncementImage] =
    useState(false);
  const [campaignDraft, setCampaignDraft] = useState({
    name: "",
    type: "coupon" as "coupon" | "full_reduction",
    status: "draft",
    threshold: "",
    discount: "",
    budget: "",
    totalUsageLimit: "",
    perUserUsageLimit: "1",
  });
  const [editingCampaignId, setEditingCampaignId] = useState<string | null>(
    null,
  );
  const load = async () => {
    setIsLoading(true);
    try {
      const [
        reportsResponse,
        productsResponse,
        analyticsResponse,
        operationsResponse,
        governanceResponse,
      ] = await Promise.all([
        fetch(`${API_BASE}/api/admin/reports`, { credentials: "include" }),
        fetch(`${API_BASE}/api/admin/moderation/products`, {
          credentials: "include",
        }),
        fetch(`${API_BASE}/api/analytics/admin?days=${analyticsDays}`, {
          credentials: "include",
        }),
        fetch(`${API_BASE}/api/admin/operations`, { credentials: "include" }),
        fetch(`${API_BASE}/api/admin/governance`, { credentials: "include" }),
      ]);
      if (reportsResponse.ok)
        setReports(
          ((await reportsResponse.json()) as { reports: typeof reports })
            .reports,
        );
      if (productsResponse.ok)
        setProducts(
          ((await productsResponse.json()) as { products: typeof products })
            .products,
        );
      if (analyticsResponse.ok)
        setAnalytics(
          (
            (await analyticsResponse.json()) as {
              analytics: NonNullable<typeof analytics>;
            }
          ).analytics,
        );
      if (operationsResponse.ok) {
        const operations = (await operationsResponse.json()) as {
          announcements: typeof announcements;
          campaigns: typeof campaigns;
        };
        setAnnouncements(operations.announcements);
        setCampaigns(operations.campaigns);
      }
      if (governanceResponse.ok) {
        const governance = (await governanceResponse.json()) as {
          tasks: typeof governanceTasks;
          admins: typeof governanceAdmins;
          rules: typeof governanceRules;
          templates: typeof enforcementTemplates;
        };
        setGovernanceTasks(governance.tasks);
        setGovernanceAdmins(governance.admins);
        setGovernanceRules(governance.rules);
        setEnforcementTemplates(governance.templates);
      }
      if (
        ![
          reportsResponse,
          productsResponse,
          analyticsResponse,
          operationsResponse,
          governanceResponse,
        ].some((response) => !response.ok)
      )
        setLastSyncedAt(new Date());
      else setNotice("部分运营数据加载失败，请刷新后重试");
    } catch {
      setNotice("运营后台暂时无法加载，请检查网络后重试");
    } finally {
      setIsLoading(false);
    }
  };
  useEffect(() => {
    void load();
  }, [analyticsDays]);
  const beginStepUp = async (action: (ticket: string) => Promise<void>) => {
    setStepUpError("");
    const response = await fetch(`${API_BASE}/api/auth/request-admin-step-up`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: "{}",
    });
    const result = (await response.json().catch(() => ({}))) as {
      error?: string;
      developmentCode?: string;
    };
    if (!response.ok) return setNotice(result.error || "无法发送二次验证码");
    setStepUpCode("");
    setStepUp({ action, developmentCode: result.developmentCode });
  };
  const confirmStepUp = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!stepUp) return;
    setStepUpError("");
    const response = await fetch(`${API_BASE}/api/auth/confirm-admin-step-up`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code: stepUpCode }),
    });
    const result = (await response.json().catch(() => ({}))) as {
      error?: string;
      ticket?: string;
    };
    if (!response.ok || !result.ticket)
      return setStepUpError(result.error || "验证失败，请重试");
    await stepUp.action(result.ticket);
    setStepUp(null);
    setStepUpCode("");
  };
  const resolveReport = (id: string, decision: "resolved" | "dismissed") =>
    beginStepUp(async (ticket) => {
      const response = await fetch(
        `${API_BASE}/api/admin/reports/${encodeURIComponent(id)}`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "X-Admin-Step-Up": ticket,
          },
          body: JSON.stringify({
            decision,
            unlistProduct: decision === "resolved",
          }),
        },
      );
      if (!response.ok) return setNotice("举报处理失败");
      setNotice("举报已处理");
      void load();
    });
  const unlistProduct = (id: string) => {
    const reason = window.prompt("请填写下架原因");
    if (!reason?.trim()) return;
    beginStepUp(async (ticket) => {
      const response = await fetch(
        `${API_BASE}/api/admin/moderation/products/${encodeURIComponent(id)}`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "X-Admin-Step-Up": ticket,
          },
          body: JSON.stringify({ decision: "rejected", reason: reason.trim() }),
        },
      );
      if (!response.ok) return setNotice("作品下架失败");
      setNotice("作品已下架");
      void load();
    });
  };
  const bulkUnlistProducts = () => {
    const reason = window.prompt("请填写批量下架原因");
    if (!reason?.trim()) return;
    beginStepUp(async (ticket) => {
      const response = await fetch(
        `${API_BASE}/api/admin/moderation/products/bulk`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "X-Admin-Step-Up": ticket,
          },
          body: JSON.stringify({
            productIds: selectedProducts,
            decision: "rejected",
            reason: reason.trim(),
          }),
        },
      );
      const payload = (await response.json().catch(() => ({}))) as {
        error?: string;
        count?: number;
      };
      if (!response.ok) return setNotice(payload.error || "批量下架失败");
      setSelectedProducts([]);
      setNotice(`已下架 ${payload.count || 0} 件作品`);
      void load();
    });
  };
  const saveRule = () =>
    beginStepUp(async (ticket) => {
      const response = await fetch(`${API_BASE}/api/admin/governance/rules`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-Admin-Step-Up": ticket,
        },
        body: JSON.stringify(ruleDraft),
      });
      const payload = (await response.json().catch(() => ({}))) as {
        error?: string;
      };
      if (!response.ok) return setNotice(payload.error || "审核规则保存失败");
      setRuleDraft({ name: "", keyword: "", action: "manual_review" });
      setNotice("审核规则已保存");
      void load();
    });
  const saveTemplate = () =>
    beginStepUp(async (ticket) => {
      const response = await fetch(
        `${API_BASE}/api/admin/governance/templates`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "X-Admin-Step-Up": ticket,
          },
          body: JSON.stringify(templateDraft),
        },
      );
      const payload = (await response.json().catch(() => ({}))) as {
        error?: string;
      };
      if (!response.ok) return setNotice(payload.error || "处罚模板保存失败");
      setTemplateDraft({
        name: "",
        targetType: "product",
        action: "unlist_product",
        reason: "",
      });
      setNotice("处罚模板已保存");
      void load();
    });
  const assignTask = (taskId: string, assigneeId: string) =>
    beginStepUp(async (ticket) => {
      const response = await fetch(
        `${API_BASE}/api/admin/governance/tasks/${encodeURIComponent(taskId)}/assign`,
        {
          method: "POST",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "X-Admin-Step-Up": ticket,
          },
          body: JSON.stringify({ assigneeId: assigneeId || null }),
        },
      );
      if (!response.ok) return setNotice("任务分派失败");
      setNotice("治理任务已分派");
      void load();
    });
  const exportGovernance = async () => {
    const response = await fetch(`${API_BASE}/api/admin/governance/export`, {
      credentials: "include",
    });
    const payload = (await response.json().catch(() => ({}))) as {
      tasks?: {
        type: string;
        targetId: string;
        status: string;
        assignee: string;
        createdAt: string;
        completedAt: string;
      }[];
      enforcements?: {
        action: string;
        targetType: string;
        targetId: string;
        reason: string;
        status: string;
        createdAt: string;
      }[];
    };
    if (!response.ok) return setNotice("治理数据导出失败");
    const rows = [
      ["类型", "对象", "状态", "处理人", "创建时间", "完成时间"],
      ...(payload.tasks || []).map((item) => [
        item.type,
        item.targetId,
        item.status,
        item.assignee,
        item.createdAt,
        item.completedAt,
      ]),
      ["处罚动作", "对象类型", "对象", "原因", "状态", "创建时间"],
      ...(payload.enforcements || []).map((item) => [
        item.action,
        item.targetType,
        item.targetId,
        item.reason,
        item.status,
        item.createdAt,
      ]),
    ];
    const csv = `\uFEFF${rows.map((row) => row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(",")).join("\n")}`;
    const url = URL.createObjectURL(
      new Blob([csv], { type: "text/csv;charset=utf-8" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = "平台治理数据.csv";
    link.click();
    URL.revokeObjectURL(url);
  };
  const saveAnnouncement = () =>
    void (async () => {
      const response = await fetch(`${API_BASE}/api/admin/announcements`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(announcementDraft),
      });
      const payload = (await response.json().catch(() => ({}))) as {
        error?: string;
      };
      if (!response.ok) return setNotice(payload.error || "公告保存失败");
      setAnnouncementDraft({
        title: "",
        content: "",
        imageUrl: "",
        audience: "all",
        status: "draft",
      });
      setAnnouncementModalOpen(false);
      setNotice("公告已保存");
      void load();
    })();
  const uploadAnnouncementImage = async (file?: File) => {
    if (!file) return;
    setUploadingAnnouncementImage(true);
    try {
      const data = await compressImageForUpload(file);
      const response = await fetch(`${API_BASE}/api/media`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ data, mediaType: "image" }),
      });
      const payload = (await response.json().catch(() => ({}))) as {
        url?: string;
        error?: string;
      };
      if (!response.ok || !payload.url)
        throw new Error(payload.error || "图片上传失败");
      setAnnouncementDraft((value) => ({ ...value, imageUrl: payload.url! }));
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "图片上传失败");
    } finally {
      setUploadingAnnouncementImage(false);
    }
  };
  const saveCampaign = () =>
    beginStepUp(async (ticket) => {
      const response = await fetch(`${API_BASE}/api/admin/campaigns`, {
        method: "POST",
        credentials: "include",
        headers: {
          "Content-Type": "application/json",
          "X-Admin-Step-Up": ticket,
        },
        body: JSON.stringify({
          id: editingCampaignId || undefined,
          name: campaignDraft.name,
          type: campaignDraft.type,
          status: campaignDraft.status,
          budget: Number(campaignDraft.budget),
          totalUsageLimit: Number(campaignDraft.totalUsageLimit),
          perUserUsageLimit: Number(campaignDraft.perUserUsageLimit),
          rule: {
            threshold: Number(campaignDraft.threshold),
            discount: Number(campaignDraft.discount),
          },
        }),
      });
      const payload = (await response.json().catch(() => ({}))) as {
        error?: string;
      };
      if (!response.ok) return setNotice(payload.error || "活动保存失败");
      setCampaignDraft({
        name: "",
        type: "coupon",
        status: "draft",
        threshold: "",
        discount: "",
        budget: "",
        totalUsageLimit: "",
        perUserUsageLimit: "1",
      });
      setEditingCampaignId(null);
      setNotice("活动已保存");
      void load();
    });
  const editCampaign = (item: CampaignSummary) => {
    setEditingCampaignId(item.id);
    setCampaignDraft({
      name: item.name,
      type: item.type,
      status: item.status,
      threshold: String(item.rule.threshold || 0),
      discount: String(item.rule.discount || ""),
      budget: item.budget === null ? "" : String(item.budget),
      totalUsageLimit:
        item.totalUsageLimit === null ? "" : String(item.totalUsageLimit),
      perUserUsageLimit: String(item.perUserUsageLimit),
    });
  };
  const endCampaign = (id: string) =>
    beginStepUp(async (ticket) => {
      const response = await fetch(
        `${API_BASE}/api/admin/campaigns/${encodeURIComponent(id)}/end`,
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
      if (!response.ok) return setNotice("活动结束失败");
      setNotice("活动已结束，新的领取与抵扣已停止");
      void load();
    });
  const analyticsPeriodLabel =
    analyticsDays === 1 ? "今日" : `近 ${analyticsDays} 天`;
  const trendDaily = (() => {
    if (!analytics) return [];
    if (analytics.days !== 90) return analytics.daily;
    const weekly = [] as { date: string; revenue: number; orders: number }[];
    for (let index = 0; index < analytics.daily.length; index += 7) {
      const days = analytics.daily.slice(index, index + 7);
      weekly.push({
        date: days[days.length - 1].date,
        revenue: days.reduce((sum, item) => sum + item.revenue, 0),
        orders: days.reduce((sum, item) => sum + item.orders, 0),
      });
    }
    return weekly;
  })();
  const openAdminSection = (section: typeof activeAdminSection) => {
    setActiveAdminSection(section);
    const url = new URL(window.location.href);
    url.searchParams.set("adminSection", section);
    window.history.pushState({ adminSection: section }, "", `${url.pathname}${url.search}${url.hash}`);
    window.scrollTo({ top: 0, behavior: "smooth" });
  };
  useEffect(() => {
    const syncAdminSection = () => {
      const section = new URLSearchParams(window.location.search).get("adminSection");
      if (["overview", "operations", "governance", "tools", "finance"].includes(section || ""))
        setActiveAdminSection(section as typeof activeAdminSection);
    };
    window.addEventListener("popstate", syncAdminSection);
    return () => window.removeEventListener("popstate", syncAdminSection);
  }, []);
  const exportAnalytics = async () => {
    const response = await fetch(
      `${API_BASE}/api/analytics/admin/export?days=${analyticsDays}`,
      { credentials: "include" },
    );
    const payload = (await response.json().catch(() => ({}))) as {
      days?: number;
      sections?: {
        name: string;
        headers: string[];
        rows: (string | number)[][];
      }[];
      error?: string;
    };
    if (!response.ok || !payload.sections)
      return setNotice(payload.error || "运营报表导出失败");
    const rows = payload.sections.flatMap(
      (section) =>
        [[section.name], section.headers, ...section.rows, []] as (
          string | number
        )[][],
    );
    const csv = `\uFEFF${rows.map((row) => row.map((value) => `"${String(value).replace(/"/g, '""')}"`).join(",")).join("\n")}`;
    const url = URL.createObjectURL(
      new Blob([csv], { type: "text/csv;charset=utf-8" }),
    );
    const link = document.createElement("a");
    link.href = url;
    link.download = `平台运营深度报表-${payload.days || analyticsDays}天.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };
  return (
    <main className="container page section admin-console">
      <header className="page-title">
        <div>
          <h1>管理员后台</h1>
          <p>{account.name}，处理用户举报与违规作品</p>
        </div>
        <div className="admin-header-actions">
          {lastSyncedAt && (
            <span>
              更新于{" "}
              {lastSyncedAt.toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
              })}
            </span>
          )}
          <button
            className="secondary"
            disabled={isLoading}
            onClick={() => void load()}
          >
            {isLoading ? "刷新中…" : "刷新数据"}
          </button>
          <button className="secondary" onClick={onLogout}>
            退出
          </button>
        </div>
      </header>
      <div className="admin-layout">
      <nav className="admin-section-nav" aria-label="管理员后台导航">
        <button
          type="button"
          className={activeAdminSection === "overview" ? "active" : ""}
          aria-current={activeAdminSection === "overview" ? "page" : undefined}
          onClick={() => openAdminSection("overview")}
        >
          <b>总览</b>
          <small>交易与运营数据</small>
        </button>
        <button
          type="button"
          className={activeAdminSection === "operations" ? "active" : ""}
          aria-current={
            activeAdminSection === "operations" ? "page" : undefined
          }
          onClick={() => openAdminSection("operations")}
        >
          <b>平台运营</b>
          <small>公告与活动</small>
        </button>
        <button
          type="button"
          className={activeAdminSection === "governance" ? "active" : ""}
          aria-current={
            activeAdminSection === "governance" ? "page" : undefined
          }
          onClick={() => openAdminSection("governance")}
        >
          <b>内容治理</b>
          <small>
            {
              governanceTasks.filter((item) => item.status !== "completed")
                .length
            }{" "}
            个待办
          </small>
        </button>
        <button
          type="button"
          className={activeAdminSection === "tools" ? "active" : ""}
          aria-current={activeAdminSection === "tools" ? "page" : undefined}
          onClick={() => openAdminSection("tools")}
        >
          <b>运营工具</b>
          <small>搜索与客服</small>
        </button>
        <button
          type="button"
          className={activeAdminSection === "finance" ? "active" : ""}
          aria-current={activeAdminSection === "finance" ? "page" : undefined}
          onClick={() => openAdminSection("finance")}
        >
          <b>资金管理</b>
          <small>费率与提现</small>
        </button>
      </nav>
      <div className="admin-content">
      {notice && <p className="auth-error">{notice}</p>}
      {stepUp && (
        <div className="admin-step-up-backdrop" role="presentation">
          <form
            className="admin-step-up-dialog"
            onSubmit={(event) => void confirmStepUp(event)}
          >
            <h2>管理员二次验证</h2>
            <p>已向您的管理员验证联系方式发送 6 位验证码。</p>
            {stepUp.developmentCode && (
              <p className="admin-step-up-code">
                开发环境验证码：{stepUp.developmentCode}
              </p>
            )}
            <input
              aria-label="二次验证码"
              inputMode="numeric"
              maxLength={6}
              pattern="[0-9]{6}"
              value={stepUpCode}
              onChange={(event) =>
                setStepUpCode(event.target.value.replace(/\D/g, ""))
              }
              placeholder="请输入 6 位验证码"
              autoFocus
              required
            />
            {stepUpError && <p className="auth-error">{stepUpError}</p>}
            <div className="admin-step-up-actions">
              <button
                type="button"
                className="secondary"
                onClick={() => setStepUp(null)}
              >
                取消
              </button>
              <button className="primary" type="submit">
                验证并继续
              </button>
            </div>
          </form>
        </div>
      )}
      {activeAdminSection === "overview" && (
        <>
      <div className="analytics-toolbar">
        <div>
          <button
            className={analyticsDays === 1 ? "active" : ""}
            onClick={() => setAnalyticsDays(1)}
          >
            今日
          </button>
          <button
            className={analyticsDays === 7 ? "active" : ""}
            onClick={() => setAnalyticsDays(7)}
          >
            近 7 天
          </button>
          <button
            className={analyticsDays === 30 ? "active" : ""}
            onClick={() => setAnalyticsDays(30)}
          >
            近 30 天
          </button>
          <button
            className={analyticsDays === 90 ? "active" : ""}
            onClick={() => setAnalyticsDays(90)}
          >
            近 90 天
          </button>
        </div>
        <button
          className="secondary"
          onClick={() => void exportAnalytics()}
          disabled={!analytics}
        >
          导出深度报表
        </button>
      </div>
      {analytics && (
        <div className="metric-grid">
          <Metric
            label={`${analyticsPeriodLabel}交易额`}
            value={money(analytics.revenue)}
            trend={`${analytics.orders} 笔订单`}
          />
          <Metric
            label="活跃店铺"
            value={String(analytics.activeShops)}
            trend="有成交店铺"
          />
          <Metric
            label="治理待办"
            value={String(analytics.pendingReports + analytics.pendingAppeals)}
            trend={`${analytics.pendingReports} 举报 · ${analytics.pendingAppeals} 申诉`}
          />
          <Metric
            label="申诉处理时效"
            value={`${analytics.appealHours} 小时`}
            trend={`待付款 ${analytics.orderStatuses.pending_payment || 0} · 待发货 ${analytics.orderStatuses.pending_fulfillment || 0}`}
          />
        </div>
      )}
      {analytics && (
        <div className="metric-grid analytics-quality">
          <Metric
            label="支付客单价"
            value={money(analytics.quality.averageOrderValue)}
            trend={`${analytics.quality.paidOrders} 笔已支付订单`}
          />
          <Metric
            label="平均件单价"
            value={money(analytics.quality.averageItemValue)}
            trend={`退款率 ${analytics.quality.refundRate}%`}
          />
          <Metric
            label="售后申请率"
            value={`${analytics.quality.afterSaleRate}%`}
            trend={`${analytics.quality.refundOrders} 笔退款 · ${money(analytics.quality.refundAmount)}`}
          />
          <Metric
            label="平均发货时效"
            value={`${analytics.quality.fulfillmentHours} 小时`}
            trend={`新客 ${analytics.customers.new} · 复购客 ${analytics.customers.repeat}`}
          />
        </div>
      )}
      {analytics && (
        <section className="admin-analytics-grid">
          <div className="studio-panel analytics-trend">
            <div className="panel-head">
              <h2>交易趋势</h2>
              <span>
                {analytics.days === 90
                  ? "按周汇总"
                  : `${analytics.activeCampaigns} 个活动生效中`}
              </span>
            </div>
            <div className="trend-bars">
              {trendDaily.map((item) => (
                <div
                  key={item.date}
                  title={`${analytics.days === 90 ? "截至 " : ""}${item.date} · ${money(item.revenue)} · ${item.orders} 单`}
                >
                  <i
                    style={{
                      height: `${Math.max(4, trendDaily.reduce((max, value) => Math.max(max, value.revenue), 0) ? (item.revenue / trendDaily.reduce((max, value) => Math.max(max, value.revenue), 0)) * 100 : 4)}%`,
                    }}
                  />
                  <small>{item.date.slice(5)}</small>
                </div>
              ))}
            </div>
          </div>
          <div className="studio-panel analytics-ranking">
            <div className="panel-head">
              <h2>类目与店铺</h2>
            </div>
            {analytics.categories.map((item) => (
              <p key={item.name}>
                <span>
                  {item.name} · {item.sales} 件
                </span>
                <b>{money(item.revenue)}</b>
              </p>
            ))}
            {analytics.topShops.map((item) => (
              <p key={item.name}>
                <span>
                  {item.name} · {item.orders} 单
                </span>
                <b>{money(item.revenue)}</b>
              </p>
            ))}
          </div>
        </section>
      )}
      {analytics && (
        <section className="admin-analytics-grid">
          <div className="studio-panel analytics-ranking">
            <div className="panel-head">
              <h2>连续转化漏斗</h2>
              <span>同一访客顺序路径</span>
            </div>
            <p>
              <span>浏览作品</span>
              <b>{analytics.funnel.views}</b>
            </p>
            <p>
              <span>
                加入购物车 · {analytics.funnel.viewToCartRate}% · 流失{" "}
                {analytics.funnel.cartDropOff}
              </span>
              <b>{analytics.funnel.addCarts}</b>
            </p>
            <p>
              <span>
                进入结算 · {analytics.funnel.cartToCheckoutRate}% · 流失{" "}
                {analytics.funnel.checkoutDropOff}
              </span>
              <b>{analytics.funnel.checkouts}</b>
            </p>
            <p>
              <span>
                完成支付 · {analytics.funnel.checkoutToPaidRate}% · 流失{" "}
                {analytics.funnel.paymentDropOff}
              </span>
              <b>{analytics.funnel.paidBuyers}</b>
            </p>
          </div>
          <div className="studio-panel analytics-ranking">
            <div className="panel-head">
              <h2>渠道归因</h2>
              <span>行为与订单合并</span>
            </div>
            {analytics.channels.map((item) => (
              <p key={item.channel}>
                <span>
                  {item.channel} · {item.visitors} 访客 · 加购{" "}
                  {item.visitorToCartRate}% · 支付 {item.checkoutToPaidRate}%
                </span>
                <b>
                  {money(item.revenue)} · {item.paidOrders} 单
                </b>
              </p>
            ))}
            {!analytics.channels.length && (
              <p>
                <span>暂无渠道行为数据</span>
              </p>
            )}
          </div>
        </section>
      )}
      {analytics && (
        <section className="admin-analytics-grid">
          <div className="studio-panel analytics-ranking">
            <div className="panel-head">
              <h2>作品效率</h2>
              <span>浏览到成交</span>
            </div>
            {analytics.productPerformance.map((item) => (
              <p key={item.id}>
                <span>
                  {item.title} · {item.views} 浏览 · {item.sales} 件 ·{" "}
                  {item.conversionRate}%
                </span>
                <b>{money(item.revenue)}</b>
              </p>
            ))}
            {!analytics.productPerformance.length && (
              <p>
                <span>暂无作品成交数据</span>
              </p>
            )}
          </div>
          <div className="studio-panel analytics-ranking">
            <div className="panel-head">
              <h2>复购分析</h2>
            </div>
            <p>
              <span>本周期新客</span>
              <b>{analytics.customers.new}</b>
            </p>
            <p>
              <span>复购客 / 订单</span>
              <b>
                {analytics.customers.repeat} /{" "}
                {analytics.customers.repeatOrders}
              </b>
            </p>
            <p>
              <span>复购率</span>
              <b>{analytics.customers.repeatRate}%</b>
            </p>
            <p>
              <span>复购交易额</span>
              <b>{money(analytics.customers.repeatRevenue)}</b>
            </p>
          </div>
        </section>
      )}
        </>
      )}
      {activeAdminSection === "operations" && (
        <>
      <section
        className={`studio-panel admin-operations admin-platform-operations${announcementModalOpen ? " announcement-modal-open" : ""}`}
      >
        <div className="panel-head">
          <h2>平台运营</h2>
          <div className="admin-platform-head-actions">
            <span>
              {announcements.length} 条公告 · {campaigns.length} 个活动
            </span>
            <button
              className="secondary"
              type="button"
              onClick={() => {
                setAnnouncementDraft({
                  title: "",
                  content: "",
                  imageUrl: "",
                  audience: "all",
                  status: "draft",
                });
                setAnnouncementModalOpen(true);
              }}
            >
              发布公告
            </button>
          </div>
        </div>
        <div className="admin-operation-grid">
          <div className="announcement-editor-inline">
            <div className="announcement-editor-head">
              <h3>发布公告</h3>
              <button
                className="secondary"
                type="button"
                onClick={() => setAnnouncementModalOpen(false)}
              >
                取消
              </button>
            </div>
            <input
              value={announcementDraft.title}
              maxLength={80}
              onChange={(event) =>
                setAnnouncementDraft({
                  ...announcementDraft,
                  title: event.target.value,
                })
              }
              placeholder="公告标题"
            />
            <textarea
              value={announcementDraft.content}
              maxLength={500}
              onChange={(event) =>
                setAnnouncementDraft({
                  ...announcementDraft,
                  content: event.target.value,
                })
              }
              placeholder="公告内容"
            />
            <div className="announcement-image-control">
              <label className="community-image-upload">
                <ImagePlus size={17} />
                <span>
                  {uploadingAnnouncementImage
                    ? "上传中…"
                    : announcementDraft.imageUrl
                      ? "更换图片"
                      : "上传图片"}
                </span>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/avif"
                  disabled={uploadingAnnouncementImage}
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    event.currentTarget.value = "";
                    void uploadAnnouncementImage(file);
                  }}
                />
              </label>
              {announcementDraft.imageUrl && (
                <span className="announcement-image-preview">
                  <img src={announcementDraft.imageUrl} alt="公告配图预览" />
                  <button
                    type="button"
                    onClick={() =>
                      setAnnouncementDraft((value) => ({
                        ...value,
                        imageUrl: "",
                      }))
                    }
                  >
                    移除
                  </button>
                </span>
              )}
            </div>
            <div>
              <select
                value={announcementDraft.audience}
                onChange={(event) =>
                  setAnnouncementDraft({
                    ...announcementDraft,
                    audience: event.target.value,
                  })
                }
              >
                <option value="all">全部用户</option>
                <option value="buyer">买家</option>
                <option value="seller">卖家</option>
              </select>
              <select
                value={announcementDraft.status}
                onChange={(event) =>
                  setAnnouncementDraft({
                    ...announcementDraft,
                    status: event.target.value,
                  })
                }
              >
                <option value="draft">保存草稿</option>
                <option value="published">立即发布</option>
              </select>
              <button
                className="primary"
                disabled={
                  !announcementDraft.title ||
                  !announcementDraft.content ||
                  uploadingAnnouncementImage
                }
                onClick={() => void saveAnnouncement()}
              >
                保存
              </button>
            </div>
          </div>
          <div>
            <h3>创建平台活动</h3>
            <input
              value={campaignDraft.name}
              maxLength={80}
              onChange={(event) =>
                setCampaignDraft({ ...campaignDraft, name: event.target.value })
              }
              placeholder="活动名称"
            />
            <div className="campaign-rule">
              <input
                type="number"
                min="0"
                value={campaignDraft.threshold}
                onChange={(event) =>
                  setCampaignDraft({
                    ...campaignDraft,
                    threshold: event.target.value,
                  })
                }
                placeholder="满额门槛"
              />
              <input
                type="number"
                min="0.01"
                step="0.01"
                value={campaignDraft.discount}
                onChange={(event) =>
                  setCampaignDraft({
                    ...campaignDraft,
                    discount: event.target.value,
                  })
                }
                placeholder="优惠金额"
              />
            </div>
            <div className="campaign-rule">
              <input
                type="number"
                min="0"
                step="0.01"
                value={campaignDraft.budget}
                onChange={(event) =>
                  setCampaignDraft({
                    ...campaignDraft,
                    budget: event.target.value,
                  })
                }
                placeholder="活动预算（留空不限）"
              />
              <input
                type="number"
                min="1"
                value={campaignDraft.totalUsageLimit}
                onChange={(event) =>
                  setCampaignDraft({
                    ...campaignDraft,
                    totalUsageLimit: event.target.value,
                  })
                }
                placeholder="总核销上限（留空不限）"
              />
            </div>
            <div className="campaign-rule">
              <input
                type="number"
                min="1"
                value={campaignDraft.perUserUsageLimit}
                onChange={(event) =>
                  setCampaignDraft({
                    ...campaignDraft,
                    perUserUsageLimit: event.target.value,
                  })
                }
                placeholder="每人限用次数"
              />
              <span className="campaign-hint">
                预算按优惠金额预占，订单取消会自动释放。
              </span>
            </div>
            <div>
              <select
                value={campaignDraft.type}
                onChange={(event) =>
                  setCampaignDraft({
                    ...campaignDraft,
                    type: event.target.value as typeof campaignDraft.type,
                  })
                }
              >
                <option value="coupon">平台券</option>
                <option value="full_reduction">满减活动</option>
              </select>
              <select
                value={campaignDraft.status}
                onChange={(event) =>
                  setCampaignDraft({
                    ...campaignDraft,
                    status: event.target.value,
                  })
                }
              >
                <option value="draft">保存草稿</option>
                <option value="active">立即启用</option>
              </select>
              <button
                className="primary"
                disabled={!campaignDraft.name || !campaignDraft.discount}
                onClick={() => void saveCampaign()}
              >
                保存
              </button>
            </div>
            <div className="admin-operation-list">
              {campaigns.slice(0, 4).map((item) => (
                <span key={item.id}>
                  {item.name} · 已核销 {item.redemptions} 次 ·{" "}
                  {money(item.spent)}
                </span>
              ))}
            </div>
          </div>
        </div>
        {!!campaigns.length && (
          <div className="campaign-performance">
            {campaigns.slice(0, 6).map((item) => (
              <article key={item.id}>
                <header>
                  <b>{item.name}</b>
                  <span>
                    {item.status === "active"
                      ? "生效中"
                      : item.status === "draft"
                        ? "草稿"
                        : "已结束"}
                  </span>
                </header>
                <p>
                  核销 {item.redemptions} 次 · 领取核销 {item.redemptionRate}% ·
                  冲销 {item.reversed} 次
                </p>
                <p>
                  优惠成本 <b>{money(item.spent)}</b> · 归因交易额{" "}
                  <b>{money(item.attributedRevenue)}</b> · ROI{" "}
                  <b>{item.roi === null ? "-" : `${item.roi}x`}</b>
                </p>
                <small>
                  归因订单 {item.attributedOrders} · 归因客单{" "}
                  {money(item.averageOrderValue)} · 预算{" "}
                  {item.budget === null
                    ? "不限"
                    : `${money(item.budget)}，剩余 ${money(item.budgetRemaining || 0)}`}
                </small>
              </article>
            ))}
          </div>
        )}
        {!!campaigns.length && (
          <div className="campaign-actions">
            {campaigns.map((item) => (
              <div key={item.id}>
                <span>{item.name}</span>
                <button
                  className="secondary"
                  onClick={() => editCampaign(item)}
                >
                  编辑
                </button>
                {item.status !== "ended" && (
                  <button
                    className="danger"
                    onClick={() => endCampaign(item.id)}
                  >
                    结束活动
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </section>
      <Suspense fallback={<section className="studio-panel app-loading" aria-busy="true"><span /></section>}>
        <LazyAdminCampaignOperations />
      </Suspense>
        </>
      )}
      {activeAdminSection === "governance" && (
        <>
      <section className="studio-panel governance-operations">
        <div className="panel-head">
          <h2>治理运营</h2>
          <button className="secondary" onClick={() => void exportGovernance()}>
            导出治理数据
          </button>
        </div>
        <div className="admin-operation-grid">
          <div>
            <h3>审核规则</h3>
            <input
              value={ruleDraft.name}
              maxLength={80}
              onChange={(event) =>
                setRuleDraft({ ...ruleDraft, name: event.target.value })
              }
              placeholder="规则名称"
            />
            <input
              value={ruleDraft.keyword}
              maxLength={80}
              onChange={(event) =>
                setRuleDraft({ ...ruleDraft, keyword: event.target.value })
              }
              placeholder="命中关键词（可选）"
            />
            <div>
              <select
                value={ruleDraft.action}
                onChange={(event) =>
                  setRuleDraft({
                    ...ruleDraft,
                    action: event.target.value as typeof ruleDraft.action,
                  })
                }
              >
                <option value="manual_review">转人工审核</option>
                <option value="reject">自动驳回</option>
              </select>
              <button
                className="primary"
                disabled={!ruleDraft.name}
                onClick={() => void saveRule()}
              >
                保存规则
              </button>
            </div>
            <div className="admin-operation-list">
              {governanceRules.slice(0, 5).map((item) => (
                <span key={item.id}>
                  {item.name} · {item.keyword || "通用"} · {item.action} ·{" "}
                  {item.enabled ? "启用" : "停用"}
                </span>
              ))}
            </div>
          </div>
          <div>
            <h3>处罚模板</h3>
            <input
              value={templateDraft.name}
              maxLength={80}
              onChange={(event) =>
                setTemplateDraft({ ...templateDraft, name: event.target.value })
              }
              placeholder="模板名称"
            />
            <textarea
              value={templateDraft.reason}
              maxLength={300}
              onChange={(event) =>
                setTemplateDraft({
                  ...templateDraft,
                  reason: event.target.value,
                })
              }
              placeholder="处罚说明"
            />
            <div>
              <select
                value={templateDraft.targetType}
                onChange={(event) => {
                  const targetType = event.target
                    .value as typeof templateDraft.targetType;
                  setTemplateDraft({
                    ...templateDraft,
                    targetType,
                    action:
                      targetType === "product"
                        ? "unlist_product"
                        : targetType === "shop"
                          ? "pause_shop"
                          : "disable_user",
                  });
                }}
              >
                <option value="product">作品</option>
                <option value="shop">店铺</option>
                <option value="user">用户</option>
              </select>
              <select
                value={templateDraft.action}
                onChange={(event) =>
                  setTemplateDraft({
                    ...templateDraft,
                    action: event.target.value,
                  })
                }
              >
                <option value="unlist_product">下架作品</option>
                <option value="pause_shop">暂停店铺</option>
                <option value="disable_user">停用用户</option>
                <option value="warning">警告</option>
              </select>
              <button
                className="primary"
                disabled={!templateDraft.name || !templateDraft.reason}
                onClick={() => void saveTemplate()}
              >
                保存模板
              </button>
            </div>
            <div className="admin-operation-list">
              {enforcementTemplates.slice(0, 5).map((item) => (
                <span key={item.id}>
                  {item.name} · {item.action} · {item.enabled ? "启用" : "停用"}
                </span>
              ))}
            </div>
          </div>
        </div>
        <div className="governance-task-list">
          <h3>审核任务分派</h3>
          {governanceTasks
            .filter((item) => item.status !== "completed")
            .slice(0, 12)
            .map((task) => (
              <div key={task.id}>
                <span>
                  <b>{task.type}</b>
                  <small>
                    {task.targetId} · {task.createdAt}
                  </small>
                </span>
                <select
                  value={task.assigneeId || ""}
                  onChange={(event) =>
                    void assignTask(task.id, event.target.value)
                  }
                >
                  <option value="">未分派</option>
                  {governanceAdmins.map((admin) => (
                    <option key={admin.id} value={admin.id}>
                      {admin.name}
                    </option>
                  ))}
                </select>
                <em>
                  {task.status === "in_progress"
                    ? `处理中：${task.assignee || ""}`
                    : "待处理"}
                </em>
              </div>
            ))}
          {!governanceTasks.some((item) => item.status !== "completed") && (
            <p>暂无待分派任务。</p>
          )}
        </div>
      </section>
      <Suspense fallback={<section className="studio-panel app-loading" aria-busy="true"><span /></section>}>
        <LazyGovernanceDeepOperations />
      </Suspense>
      <Suspense fallback={<section className="studio-panel app-loading" aria-busy="true"><span /></section>}>
        <LazyAdminCommunityOperations
          compressImageForUpload={compressImageForUpload}
        />
      </Suspense>
      <Suspense fallback={<section className="studio-panel app-loading" aria-busy="true"><span /></section>}>
        <LazyGovernanceServiceInsights />
      </Suspense>
      <Suspense fallback={<section className="studio-panel app-loading" aria-busy="true"><span /></section>}>
        <LazyRiskControlOperations />
      </Suspense>
      <section className="studio-panel">
        <div className="panel-head">
          <h2>待处理举报</h2>
          <span>
            {reports.filter((item) => item.status === "pending").length} 条
          </span>
        </div>
        {reports
          .filter((item) => item.status === "pending")
          .map((report) => (
            <article className="seller-order" key={report.id}>
              <span>
                <b>{report.reason}</b>
                <small>
                  {report.targetType} · {report.targetId} · {report.reporter}
                </small>
                <small>{report.detail || "未补充说明"}</small>
              </span>
              <div>
                <button
                  className="secondary"
                  onClick={() => void resolveReport(report.id, "dismissed")}
                >
                  驳回
                </button>
                <button
                  className="primary"
                  onClick={() => void resolveReport(report.id, "resolved")}
                >
                  处理并下架
                </button>
              </div>
            </article>
          ))}
        {!reports.some((item) => item.status === "pending") && (
          <p>暂无待处理举报。</p>
        )}
      </section>
      <section className="studio-panel">
        <div className="panel-head">
          <h2>已上架作品处置</h2>
          <span>{products.length} 件 · 仅用于违规下架</span>
          <div className="governance-bulk">
            <label>
              <input
                type="checkbox"
                checked={
                  products.length > 0 &&
                  products.every((product) =>
                    selectedProducts.includes(product.id),
                  )
                }
                onChange={(event) =>
                  setSelectedProducts(
                    event.target.checked
                      ? products.map((product) => product.id)
                      : [],
                  )
                }
              />
              全选
            </label>
            <button
              className="danger"
              disabled={!selectedProducts.length}
              onClick={() => void bulkUnlistProducts()}
            >
              批量下架
            </button>
          </div>
        </div>
        {products.map((product) => (
          <article className="seller-order" key={product.id}>
            <span>
              <label className="governance-select">
                <input
                  type="checkbox"
                  checked={selectedProducts.includes(product.id)}
                  onChange={(event) =>
                    setSelectedProducts((items) =>
                      event.target.checked
                        ? [...items, product.id]
                        : items.filter((id) => id !== product.id),
                    )
                  }
              />
              选择
              </label>
              <b>{product.title}</b>
              <small>已上架</small>
            </span>
            <div>
              <button
                className="danger"
                onClick={() => void unlistProduct(product.id)}
              >
                下架
              </button>
            </div>
          </article>
        ))}
      </section>
        </>
      )}
      {activeAdminSection === "tools" && (
        <>
          <Suspense fallback={<section className="studio-panel app-loading" aria-busy="true"><span /></section>}>
            <LazyAdminServiceManagement />
          </Suspense>
          <Suspense fallback={<section className="studio-panel app-loading" aria-busy="true"><span /></section>}>
            <LazyAdminToolsOperations />
          </Suspense>
        </>
      )}
      {activeAdminSection === "finance" && (
        <Suspense fallback={<section className="studio-panel app-loading" aria-busy="true"><span /></section>}>
          <LazyAdminFinanceOperations />
        </Suspense>
      )}
      </div>
      </div>
    </main>
  );
}
