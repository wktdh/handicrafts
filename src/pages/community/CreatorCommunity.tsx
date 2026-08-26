import { useEffect, useRef, useState, type FormEvent } from "react";
import { ImagePlus, Send, Smile, X } from "lucide-react";

const API_BASE =
  (import.meta as ImportMeta & { env?: { VITE_API_BASE?: string } }).env
    ?.VITE_API_BASE ?? "";

type CommunityComment = {
  id: string;
  nickname: string;
  content: string;
  createdAt: string;
  parentCommentId?: string | null;
  imageUrl?: string | null;
  imageUrls?: string[];
};
type CommunityPost = {
  id: string;
  nickname: string;
  category: string;
  title: string;
  content: string;
  createdAt: string;
  comments: CommunityComment[];
  imageUrl?: string | null;
  imageUrls?: string[];
};
const communityWebsocketUrl = (visitorId: string) => {
  const endpoint = new URL(API_BASE || window.location.origin, window.location.origin);
  endpoint.protocol = endpoint.protocol === "https:" ? "wss:" : "ws:";
  const basePath = endpoint.pathname.endsWith("/")
    ? endpoint.pathname.slice(0, -1)
    : endpoint.pathname;
  endpoint.pathname = `${basePath}/ws/community`;
  endpoint.search = new URLSearchParams({ visitorId }).toString();
  return endpoint.toString();
};

const MAX_UPLOAD_IMAGE_SIZE = 3 * 1024 * 1024;
const COMMUNITY_CATEGORIES = [
  "全部",
  "店铺经营",
  "商品拍摄",
  "定价与营销",
  "物流经验",
  "平台建议",
  "闲聊交流",
];
const COMMUNITY_EMOJIS = [
  "👍", "😊", "🤔", "👏", "🙌", "✨", "🎉", "💡",
  "❤️", "🌟", "🤝", "🙏", "🌿", "🌸", "🎀", "🏡",
];

