import { useEffect, useRef, useState } from "react";
import { Maximize2, Minimize2, Send, X } from "lucide-react";

const API_BASE =
  (import.meta as ImportMeta & { env?: { VITE_API_BASE?: string } }).env
    ?.VITE_API_BASE ?? "";

type SellerAiAssistantMessage = {
  id: string;
  role: "assistant" | "user";
  content: string;
};

function renderAiMessageContent(content: string) {
  return content
    .split(/(\*\*[^*]+\*\*|(?:结论|可执行措施|建议|下一步)[：:])/g)
    .map((part, index) => {
      const markdownBold = part.startsWith("**") && part.endsWith("**");
      const sectionTitle = /^(结论|可执行措施|建议|下一步)[：:]$/.test(part);
      return markdownBold || sectionTitle ? (
        <strong className="seller-ai-section-title" key={index}>
          {markdownBold ? part.slice(2, -2) : part}
        </strong>
      ) : (
        part
      );
    });
}

export default function SellerAiAssistant({
  floating = false,
  onClose,
}: {
  floating?: boolean;
  onClose?: () => void;
}) {
  const [messages, setMessages] = useState<SellerAiAssistantMessage[]>([
    {
      id: "welcome",
      role: "assistant",
      content:
        "你好，我是 AI 运营助手。可以基于近 30 天的店铺数据，帮你分析曝光、点击、收藏、加购和订单，并给出下一步建议。",
    },
  ]);
  const [draft, setDraft] = useState("");
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [expanded, setExpanded] = useState(false);
  const messageListRef = useRef<HTMLDivElement>(null);
  const composerRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => composerRef.current?.focus());
    return () => window.cancelAnimationFrame(frame);
  }, []);

  useEffect(() => {
    const frame = window.requestAnimationFrame(() => {
      const list = messageListRef.current;
      if (list) list.scrollTop = list.scrollHeight;
    });
    return () => window.cancelAnimationFrame(frame);
  }, [messages, sending]);

  const sendMessage = async (value: string) => {
    const question = value.trim();
    if (!question || sending) return;
    const userMessage: SellerAiAssistantMessage = {
      id: `user-${Date.now()}`,
      role: "user",
      content: question,
    };
    const history = messages.map(({ role, content }) => ({ role, content }));
    setMessages((current) => [...current, userMessage]);
    setDraft("");
    setError("");
    setSending(true);
    try {
      const response = await fetch(`${API_BASE}/api/seller/ai-assistant/chat`, {
        method: "POST",
        credentials: "include",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: question, history }),
      });
      const payload = (await response.json().catch(() => ({}))) as {
        reply?: string;
        error?: string;
      };
      const reply = payload.reply;
      if (!response.ok || !reply)
        throw new Error(payload.error || "AI 助手暂时无法回复，请稍后重试");
      setMessages((current) => [
        ...current,
        {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: reply,
        },
      ]);
    } catch (reason) {
      setError(
        reason instanceof Error ? reason.message : "AI 助手暂时无法回复，请稍后重试",
      );
    } finally {
      setSending(false);
    }
  };

  return (
    <section
      className={`seller-ai-assistant${floating ? " floating" : ""}${expanded ? " expanded" : ""}`}
      data-testid="seller-ai-assistant"
    >
      <div className="studio-title seller-ai-title">
        <div>
          <h1>AI运营助手</h1>
          <p>结合店铺最近 30 天的数据，获取可执行的经营建议。</p>
        </div>
        {onClose && (
          <div className="seller-ai-actions">
            <button
              className="seller-ai-expand"
              type="button"
              onClick={() => setExpanded((value) => !value)}
              aria-label={expanded ? "还原面板大小" : "放大面板"}
              title={expanded ? "还原面板大小" : "放大面板"}
            >
              {expanded ? <Minimize2 size={17} /> : <Maximize2 size={17} />}
            </button>
            <button
              className="seller-ai-close"
              type="button"
              onClick={onClose}
              aria-label="关闭 AI 运营助手"
            >
              <X size={18} />
            </button>
          </div>
        )}
      </div>
      <div
        className={`seller-ai-chat${messages.length > 1 ? " has-conversation" : ""}`}
        aria-live="polite"
      >
        {messages.length === 1 && !sending && (
          <div className="seller-ai-suggestions">
            {[
              "我的店铺现在最需要优先优化什么？",
              "哪些作品的点击率需要提升？",
              "怎样把收藏和加购转成订单？",
            ].map((suggestion) => (
              <button
                key={suggestion}
                type="button"
                disabled={sending}
                onClick={() => void sendMessage(suggestion)}
              >
                {suggestion}
              </button>
            ))}
          </div>
        )}
        <div className="seller-ai-message-list" ref={messageListRef}>
          {messages.map((message) => (
            <div key={message.id} className={`seller-ai-message ${message.role}`}>
              <article>
                <p>{renderAiMessageContent(message.content)}</p>
              </article>
            </div>
          ))}
          {sending && (
            <div className="seller-ai-message assistant pending">
              <article>
                <p>正在分析店铺数据…</p>
              </article>
            </div>
          )}
        </div>
        {error && <p className="seller-ai-error">{error}</p>}
        <form
          className="seller-ai-composer"
          onSubmit={(event) => {
            event.preventDefault();
            void sendMessage(draft);
          }}
        >
          <div className="seller-ai-input-wrap">
            <textarea
              ref={composerRef}
              value={draft}
              disabled={sending}
              onChange={(event) => setDraft(event.target.value)}
              onKeyDown={(event) => {
                if (
                  event.key === "Enter" &&
                  !event.shiftKey &&
                  !event.nativeEvent.isComposing
                ) {
                  event.preventDefault();
                  void sendMessage(draft);
                }
              }}
              placeholder="例如：我的商品曝光有了，为什么订单还是少？"
              maxLength={2000}
            />
            <div>
              <button
                className="primary"
                type="submit"
                disabled={sending || !draft.trim()}
                aria-label="发送"
                title="发送"
              >
                <Send size={16} />
              </button>
            </div>
          </div>
          <p className="seller-ai-disclaimer">
            推荐和回答由 AI 生成，仅供参考。
          </p>
        </form>
      </div>
    </section>
  );
}


