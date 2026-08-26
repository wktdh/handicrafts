import { lazy, Suspense, useEffect, useRef, useState } from "react";
import { ChevronDown, ImagePlus, Search, Settings2 } from "lucide-react";
import {
  playNewBuyerMessageChime,
  unlockNewBuyerMessageChime,
} from "../../audio/newBuyerMessageChime";
import type { Order, Product, ShopMessage } from "../../App";

const LazySupportDialog = lazy(() => import("./SupportDialog"));

function money(value: number) {
  return `$${value.toFixed(2)}`;
}

const sellerMessageAutomationDefaults = {
  timezone: "Asia/Shanghai",
  weeklyHours: {
    mon: [{ start: "09:00", end: "18:00" }],
    tue: [{ start: "09:00", end: "18:00" }],
    wed: [{ start: "09:00", end: "18:00" }],
    thu: [{ start: "09:00", end: "18:00" }],
    fri: [{ start: "09:00", end: "18:00" }],
    sat: [],
    sun: [],
  },
  unansweredMinutes: 3,
  offHoursAutoReplyEnabled: true,
  offHoursReplyTemplate: "店主当前处于非工作时间，已收到您的消息，请耐心等待，我们会在工作时间尽快回复您。",
  urgentEmailEnabled: true,
  urgentSmsEnabled: false,
  unansweredEmailEnabled: true,
  aiReplyEnabled: true,
};

const sellerMessageWeekdays = [
  ["mon", "周一"], ["tue", "周二"], ["wed", "周三"], ["thu", "周四"],
  ["fri", "周五"], ["sat", "周六"], ["sun", "周日"],
] as const;

function websocketUrl(apiBase: string) {
  const endpoint = new URL(apiBase || window.location.origin, window.location.origin);
  endpoint.protocol = endpoint.protocol === "https:" ? "wss:" : "ws:";
  endpoint.pathname = `${endpoint.pathname.replace(/\/$/, "")}/ws`;
  endpoint.search = "";
  return endpoint.toString();
}

