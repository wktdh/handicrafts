import { useEffect, useState } from "react";
import { ImagePlus } from "lucide-react";

const API_BASE =
  (import.meta as ImportMeta & { env?: { VITE_API_BASE?: string } }).env
    ?.VITE_API_BASE ?? "";

export default function AdminCommunityOperations({
  compressImageForUpload,
}: {
  compressImageForUpload: (file: File) => Promise<string>;
}) {
  type CommunityAdminPost = {
    id: string;
    nickname: string;
    category: string;
    title: string;
    content: string;
    imageUrl?: string | null;
    createdAt: string;
    pinned: boolean;
    commentCount: number;
  };
  const [posts, setPosts] = useState<CommunityAdminPost[]>([]);
  const [notice, setNotice] = useState("");
  const [editingPost, setEditingPost] = useState<CommunityAdminPost | null>(
    null,
  );
  const [postEditTitle, setPostEditTitle] = useState("");
  const [postEditContent, setPostEditContent] = useState("");
  const [postEditImageUrl, setPostEditImageUrl] = useState("");
  const [uploadingPostEditImage, setUploadingPostEditImage] = useState(false);
  const [savingPostEdit, setSavingPostEdit] = useState(false);
  const load = async () => {
    const response = await fetch(`${API_BASE}/api/admin/community/posts`, {
      credentials: "include",
    });
    const payload = (await response.json().catch(() => ({}))) as {
      posts?: CommunityAdminPost[];
      error?: string;
    };
    if (!response.ok) return setNotice(payload.error || "社区帖子加载失败");
    setPosts(payload.posts || []);
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
  const pin = (post: CommunityAdminPost) =>
    void (async () => {
      const response = await fetch(
        `${API_BASE}/api/admin/community/posts/${encodeURIComponent(post.id)}/pin`,
        {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ pinned: !post.pinned }),
        },
      );
      const payload = (await response.json().catch(() => ({}))) as {
        error?: string;
      };
      if (!response.ok) return setNotice(payload.error || "置顶状态更新失败");
      setNotice(post.pinned ? "已取消置顶" : "帖子已置顶");
      await load();
    })();
  const edit = (post: CommunityAdminPost) => {
    setNotice("");
    setEditingPost(post);
    setPostEditTitle(post.title);
    setPostEditContent(post.content);
    setPostEditImageUrl(post.imageUrl || "");
  };
  const uploadPostEditImage = async (file?: File) => {
    if (!file) return;
    setUploadingPostEditImage(true);
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
      setPostEditImageUrl(payload.url);
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "图片上传失败");
    } finally {
      setUploadingPostEditImage(false);
    }
  };
  const savePostEdit = async () => {
    if (!editingPost || !postEditTitle.trim() || !postEditContent.trim())
      return setNotice("请填写帖子标题和正文");
    setSavingPostEdit(true);
    try {
      const response = await fetch(
        `${API_BASE}/api/admin/community/posts/${encodeURIComponent(editingPost.id)}`,
        {
          method: "PUT",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            title: postEditTitle.trim(),
            content: postEditContent.trim(),
            imageUrl: postEditImageUrl || null,
          }),
        },
      );
      const payload = (await response.json().catch(() => ({}))) as {
        error?: string;
      };
      if (!response.ok) return setNotice(payload.error || "帖子编辑失败");
      setEditingPost(null);
      setNotice("帖子已编辑");
      await load();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "帖子编辑失败");
    } finally {
      setSavingPostEdit(false);
    }
  };
  const remove = (post: CommunityAdminPost) => {
    const reason = window.prompt("请填写删除原因");
    if (!reason?.trim()) return;
    void withStepUp(async (ticket) => {
      const response = await fetch(
        `${API_BASE}/api/admin/community/posts/${encodeURIComponent(post.id)}`,
        {
          method: "DELETE",
          credentials: "include",
          headers: {
            "Content-Type": "application/json",
            "X-Admin-Step-Up": ticket,
          },
          body: JSON.stringify({ reason: reason.trim() }),
        },
      );
      const payload = (await response.json().catch(() => ({}))) as {
        error?: string;
      };
      if (!response.ok) return setNotice(payload.error || "帖子删除失败");
      setNotice("帖子已删除");
      await load();
    });
  };
  return (
    <>
      <section className="studio-panel admin-community-operations">
        <div className="panel-head">
          <div>
            <h2>社区帖子管理</h2>
          </div>
          <button className="secondary" onClick={() => void load()}>
            刷新
          </button>
        </div>
        {notice && <p className="auth-error">{notice}</p>}
        <div className="admin-operation-list">
          {posts.map((post) => (
            <div key={post.id}>
              <span>
                <b>
                  {post.pinned ? "置顶 · " : ""}
                  {post.title}
                </b>
              </span>
              <div className="admin-community-actions">
                <button className="secondary" onClick={() => pin(post)}>
                  {post.pinned ? "取消置顶" : "置顶"}
                </button>
                <button className="secondary" onClick={() => edit(post)}>
                  编辑
                </button>
                <button className="danger" onClick={() => remove(post)}>
                  删除
                </button>
              </div>
            </div>
          ))}
          {!posts.length && <p>暂无已发布帖子。</p>}
        </div>
      </section>
      {editingPost && (
        <div
          className="admin-community-editor-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) setEditingPost(null);
          }}
        >
          <form
            className="studio-panel admin-community-editor-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="admin-community-editor-title"
            onSubmit={(event) => {
              event.preventDefault();
              void savePostEdit();
            }}
          >
            <div className="panel-head">
              <h2 id="admin-community-editor-title">编辑帖子</h2>
            </div>
            {notice && <p className="auth-error">{notice}</p>}
            <label>
              帖子标题
              <input
                value={postEditTitle}
                maxLength={80}
                onChange={(event) => setPostEditTitle(event.target.value)}
                required
              />
            </label>
            <label>
              帖子正文
              <textarea
                value={postEditContent}
                maxLength={2000}
                onChange={(event) => setPostEditContent(event.target.value)}
                required
              />
            </label>
            <div className="admin-community-editor-image">
              <label className="community-image-upload">
                <ImagePlus size={17} />
                <span>
                  {uploadingPostEditImage
                    ? "上传中…"
                    : postEditImageUrl
                      ? "更换图片"
                      : "添加图片"}
                </span>
                <input
                  type="file"
                  accept="image/jpeg,image/png,image/webp,image/avif"
                  disabled={uploadingPostEditImage}
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    event.currentTarget.value = "";
                    void uploadPostEditImage(file);
                  }}
                />
              </label>
              {postEditImageUrl && (
                <span className="announcement-image-preview">
                  <img src={postEditImageUrl} alt="帖子配图预览" />
                  <button type="button" onClick={() => setPostEditImageUrl("")}>
                    移除
                  </button>
                </span>
              )}
            </div>
            <footer>
              <button
                type="button"
                className="secondary"
                disabled={savingPostEdit}
                onClick={() => setEditingPost(null)}
              >
                取消
              </button>
              <button
                type="submit"
                className="primary"
                disabled={savingPostEdit || uploadingPostEditImage}
              >
                {savingPostEdit ? "保存中…" : "保存修改"}
              </button>
            </footer>
          </form>
        </div>
      )}
    </>
  );
}