export default function CreatorCommunity({
  accountName = "",
  compressImageForUpload,
}: {
  accountName?: string;
  compressImageForUpload: (file: File) => Promise<string>;
}) {
  const savedNickname = window.localStorage.getItem(
    "creator-community-nickname",
  );
  const accountNickname = accountName.trim().slice(0, 24);
  const [visitorId] = useState(() => {
    const key = "creator-community-visitor-id";
    const existing = window.localStorage.getItem(key);
    if (existing) return existing;
    const next =
      window.crypto?.randomUUID?.() ||
      `visitor-${Math.random().toString(36).slice(2)}-${Date.now()}`;
    window.localStorage.setItem(key, next);
    return next;
  });
  const [nickname, setNickname] = useState(() => savedNickname || accountNickname);
  const [nicknameDialogOpen, setNicknameDialogOpen] = useState(
    () => !savedNickname && !accountNickname,
  );
  const [posts, setPosts] = useState<CommunityPost[]>([]);
  const [category, setCategory] = useState("全部");
  const [postCategory, setPostCategory] = useState("店铺经营");
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [postImageUrls, setPostImageUrls] = useState<string[]>([]);
  const [commentImageUrls, setCommentImageUrls] = useState<
    Record<string, string[]>
  >({});
  const [expandedReplies, setExpandedReplies] = useState<
    Record<string, boolean>
  >({});
  const [previewImageUrl, setPreviewImageUrl] = useState<string | null>(null);
  const [uploadingImage, setUploadingImage] = useState(false);
  const [commentDrafts, setCommentDrafts] = useState<Record<string, string>>(
    {},
  );
  const [replyingTo, setReplyingTo] = useState<{
    postId: string;
    commentId: string;
    nickname: string;
  } | null>(null);
  const commentInputRefs = useRef<Record<string, HTMLTextAreaElement | null>>(
    {},
  );
  const postContentRef = useRef<HTMLTextAreaElement | null>(null);
  const [emojiPickerTarget, setEmojiPickerTarget] = useState<string | null>(
    null,
  );
  const [notice, setNotice] = useState("");
  const [loading, setLoading] = useState(true);
  const [posting, setPosting] = useState(false);
  const [postDialogOpen, setPostDialogOpen] = useState(false);
  const [reportTarget, setReportTarget] = useState<{
    type: "post" | "comment";
    id: string;
  } | null>(null);
  const [reportReason, setReportReason] = useState("广告或骚扰");
  const [reporting, setReporting] = useState(false);

  const flash = (message: string) => {
    setNotice(message);
    window.setTimeout(() => setNotice(""), 2400);
  };
  const loadPosts = async () => {
    setLoading(true);
    try {
      const query =
        category === "全部" ? "" : `?category=${encodeURIComponent(category)}`;
      const response = await fetch(`${API_BASE}/api/community/posts${query}`);
      const payload = (await response.json()) as {
        posts?: CommunityPost[];
        error?: string;
      };
      if (!response.ok) throw new Error(payload.error || "社区内容加载失败");
      setPosts(payload.posts || []);
    } catch (error) {
      flash(error instanceof Error ? error.message : "社区内容加载失败");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    void loadPosts();
  }, [category]);
  useEffect(() => {
    if (!previewImageUrl) return;
    const closeOnEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") setPreviewImageUrl(null);
    };
    window.addEventListener("keydown", closeOnEscape);
    return () => window.removeEventListener("keydown", closeOnEscape);
  }, [previewImageUrl]);
  useEffect(() => {
    let active = true;
    let retryTimer: number | undefined;
    let socket: WebSocket | undefined;
    const connect = () => {
      if (!active) return;
      try {
        socket = new WebSocket(communityWebsocketUrl(visitorId));
        socket.onmessage = (event) => {
          try {
            const payload = JSON.parse(event.data) as { type?: string };
            if (
              payload.type === "community_post_created" ||
              payload.type === "community_comment_created"
            )
              void loadPosts();
          } catch {
            /* Ignore malformed broadcast frames. */
          }
        };
        socket.onclose = () => {
          if (active) retryTimer = window.setTimeout(connect, 3000);
        };
        socket.onerror = () => socket?.close();
      } catch {
        retryTimer = window.setTimeout(connect, 3000);
      }
    };
    connect();
    return () => {
      active = false;
      if (retryTimer) window.clearTimeout(retryTimer);
      socket?.close();
    };
  }, [visitorId, category]);
  const identity = () => {
    const value = nickname.trim() || accountNickname;
    if (value.length < 2 || value.length > 24) {
      flash("请先填写 2 到 24 个字符的昵称");
      return null;
    }
    if (nickname.trim())
      window.localStorage.setItem("creator-community-nickname", value);
    return value;
  };
  const saveNickname = (event: FormEvent) => {
    event.preventDefault();
    if (!identity()) return;
    setNicknameDialogOpen(false);
    flash("昵称已保存");
  };
  const uploadCommunityImage = async (
    file: File,
    onUploaded: (url: string) => void,
  ) => {
    if (!["image/jpeg", "image/png", "image/webp"].includes(file.type))
      return flash("图片仅支持 JPG、PNG 或 WebP 格式");
    if (file.size > MAX_UPLOAD_IMAGE_SIZE) return flash("图片不能超过 3MB");
    setUploadingImage(true);
    try {
      const data = await compressImageForUpload(file);
      const response = await fetch(`${API_BASE}/api/community/media`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ visitorId, data }),
      });
      const payload = (await response.json().catch(() => ({}))) as {
        url?: string;
        error?: string;
      };
      if (!response.ok || !payload.url)
        throw new Error(payload.error || "图片上传失败");
      onUploaded(payload.url);
    } catch (error) {
      flash(error instanceof Error ? error.message : "图片上传失败");
    } finally {
      setUploadingImage(false);
    }
  };
  const createPost = async (event: FormEvent) => {
    event.preventDefault();
    const name = identity();
    if (!name || posting) return;
    setPosting(true);
    try {
      const response = await fetch(`${API_BASE}/api/community/posts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          visitorId,
          nickname: name,
          category: postCategory,
          title,
          content,
          attachmentUrls: postImageUrls,
        }),
      });
      const payload = (await response.json()) as {
        post?: CommunityPost;
        error?: string;
      };
      if (!response.ok) throw new Error(payload.error || "发帖失败");
      setTitle("");
      setContent("");
      setPostImageUrls([]);
      setPostDialogOpen(false);
      flash("帖子已发布");
      await loadPosts();
    } catch (error) {
      flash(error instanceof Error ? error.message : "发帖失败");
    } finally {
      setPosting(false);
    }
  };
  const addComment = async (postId: string) => {
    const name = identity();
    const draft = (commentDrafts[postId] || "").trim();
    const attachmentUrls: string[] = [];
    if (!name || !draft) return;
    const replyPrefix =
      replyingTo?.postId === postId ? `@${replyingTo.nickname}：` : "";
    const parentCommentId = replyPrefix && draft.startsWith(replyPrefix)
      ? replyingTo?.commentId
      : undefined;
    const response = await fetch(
      `${API_BASE}/api/community/posts/${encodeURIComponent(postId)}/comments`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          visitorId,
          nickname: name,
          content: draft,
          parentCommentId,
          attachmentUrls,
        }),
      },
    );
    const payload = (await response.json()) as {
      comment?: CommunityComment;
      error?: string;
    };
    if (!response.ok) {
      flash(payload.error || "评论失败");
      return;
    }
    setCommentDrafts((current) => ({ ...current, [postId]: "" }));
    setCommentImageUrls((current) => ({ ...current, [postId]: [] }));
    setReplyingTo((current) => (current?.postId === postId ? null : current));
    commentInputRefs.current[postId]?.blur();
    setPosts((current) =>
      current.map((post) =>
        post.id === postId && payload.comment
          ? { ...post, comments: [...post.comments, payload.comment] }
          : post,
      ),
    );
  };
  const removeCommentImage = (postId: string, imageUrl: string) => {
    setCommentImageUrls((current) => ({
      ...current,
      [postId]: (current[postId] || []).filter((url) => url !== imageUrl),
    }));
  };
  const insertPostEmoji = (emoji: string) => {
    const field = postContentRef.current;
    const start = field?.selectionStart ?? content.length;
    const end = field?.selectionEnd ?? start;
    setContent(
      (current) => `${current.slice(0, start)}${emoji}${current.slice(end)}`,
    );
    setEmojiPickerTarget(null);
    window.setTimeout(() => {
      field?.focus();
      field?.setSelectionRange(start + emoji.length, start + emoji.length);
    }, 0);
  };
  const insertCommentEmoji = (postId: string, emoji: string) => {
    const field = commentInputRefs.current[postId];
    const current = commentDrafts[postId] || "";
    const start = field?.selectionStart ?? current.length;
    const end = field?.selectionEnd ?? start;
    setCommentDrafts((drafts) => ({
      ...drafts,
      [postId]: `${current.slice(0, start)}${emoji}${current.slice(end)}`,
    }));
    setEmojiPickerTarget(null);
    window.setTimeout(() => {
      field?.focus();
      field?.setSelectionRange(start + emoji.length, start + emoji.length);
    }, 0);
  };
  const beginReply = (postId: string, comment: CommunityComment) => {
    const prefix = `@${comment.nickname}：`;
    setReplyingTo({
      postId,
      commentId: comment.id,
      nickname: comment.nickname,
    });
    setCommentDrafts((current) => {
      const existing = current[postId] || "";
      const content = existing.replace(/^@[^：:\s]+[：:]\s*/, "");
      return { ...current, [postId]: `${prefix}${content}` };
    });
    window.setTimeout(() => commentInputRefs.current[postId]?.focus(), 0);
  };
  const renderComments = (
    post: CommunityPost,
    parentCommentId: string | null = null,
    depth = 0,
  ) => {
    const matchingComments = post.comments.filter(
      (comment) => (comment.parentCommentId || null) === parentCommentId,
    );
    const visibleComments =
      parentCommentId === null && !expandedReplies[post.id]
        ? matchingComments.slice(0, 3)
        : matchingComments;
    return visibleComments.map((comment) => {
      const repliedComment = comment.parentCommentId
        ? post.comments.find((item) => item.id === comment.parentCommentId)
        : undefined;
      const replyMention = repliedComment ? `@${repliedComment.nickname}：` : "";
      const commentContent =
        replyMention &&
        (comment.content.startsWith(replyMention) ||
          comment.content.startsWith(`${replyMention.slice(0, -1)}:`))
          ? comment.content.slice(replyMention.length).trimStart()
          : comment.content;
      const imageUrls = comment.imageUrls?.length
        ? comment.imageUrls
        : comment.imageUrl
          ? [comment.imageUrl]
          : [];
      return (
        <div
          className="community-comment-thread"
          key={comment.id}
          style={{ marginLeft: `${Math.min(depth, 3) * 18}px` }}
        >
          <div
            className={`community-comment${depth ? " community-comment-reply" : ""}${imageUrls.length ? " community-comment-with-image" : ""}`}
          >
            <b>{comment.nickname}</b>
            <div className="community-comment-body">
              <div className="community-comment-message-row">
                {imageUrls.length > 0 && (
                  <div className="community-attachment-list">
                    {imageUrls.map((url, index) => (
                      <button
                        type="button"
                        className="community-attachment-button"
                        aria-label={`放大评论图片 ${index + 1}`}
                        onClick={() => setPreviewImageUrl(url)}
                        key={url}
                      >
                        <img
                          className="community-attachment community-comment-attachment"
                          src={url}
                          alt={`评论图片 ${index + 1}`}
                        />
                      </button>
                    ))}
                  </div>
                )}
                {repliedComment && (
                  <span className="community-reply-mention">{replyMention}</span>
                )}
                <span>{commentContent}</span>
                <time className="community-comment-time">
                  {new Date(
                    comment.createdAt.replace(" ", "T") + "Z",
                  ).toLocaleString()}
                </time>
                <button
                  type="button"
                  className="community-comment-reply-link"
                  onClick={() => beginReply(post.id, comment)}
                >
                  回复
                </button>
                <button
                  type="button"
                  className="community-report-link"
                  onClick={() =>
                    setReportTarget({ type: "comment", id: comment.id })
                  }
                >
                  举报
                </button>
              </div>
            </div>
          </div>
          {renderComments(post, comment.id, depth + 1)}
        </div>
      );
    });
  };
  const PostDialog = () =>
    !postDialogOpen ? null : (
      <div
        className="community-post-backdrop"
        role="presentation"
        onMouseDown={(event) => {
          if (event.target === event.currentTarget && !posting)
            setPostDialogOpen(false);
        }}
      >
        <section
          className="community-post-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="community-post-title"
        >
          <header>
            <div>
              <p className="eyebrow">CREATOR COMMUNITY</p>
              <h2 id="community-post-title">发布一个话题</h2>
            </div>
            <button
              type="button"
              className="community-dialog-close"
              disabled={posting}
              onClick={() => setPostDialogOpen(false)}
            >
              取消
            </button>
          </header>
          <p className="community-post-dialog-intro">
            无需注册，昵称只保存在当前浏览器。
          </p>
          <form onSubmit={createPost}>
            <div className="community-form-grid">
              <label>
                分类
                <select
                  value={postCategory}
                  onChange={(event) => setPostCategory(event.target.value)}
                >
                  {COMMUNITY_CATEGORIES.slice(1).map((item) => (
                    <option key={item}>{item}</option>
                  ))}
                </select>
              </label>
              <label>
                标题
                <input
                  value={title}
                  maxLength={80}
                  onChange={(event) => setTitle(event.target.value)}
                  placeholder="想和其他创作者聊什么？"
                  required
                />
              </label>
              <label className="community-form-wide">
                正文
                <textarea
                  ref={postContentRef}
                  value={content}
                  maxLength={2000}
                  onChange={(event) => setContent(event.target.value)}
                  placeholder="分享你的经验或问题"
                  required
                />
              </label>
            </div>
            <div className="community-post-emoji-control">
              <button
                type="button"
                className="community-emoji-toggle"
                aria-label="添加表情"
                title="添加表情"
                onClick={() =>
                  setEmojiPickerTarget((current) =>
                    current === "post" ? null : "post",
                  )
                }
              >
                <Smile size={17} />
              </button>
              {emojiPickerTarget === "post" && (
                <div className="community-emoji-picker">
                  {COMMUNITY_EMOJIS.map((emoji) => (
                    <button
                      type="button"
                      key={emoji}
                      onMouseDown={(event) => event.preventDefault()}
                      onClick={() => insertPostEmoji(emoji)}
                    >
                      {emoji}
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className="community-post-image-control">
              <label className="community-image-upload">
                <ImagePlus size={17} />
                <span>{uploadingImage ? "上传中…" : "添加图片"}</span>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp"
                  multiple
                  disabled={uploadingImage}
                  onChange={(event) => {
                    const files = Array.from(event.target.files || []);
                    event.currentTarget.value = "";
                    files
                      .slice(0, Math.max(0, 6 - postImageUrls.length))
                      .forEach(
                        (file) =>
                          void uploadCommunityImage(file, (url) =>
                            setPostImageUrls((current) =>
                              current.includes(url) || current.length >= 6
                                ? current
                                : [...current, url],
                            ),
                          ),
                      );
                  }}
                />
              </label>
              {postImageUrls.length > 0 && (
                <div className="community-post-image-preview">
                  {postImageUrls.map((url, index) => (
                    <span key={url}>
                      <img src={url} alt={`待发布图片 ${index + 1}`} />
                    </span>
                  ))}
                </div>
              )}
            </div>
            <div className="community-form-actions">
              <span>{notice}</span>
              <button className="primary" disabled={posting || uploadingImage}>
                {posting ? "发布中…" : "发布话题"}
              </button>
            </div>
          </form>
        </section>
      </div>
    );
  const CommunityImageLightbox = () =>
    !previewImageUrl ? null : (
      <div
        className="community-image-lightbox"
        role="presentation"
        onMouseDown={(event) => {
          if (event.target === event.currentTarget) setPreviewImageUrl(null);
        }}
      >
        <figure role="dialog" aria-modal="true" aria-label="图片预览">
          <img src={previewImageUrl} alt="社区图片预览" />
          <button
            type="button"
            aria-label="关闭图片预览"
            onClick={() => setPreviewImageUrl(null)}
          >
            <X size={19} />
          </button>
        </figure>
      </div>
    );
  const report = async (
    targetType: "post" | "comment",
    targetId: string,
    reason: string,
  ) => {
    const name = identity();
    if (!name) return false;
    const response = await fetch(`${API_BASE}/api/community/reports`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        visitorId,
        nickname: name,
        targetType,
        targetId,
        reason,
      }),
    });
    const payload = (await response.json()) as { error?: string };
    flash(
      response.ok ? "举报已提交，感谢你的反馈" : payload.error || "举报失败",
    );
    return response.ok;
  };
  const submitReport = async (event: FormEvent) => {
    event.preventDefault();
    if (!reportTarget || reporting) return;
    setReporting(true);
    const succeeded = await report(
      reportTarget.type,
      reportTarget.id,
      reportReason,
    );
    setReporting(false);
    if (succeeded) {
      setReportTarget(null);
      setReportReason("广告或骚扰");
    }
  };
  return (
    <>
      {PostDialog()}
      <CommunityImageLightbox />
      <main className="community-page">
        <section className="container section">
          <div className="community-hero">
            <div>
              <p className="eyebrow">CREATOR COMMUNITY</p>
              <h1>创作者社区</h1>
              <p>分享创作手工作品的心得、灵感。</p>
            </div>
            <div className="community-current-nickname">
              <b>{nickname}</b>
              <button type="button" onClick={() => setNicknameDialogOpen(true)}>
                修改
              </button>
            </div>
          </div>
          <div className="community-toolbar">
            <div className="community-category-tabs">
              {COMMUNITY_CATEGORIES.map((item) => (
                <button
                  key={item}
                  className={category === item ? "active" : ""}
                  onClick={() => setCategory(item)}
                >
                  {item}
                </button>
              ))}
            </div>
            <div className="community-toolbar-actions">
              <button className="secondary" onClick={() => void loadPosts()}>
                刷新
              </button>
              <button
                className="primary"
                onClick={() => setPostDialogOpen(true)}
              >
                发布话题
              </button>
            </div>
          </div>
          <div className="community-post-list">
            {loading ? (
              <p className="community-empty">正在加载社区内容…</p>
            ) : posts.length === 0 ? (
              <p className="community-empty">还没有话题，来发布第一篇吧。</p>
            ) : (
              posts.map((post) => (
                <article className="community-post" key={post.id}>
                  <header>
                    <div>
                      <div className="community-post-title-row">
                        <span className="community-post-category">
                          {post.category}
                        </span>
                        <h2>{post.title}</h2>
                      </div>
                      <small>
                        <span className="community-author">
                          {post.nickname}
                          <i className="community-owner-badge">帖主</i>
                        </span>{" "}
                        ·{" "}
                        {new Date(
                          post.createdAt.replace(" ", "T") + "Z",
                        ).toLocaleString()}
                      </small>
                    </div>
                    <button
                      className="community-report-link"
                      onClick={() =>
                        setReportTarget({ type: "post", id: post.id })
                      }
                    >
                      举报
                    </button>
                  </header>
                  <p className="community-post-content">{post.content}</p>
                  {(post.imageUrls?.length
                    ? post.imageUrls
                    : post.imageUrl
                      ? [post.imageUrl]
                      : []
                  ).map((url, index) => (
                    <button
                      type="button"
                      className="community-attachment-button community-post-attachment-button"
                      aria-label={`放大帖子图片 ${index + 1}`}
                      onClick={() => setPreviewImageUrl(url)}
                      key={url}
                    >
                      <img
                        className="community-attachment community-post-attachment"
                        src={url}
                        alt={`帖子图片 ${index + 1}`}
                      />
                    </button>
                  ))}
                  <div className="community-comment-list">
                    {renderComments(post)}
                    {post.comments.filter((comment) => !comment.parentCommentId)
                      .length > 3 && (
                      <button
                        type="button"
                        className="community-replies-toggle"
                        onClick={() =>
                          setExpandedReplies((current) => ({
                            ...current,
                            [post.id]: !current[post.id],
                          }))
                        }
                      >
                        {expandedReplies[post.id]
                          ? "收起回复"
                          : `展开其余 ${post.comments.filter((comment) => !comment.parentCommentId).length - 3} 条回复`}
                      </button>
                    )}
                  </div>
                  <form
                    className="community-comment-form"
                    onSubmit={(event) => {
                      event.preventDefault();
                      void addComment(post.id);
                    }}
                  >
                    <label
                      className="community-comment-image-upload"
                      title="添加图片"
                    >
                      <ImagePlus size={16} />
                      <input
                        type="file"
                        accept="image/jpeg,image/png,image/webp"
                        multiple
                        onChange={(event) => {
                          const files = Array.from(event.target.files || []);
                          event.currentTarget.value = "";
                          files
                            .slice(
                              0,
                              Math.max(
                                0,
                                6 - (commentImageUrls[post.id] || []).length,
                              ),
                            )
                            .forEach(
                              (file) =>
                                void uploadCommunityImage(file, (url) =>
                                  setCommentImageUrls((current) => ({
                                    ...current,
                                    [post.id]:
                                      (current[post.id] || []).includes(url) ||
                                      (current[post.id] || []).length >= 6
                                        ? current[post.id] || []
                                        : [...(current[post.id] || []), url],
                                  })),
                                ),
                            );
                        }}
                      />
                    </label>
                    <div
                      className={`community-comment-composer${commentDrafts[post.id] ? " has-content" : ""}`}
                    >
                      {(commentImageUrls[post.id] || []).length > 0 && (
                        <span className="community-image-ready">
                          <b>{nickname}</b>
                          {commentImageUrls[post.id].map((url, index) => (
                            <span className="community-image-thumb" key={url}>
                              <img src={url} alt={`待回复图片 ${index + 1}`} />
                              <button
                                type="button"
                                aria-label={`删除待回复图片 ${index + 1}`}
                                title="删除图片"
                                onClick={() => removeCommentImage(post.id, url)}
                              >
                                <X size={13} />
                              </button>
                            </span>
                          ))}
                        </span>
                      )}
                      <div className="community-comment-emoji-control">
                        <button
                          type="button"
                          className="community-emoji-toggle"
                          aria-label="添加回复表情"
                          title="添加表情"
                          onClick={() =>
                            setEmojiPickerTarget((current) =>
                              current === `comment-${post.id}`
                                ? null
                                : `comment-${post.id}`,
                            )
                          }
                        >
                          <Smile size={17} />
                        </button>
                        {emojiPickerTarget === `comment-${post.id}` && (
                          <div className="community-emoji-picker">
                            {COMMUNITY_EMOJIS.map((emoji) => (
                              <button
                                type="button"
                                key={emoji}
                                onMouseDown={(event) => event.preventDefault()}
                                onClick={() =>
                                  insertCommentEmoji(post.id, emoji)
                                }
                              >
                                {emoji}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                      <textarea
                        ref={(element) => {
                          commentInputRefs.current[post.id] = element;
                        }}
                        value={commentDrafts[post.id] || ""}
                        maxLength={500}
                        rows={3}
                        onChange={(event) => {
                          const value = event.target.value;
                          setCommentDrafts((current) => ({
                            ...current,
                            [post.id]: value,
                          }));
                          setReplyingTo((current) => {
                            if (current?.postId !== post.id) return current;
                            return value.startsWith(`@${current.nickname}：`)
                              ? current
                              : null;
                          });
                        }}
                        onKeyDown={(event) => {
                          if (
                            event.key === "Enter" &&
                            event.shiftKey &&
                            !event.nativeEvent.isComposing
                          ) {
                            event.preventDefault();
                            if (!uploadingImage) void addComment(post.id);
                          }
                        }}
                        placeholder="写下你的回复…"
                      />
                      <button
                        type="button"
                        className="community-comment-cancel"
                        onClick={(event) => {
                          event.currentTarget.blur();
                          setCommentDrafts((current) => ({
                            ...current,
                            [post.id]: "",
                          }));
                          setCommentImageUrls((current) => ({
                            ...current,
                            [post.id]: [],
                          }));
                          setReplyingTo((current) =>
                            current?.postId === post.id ? null : current,
                          );
                          setEmojiPickerTarget(null);
                        }}
                      >
                        取消
                      </button>
                      <button
                        className="secondary community-comment-submit"
                        disabled={uploadingImage}
                        onClick={(event) => event.currentTarget.blur()}
                        aria-label="发送"
                        title="发送"
                      >
                        <Send size={15} />
                      </button>
                    </div>
                  </form>
                </article>
              ))
            )}
          </div>
        </section>
      </main>
      {nicknameDialogOpen && (
        <div
          className="community-nickname-backdrop"
          role="presentation"
          onMouseDown={(event) => event.preventDefault()}
        >
          <section
            className="community-nickname-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="community-nickname-title"
          >
            <header className="community-nickname-dialog-header">
              <p className="eyebrow">WELCOME</p>
              <button
                type="button"
                className="community-dialog-close"
                onClick={() => setNicknameDialogOpen(false)}
              >
                关闭
              </button>
            </header>
            <h2 id="community-nickname-title">先设置一个社区昵称</h2>
            <p>社区无需注册，取一个昵称和其他创作者交流起来吧。</p>
            <form onSubmit={saveNickname}>
              <label>
                昵称
                <input
                  autoFocus
                  value={nickname}
                  maxLength={24}
                  onChange={(event) => setNickname(event.target.value)}
                  placeholder="例如：木棉手作"
                />
              </label>
              <button className="primary">进入创作者社区</button>
            </form>
          </section>
        </div>
      )}
      {reportTarget && (
        <div
          className="community-report-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setReportTarget(null);
          }}
        >
          <section
            className="community-report-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="community-report-title"
          >
            <header>
              <div>
                <p className="eyebrow">COMMUNITY SAFETY</p>
                <h2 id="community-report-title">举报内容</h2>
              </div>
            </header>
            <p className="community-report-intro">
              请选择举报原因，我们会尽快审核处理。
            </p>
            <form onSubmit={submitReport}>
              <label>
                举报原因
                <select
                  value={reportReason}
                  onChange={(event) => setReportReason(event.target.value)}
                >
                  <option>广告或骚扰</option>
                  <option>不当或违规内容</option>
                  <option>侵权或抄袭</option>
                  <option>其他</option>
                </select>
              </label>
              <div className="community-report-notice">
                举报内容会提交给平台审核，请勿重复提交。
              </div>
              <footer>
                <button
                  type="button"
                  className="secondary"
                  onClick={() => setReportTarget(null)}
                >
                  取消
                </button>
                <button className="primary" disabled={reporting}>
                  {reporting ? "提交中…" : "提交举报"}
                </button>
              </footer>
            </form>
          </section>
        </div>
      )}
    </>
  );
}