export default function MessagesPage({
  role,
  apiBase,
  compressImageForUpload,
  productListImageUrl,
  embedded = false,
  onUnreadChange,
  messageSoundEnabled,
  onMessageSoundEnabledChange,
  onTestMessageSound,
}: {
  role: "buyer" | "seller";
  embedded?: boolean;
  onUnreadChange?: (unread: number) => void;
  messageSoundEnabled?: boolean;
  onMessageSoundEnabledChange?: (enabled: boolean) => void;
  onTestMessageSound?: () => void;
  apiBase: string;
  compressImageForUpload: (file: File) => Promise<string>;
  productListImageUrl: (
    url: string | null | undefined,
    width: 160 | 400 | 800,
  ) => string | undefined;
}) {
  const roleText = (zh: string, en: string) => (role === "seller" ? zh : en);
  type Conversation = {
    shopId: string;
    shop: string;
    buyerUserId?: string;
    buyer?: string;
    preview: string;
    lastMessageAt: string;
    unread: number;
    priority?: "normal" | "high" | "urgent";
    priorityReason?: string;
  };
  type SyncedShopMessage = ShopMessage & { cursor?: number };
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [selectedKey, setSelectedKey] = useState("");
  const [messages, setMessages] = useState<SyncedShopMessage[]>([]);
  const [orders, setOrders] = useState<Order[]>([]);
  const [content, setContent] = useState("");
  const [uploadingMessageImage, setUploadingMessageImage] = useState(false);
  const [search, setSearch] = useState("");
  const [products, setProducts] = useState<Product[]>([]);
  const [selectedCardValue, setSelectedCardValue] = useState("");
  const [cardPickerOpen, setCardPickerOpen] = useState(false);
  const [notice, setNotice] = useState("");
  const [supportOpen, setSupportOpen] = useState(false);
  const [messageSettingsOpen, setMessageSettingsOpen] = useState(false);
  const [sellerAutomationSettings, setSellerAutomationSettings] = useState(sellerMessageAutomationDefaults);
  const [sellerAutomationSaving, setSellerAutomationSaving] = useState(false);
  const [sellerAiDraftLoading, setSellerAiDraftLoading] = useState(false);
  const messageSoundStorageKey =
    role === "seller"
      ? "seller-message-sound-enabled"
      : "buyer-message-sound-enabled";
  const [localMessageSoundEnabled, setLocalMessageSoundEnabled] = useState(
    () => window.localStorage.getItem(messageSoundStorageKey) !== "false",
  );
  const resolvedMessageSoundEnabled =
    messageSoundEnabled ?? localMessageSoundEnabled;
  const messageSoundEnabledRef = useRef(resolvedMessageSoundEnabled);
  const lastMessageSoundAtRef = useRef(0);
  const messageCursor = useRef(0);
  const messagesContainerRef = useRef<HTMLDivElement | null>(null);
  const cardPickerRef = useRef<HTMLDivElement | null>(null);

  const loadSellerAutomationSettings = async (shopId: string) => {
    if (role !== "seller" || !shopId) return;
    const response = await fetch(`${apiBase}/api/seller/message-automation?shopId=${encodeURIComponent(shopId)}`, { credentials: "include" });
    const payload = (await response.json().catch(() => ({}))) as { settings?: typeof sellerMessageAutomationDefaults };
    if (response.ok && payload.settings) setSellerAutomationSettings({ ...sellerMessageAutomationDefaults, ...payload.settings });
  };

  const saveSellerAutomationSettings = async () => {
    if (role !== "seller" || !selected) return;
    setSellerAutomationSaving(true);
    try {
      const response = await fetch(`${apiBase}/api/seller/message-automation/settings`, {
        method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ shopId: selected.shopId, ...sellerAutomationSettings }),
      });
      const payload = (await response.json().catch(() => ({}))) as { settings?: typeof sellerMessageAutomationDefaults; error?: string };
      if (!response.ok) throw new Error(payload.error || "客服自动化设置保存失败");
      if (payload.settings) setSellerAutomationSettings({ ...sellerMessageAutomationDefaults, ...payload.settings });
      setNotice("客服自动化设置已保存");
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "客服自动化设置保存失败");
    } finally {
      setSellerAutomationSaving(false);
    }
  };

  const generateSellerAiDraft = async () => {
    if (role !== "seller" || !selected) return;
    setSellerAiDraftLoading(true);
    try {
      const response = await fetch(`${apiBase}/api/seller/message-automation/ai-draft`, {
        method: "POST", credentials: "include", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ shopId: selected.shopId, buyerUserId: selected.buyerUserId }),
      });
      const payload = (await response.json().catch(() => ({}))) as { draft?: string; error?: string };
      if (!response.ok || !payload.draft) throw new Error(payload.error || "AI 回复建议生成失败");
      setContent(payload.draft);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "AI 回复建议生成失败");
    } finally {
      setSellerAiDraftLoading(false);
    }
  };

  const endpoint =
    role === "buyer" ? "/api/messages/buyer" : "/api/messages/seller";
  const conversationKey = (item: Conversation) =>
    `${item.shopId}:${item.buyerUserId || "buyer"}`;
  const selected = conversations.find(
    (item) => conversationKey(item) === selectedKey,
  );
  const updateMessageSoundEnabled = (enabled: boolean) => {
    if (onMessageSoundEnabledChange) onMessageSoundEnabledChange(enabled);
    else setLocalMessageSoundEnabled(enabled);
  };
  const playIncomingMessageSound = () => {
    if (!messageSoundEnabledRef.current) return;
    const now = Date.now();
    if (now - lastMessageSoundAtRef.current < 10000) return;
    lastMessageSoundAtRef.current = now;
    void playNewBuyerMessageChime();
  };

  useEffect(() => {
    messageSoundEnabledRef.current = resolvedMessageSoundEnabled;
  }, [resolvedMessageSoundEnabled]);
  useEffect(() => {
    if (!onMessageSoundEnabledChange)
      window.localStorage.setItem(
        messageSoundStorageKey,
        String(localMessageSoundEnabled),
      );
  }, [
    localMessageSoundEnabled,
    messageSoundStorageKey,
    onMessageSoundEnabledChange,
  ]);
  useEffect(() => {
    const unlock = () => void unlockNewBuyerMessageChime();
    document.addEventListener("pointerdown", unlock, { once: true });
    document.addEventListener("keydown", unlock, { once: true });
    return () => {
      document.removeEventListener("pointerdown", unlock);
      document.removeEventListener("keydown", unlock);
    };
  }, []);

  const loadConversations = async (keepSelection = true) => {
    const query = search.trim()
      ? `?q=${encodeURIComponent(search.trim())}`
      : "";
    const response = await fetch(`${apiBase}${endpoint}${query}`, {
      credentials: "include",
    });
    const payload = (await response.json().catch(() => ({}))) as {
      conversations?: Conversation[];
      error?: string;
    };
    if (!response.ok) throw new Error(payload.error || roleText("消息加载失败", "Messages could not be loaded"));
    const next = payload.conversations || [];
    setConversations(next);
    onUnreadChange?.(next.reduce((total, item) => total + item.unread, 0));
    if (
      !keepSelection ||
      !next.some((item) => conversationKey(item) === selectedKey)
    ) {
      setMessages([]);
      messageCursor.current = 0;
      setSelectedKey(next[0] ? conversationKey(next[0]) : "");
    }
  };

  const openConversation = async (item: Conversation) => {
    setSelectedKey(conversationKey(item));
    setMessages([]);
    messageCursor.current = 0;
    setNotice("");
    const params = new URLSearchParams({ shopId: item.shopId });
    if (role === "seller" && item.buyerUserId)
      params.set("buyerUserId", item.buyerUserId);
    const response = await fetch(
      `${apiBase}${endpoint}?${params.toString()}`,
      { credentials: "include" },
    );
    const payload = (await response.json().catch(() => ({}))) as {
      messages?: SyncedShopMessage[];
      error?: string;
    };
    if (!response.ok) return setNotice(payload.error || roleText("会话加载失败", "Conversation could not be loaded"));
    const nextMessages = payload.messages || [];
    messageCursor.current = nextMessages[nextMessages.length - 1]?.cursor || 0;
    setMessages(nextMessages);
    void loadConversations();
  };

  useEffect(() => {
    void loadConversations(false).catch((error: Error) =>
      setNotice(error.message),
    );
    fetch(
      `${apiBase}${role === "buyer" ? "/api/orders" : "/api/orders/seller"}`,
      { credentials: "include" },
    )
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((payload: { orders?: Order[] }) => setOrders(payload.orders || []))
      .catch(() => undefined);
    fetch(`${apiBase}/api/catalog/products`)
      .then((response) => (response.ok ? response.json() : Promise.reject()))
      .then((payload: { products?: Product[] }) =>
        setProducts(payload.products || []),
      )
      .catch(() => undefined);
  }, [role]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadConversations(false).catch((error: Error) =>
        setNotice(error.message),
      );
    }, 220);
    return () => window.clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    if (role === "seller" && selected?.shopId) void loadSellerAutomationSettings(selected.shopId).catch(() => undefined);
  }, [role, selected?.shopId]);

  useEffect(() => {
    const closeCardPicker = (event: PointerEvent) => {
      if (!cardPickerRef.current?.contains(event.target as Node))
        setCardPickerOpen(false);
    };
    document.addEventListener("pointerdown", closeCardPicker);
    return () => document.removeEventListener("pointerdown", closeCardPicker);
  }, []);

  useEffect(() => {
    if (!selected || messages.length) return;
    void openConversation(selected);
  }, [selectedKey, conversations]);

  useEffect(() => {
    const container = messagesContainerRef.current;
    if (!container) return;
    window.requestAnimationFrame(() => {
      container.scrollTop = container.scrollHeight;
    });
  }, [messages.length, selectedKey]);

  useEffect(() => {
    if (!selected) return;
    const params = new URLSearchParams({
      shopId: selected.shopId,
      after: String(messageCursor.current),
    });
    if (role === "seller" && selected.buyerUserId)
      params.set("buyerUserId", selected.buyerUserId);
    const updatesEndpoint = `${endpoint}/updates`;
    let active = true;
    const poll = async () => {
      try {
        params.set("after", String(messageCursor.current));
        const response = await fetch(
          `${apiBase}${updatesEndpoint}?${params.toString()}`,
          { credentials: "include" },
        );
        const payload = (await response.json().catch(() => ({}))) as {
          messages?: SyncedShopMessage[];
          cursor?: number;
          error?: string;
        };
        if (!response.ok)
            throw new Error(payload.error || roleText("消息同步失败", "Message sync failed"));
        const incoming = payload.messages || [];
        if (!active || !incoming.length) return;
        if (
          role === "buyer" &&
          incoming.some((message) => message.sender !== role)
        )
          playIncomingMessageSound();
        messageCursor.current =
          payload.cursor ||
          incoming[incoming.length - 1]?.cursor ||
          messageCursor.current;
        setMessages((current) => {
          const existing = new Set(current.map((message) => message.id));
          return [
            ...current,
            ...incoming.filter((message) => !existing.has(message.id)),
          ];
        });
        void loadConversations();
      } catch (error) {
        if (active)
          setNotice(
            error instanceof Error ? error.message : roleText("消息同步失败", "Message sync failed"),
          );
      }
    };
    const timer = window.setInterval(() => {
      void poll();
    }, 4000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, [endpoint, role, selectedKey]);

  useEffect(() => {
    if (role !== "buyer" || typeof WebSocket === "undefined") return;
    let socket: WebSocket | null = null;
    let reconnectTimer: number | undefined;
    let disposed = false;
    const connect = () => {
      socket = new WebSocket(websocketUrl(apiBase));
      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(String(event.data)) as {
            type?: string;
            audience?: string;
          };
          if (payload.type !== "message.new" || payload.audience !== "buyer")
            return;
          void loadConversations().catch(() => undefined);
          playIncomingMessageSound();
        } catch {
          // Ignore malformed push events and keep the connection alive.
        }
      };
      socket.onclose = () => {
        if (!disposed) reconnectTimer = window.setTimeout(connect, 3000);
      };
    };
    connect();
    return () => {
      disposed = true;
      if (reconnectTimer !== undefined) window.clearTimeout(reconnectTimer);
      socket?.close();
    };
  }, [apiBase, role]);

  const sendMessage = async (payload: {
    type: "text" | "image" | "order" | "product";
    content?: string;
    attachmentUrl?: string;
    orderId?: string;
    productId?: string;
  }) => {
    if (!selected) return setNotice(roleText("请先选择一个会话", "Select a conversation first"));
    const body =
      role === "buyer"
        ? { shopId: selected.shopId, ...payload }
        : {
            shopId: selected.shopId,
            buyerUserId: selected.buyerUserId,
            ...payload,
          };
    const response = await fetch(`${apiBase}${endpoint}`, {
      method: "POST",
      credentials: "include",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    const result = (await response.json().catch(() => ({}))) as {
      error?: string;
    };
    if (!response.ok) return setNotice(result.error || roleText("消息发送失败", "Message could not be sent"));
    setContent("");
    setSelectedCardValue("");
    await openConversation(selected);
  };

  const uploadImage = async (file: File) => {
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type))
      throw new Error('Please choose a JPG, PNG, or WebP image');
    setUploadingMessageImage(true);
    try {
      const data = await compressImageForUpload(file);
      const response = await fetch(`${apiBase}/api/media`, {
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
        throw new Error(payload.error || roleText("图片上传失败", "Image upload failed"));
      await sendMessage({ type: "image", attachmentUrl: payload.url });
    } finally {
      setUploadingMessageImage(false);
    }
  };

  const matchingOrders = orders.filter(
    (order) =>
      !!selected &&
      String(order.shopId) === String(selected.shopId) &&
      (role === "buyer" || order.buyerUserId === selected.buyerUserId),
  );
  const matchingProducts = products.filter(
    (product) =>
      !!selected &&
      String(product.analyticsShopId) === String(selected.shopId) &&
      product.publishStatus === "published",
  );
  const currentInquiryProductId = [...messages]
    .reverse()
    .find((message) => message.product?.id)
    ?.product?.id;
  useEffect(() => {
    setSelectedCardValue(
      currentInquiryProductId ? `product:${currentInquiryProductId}` : "",
    );
  }, [selectedKey, currentInquiryProductId]);
  const selectedCardLabel = (() => {
    const productId = selectedCardValue.replace(/^product:/, "");
    const product = matchingProducts.find((item) => item.catalogId === productId);
    if (product) return `${product.title} - ${money(product.price)}`;
    const orderId = selectedCardValue.replace(/^order:/, "");
    const order = matchingOrders.find(
      (item) => (item.orderId || item.id) === orderId,
    );
    return order
      ? `${roleText("\u8ba2\u5355", "Order")} ${order.id} - ${money(order.amount)}`
      : roleText("\u53d1\u9001\u5361\u7247", "Send a card");
  })();
  const selectCard = (value: string) => {
    setSelectedCardValue(value);
    setCardPickerOpen(false);
  };
  const visibleConversations = conversations.filter((item) =>
    `${item.shop} ${item.buyer || ""} ${item.preview}`
      .toLowerCase()
      .includes(search.trim().toLowerCase()),
  );
  const shellClass = embedded
    ? "conversation-center conversation-embedded"
    : "container page section conversation-center";
  return (
    <div className={shellClass}>
      {notice && <p className="auth-error">{notice}</p>}
      {!embedded && role === "buyer" && (
        <div className="conversation-support-action">
          <button
            className="primary"
            type="button"
            onClick={() => {
              setSupportOpen(true);
            }}
          >
            Contact support
          </button>
        </div>
      )}
      <section className="conversation-layout">
        <div className="conversation-title">
          <h1>{roleText("买家消息", "Messages")}</h1>
          {(role === "buyer" || role === "seller" || onMessageSoundEnabledChange) && (
            <div className="message-settings">
              <button
                className="icon-button"
                type="button"
                aria-label="消息提醒设置"
                aria-expanded={messageSettingsOpen}
                onClick={() => setMessageSettingsOpen((open) => !open)}
              >
                <Settings2 size={19} />
              </button>
              {messageSettingsOpen && (
                <div className="message-settings-panel">
                  <b>消息提醒</b>
                  <div className="message-sound-switch">
                    <input
                      type="checkbox"
                      checked={resolvedMessageSoundEnabled}
                      onChange={(event) => updateMessageSoundEnabled(event.target.checked)}
                    />
                    <span
                      role="checkbox"
                      tabIndex={0}
                      aria-checked={resolvedMessageSoundEnabled}
                      onClick={() => updateMessageSoundEnabled(!resolvedMessageSoundEnabled)}
                      onKeyDown={(event) => {
                        if (event.key === "Enter" || event.key === " ") {
                          event.preventDefault();
                          updateMessageSoundEnabled(!resolvedMessageSoundEnabled);
                        }
                      }}
                    >
                      {roleText("新买家消息提示音", "New seller reply chime")}
                    </span>
                    <button
                      className="message-sound-test-link"
                      type="button"
                      onClick={() =>
                        void (onTestMessageSound
                          ? onTestMessageSound()
                          : playNewBuyerMessageChime())
                      }
                    >
                      {roleText("试听提示音", "Test chime")}
                    </button>
                  </div>
                  <p>
                    {roleText(
                      "收到新消息时播放“叮咚”；连续消息 10 秒内只提醒一次。",
                      "Plays a chime for a new seller reply. Consecutive messages are limited to one alert every 10 seconds.",
                    )}
                  </p>
                  {role === "seller" && (
                    <div className="seller-message-automation-settings">
                      <b>智能客服分流</b>
                      <label className="seller-message-timezone">工作时区<select value="Asia/Shanghai" onChange={() => setSellerAutomationSettings((value) => ({ ...value, timezone: "Asia/Shanghai" }))}><option value="Asia/Shanghai">中国标准时间（UTC+8）</option></select></label>
                      <div className="seller-message-work-hours">
                        {sellerMessageWeekdays.map(([day, label]) => {
                          const window = sellerAutomationSettings.weeklyHours[day]?.[0];
                          const timeRange = window || { start: "09:00", end: "18:00" };
                          return <div className="seller-message-work-day" key={day}><div className="seller-message-day-toggle"><input type="checkbox" checked={Boolean(window)} onChange={(event) => setSellerAutomationSettings((value) => ({ ...value, weeklyHours: { ...value.weeklyHours, [day]: event.target.checked ? [timeRange] : [] } }))} /><span role="checkbox" tabIndex={0} aria-checked={Boolean(window)} onClick={() => setSellerAutomationSettings((value) => ({ ...value, weeklyHours: { ...value.weeklyHours, [day]: window ? [] : [timeRange] } }))} onKeyDown={(event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); setSellerAutomationSettings((value) => ({ ...value, weeklyHours: { ...value.weeklyHours, [day]: value.weeklyHours[day]?.[0] ? [] : [timeRange] } })); } }}>{label}</span></div><input type="time" disabled={!window} value={timeRange.start} onChange={(event) => setSellerAutomationSettings((value) => ({ ...value, weeklyHours: { ...value.weeklyHours, [day]: [{ ...timeRange, start: event.target.value }] } }))} /><span>至</span><input type="time" disabled={!window} value={timeRange.end} onChange={(event) => setSellerAutomationSettings((value) => ({ ...value, weeklyHours: { ...value.weeklyHours, [day]: [{ ...timeRange, end: event.target.value }] } }))} /></div>;
                        })}
                      </div>
                      <div className="message-sound-switch"><input type="checkbox" checked={sellerAutomationSettings.offHoursAutoReplyEnabled} onChange={(event) => setSellerAutomationSettings((value) => ({ ...value, offHoursAutoReplyEnabled: event.target.checked }))} /><span role="checkbox" tabIndex={0} aria-checked={sellerAutomationSettings.offHoursAutoReplyEnabled} onClick={() => setSellerAutomationSettings((value) => ({ ...value, offHoursAutoReplyEnabled: !value.offHoursAutoReplyEnabled }))}>非工作时间自动确认</span></div>
                      <textarea maxLength={500} value={sellerAutomationSettings.offHoursReplyTemplate} onChange={(event) => setSellerAutomationSettings((value) => ({ ...value, offHoursReplyTemplate: event.target.value }))} aria-label="非工作时间自动回复" />
                      <label className="seller-message-reminder-minutes">未回复提醒时间（分钟）<input type="number" min="1" max="60" value={sellerAutomationSettings.unansweredMinutes} onChange={(event) => setSellerAutomationSettings((value) => ({ ...value, unansweredMinutes: Math.max(1, Math.min(60, Number(event.target.value) || 3)) }))} /></label>
                      <div className="message-sound-switch"><input type="checkbox" checked={sellerAutomationSettings.unansweredEmailEnabled} onChange={(event) => setSellerAutomationSettings((value) => ({ ...value, unansweredEmailEnabled: event.target.checked }))} /><span role="checkbox" tabIndex={0} aria-checked={sellerAutomationSettings.unansweredEmailEnabled} onClick={() => setSellerAutomationSettings((value) => ({ ...value, unansweredEmailEnabled: !value.unansweredEmailEnabled }))}>未回复时发送邮件提醒</span></div>
                      <div className="message-sound-switch"><input type="checkbox" checked={sellerAutomationSettings.urgentEmailEnabled} onChange={(event) => setSellerAutomationSettings((value) => ({ ...value, urgentEmailEnabled: event.target.checked }))} /><span role="checkbox" tabIndex={0} aria-checked={sellerAutomationSettings.urgentEmailEnabled} onClick={() => setSellerAutomationSettings((value) => ({ ...value, urgentEmailEnabled: !value.urgentEmailEnabled }))}>紧急消息发送邮件</span></div>
                      <div className="message-sound-switch"><input type="checkbox" checked={sellerAutomationSettings.urgentSmsEnabled} onChange={(event) => setSellerAutomationSettings((value) => ({ ...value, urgentSmsEnabled: event.target.checked }))} /><span role="checkbox" tabIndex={0} aria-checked={sellerAutomationSettings.urgentSmsEnabled} onClick={() => setSellerAutomationSettings((value) => ({ ...value, urgentSmsEnabled: !value.urgentSmsEnabled }))}>紧急消息发送短信（需短信服务已配置）</span></div>
                      <div className="message-sound-switch"><input type="checkbox" checked={sellerAutomationSettings.aiReplyEnabled} onChange={(event) => setSellerAutomationSettings((value) => ({ ...value, aiReplyEnabled: event.target.checked }))} /><span role="checkbox" tabIndex={0} aria-checked={sellerAutomationSettings.aiReplyEnabled} onClick={() => setSellerAutomationSettings((value) => ({ ...value, aiReplyEnabled: !value.aiReplyEnabled }))}>允许生成 AI 回复建议</span></div>
                      <button className="secondary" type="button" disabled={sellerAutomationSaving} onClick={() => void saveSellerAutomationSettings()}>{sellerAutomationSaving ? "保存中…" : "保存客服设置"}</button>
                    </div>
                  )}
                </div>
              )}
            </div>
          )}
        </div>
        <aside className="conversation-sidebar">
          <div className="conversation-search">
            <Search size={16} />
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder={roleText("搜索会话或消息", "Search conversations or messages")}
            />
          </div>
          <div className="conversation-list">
            {visibleConversations.map((item) => (
              <button
                key={conversationKey(item)}
                className={
                  conversationKey(item) === selectedKey ? "selected" : ""
                }
                onClick={() => void openConversation(item)}
              >
                <b>{role === "seller" ? item.buyer || "买家" : item.shop}</b>
                {role === "seller" && item.priority && item.priority !== "normal" && (
                  <strong className={`conversation-priority conversation-priority-${item.priority}`}>
                    {item.priority === "urgent" ? "Urgent" : "Priority"}
                  </strong>
                )}
                <span>{item.preview}</span>
                <small>{item.lastMessageAt}</small>
                {item.unread > 0 && (
                  <i>{item.unread > 99 ? "99+" : item.unread}</i>
                )}
              </button>
            ))}
            {!visibleConversations.length && <p>{roleText("没有匹配的会话", "No matching conversations")}</p>}
          </div>
        </aside>
        <div className="conversation-detail">
          {selected ? (
            <>
              <div className="conversation-messages" ref={messagesContainerRef}>
                {messages.map((message) => (
                  <article
                    className={
                      (
                        role === "buyer"
                          ? message.sender === "buyer"
                          : message.sender === "seller"
                      )
                        ? "outgoing"
                        : "incoming"
                    }
                    key={message.id}
                  >
                    <small>{message.createdAt}</small>
                    {role === "seller" && message.priority && message.priority !== "normal" && message.sender === "buyer" && (
                      <strong className={`message-priority message-priority-${message.priority}`}>
                        {message.priority === "urgent" ? "Urgent: handle now" : "Priority message"}
                      </strong>
                    )}
                    {message.type === "image" ? (
                      <img src={message.attachmentUrl} alt={roleText("聊天图片", "Chat image")} />
                    ) : message.product ? (
                      <a
                        className="message-product-card"
                        href={`?product=${encodeURIComponent(message.product.id)}`}
                        target="_blank"
                        rel="noreferrer"
                      >
                        {message.product.image && (
                          <img
                            src={productListImageUrl(message.product.image, 160)}
                            alt={message.product.title || "Product"}
                          />
                        )}
                        <span>
                          <b>{message.product.title}</b>
                          <strong>{money(message.product.price || 0)}</strong>
                        </span>
                      </a>
                    ) : message.type === "order" && message.order ? (
                      <div className="message-order-card">
                        {message.order.image && (
                          <img
                            src={productListImageUrl(message.order.image, 160)}
                            alt={roleText("订单商品", "Order item")}
                          />
                        )}
                        <span>
                          <b>{message.order.title}</b>
                          <small>
                            {roleText("订单", "Order")} {message.order.orderNo || message.order.id} ·{" "}
                            {message.order.status}
                          </small>
                          <strong>{money(message.order.amount || 0)}</strong>
                        </span>
                      </div>
                    ) : (
                      <p>{message.content}</p>
                    )}
                  </article>
                ))}
                {!messages.length && (
                  <p className="conversation-empty">{roleText("请选择一个会话查看消息。", "Select a conversation to view messages.")}</p>
                )}
              </div>
              <div className="conversation-tools">
                <div className="conversation-card-picker" ref={cardPickerRef}>
                  <button
                    className="conversation-card-picker-trigger"
                    type="button"
                    aria-expanded={cardPickerOpen}
                    onClick={() => setCardPickerOpen((open) => !open)}
                  >
                    <span>{selectedCardLabel}</span>
                    <ChevronDown size={16} />
                  </button>
                  {cardPickerOpen && (
                    <div className="conversation-card-picker-menu" role="listbox">
                      {matchingProducts.length > 0 && (
                        <div className="conversation-card-picker-group">
                          <b>{roleText("\u5546\u54c1", "Products")}</b>
                          {matchingProducts.map((product) => {
                            const isCurrent = product.catalogId === currentInquiryProductId;
                            return (
                              <button
                                className={isCurrent ? "current" : ""}
                                type="button"
                                role="option"
                                aria-selected={selectedCardValue === `product:${product.catalogId}`}
                                key={product.catalogId}
                                onClick={() => selectCard(`product:${product.catalogId}`)}
                              >
                                {product.image ? (
                                  <img
                                    src={productListImageUrl(product.image, 160)}
                                    alt=""
                                  />
                                ) : (
                                  <span className="conversation-card-picker-image-placeholder" />
                                )}
                                <span>
                                  {isCurrent && (
                                    <small>{roleText("\u5f53\u524d\u6d4f\u89c8", "Currently viewing")}</small>
                                  )}
                                  <b>{product.title}</b>
                                  <em>{money(product.price)}</em>
                                </span>
                              </button>
                            );
                          })}
                        </div>
                      )}
                      {matchingOrders.length > 0 && (
                        <div className="conversation-card-picker-group">
                          <b>{roleText("\u8ba2\u5355", "Orders")}</b>
                          {matchingOrders.map((order) => (
                            <button
                              type="button"
                              role="option"
                              aria-selected={selectedCardValue === `order:${order.orderId || order.id}`}
                              key={order.orderId || order.id}
                              onClick={() => selectCard(`order:${order.orderId || order.id}`)}
                            >
                              <span>
                                <b>{roleText("\u8ba2\u5355", "Order")} {order.id}</b>
                                <em>{money(order.amount)}</em>
                              </span>
                            </button>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
                <button
                  className="secondary"
                  type="button"
                  disabled={!selectedCardValue}
                  onClick={() => {
                    const [type, id] = selectedCardValue.split(":", 2);
                    if (type === "product" && id)
                      void sendMessage({ type: "product", productId: id });
                    if (type === "order" && id)
                      void sendMessage({ type: "order", orderId: id });
                  }}
                >
                  {roleText("\u53d1\u9001", "Send")}
                </button>
              </div>
              <form
                className="conversation-composer"
                onSubmit={(event) => {
                  event.preventDefault();
                  if (content.trim())
                    void sendMessage({ type: "text", content: content.trim() });
                }}
              >
                {role === "seller" && (
                  <button
                    className="secondary conversation-ai-draft"
                    type="button"
                    disabled={sellerAiDraftLoading}
                    onClick={() => void generateSellerAiDraft()}
                  >
                    {sellerAiDraftLoading ? "Generating…" : "AI reply draft"}
                  </button>
                )}
                <label
                  className="icon-upload conversation-image-upload"
                  title={roleText("添加图片", "Add an image")}
                >
                  <ImagePlus size={17} />
                  <input
                    type="file"
                    accept="image/jpeg,image/png,image/webp"
                    disabled={uploadingMessageImage}
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      event.currentTarget.value = "";
                      if (file)
                        void uploadImage(file).catch((error: Error) =>
                          setNotice(error.message),
                        );
                    }}
                  />
                </label>
                <input
                  value={content}
                  onChange={(event) => setContent(event.target.value)}
                  maxLength={500}
                  placeholder={roleText("输入消息", "Write a message")}
                />
                <button className="primary" disabled={uploadingMessageImage}>
                  Send
                </button>
              </form>
            </>
          ) : (
            <div className="conversation-empty">
              No conversations yet. Contact a maker from a product or order.
            </div>
          )}
        </div>
      </section>
      {supportOpen && (
        <Suspense fallback={null}>
          <LazySupportDialog apiBase={apiBase} onClose={() => setSupportOpen(false)} />
        </Suspense>
      )}
    </div>
  );
}
