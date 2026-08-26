import base64
import binascii
import hashlib
import hmac
import ipaddress
import io
import json
import math
import re
import secrets
import smtplib
import threading
import time
from datetime import datetime, timedelta, timezone
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sqlite3
import os
from urllib.parse import parse_qs, urlparse
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from sqlite_config import connect as sqlite_connect

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    from pywebpush import WebPushException, webpush
except ImportError:  # Allows local API development before the optional push dependency is installed.
    WebPushException = Exception
    webpush = None

try:
    from qcloud_cos import CosConfig, CosS3Client
except ImportError:  # COS is optional in local development and test environments.
    CosConfig = None
    CosS3Client = None

try:
    from PIL import Image, ImageOps, UnidentifiedImageError
except ImportError:  # Production installs Pillow; keeping this optional preserves local API tooling.
    Image = ImageOps = None
    UnidentifiedImageError = Exception


class SlidingWindowRateLimiter:
    """Thread-safe, in-process protection for costly browser actions.

    The API is served by one threaded Supervisor process today, so keeping only
    recent timestamps in memory avoids adding a database write on every normal
    request. Limits are intentionally scoped by both account and client IP at
    their call sites. If the API is later scaled to multiple processes, move
    this implementation to Redis so the quota is shared across workers.
    """

    def __init__(self) -> None:
        self._events: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    def allow(self, scope: str, subject: str, maximum: int, window_seconds: int) -> tuple[bool, int]:
        now = time.monotonic()
        key = f"{scope}:{subject}"
        with self._lock:
            # Login identifiers are client supplied. Bound the cache so a bot
            # cannot turn the limiter itself into a memory exhaustion target.
            if key not in self._events and len(self._events) >= 10_000:
                self._events.pop(next(iter(self._events)))
            entries = [item for item in self._events.get(key, []) if now - item < window_seconds]
            if len(entries) >= maximum:
                self._events[key] = entries
                retry_after = max(1, math.ceil(window_seconds - (now - entries[0])))
                return False, retry_after
            entries.append(now)
            self._events[key] = entries
            return True, 0


ROOT = Path(__file__).resolve().parent


def load_local_environment(path: Path) -> None:
    """Load simple KEY=VALUE pairs locally when python-dotenv is unavailable."""
    if not path.exists():
        return
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
            value = value[1:-1]
        os.environ.setdefault(key, value)


if load_dotenv:
    load_dotenv(ROOT.parent / ".env")
else:
    load_local_environment(ROOT.parent / ".env")
DB_PATH = Path(os.environ.get("HANDICRAFTS_DB_PATH", ROOT / "handicrafts.db"))
MEDIA_DIR = Path(os.environ.get("HANDICRAFTS_MEDIA_DIR", ROOT.parent / "src" / "images" / "uploads"))
QUARANTINE_MEDIA_DIR = Path(os.environ.get("HANDICRAFTS_QUARANTINE_MEDIA_DIR", ROOT / "media-quarantine"))
LEGACY_MEDIA_DIR = ROOT / "media"
SESSION_SECRET = os.environ.get("HANDICRAFTS_SESSION_SECRET", "development-only-change-me")
PRODUCTION_HTTPS = os.environ.get("HANDICRAFTS_HTTPS", "0") == "1"
# During the public test phase, registration must be usable before the SMS
# provider is connected. Set this to 0 when switching to production SMS.
REGISTRATION_TEST_MODE = os.environ.get("HANDICRAFTS_REGISTRATION_TEST_MODE", "1") == "1"
TENCENT_SMS_SECRET_ID = os.environ.get("TENCENT_SMS_SECRET_ID", "").strip()
TENCENT_SMS_SECRET_KEY = os.environ.get("TENCENT_SMS_SECRET_KEY", "").strip()
TENCENT_SMS_APP_ID = os.environ.get("TENCENT_SMS_APP_ID", "").strip()
TENCENT_SMS_SIGN_NAME = os.environ.get("TENCENT_SMS_SIGN_NAME", "").strip()
TENCENT_SMS_REGION = os.environ.get("TENCENT_SMS_REGION", "ap-guangzhou").strip() or "ap-guangzhou"
TENCENT_SMS_ENABLED = os.environ.get("HANDICRAFTS_SMS_ENABLED", "0") == "1"
TENCENT_SMS_TEMPLATES = {
    "contact_verify": os.environ.get("TENCENT_SMS_TEMPLATE_VERIFICATION", "2705679").strip(),
    "password_reset": os.environ.get("TENCENT_SMS_TEMPLATE_VERIFICATION", "2705679").strip(),
    "admin_step_up": os.environ.get("TENCENT_SMS_TEMPLATE_ADMIN_STEP_UP", "2705713").strip(),
    "logistics_alert": os.environ.get("TENCENT_SMS_TEMPLATE_LOGISTICS_ALERT", "2705684").strip(),
    "settlement": os.environ.get("TENCENT_SMS_TEMPLATE_SETTLEMENT", "2705683").strip(),
    "seller_rejected": os.environ.get("TENCENT_SMS_TEMPLATE_SELLER_REJECTED", "2705682").strip(),
    "seller_accepted": os.environ.get("TENCENT_SMS_TEMPLATE_SELLER_ACCEPTED", "2705681").strip(),
    "seller_message_urgent": os.environ.get("TENCENT_SMS_TEMPLATE_SELLER_MESSAGE_URGENT", "").strip(),
}
SENSITIVE_CONTENT_WORDS = ("赌博", "博彩", "色情", "成人", "毒品", "枪支", "仿真枪", "管制刀具", "盗版", "假货")
IMAGE_MIME_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
VIDEO_MIME_TYPES = {"video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_VIDEO_BYTES = 50 * 1024 * 1024
MAX_REQUEST_BODY_BYTES = 70 * 1024 * 1024
LOGIN_FAILURES: dict[str, list[datetime]] = {}
LOGIN_FAILURES_LOCK = threading.Lock()
SMS_REQUESTS: dict[str, list[datetime]] = {}
REQUEST_RATE_LIMITER = SlidingWindowRateLimiter()
ORDER_EXPIRY_SCAN_SECONDS = max(5, int(os.environ.get("HANDICRAFTS_ORDER_EXPIRY_SCAN_SECONDS", "30")))
CUSTOMER_SERVICE_WEBHOOK_SECRET = os.environ.get("CUSTOMER_SERVICE_WEBHOOK_SECRET", "")
LOGISTICS_WEBHOOK_SECRET = os.environ.get("HANDICRAFTS_LOGISTICS_WEBHOOK_SECRET", "")
ALLOWED_BROWSER_ORIGINS = {
    origin.strip().rstrip("/")
    for origin in os.environ.get("HANDICRAFTS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
}
LIANLIAN_MODE = os.environ.get("HANDICRAFTS_LIANLIAN_MODE", "unconfigured").strip().lower()
AUTO_APPROVE_SELLER_VERIFICATION = os.environ.get("HANDICRAFTS_AUTO_APPROVE_SELLER_VERIFICATION", "1").strip() == "1"
VAPID_PUBLIC_KEY = os.environ.get("HANDICRAFTS_VAPID_PUBLIC_KEY", "").strip()
VAPID_PRIVATE_KEY = os.environ.get("HANDICRAFTS_VAPID_PRIVATE_KEY", "").strip()
VAPID_SUBJECT = os.environ.get("HANDICRAFTS_VAPID_SUBJECT", "mailto:admin@example.com").strip()
PRODUCT_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
SKU_CODE_ALPHABET = PRODUCT_CODE_ALPHABET
SELLER_OPERATING_CATEGORIES = {
    "布艺缝纫", "黏土&塑形", "滴胶&树脂", "编织", "木质&木艺", "皮具", "首饰", "陶艺陶瓷",
    "刺绣", "花艺干花", "香薰蜡烛 & 香氛", "古风国风", "绘画肌理", "纸品文创", "宠物专属",
    "微缩景观", "羊毛毡", "皂类", "非遗",
}
SELLER_PAYOUT_METHODS = {"bank_card", "alipay", "wechat"}
SELLER_PAYOUT_SCHEDULES = {"daily", "weekly", "biweekly", "monthly"}
SETTLEMENT_MIN_PAYOUT_CENTS = 2500
SETTLEMENT_HOLD_BUSINESS_DAYS = 3
NEW_SELLER_RISK_WINDOW_DAYS = 90
PLATFORM_CURRENCY = "USD"
USD_EXCHANGE_RATE = "1.00000000"
SHIPPING_COUNTRIES = {
    "US": "United States", "CA": "Canada", "GB": "United Kingdom",
    "DE": "Germany", "FR": "France", "IT": "Italy", "ES": "Spain",
    "NL": "Netherlands", "BE": "Belgium", "AT": "Austria", "IE": "Ireland",
    "SE": "Sweden", "DK": "Denmark", "FI": "Finland", "PT": "Portugal",
    "PL": "Poland", "CZ": "Czechia", "LU": "Luxembourg",
}
DEFAULT_NORTH_AMERICA_COUNTRIES = ("US", "CA")
DEFAULT_EUROPE_COUNTRIES = (
    "GB", "DE", "FR", "IT", "ES", "NL", "BE", "AT", "IE", "SE", "DK", "FI", "PT", "PL", "CZ", "LU",
)
COMMUNITY_CATEGORIES = {"店铺经营", "商品拍摄", "定价营销", "物流经验", "平台建议", "平台公告", "闲聊交流"}
COMMUNITY_RATE_LIMITS: dict[str, list[datetime]] = {}
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "").strip()
OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "").strip().rstrip("/")
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-5.6-terra").strip()
VISION_API_KEY = os.environ.get("VISION_API_KEY", "").strip()
VISION_BASE_URL = os.environ.get("VISION_BASE_URL", "").strip().rstrip("/")
VISION_MODEL = os.environ.get("VISION_MODEL", "qwen-vl-plus").strip()
SMTP_HOST = os.environ.get("HANDICRAFTS_SMTP_HOST", "").strip()
SMTP_PORT = int(os.environ.get("HANDICRAFTS_SMTP_PORT", "587"))
SMTP_USERNAME = os.environ.get("HANDICRAFTS_SMTP_USERNAME", "").strip()
SMTP_PASSWORD = os.environ.get("HANDICRAFTS_SMTP_PASSWORD", "")
SMTP_FROM = os.environ.get("HANDICRAFTS_SMTP_FROM", SMTP_USERNAME).strip()
SMTP_STARTTLS = os.environ.get("HANDICRAFTS_SMTP_STARTTLS", "1") == "1"
MESSAGE_AUTOMATION_SCAN_SECONDS = max(15, int(os.environ.get("HANDICRAFTS_MESSAGE_AUTOMATION_SCAN_SECONDS", "30")))


def validate_production_configuration() -> None:
    """Reject unsafe production defaults before the API begins serving traffic."""
    if not PRODUCTION_HTTPS:
        return
    problems = []
    if SESSION_SECRET == "development-only-change-me" or len(SESSION_SECRET) < 32:
        problems.append("HANDICRAFTS_SESSION_SECRET must be a random value of at least 32 characters")
    if REGISTRATION_TEST_MODE:
        problems.append("HANDICRAFTS_REGISTRATION_TEST_MODE must be 0")
    if AUTO_APPROVE_SELLER_VERIFICATION:
        problems.append("HANDICRAFTS_AUTO_APPROVE_SELLER_VERIFICATION must be 0")
    if not ALLOWED_BROWSER_ORIGINS:
        problems.append("HANDICRAFTS_ALLOWED_ORIGINS must include the public HTTPS origins")
    if problems:
        raise RuntimeError("Unsafe production configuration: " + "; ".join(problems))


def public_cos_settings() -> dict[str, str] | None:
    """Return public-media COS settings only when every required value is present.

    Keeping the configuration in environment variables lets local development retain
    the filesystem backend and prevents cloud credentials from reaching the browser.
    """
    secret_id = os.environ.get("HANDICRAFTS_COS_SECRET_ID", "").strip()
    secret_key = os.environ.get("HANDICRAFTS_COS_SECRET_KEY", "").strip()
    bucket = os.environ.get("HANDICRAFTS_COS_BUCKET", "").strip()
    cdn_base_url = os.environ.get("HANDICRAFTS_COS_CDN_BASE_URL", "").strip().rstrip("/")
    if not all((secret_id, secret_key, bucket, cdn_base_url)):
        return None
    return {
        "secret_id": secret_id,
        "secret_key": secret_key,
        "bucket": bucket,
        "region": os.environ.get("HANDICRAFTS_COS_REGION", "ap-guangzhou").strip() or "ap-guangzhou",
        "cdn_base_url": cdn_base_url,
        "prefix": os.environ.get("HANDICRAFTS_COS_PUBLIC_PREFIX", "products").strip("/ ") or "products",
        "quarantine_prefix": os.environ.get("HANDICRAFTS_COS_QUARANTINE_PREFIX", "quarantine").strip("/ ") or "quarantine",
    }


def public_cos_media_key(url: object) -> str | None:
    """Map a CDN URL produced by this service back to its COS object key."""
    settings = public_cos_settings()
    value = str(url or "")
    if not settings or not value.startswith(f"{settings['cdn_base_url']}/"):
        return None
    key = urlparse(value).path.lstrip("/")
    prefix = f"{settings['prefix']}/"
    return key if key.startswith(prefix) else None


def cos_client(settings: dict[str, str]) -> object:
    if CosConfig is None or CosS3Client is None:
        raise RuntimeError("COS 上传已启用，但未安装 cos-python-sdk-v5；请重新安装 requirements.txt")
    return CosS3Client(CosConfig(Region=settings["region"], SecretId=settings["secret_id"], SecretKey=settings["secret_key"]))


def create_public_cos_upload_ticket(user_id: str, mime_type: str, byte_size: int, content_hash: str | None = None, media_type: str = "image") -> dict[str, object]:
    """Create a short-lived PUT URL in the non-public product-media quarantine."""
    settings = public_cos_settings()
    if not settings:
        raise ValueError("COS 尚未配置，暂不能直传图片")
    allowed = IMAGE_MIME_TYPES if media_type == "image" else VIDEO_MIME_TYPES
    maximum_size = MAX_IMAGE_BYTES if media_type == "image" else MAX_VIDEO_BYTES
    if media_type not in {"image", "video"} or mime_type not in allowed or not 0 < byte_size <= maximum_size:
        raise ValueError("图片类型或大小无效")
    created = datetime.now(timezone.utc)
    filename = f"{media_type}-{secrets.token_urlsafe(16)}{allowed[mime_type]}"
    storage_key = f"{settings['quarantine_prefix']}/{created:%Y/%m}/{filename}"
    try:
        upload_url = cos_client(settings).get_presigned_url(
            Method="PUT",
            Bucket=settings["bucket"],
            Key=storage_key,
            Params={},
            Headers={"Content-Type": mime_type},
            Expired=600,
        )
    except Exception as error:
        raise RuntimeError("无法创建 COS 直传签名，请检查 CAM 权限和存储桶配置") from error
    asset_id = f"asset-{secrets.token_urlsafe(12)}"
    verified_hash = content_hash if content_hash and re.fullmatch(r"[a-f0-9]{64}", content_hash) else None
    with database() as connection:
        connection.execute(
            "INSERT INTO media_assets (id, uploader_user_id, media_type, mime_type, storage_key, public_url, byte_size, content_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (asset_id, user_id, media_type, mime_type, storage_key, f"/api/seller/media/assets/{asset_id}/preview", byte_size, verified_hash),
        )
    return {"id": asset_id, "assetId": asset_id, "uploadUrl": upload_url, "previewUrl": f"/api/seller/media/assets/{asset_id}/preview", "headers": {"Content-Type": mime_type}, "expiresIn": 600}


def cos_object_bytes(settings: dict[str, str], storage_key: str) -> bytes:
    try:
        response = cos_client(settings).get_object(Bucket=settings["bucket"], Key=storage_key)
        return response["Body"].get_raw_stream().read()
    except Exception as error:
        raise ValueError("隔离媒体不存在或无法读取，请重新上传") from error


def sanitise_product_image(binary: bytes, expected_mime_type: str) -> bytes:
    """Decode, bound and re-encode an image so EXIF and disguised files are removed."""
    if Image is None or ImageOps is None:
        raise RuntimeError("图片安全处理依赖 Pillow，生产环境请安装 requirements.txt")
    formats = {"image/jpeg": "JPEG", "image/png": "PNG", "image/webp": "WEBP"}
    try:
        with Image.open(io.BytesIO(binary)) as source:
            if source.format != formats[expected_mime_type]:
                raise ValueError("图片实际格式与声明类型不一致")
            source.verify()
        with Image.open(io.BytesIO(binary)) as source:
            image = ImageOps.exif_transpose(source)
            if image.width < 1 or image.height < 1 or image.width * image.height > 40_000_000:
                raise ValueError("图片像素尺寸不符合要求")
            if expected_mime_type == "image/jpeg":
                image = image.convert("RGB")
            elif expected_mime_type == "image/png" and image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA" if "transparency" in image.info else "RGB")
            elif expected_mime_type == "image/webp" and image.mode not in {"RGB", "RGBA"}:
                image = image.convert("RGBA" if "transparency" in image.info else "RGB")
            output = io.BytesIO()
            image.save(output, format=formats[expected_mime_type], optimize=True)
            return output.getvalue()
    except (UnidentifiedImageError, OSError, ValueError) as error:
        raise ValueError("图片内容无法通过安全校验") from error


def validate_product_video(binary: bytes, expected_mime_type: str) -> bytes:
    """Reject common disguised files before a video can enter the public bucket."""
    is_iso_base_media = len(binary) >= 12 and binary[4:8] == b"ftyp"
    valid = (
        expected_mime_type in {"video/mp4", "video/quicktime"} and is_iso_base_media
    ) or (expected_mime_type == "video/webm" and binary.startswith(b"\x1a\x45\xdf\xa3"))
    if not valid:
        raise ValueError("视频内容无法通过安全校验")
    return binary


def complete_product_media_upload(user_id: str, asset_id: str) -> dict[str, object]:
    """Verify and sanitise a quarantined direct upload before product use."""
    with database() as connection:
        connection.row_factory = sqlite3.Row
        asset = connection.execute(
            "SELECT * FROM media_assets WHERE id = ? AND uploader_user_id = ? AND status = 'temporary'",
            (asset_id, user_id),
        ).fetchone()
        if not asset:
            raise ValueError("媒体不存在、无权操作，或已完成处理")
        settings = public_cos_settings()
        if not settings or not str(asset["storage_key"]).startswith(f"{settings['quarantine_prefix']}/"):
            raise ValueError("该媒体不属于 COS 隔离上传任务")
        original = cos_object_bytes(settings, asset["storage_key"])
        if len(original) != int(asset["byte_size"]):
            raise ValueError("上传文件大小与签名请求不一致")
        actual_hash = hashlib.sha256(original).hexdigest()
        expected_hash = str(asset["content_hash"] or "")
        if expected_hash and not hmac.compare_digest(expected_hash, actual_hash):
            raise ValueError("上传文件校验和不一致")
        sanitized = (
            sanitise_product_image(original, asset["mime_type"])
            if asset["media_type"] == "image"
            else validate_product_video(original, asset["mime_type"])
        )
        try:
            cos_client(settings).put_object(
                Bucket=settings["bucket"], Key=asset["storage_key"], Body=sanitized,
                ContentType=asset["mime_type"], CacheControl="no-store",
            )
        except Exception as error:
            raise RuntimeError("无法完成隔离媒体处理") from error
        connection.execute(
            "UPDATE media_assets SET byte_size = ?, content_hash = ?, moderation_status = 'approved', verified_at = CURRENT_TIMESTAMP WHERE id = ?",
            (len(sanitized), hashlib.sha256(sanitized).hexdigest(), asset_id),
        )
    return {"id": asset_id, "assetId": asset_id, "previewUrl": f"/api/seller/media/assets/{asset_id}/preview", "status": "temporary"}


def upload_public_media_to_cos(filename: str, mime_type: str, binary: bytes) -> tuple[str, str] | None:
    """Upload public catalogue media and return its COS key and CDN URL.

    Returning None deliberately preserves the local media path when COS has not
    been configured, which keeps development and automated tests self-contained.
    """
    settings = public_cos_settings()
    if not settings:
        return None
    created = datetime.now(timezone.utc)
    storage_key = f"{settings['prefix']}/{created:%Y/%m}/{filename}"
    try:
        client = cos_client(settings)
        client.put_object(
            Bucket=settings["bucket"],
            Key=storage_key,
            Body=binary,
            ContentType=mime_type,
            CacheControl="public, max-age=31536000, immutable",
        )
    except Exception as error:
        raise RuntimeError("商品图片上传到 COS 失败，请检查 CAM 权限、存储桶和地域配置") from error
    return storage_key, f"{settings['cdn_base_url']}/{storage_key}"


def delete_public_media_from_cos(storage_key: str) -> bool:
    settings = public_cos_settings()
    if not settings or not storage_key.startswith(f"{settings['prefix']}/"):
        return False
    try:
        cos_client(settings).delete_object(Bucket=settings["bucket"], Key=storage_key)
        return True
    except Exception:
        return False


def websocket_text_frame(payload: dict) -> bytes:
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    size = len(body)
    if size < 126:
        return bytes((0x81, size)) + body
    if size < 65536:
        return bytes((0x81, 126)) + size.to_bytes(2, "big") + body
    return bytes((0x81, 127)) + size.to_bytes(8, "big") + body


class LiveMessageHub:
    """In-process authenticated WebSocket fan-out for message events."""

    def __init__(self) -> None:
        self.clients: dict[str, dict[object, threading.Lock]] = {}
        self.lock = threading.Lock()

    def add(self, user_id: str, client: object) -> None:
        with self.lock:
            self.clients.setdefault(user_id, {})[client] = threading.Lock()

    def remove(self, user_id: str, client: object) -> None:
        with self.lock:
            clients = self.clients.get(user_id)
            if not clients:
                return
            clients.pop(client, None)
            if not clients:
                self.clients.pop(user_id, None)

    def publish(self, user_ids: list[str] | set[str], payload: dict) -> None:
        frame = websocket_text_frame(payload)
        with self.lock:
            recipients = [
                (user_id, client, send_lock)
                for user_id in set(user_ids)
                for client, send_lock in self.clients.get(user_id, {}).items()
            ]
        for user_id, client, send_lock in recipients:
            try:
                with send_lock:
                    client.sendall(frame)
            except OSError:
                self.remove(user_id, client)


LIVE_MESSAGE_HUB = LiveMessageHub()


class CommunityLiveHub:
    """Anonymous community event fan-out; content still persists in SQLite."""

    def __init__(self) -> None:
        self.clients: dict[object, threading.Lock] = {}
        self.lock = threading.Lock()

    def add(self, client: object) -> None:
        with self.lock:
            self.clients[client] = threading.Lock()

    def remove(self, client: object) -> None:
        with self.lock:
            self.clients.pop(client, None)

    def publish(self, payload: dict) -> None:
        frame = websocket_text_frame(payload)
        with self.lock:
            clients = list(self.clients.items())
        for client, send_lock in clients:
            try:
                with send_lock:
                    client.sendall(frame)
            except OSError:
                self.remove(client)


COMMUNITY_LIVE_HUB = CommunityLiveHub()


def web_push_is_configured() -> bool:
    return bool(webpush and VAPID_PUBLIC_KEY and VAPID_PRIVATE_KEY and VAPID_SUBJECT)


def send_web_push_notifications(user_ids: list[str] | set[str], payload: dict) -> None:
    """Deliver a payload to stored browser subscriptions and prune expired endpoints."""
    if not web_push_is_configured() or not user_ids:
        return
    recipients = tuple(set(user_ids))
    with database() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            f"SELECT id, endpoint, subscription_json FROM push_subscriptions WHERE user_id IN ({','.join('?' for _ in recipients)})",
            recipients,
        ).fetchall()
    expired: list[str] = []
    for row in rows:
        try:
            webpush(
                subscription_info=json.loads(row["subscription_json"]),
                data=json.dumps(payload, ensure_ascii=False),
                vapid_private_key=VAPID_PRIVATE_KEY,
                vapid_claims={"sub": VAPID_SUBJECT},
            )
        except WebPushException as error:
            response = getattr(error, "response", None)
            if getattr(response, "status_code", None) in {404, 410}:
                expired.append(row["id"])
        except (ValueError, TypeError, json.JSONDecodeError):
            expired.append(row["id"])
    if expired:
        with database() as connection:
            connection.executemany("DELETE FROM push_subscriptions WHERE id = ?", [(item,) for item in expired])


def enqueue_web_push_notifications(user_ids: list[str] | set[str], payload: dict) -> None:
    if web_push_is_configured() and user_ids:
        threading.Thread(target=send_web_push_notifications, args=(user_ids, payload), daemon=True).start()


class StepUpRequiredError(Exception):
    pass


def database() -> sqlite3.Connection:
    return sqlite_connect(DB_PATH)


def number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0


def community_identity(handler: BaseHTTPRequestHandler, payload: dict) -> tuple[str, str]:
    visitor_id = str(payload.get("visitorId") or "").strip()
    nickname = re.sub(r"\s+", " ", str(payload.get("nickname") or "").strip())
    if not nickname:
        user_id = session_user(handler)
        if user_id:
            with database() as connection:
                user = connection.execute(
                    "SELECT display_name FROM users WHERE id = ? AND status = 'active'",
                    (user_id,),
                ).fetchone()
            nickname = re.sub(r"\s+", " ", str(user[0] if user else "").strip())
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,120}", visitor_id):
        raise ValueError("访客身份无效，请刷新页面后重试")
    if not 2 <= len(nickname) <= 24:
        raise ValueError("临时昵称请填写 2 到 24 个字符")
    return visitor_id, nickname


def community_attachment_urls(payload: dict) -> list[str]:
    values = payload.get("attachmentUrls") if isinstance(payload.get("attachmentUrls"), list) else []
    urls = [str(value).strip() for value in values if str(value).strip()]
    legacy_url = str(payload.get("attachmentUrl") or "").strip()
    if legacy_url:
        urls.append(legacy_url)
    urls = list(dict.fromkeys(urls))
    if len(urls) > 6 or any(not url.startswith("/media/") or len(url) > 300 for url in urls):
        raise ValueError("图片地址无效，最多可添加 6 张图片")
    return urls


def community_rate_allowed(handler: object, visitor_id: str, action: str, maximum: int, seconds: int) -> bool:
    ip_address = getattr(handler, "client_address", ("unknown",))[0]
    key = f"{action}:{ip_address}:{visitor_id}"
    now = datetime.now(timezone.utc)
    entries = [item for item in COMMUNITY_RATE_LIMITS.get(key, []) if (now - item).total_seconds() < seconds]
    if len(entries) >= maximum:
        COMMUNITY_RATE_LIMITS[key] = entries
        return False
    entries.append(now)
    COMMUNITY_RATE_LIMITS[key] = entries
    return True


def community_posts_payload(connection: sqlite3.Connection, category: str = "") -> list[dict]:
    connection.row_factory = sqlite3.Row
    query = "SELECT * FROM community_posts WHERE status = 'published'"
    params: tuple[object, ...] = ()
    if category:
        query += " AND category = ?"
        params = (category,)
    posts = connection.execute(
        f"{query} ORDER BY is_pinned DESC, pinned_at DESC, created_at DESC LIMIT 100",
        params,
    ).fetchall()
    post_ids = [row["id"] for row in posts]
    comments_by_post: dict[str, list[dict]] = {post_id: [] for post_id in post_ids}
    post_images: dict[str, list[str]] = {post_id: [] for post_id in post_ids}
    if post_ids:
        placeholders = ",".join("?" for _ in post_ids)
        for row in connection.execute(f"SELECT post_id, image_url FROM community_post_images WHERE post_id IN ({placeholders}) ORDER BY sort_order, created_at", post_ids).fetchall():
            post_images[row["post_id"]].append(row["image_url"])
    if post_ids:
        placeholders = ",".join("?" for _ in post_ids)
        comments = connection.execute(
            f"SELECT * FROM community_comments WHERE post_id IN ({placeholders}) AND status = 'published' ORDER BY created_at ASC",
            post_ids,
        ).fetchall()
        comment_ids = [row["id"] for row in comments]
        comment_images: dict[str, list[str]] = {comment_id: [] for comment_id in comment_ids}
        if comment_ids:
            comment_placeholders = ",".join("?" for _ in comment_ids)
            for image in connection.execute(f"SELECT comment_id, image_url FROM community_comment_images WHERE comment_id IN ({comment_placeholders}) ORDER BY sort_order, created_at", comment_ids).fetchall():
                comment_images[image["comment_id"]].append(image["image_url"])
        else:
            comment_images = {}
        for row in comments:
            images = comment_images.get(row["id"], [])
            if not images and row["attachment_url"]:
                images = [row["attachment_url"]]
            comments_by_post[row["post_id"]].append({
                "id": row["id"], "nickname": row["nickname"], "content": row["content"], "createdAt": row["created_at"], "parentCommentId": row["parent_comment_id"], "imageUrl": images[0] if images else None, "imageUrls": images,
            })
    for post_id, row in zip(post_ids, posts):
        if not post_images[post_id] and row["attachment_url"]:
            post_images[post_id] = [row["attachment_url"]]
    return [{
        "id": row["id"], "nickname": row["nickname"], "category": f"置顶 · {row['category']}" if row["is_pinned"] else row["category"], "title": row["title"],
        "content": row["content"], "createdAt": row["created_at"], "pinned": bool(row["is_pinned"]), "imageUrl": post_images[row["id"]][0] if post_images[row["id"]] else None, "imageUrls": post_images[row["id"]], "comments": comments_by_post[row["id"]],
    } for row in posts]


def admin_community_posts_payload(connection: sqlite3.Connection) -> list[dict]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT community_posts.*, COALESCE((SELECT image_url FROM community_post_images WHERE post_id = community_posts.id ORDER BY sort_order, created_at LIMIT 1), community_posts.attachment_url) AS image_url, COUNT(community_comments.id) AS comment_count
        FROM community_posts
        LEFT JOIN community_comments
          ON community_comments.post_id = community_posts.id
          AND community_comments.status = 'published'
        WHERE community_posts.status = 'published'
        GROUP BY community_posts.id
        ORDER BY community_posts.is_pinned DESC, community_posts.pinned_at DESC, community_posts.created_at DESC
        LIMIT 100
        """
    ).fetchall()
    return [{
        "id": row["id"], "nickname": row["nickname"], "category": row["category"],
        "title": row["title"], "content": row["content"], "createdAt": row["created_at"],
        "pinned": bool(row["is_pinned"]), "commentCount": row["comment_count"], "imageUrl": row["image_url"],
    } for row in rows]


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


def token_hash(token: str) -> str:
    return hashlib.sha256(f"{SESSION_SECRET}:{token}".encode("utf-8")).hexdigest()


class SmsDeliveryError(ValueError):
    """A safe, user-facing error for an unsuccessful SMS delivery."""


def tencent_sms_is_configured() -> bool:
    return bool(
        TENCENT_SMS_SECRET_ID
        and TENCENT_SMS_SECRET_KEY
        and TENCENT_SMS_APP_ID
        and TENCENT_SMS_SIGN_NAME
    )


def tencent_sms_phone_number(destination: str) -> str:
    """Return a Tencent Cloud E.164 destination for a mainland China mobile."""
    phone = re.sub(r"[\s-]", "", str(destination or ""))
    if phone.startswith("+86"):
        phone = phone[3:]
    elif phone.startswith("0086"):
        phone = phone[4:]
    if not re.fullmatch(r"1\d{10}", phone):
        raise SmsDeliveryError("短信验证码仅支持已绑定的中国大陆手机号码")
    return f"+86{phone}"


def sms_request_allowed(handler: BaseHTTPRequestHandler, destination: str, purpose: str) -> bool:
    """Apply a small in-memory limit before any billable SMS request."""
    now = datetime.now(timezone.utc)
    ip_address = getattr(handler, "client_address", ("unknown",))[0]
    key = f"{ip_address}:{destination}:{purpose}"
    requests = [item for item in SMS_REQUESTS.get(key, []) if (now - item).total_seconds() < 600]
    if (requests and (now - requests[-1]).total_seconds() < 60) or len(requests) >= 5:
        SMS_REQUESTS[key] = requests
        return False
    requests.append(now)
    SMS_REQUESTS[key] = requests
    return True


def send_tencent_sms(destination: str, template_id: str, template_params: list[str] | None = None) -> None:
    """Send one approved Tencent Cloud SMS template without exposing credentials."""
    if not tencent_sms_is_configured() or not template_id:
        raise SmsDeliveryError("短信服务尚未完成配置，请联系平台管理员")
    timestamp = int(time.time())
    date = datetime.fromtimestamp(timestamp, timezone.utc).strftime("%Y-%m-%d")
    payload = {
        "PhoneNumberSet": [tencent_sms_phone_number(destination)],
        "SmsSdkAppId": TENCENT_SMS_APP_ID,
        "SignName": TENCENT_SMS_SIGN_NAME,
        "TemplateId": template_id,
        "TemplateParamSet": template_params or [],
    }
    body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    hashed_payload = hashlib.sha256(body).hexdigest()
    canonical_headers = "content-type:application/json; charset=utf-8\nhost:sms.tencentcloudapi.com\n"
    signed_headers = "content-type;host"
    canonical_request = f"POST\n/\n\n{canonical_headers}\n{signed_headers}\n{hashed_payload}"
    credential_scope = f"{date}/sms/tc3_request"
    string_to_sign = "TC3-HMAC-SHA256\n{}\n{}\n{}".format(
        timestamp,
        credential_scope,
        hashlib.sha256(canonical_request.encode("utf-8")).hexdigest(),
    )

    def sign(key: bytes, message: str) -> bytes:
        return hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()

    secret_date = sign(("TC3" + TENCENT_SMS_SECRET_KEY).encode("utf-8"), date)
    secret_service = sign(secret_date, "sms")
    secret_signing = sign(secret_service, "tc3_request")
    signature = hmac.new(secret_signing, string_to_sign.encode("utf-8"), hashlib.sha256).hexdigest()
    authorization = (
        "TC3-HMAC-SHA256 Credential={}/{}, SignedHeaders={}, Signature={}"
        .format(TENCENT_SMS_SECRET_ID, credential_scope, signed_headers, signature)
    )
    request = Request(
        "https://sms.tencentcloudapi.com/",
        data=body,
        method="POST",
        headers={
            "Authorization": authorization,
            "Content-Type": "application/json; charset=utf-8",
            "Host": "sms.tencentcloudapi.com",
            "X-TC-Action": "SendSms",
            "X-TC-Timestamp": str(timestamp),
            "X-TC-Version": "2021-01-11",
            "X-TC-Region": TENCENT_SMS_REGION,
        },
    )
    try:
        with urlopen(request, timeout=10) as response:
            result = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, OSError):
        raise SmsDeliveryError("短信发送失败，请稍后重试") from None
    response_body = result.get("Response") if isinstance(result, dict) else None
    status = response_body.get("SendStatusSet", [{}])[0] if isinstance(response_body, dict) and response_body.get("SendStatusSet") else {}
    if response_body.get("Error") or status.get("Code") != "Ok":
        raise SmsDeliveryError("短信发送失败，请稍后重试")


def verification_expiry_minutes(purpose: str) -> int:
    return 5 if purpose == "admin_step_up" else 2


def issue_verification(connection: sqlite3.Connection, user_id: str | None, destination: str, purpose: str) -> str:
    code = f"{secrets.randbelow(900000) + 100000}"
    connection.execute("UPDATE verification_tokens SET consumed_at = CURRENT_TIMESTAMP WHERE destination = ? AND purpose = ? AND consumed_at IS NULL", (destination, purpose))
    connection.execute("INSERT INTO verification_tokens (id, user_id, destination, purpose, token_hash, expires_at) VALUES (?, ?, ?, ?, ?, datetime('now', ?))", (f"verify-{secrets.token_urlsafe(10)}", user_id, destination, purpose, token_hash(code), f"+{verification_expiry_minutes(purpose)} minutes"))
    return code


def deliver_verification_code(destination: str, purpose: str, code: str) -> bool:
    """Deliver a verification code.  Development only exposes a code when SMS is disabled."""
    if TENCENT_SMS_ENABLED:
        template_params = [code, "5"] if purpose in {"contact_verify", "password_reset"} else [code]
        send_tencent_sms(destination, TENCENT_SMS_TEMPLATES.get(purpose, ""), template_params)
        return True
    if PRODUCTION_HTTPS:
        raise SmsDeliveryError("短信服务尚未启用，请联系平台管理员")
    return False


def enqueue_tencent_sms_notification(destination: str, purpose: str) -> None:
    """Best-effort delivery for approved notification templates.

    Business records and in-site notices must not fail merely because an SMS
    provider is temporarily unavailable, so notification sends are isolated in
    a background thread. Verification messages intentionally do not use this
    helper because their delivery must succeed before a code can be accepted.
    """
    template_id = TENCENT_SMS_TEMPLATES.get(purpose, "")
    if not TENCENT_SMS_ENABLED or not template_id or not str(destination or "").strip():
        return

    def deliver() -> None:
        try:
            send_tencent_sms(destination, template_id)
        except SmsDeliveryError:
            # Do not log phone numbers, verification data, or cloud errors.
            pass

    threading.Thread(target=deliver, daemon=True).start()


def consume_verification(connection: sqlite3.Connection, destination: str, purpose: str, code: str) -> sqlite3.Row | None:
    connection.row_factory = sqlite3.Row
    row = connection.execute("SELECT * FROM verification_tokens WHERE destination = ? AND purpose = ? AND consumed_at IS NULL AND expires_at > CURRENT_TIMESTAMP ORDER BY created_at DESC LIMIT 1", (destination, purpose)).fetchone()
    if not row or row["attempts"] >= 5 or not secrets.compare_digest(row["token_hash"], token_hash(code)):
        if row: connection.execute("UPDATE verification_tokens SET attempts = attempts + 1 WHERE id = ?", (row["id"],))
        return None
    connection.execute("UPDATE verification_tokens SET consumed_at = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],))
    return row


def verify_password(password: str, stored: str) -> tuple[bool, bool]:
    parts = stored.split("$")
    if len(parts) == 6 and parts[0] == "scrypt":
        try:
            digest = hashlib.scrypt(password.encode("utf-8"), salt=bytes.fromhex(parts[4]), n=int(parts[1]), r=int(parts[2]), p=int(parts[3]), dklen=32)
            return secrets.compare_digest(digest.hex(), parts[5]), False
        except (ValueError, TypeError):
            return False, False
    return secrets.compare_digest(password, stored), True


def client_ip(handler: BaseHTTPRequestHandler) -> str:
    """Return the visitor address forwarded by the local reverse proxy.

    The production API binds to 127.0.0.1, so only trust proxy headers when
    that local proxy is the peer. This avoids letting direct callers spoof an
    address by adding X-Forwarded-For themselves.
    """
    peer_ip = str(getattr(handler, "client_address", ("unknown",))[0])
    if peer_ip not in {"127.0.0.1", "::1"}:
        return peer_ip
    forwarded = handler.headers.get("X-Real-IP", "") or handler.headers.get("X-Forwarded-For", "").rsplit(",", 1)[-1].strip()
    try:
        return str(ipaddress.ip_address(forwarded))
    except ValueError:
        return peer_ip


def login_allowed(client_ip: str) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    with LOGIN_FAILURES_LOCK:
        failures = [item for item in LOGIN_FAILURES.get(client_ip, []) if item > cutoff]
        LOGIN_FAILURES[client_ip] = failures
        return len(failures) < 5


def session_cookie(token: str) -> str:
    secure = "; Secure" if PRODUCTION_HTTPS else ""
    return f"handicrafts_session={token}; Path=/; Max-Age=1209600; HttpOnly; SameSite=Lax{secure}"


def register_login_failure(client_ip: str) -> None:
    with LOGIN_FAILURES_LOCK:
        LOGIN_FAILURES.setdefault(client_ip, []).append(datetime.now(timezone.utc))


def clear_login_failures(client_ip: str) -> None:
    with LOGIN_FAILURES_LOCK:
        LOGIN_FAILURES.pop(client_ip, None)


def seo_tags(product: dict) -> list[str]:
    tags: list[str] = []
    for raw_tag in product.get("seoTags") or []:
        tag = str(raw_tag).strip().lstrip("#")
        if not tag or tag in tags:
            continue
        if len(tag) > 10:
            raise ValueError("每个搜索标签最多 10 个字")
        tags.append(tag)
    if len(tags) > 12:
        raise ValueError("最多添加 12 个搜索标签")
    return tags


def buyer_seo_tags(product: dict) -> list[str]:
    tags: list[str] = []
    for raw_tag in product.get("buyerSeoTags") or []:
        tag = str(raw_tag).strip().lstrip("#")
        if not tag or tag in tags:
            continue
        if len(tag) > 40:
            raise ValueError("English search tags can contain up to 40 characters")
        tags.append(tag)
    if len(tags) > 12:
        raise ValueError("You can add up to 12 English search tags")
    return tags


def media_url_is_allowed(url: object, media_type: str) -> bool:
    value = str(url or "")
    if value.startswith("/media/") or value.startswith("https://") or value.startswith("http://"):
        return True
    return value.startswith(f"data:{'image/' if media_type == 'image' else 'video/'}")


def validate_product_media(product: dict) -> None:
    images = [image for image in product.get("images") or ([product.get("image")] if product.get("image") else []) if image]
    if not images:
        raise ValueError("请至少上传 1 张作品图片")
    if len(images) > 10:
        raise ValueError("作品图片最多 10 张")
    if any(not media_url_is_allowed(image, "image") for image in images):
        raise ValueError("图片地址不合法")
    video = product.get("video")
    if video and not media_url_is_allowed(video, "video"):
        raise ValueError("视频地址不合法")


def moderation_text(product: dict, title: str, tags: list[str]) -> str:
    variants = product.get("variants") or []
    variant_text = "".join(
        f"{variant.get('name') or ''}{''.join(str(value) for value in variant.get('values') or [])}"
        for variant in variants
    )
    return "".join(
        (
            title,
            str(product.get("description") or ""),
            str(product.get("material") or ""),
            str(product.get("craftsmanship") or ""),
            "".join(tags),
            str(product.get("buyerTitle") or ""),
            str(product.get("buyerDescription") or ""),
            str(product.get("buyerMaterial") or ""),
            "".join(buyer_seo_tags(product)),
            variant_text,
        )
    ).lower()


def governance_rule_conditions(rule: sqlite3.Row) -> tuple[list[dict], str]:
    try:
        conditions = json.loads(rule["conditions_json"] or "[]")
    except (TypeError, json.JSONDecodeError):
        conditions = []
    if not isinstance(conditions, list):
        conditions = []
    if not conditions and rule["keyword"]:
        conditions = [{"field": "content", "operator": "contains", "value": rule["keyword"]}]
    return [item for item in conditions if isinstance(item, dict)], str(rule["condition_logic"] or "all")


def normalized_governance_conditions(raw: object, keyword: str) -> list[dict]:
    values = raw if isinstance(raw, list) else []
    if not values and keyword:
        values = [{"field": "content", "operator": "contains", "value": keyword}]
    if not 1 <= len(values) <= 8:
        raise ValueError("审核规则需要 1-8 个条件")
    normalized: list[dict] = []
    for value in values:
        if not isinstance(value, dict):
            raise ValueError("审核条件格式无效")
        field, operator, expected = str(value.get("field") or ""), str(value.get("operator") or "contains"), str(value.get("value") or "").strip().lower()
        if field not in {"content", "title", "description", "material", "category", "tags"} or operator not in {"contains", "equals", "not_contains"} or not 1 <= len(expected) <= 80:
            raise ValueError("审核条件无效")
        normalized.append({"field": field, "operator": operator, "value": expected})
    return normalized


def governance_condition_matches(condition: dict, product: dict, title: str, tags: list[str], content: str) -> bool:
    field, operator, expected = str(condition.get("field") or "content"), str(condition.get("operator") or "contains"), str(condition.get("value") or "").strip().lower()
    values = {
        "content": content,
        "title": title.lower(),
        "description": str(product.get("description") or "").lower(),
        "material": str(product.get("material") or "").lower(),
        "category": str(product.get("category") or "").lower(),
        "tags": " ".join(tags).lower(),
    }
    actual = values.get(field, "")
    if not expected:
        return False
    if operator == "equals":
        return actual == expected
    if operator == "not_contains":
        return expected not in actual
    return expected in actual


def matched_governance_rule(connection: sqlite3.Connection, product_id: str, product: dict, title: str, tags: list[str], content: str) -> sqlite3.Row | None:
    rows = connection.execute(
        "SELECT * FROM governance_rules WHERE enabled = 1 AND release_status = 'active' ORDER BY priority ASC, updated_at DESC"
    ).fetchall()
    for row in rows:
        conditions, logic = governance_rule_conditions(row)
        if not conditions:
            continue
        results = [governance_condition_matches(condition, product, title, tags, content) for condition in conditions]
        if not (any(results) if logic == "any" else all(results)):
            continue
        bucket = int(hashlib.sha256(f"{row['id']}:{product_id}".encode("utf-8")).hexdigest()[:8], 16) % 100
        if bucket >= int(row["rollout_percent"]):
            continue
        return row
    return None


def record_governance_rule_hit(connection: sqlite3.Connection, rule: sqlite3.Row, product_id: str, content: str) -> None:
    connection.execute(
        "INSERT INTO governance_rule_hits (id, rule_id, rule_version, product_id, action, rollout_percent, content_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (f"rule-hit-{secrets.token_urlsafe(10)}", rule["id"], rule["version"], product_id, rule["action"], rule["rollout_percent"], hashlib.sha256(content.encode("utf-8")).hexdigest()),
    )


def write_moderation_log(connection: sqlite3.Connection, product_id: str, content: str, status: str, reason: str | None) -> None:
    fingerprint = hashlib.sha256(content.encode("utf-8")).hexdigest()
    connection.execute(
        "INSERT OR IGNORE INTO product_moderation_logs (id, product_id, content_hash, status, reason) VALUES (?, ?, ?, ?, ?)",
        (f"moderation-{secrets.token_urlsafe(10)}", product_id, fingerprint, status, reason),
    )


def decode_media_data_url(value: object, expected_type: str) -> tuple[str, bytes]:
    match = re.fullmatch(r"data:([\w.+-]+/[\w.+-]+);base64,([A-Za-z0-9+/=\s]+)", str(value or ""))
    if not match:
        raise ValueError("媒体文件格式无效")
    mime_type, encoded = match.groups()
    allowed = IMAGE_MIME_TYPES if expected_type == "image" else VIDEO_MIME_TYPES
    if mime_type not in allowed:
        raise ValueError("不支持的媒体格式")
    try:
        binary = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise ValueError("媒体文件无法解析")
    limit = MAX_IMAGE_BYTES if expected_type == "image" else MAX_VIDEO_BYTES
    if not binary or len(binary) > limit:
        raise ValueError("媒体文件大小不符合要求")
    return mime_type, binary


def create_quarantined_product_media(user_id: str, media_type: str, data: object) -> dict[str, object]:
    """Accept a local-development upload into private quarantine and verify it."""
    mime_type, binary = decode_media_data_url(data, media_type)
    sanitized = sanitise_product_image(binary, mime_type) if media_type == "image" else validate_product_video(binary, mime_type)
    asset_id = f"asset-{secrets.token_urlsafe(12)}"
    filename = f"{asset_id}{(IMAGE_MIME_TYPES if media_type == 'image' else VIDEO_MIME_TYPES)[mime_type]}"
    QUARANTINE_MEDIA_DIR.mkdir(parents=True, exist_ok=True)
    (QUARANTINE_MEDIA_DIR / filename).write_bytes(sanitized)
    with database() as connection:
        connection.execute(
            """
            INSERT INTO media_assets (id, uploader_user_id, media_type, mime_type, storage_key, public_url, byte_size, content_hash, verified_at, moderation_status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, 'approved')
            """,
            (asset_id, user_id, media_type, mime_type, f"quarantine-local/{filename}", f"/api/seller/media/assets/{asset_id}/preview", len(sanitized), hashlib.sha256(sanitized).hexdigest()),
        )
    return {"id": asset_id, "assetId": asset_id, "previewUrl": f"/api/seller/media/assets/{asset_id}/preview", "status": "temporary"}


def quarantined_media_bytes(asset: sqlite3.Row) -> bytes:
    settings = public_cos_settings()
    storage_key = str(asset["storage_key"])
    if settings and storage_key.startswith(f"{settings['quarantine_prefix']}/"):
        return cos_object_bytes(settings, storage_key)
    filename = Path(storage_key).name
    path = QUARANTINE_MEDIA_DIR / filename
    if not path.is_file():
        raise ValueError("隔离媒体不存在")
    return path.read_bytes()


def promote_product_media_assets(connection: sqlite3.Connection, user_id: str, asset_ids: list[str], *, activate: bool = True, enforce_listing_limits: bool = True) -> list[sqlite3.Row]:
    """Authorize verified assets, publish them, and return media rows in request order."""
    if not 1 <= len(asset_ids) <= 11 or len(set(asset_ids)) != len(asset_ids):
        raise ValueError("商品媒体资产数量或顺序无效")
    placeholders = ",".join("?" for _ in asset_ids)
    rows = connection.execute(
        f"SELECT * FROM media_assets WHERE id IN ({placeholders})", tuple(asset_ids)
    ).fetchall()
    by_id = {str(row["id"]): row for row in rows}
    if len(by_id) != len(asset_ids):
        raise ValueError("商品引用了不存在的媒体资产")
    ordered = [by_id[asset_id] for asset_id in asset_ids]
    if any(row["uploader_user_id"] != user_id for row in ordered):
        raise ValueError("只能引用自己上传的媒体资产")
    if any(row["status"] not in ("temporary", "active") or row["moderation_status"] != "approved" or not row["verified_at"] for row in ordered):
        raise ValueError("媒体尚未完成安全校验或审核")
    images = [row for row in ordered if row["media_type"] == "image"]
    videos = [row for row in ordered if row["media_type"] == "video"]
    if enforce_listing_limits and (not 1 <= len(images) <= 10 or len(videos) > 1):
        raise ValueError("商品需要 1-10 张已审核图片，且最多 1 个视频")
    settings = public_cos_settings()
    for row in ordered:
        if not activate:
            continue
        if row["status"] == "active":
            continue
        extension = (IMAGE_MIME_TYPES if row["media_type"] == "image" else VIDEO_MIME_TYPES)[row["mime_type"]]
        filename = f"{row['id']}{extension}"
        if settings:
            public_key = f"{settings['prefix']}/{datetime.now(timezone.utc):%Y/%m}/{filename}"
            content = quarantined_media_bytes(row)
            try:
                cos_client(settings).put_object(Bucket=settings["bucket"], Key=public_key, Body=content, ContentType=row["mime_type"], CacheControl="public, max-age=31536000, immutable")
                cos_client(settings).delete_object(Bucket=settings["bucket"], Key=row["storage_key"])
            except Exception as error:
                raise RuntimeError("媒体发布到 CDN 失败") from error
            storage_key, public_url = public_key, f"{settings['cdn_base_url']}/{public_key}"
        else:
            source = QUARANTINE_MEDIA_DIR / Path(row["storage_key"]).name
            if not source.is_file():
                raise ValueError("隔离媒体不存在")
            MEDIA_DIR.mkdir(parents=True, exist_ok=True)
            target = MEDIA_DIR / filename
            target.write_bytes(source.read_bytes())
            source.unlink()
            storage_key, public_url = filename, f"/media/{filename}"
        connection.execute(
            "UPDATE media_assets SET storage_key = ?, public_url = ?, status = 'active' WHERE id = ?",
            (storage_key, public_url, row["id"]),
        )
    refreshed = connection.execute(
        f"SELECT * FROM media_assets WHERE id IN ({placeholders})", tuple(asset_ids)
    ).fetchall()
    refreshed_by_id = {str(row["id"]): row for row in refreshed}
    return [refreshed_by_id[asset_id] for asset_id in asset_ids]


def media_storage_key(url: object) -> str | None:
    value = str(url or "")
    cos_key = public_cos_media_key(value)
    if cos_key:
        return cos_key
    marker = "/media/"
    if marker not in value:
        return None
    return Path(value.split(marker, 1)[1].split("?", 1)[0]).name or None


def link_media_assets(connection: sqlite3.Connection, urls: list[object], target_type: str, target_id: str, uploader_user_id: str | None = None) -> None:
    keys = [key for key in (media_storage_key(url) for url in urls) if key]
    if not keys:
        return
    placeholders = ",".join("?" for _ in keys)
    ownership = " AND uploader_user_id = ?" if uploader_user_id else ""
    assets = connection.execute(
        f"SELECT id FROM media_assets WHERE storage_key IN ({placeholders}) AND status != 'deleted'{ownership}", tuple(keys) + ((uploader_user_id,) if uploader_user_id else tuple())
    ).fetchall()
    for asset in assets:
        connection.execute(
            "INSERT OR IGNORE INTO media_asset_links (id, asset_id, target_type, target_id) VALUES (?, ?, ?, ?)",
            (f"asset-link-{secrets.token_urlsafe(10)}", asset[0], target_type, target_id),
        )
        connection.execute("UPDATE media_assets SET status = 'active' WHERE id = ?", (asset[0],))


def record_risk_case(
    connection: sqlite3.Connection,
    category: str,
    severity: str,
    reason_code: str,
    *,
    subject_user_id: str | None = None,
    order_id: str | None = None,
    product_id: str | None = None,
    detail: dict | None = None,
    fingerprint_parts: tuple[object, ...] = (),
) -> None:
    """Create or refresh a deduplicated, reviewable marketplace risk case."""
    fingerprint_source = "|".join(str(item or "") for item in (category, reason_code, subject_user_id, order_id, product_id, *fingerprint_parts))
    fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
    connection.execute(
        """
        INSERT INTO risk_cases (id, fingerprint, category, severity, subject_user_id, order_id, product_id, reason_code, detail_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(fingerprint) DO UPDATE SET
          severity = CASE WHEN excluded.severity = 'high' OR risk_cases.severity = 'low' AND excluded.severity = 'medium' THEN excluded.severity ELSE risk_cases.severity END,
          detail_json = excluded.detail_json,
          occurrences = risk_cases.occurrences + 1,
          last_seen_at = CURRENT_TIMESTAMP,
          status = CASE WHEN risk_cases.status IN ('resolved', 'dismissed') THEN 'open' ELSE risk_cases.status END,
          resolved_at = NULL, resolved_by_user_id = NULL, resolution_note = NULL
        """,
        (
            f"risk-{secrets.token_urlsafe(10)}", fingerprint, category, severity,
            subject_user_id, order_id, product_id, reason_code,
            json.dumps(detail or {}, ensure_ascii=False),
        ),
    )


def write_after_sale_case_event(
    connection: sqlite3.Connection,
    after_sale_id: str,
    event_type: str,
    *,
    actor_user_id: str | None = None,
    detail: dict | None = None,
    evidence: list[str] | None = None,
) -> None:
    hashes = [hashlib.sha256(item.encode("utf-8")).hexdigest() for item in evidence or []]
    connection.execute(
        "INSERT INTO after_sale_case_events (id, after_sale_id, actor_user_id, event_type, detail_json, evidence_hashes_json) VALUES (?, ?, ?, ?, ?, ?)",
        (
            f"after-sale-event-{secrets.token_urlsafe(10)}", after_sale_id,
            actor_user_id, event_type, json.dumps(detail or {}, ensure_ascii=False),
            json.dumps(hashes, ensure_ascii=False),
        ),
    )


def record_product_image_fingerprints(connection: sqlite3.Connection, product_id: str, urls: list[object]) -> None:
    """Record exact binary image hashes and queue matches from different products.

    Exact hashes deliberately flag cases for review instead of auto-unlisting: a maker
    can legitimately reuse a product image for a variation or a relisted work.
    """
    keys = [key for key in (media_storage_key(url) for url in urls) if key]
    if not keys:
        return
    placeholders = ",".join("?" for _ in keys)
    assets = connection.execute(
        f"SELECT public_url, content_hash FROM media_assets WHERE storage_key IN ({placeholders}) AND content_hash IS NOT NULL",
        tuple(keys),
    ).fetchall()
    for asset in assets:
        content_hash = str(asset["content_hash"] or "")
        if not re.fullmatch(r"[a-f0-9]{64}", content_hash):
            continue
        connection.execute(
            "INSERT OR IGNORE INTO product_image_fingerprints (id, product_id, media_url, content_hash) VALUES (?, ?, ?, ?)",
            (f"product-image-hash-{secrets.token_urlsafe(10)}", product_id, asset["public_url"], content_hash),
        )
        matches = connection.execute(
            "SELECT product_id, media_url FROM product_image_fingerprints WHERE content_hash = ? AND product_id != ? LIMIT 10",
            (content_hash, product_id),
        ).fetchall()
        for match in matches:
            pair = tuple(sorted((product_id, str(match["product_id"]))))
            record_risk_case(
                connection, "image_duplicate", "medium", "exact_image_hash_match",
                product_id=product_id,
                detail={"matchedProductId": match["product_id"], "mediaUrl": asset["public_url"], "matchedMediaUrl": match["media_url"]},
                fingerprint_parts=(content_hash, *pair),
            )


def risk_cases_payload(connection: sqlite3.Connection) -> list[dict]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        """
        SELECT risk_cases.*, users.display_name AS subject_name, orders.order_no,
               products.title AS product_title
        FROM risk_cases
        LEFT JOIN users ON users.id = risk_cases.subject_user_id
        LEFT JOIN orders ON orders.id = risk_cases.order_id
        LEFT JOIN products ON products.id = risk_cases.product_id
        ORDER BY CASE risk_cases.status WHEN 'open' THEN 0 WHEN 'reviewing' THEN 1 ELSE 2 END,
                 CASE risk_cases.severity WHEN 'high' THEN 0 WHEN 'medium' THEN 1 ELSE 2 END,
                 risk_cases.last_seen_at DESC
        LIMIT 200
        """
    ).fetchall()
    return [
        {
            "id": row["id"], "category": row["category"], "severity": row["severity"],
            "status": row["status"], "reasonCode": row["reason_code"],
            "subjectUserId": row["subject_user_id"], "subject": row["subject_name"],
            "orderNo": row["order_no"], "productId": row["product_id"],
            "productTitle": row["product_title"], "detail": json.loads(row["detail_json"] or "{}"),
            "occurrences": row["occurrences"], "createdAt": row["created_at"],
            "lastSeenAt": row["last_seen_at"], "resolutionNote": row["resolution_note"],
        }
        for row in rows
    ]


def cleanup_temporary_media(connection: sqlite3.Connection) -> int:
    rows = connection.execute(
        """
        SELECT media_assets.id, media_assets.storage_key FROM media_assets
        WHERE media_assets.status = 'temporary' AND media_assets.created_at <= datetime('now', '-24 hours')
          AND NOT EXISTS (SELECT 1 FROM media_asset_links WHERE media_asset_links.asset_id = media_assets.id)
        """
    ).fetchall()
    settings = public_cos_settings()
    for asset_id, storage_key in rows:
        storage_key = str(storage_key)
        if settings and storage_key.startswith(f"{settings['quarantine_prefix']}/"):
            try:
                cos_client(settings).delete_object(Bucket=settings["bucket"], Key=storage_key)
            except Exception:
                # The database marker still prevents a failed/expired upload from
                # being attached later. A provider lifecycle rule is the final
                # backstop for an object COS could not delete here.
                pass
        elif storage_key.startswith("quarantine-local/"):
            path = QUARANTINE_MEDIA_DIR / Path(storage_key).name
            if path.is_file():
                path.unlink()
        elif not delete_public_media_from_cos(storage_key):
            path = MEDIA_DIR / Path(storage_key).name
            if not path.is_file():
                path = LEGACY_MEDIA_DIR / Path(storage_key).name
            if path.is_file():
                path.unlink()
        connection.execute("UPDATE media_assets SET status = 'deleted', deleted_at = CURRENT_TIMESTAMP WHERE id = ?", (asset_id,))
    return len(rows)


def media_rows(product_id: str, product: dict) -> list[tuple]:
    assets = product.get("_media_assets") or []
    if assets:
        return [
            (f"{product_id}-media-{index}", product_id, row["media_type"], row["storage_key"], row["public_url"], index, int(index == 0 and row["media_type"] == "image"), row["asset_id"] if "asset_id" in row.keys() else row["id"])
            for index, row in enumerate(assets)
        ]
    images = product.get("images") or ([product["image"]] if product.get("image") else [])
    rows = [
        (f"{product_id}-image-{index}", product_id, "image", url, url, index, int(index == 0), None)
        for index, url in enumerate(images)
        if url
    ]
    if product.get("video"):
        rows.append((f"{product_id}-video", product_id, "video", product["video"], product["video"], len(rows), 0, None))
    return rows


def resolve_product_media_assets(connection: sqlite3.Connection, user_id: str, product_id: str, product: dict, status: str, existing: bool) -> None:
    """Replace client URLs with seller-owned, verified asset records."""
    raw_ids = product.get("mediaAssetIds")
    asset_ids = [str(value).strip() for value in raw_ids] if isinstance(raw_ids, list) else []
    if asset_ids:
        assets = promote_product_media_assets(connection, user_id, asset_ids, activate=status == "published")
        product["_media_assets"] = assets
        product["images"] = [row["public_url"] for row in assets if row["media_type"] == "image"]
        product["image"] = product["images"][0] if product["images"] else ""
        product["video"] = next((row["public_url"] for row in assets if row["media_type"] == "video"), "")
        return
    if existing:
        current_media = connection.execute(
            "SELECT id, asset_id, media_type, storage_key, public_url FROM product_media WHERE product_id = ? ORDER BY sort_order",
            (product_id,),
        ).fetchall()
        current_asset_ids = [str(row["asset_id"]) for row in current_media if row["asset_id"]]
        if status == "published" and current_asset_ids and len(current_asset_ids) == len(current_media):
            assets = promote_product_media_assets(connection, user_id, current_asset_ids, activate=True)
            product["_media_assets"] = assets
            product["images"] = [row["public_url"] for row in assets if row["media_type"] == "image"]
            product["image"] = product["images"][0] if product["images"] else ""
            product["video"] = next((row["public_url"] for row in assets if row["media_type"] == "video"), "")
            return
        # Legacy listings may retain their historical URL-only media while they
        # are edited. New media for a listing is always represented by asset ID.
        if current_asset_ids and len(current_asset_ids) == len(current_media):
            product["_media_assets"] = current_media
        product["images"] = [row["public_url"] for row in current_media if row["media_type"] == "image"]
        product["image"] = product["images"][0] if product["images"] else ""
        product["video"] = next((row["public_url"] for row in current_media if row["media_type"] == "video"), "")
        return
    if status == "published":
        raise ValueError("新商品只能引用已完成安全审核的媒体资产")


def resolve_product_variant_media_assets(connection: sqlite3.Connection, user_id: str, product: dict, status: str) -> None:
    """Resolve variant thumbnails through the same private asset workflow."""
    for variant in product.get("variants") or []:
        if not isinstance(variant, dict):
            continue
        asset_ids = variant.get("valueAssetIds")
        if not isinstance(asset_ids, dict):
            continue
        resolved_urls = dict(variant.get("valueImages") or {})
        for value, asset_id in asset_ids.items():
            clean_id = str(asset_id or "").strip()
            if not clean_id:
                continue
            asset = promote_product_media_assets(
                connection, user_id, [clean_id], activate=status == "published", enforce_listing_limits=False
            )[0]
            if asset["media_type"] != "image":
                raise ValueError("Variant media must be an image asset")
            resolved_urls[str(value)] = asset["public_url"]
        variant["valueImages"] = resolved_urls


def generate_product_code(connection: sqlite3.Connection) -> str:
    """Return a unique, human-readable eight-character product code."""
    for _ in range(100):
        code = "".join(secrets.choice(PRODUCT_CODE_ALPHABET) for _ in range(8))
        if not connection.execute("SELECT 1 FROM products WHERE product_code = ?", (code,)).fetchone():
            return code
    raise RuntimeError("无法生成唯一作品编号")


def generate_sku_code(connection: sqlite3.Connection) -> str:
    """Return a globally unique, merchant-readable SKU code."""
    for _ in range(100):
        code = "SKU-" + "".join(secrets.choice(SKU_CODE_ALPHABET) for _ in range(10))
        if not connection.execute(
            "SELECT 1 FROM product_skus WHERE sku_code = ? COLLATE NOCASE", (code,)
        ).fetchone():
            return code
    raise RuntimeError("无法生成唯一 SKU 编号")


def product_sku_codes(connection: sqlite3.Connection, product_id: str, product: dict) -> tuple[list[dict], str | None]:
    """Fill blank SKU codes and reject duplicates before replacing a product's SKUs."""
    skus = product.get("skus") or []
    supplied_skus = skus if skus else [{}]
    codes: list[str] = []
    seen: set[str] = set()
    for sku in supplied_skus:
        code = str(sku.get("code") or "").strip()
        if code:
            if len(code) > 40:
                raise ValueError("SKU 编号最多 40 个字符")
            if re.search(r"[\r\n\t]", code):
                raise ValueError("SKU 编号不能包含换行或制表符")
        else:
            code = generate_sku_code(connection)
        normalized = code.casefold()
        if normalized in seen:
            raise ValueError("SKU 编号在本件作品中不能重复")
        if connection.execute(
            "SELECT 1 FROM product_skus WHERE sku_code = ? COLLATE NOCASE AND product_id <> ?",
            (code, product_id),
        ).fetchone():
            raise ValueError("该 SKU 编号已被使用")
        seen.add(normalized)
        codes.append(code)
    for sku, code in zip(skus, codes):
        sku["code"] = code
    return skus, None if skus else codes[0]


def ensure_product_codes(connection: sqlite3.Connection) -> None:
    missing = connection.execute(
        "SELECT id FROM products WHERE product_code IS NULL OR TRIM(product_code) = ''"
    ).fetchall()
    for row in missing:
        product_id = row["id"] if isinstance(row, sqlite3.Row) else row[0]
        while True:
            code = generate_product_code(connection)
            try:
                connection.execute(
                    "UPDATE products SET product_code = ? WHERE id = ? AND (product_code IS NULL OR TRIM(product_code) = '')",
                    (code, product_id),
                )
                break
            except sqlite3.IntegrityError:
                continue


def product_title_units(value: str) -> int:
    """Count Han characters as 2.5 units and all other characters as one."""
    return sum(
        5 if "\u3400" <= character <= "\u4dbf" or "\u4e00" <= character <= "\u9fff" or "\uf900" <= character <= "\ufaff" else 2
        for character in value.strip()
    )


def truncate_product_title(value: str, maximum_units: int = 250) -> str:
    result = []
    units = 0
    for character in value.strip():
        next_units = 5 if "\u3400" <= character <= "\u4dbf" or "\u4e00" <= character <= "\u9fff" or "\uf900" <= character <= "\ufaff" else 2
        if units + next_units > maximum_units:
            break
        result.append(character)
        units += next_units
    return "".join(result).strip()


def upsert_product(connection: sqlite3.Connection, product_id: str, shop_id: str, product: dict, status: str) -> None:
    connection.row_factory = sqlite3.Row
    title = str(product.get("title") or "未命名作品").strip()
    media_urls = product.get("images") or ([product.get("image")] if product.get("image") else [])
    tags = seo_tags(product)
    buyer_title = str(product.get("buyerTitle") or "").strip()
    buyer_description = str(product.get("buyerDescription") or "").strip()
    buyer_material = str(product.get("buyerMaterial") or "").strip()
    craftsmanship = str(product.get("craftsmanship") or "").strip()
    buyer_tags = buyer_seo_tags(product)
    existing = connection.execute("SELECT product_code FROM products WHERE id = ?", (product_id,)).fetchone()
    if product_title_units(title) > 250:
        raise ValueError("作品名称最多 50 个汉字或 125 个英文字符，符号按 1 个字符计")
    if len(buyer_title) > 140 or len(buyer_description) > 1500 or len(buyer_material) > 300:
        raise ValueError("English listing copy is too long")
    if len(craftsmanship) > 300:
        raise ValueError("制作工艺最多 300 个字")
    if status == "published" and not existing and not craftsmanship:
        raise ValueError("请填写制作工艺")
    content = moderation_text(product, title, tags)
    sensitive_word = next((word for word in SENSITIVE_CONTENT_WORDS if word in content), None)
    if sensitive_word:
        with database() as audit_connection:
            write_moderation_log(audit_connection, product_id, content, "rejected", f"包含敏感词“{sensitive_word}”")
        raise ValueError(f"内容审核未通过：包含敏感词“{sensitive_word}”")
    matched_rule = matched_governance_rule(connection, product_id, product, title, tags, content)
    if matched_rule and matched_rule["action"] == "reject":
        reason = f"命中审核规则“{matched_rule['name']}”"
        write_moderation_log(connection, product_id, content, "rejected", reason)
        raise ValueError(f"内容审核未通过：{reason}")
    # 卖家发布默认上架。命中人工巡查规则仅记录风险线索，不阻断发布；
    # 平台如确认违规，再通过治理处置将作品下架。
    moderation_status = "approved"
    moderation_reason = None
    effective_status = status
    if status == "published":
        validate_product_media(product)
    price = int(round(number(product.get("price")) * 100))
    supplied_currency = str(product.get("currency") or PLATFORM_CURRENCY).upper()
    if supplied_currency != PLATFORM_CURRENCY:
        raise ValueError("平台商品价格仅支持 USD")
    stock = max(0, int(number(product.get("stock"))))
    raw_weight_grams = product.get("weightGrams")
    weight_grams = None if raw_weight_grams is None or str(raw_weight_grams).strip() == "" else int(round(number(raw_weight_grams)))
    if weight_grams is not None and not 1 <= weight_grams <= 100000:
        raise ValueError("商品重量须为 1 至 100000 g 之间的整数")
    dimensions = str(product.get("dimensions") or "").strip() or None
    if dimensions is not None and len(dimensions) > 100:
        raise ValueError("商品尺寸说明最多 100 个字")
    low_stock_threshold = max(0, int(number(product.get("lowStockThreshold", 3))))
    supports_custom = int(bool(product.get("custom")))
    supplied_code = str(product.get("code") or "").strip().upper()
    product_code = supplied_code or (existing["product_code"] if existing and existing["product_code"] else generate_product_code(connection))
    if not re.fullmatch(r"[A-Z0-9]{8}", product_code):
        raise ValueError("作品编号必须为 8 位字母或数字")
    skus, default_sku_code = product_sku_codes(connection, product_id, product)
    connection.execute(
        """
        INSERT INTO products (id, shop_id, product_code, category, title, description, material, craftsmanship, buyer_title, buyer_description, buyer_material, buyer_seo_tags_json, weight_grams, dimensions, price_cents, price_currency, stock, low_stock_threshold, supports_custom, status, published_at, moderation_status, moderation_reason, moderated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CASE WHEN ? = 'published' THEN CURRENT_TIMESTAMP END, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET
          product_code = COALESCE(products.product_code, excluded.product_code),
          category = excluded.category,
          title = excluded.title,
          description = excluded.description,
          material = excluded.material,
          craftsmanship = excluded.craftsmanship,
          buyer_title = excluded.buyer_title,
          buyer_description = excluded.buyer_description,
          buyer_material = excluded.buyer_material,
          buyer_seo_tags_json = excluded.buyer_seo_tags_json,
          weight_grams = excluded.weight_grams,
          dimensions = excluded.dimensions,
          price_cents = excluded.price_cents,
          price_currency = excluded.price_currency,
          stock = excluded.stock,
          low_stock_threshold = excluded.low_stock_threshold,
          supports_custom = excluded.supports_custom,
          status = excluded.status,
          moderation_status = excluded.moderation_status,
          moderation_reason = excluded.moderation_reason,
          moderated_at = CURRENT_TIMESTAMP,
          published_at = CASE WHEN excluded.status = 'published' THEN COALESCE(products.published_at, CURRENT_TIMESTAMP) ELSE products.published_at END,
          updated_at = CURRENT_TIMESTAMP
        """,
        (
            product_id,
            shop_id,
            product_code,
            product.get("category", "陶艺"),
            title,
            product.get("description") or "",
            product.get("material") or "手工制作",
            craftsmanship,
            buyer_title,
            buyer_description,
            buyer_material,
            json.dumps(buyer_tags, ensure_ascii=False),
            weight_grams,
            dimensions,
            price,
            PLATFORM_CURRENCY,
            stock,
            low_stock_threshold,
            supports_custom,
            effective_status,
            effective_status,
            moderation_status,
            moderation_reason,
        ),
    )
    if matched_rule:
        record_governance_rule_hit(connection, matched_rule, product_id, content)
    write_moderation_log(connection, product_id, content, "approved", None)
    connection.execute("DELETE FROM media_asset_links WHERE target_type IN ('product', 'product_variant') AND target_id = ?", (product_id,))
    connection.execute("DELETE FROM product_media WHERE product_id = ?", (product_id,))
    connection.execute("DELETE FROM product_options WHERE product_id = ?", (product_id,))
    connection.execute("DELETE FROM product_skus WHERE product_id = ?", (product_id,))
    connection.execute("DELETE FROM product_seo_tags WHERE product_id = ?", (product_id,))
    connection.executemany(
        "INSERT INTO product_seo_tags (product_id, tag, weight, sort_order) VALUES (?, ?, ?, ?)",
        [(product_id, tag, 1, index) for index, tag in enumerate(tags)],
    )
    connection.executemany(
        "INSERT INTO product_media (id, product_id, media_type, storage_key, public_url, sort_order, is_cover, asset_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        media_rows(product_id, product),
    )
    asset_rows = product.get("_media_assets") or []
    if asset_rows:
        for asset in asset_rows:
            asset_id = asset["asset_id"] if "asset_id" in asset.keys() else asset["id"]
            connection.execute(
                "INSERT INTO media_asset_links (id, asset_id, target_type, target_id) VALUES (?, ?, 'product', ?)",
                (f"asset-link-{secrets.token_urlsafe(10)}", asset_id, product_id),
            )
    else:
        link_media_assets(connection, [*media_urls, product.get("video")], "product", product_id)
    if status == "published":
        record_product_image_fingerprints(connection, product_id, media_urls)
    option_value_ids: dict[tuple[str, str], str] = {}
    for option_index, variant in enumerate(product.get("variants") or []):
        option_id = f"{product_id}-option-{option_index}"
        connection.execute(
            "INSERT INTO product_options (id, product_id, name, sort_order) VALUES (?, ?, ?, ?)",
            (option_id, product_id, variant.get("name") or "规格", option_index),
        )
        images = variant.get("valueImages") or {}
        image_asset_ids = variant.get("valueAssetIds") or {}
        for value_index, value in enumerate(variant.get("values") or []):
            value_id = f"{option_id}-value-{value_index}"
            connection.execute(
                "INSERT INTO product_option_values (id, option_id, value, image_url, asset_id, sort_order) VALUES (?, ?, ?, ?, ?, ?)",
                (value_id, option_id, value, images.get(value), image_asset_ids.get(value), value_index),
            )
            if image_asset_ids.get(value):
                connection.execute(
                    "INSERT INTO media_asset_links (id, asset_id, target_type, target_id) VALUES (?, ?, 'product_variant', ?)",
                    (f"asset-link-{secrets.token_urlsafe(10)}", image_asset_ids[value], product_id),
                )
            option_value_ids[(variant.get("name") or "规格", value)] = value_id
    if skus:
        for sku_index, sku in enumerate(skus):
            option_value_ids_json = json.dumps(
                [
                    option_value_ids[(name, value)]
                    for name, value in (sku.get("optionValues") or {}).items()
                    if (name, value) in option_value_ids
                ],
                ensure_ascii=False,
            )
            connection.execute(
                "INSERT INTO product_skus (id, product_id, sku_code, price_cents, stock, option_value_ids, status) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    f"{product_id}-sku-{sku_index}",
                    product_id,
                    sku["code"],
                    int(round(number(sku.get("price", price / 100)) * 100)),
                    max(0, int(number(sku.get("stock")))),
                    option_value_ids_json,
                    "disabled" if sku.get("status") == "disabled" else "active",
                ),
            )
    else:
        connection.execute(
            "INSERT INTO product_skus (id, product_id, sku_code, price_cents, stock) VALUES (?, ?, ?, ?, ?)",
            (f"{product_id}-default-sku", product_id, default_sku_code, price, stock),
        )
    if skus:
        refresh_product_stock(connection, product_id)


def migrate(payload: dict, authenticated_user_id: str | None = None) -> dict:
    seller = payload.get("seller") or {}
    data = payload.get("data") or {}
    seller_id = authenticated_user_id or seller.get("id")
    seller_name = seller.get("name") or "本地卖家"
    if not seller_id:
        raise ValueError("缺少卖家身份")
    user_id = seller_id if authenticated_user_id else f"legacy-seller-{seller_id}"
    products = [item for item in data.get("products") or [] if item.get("shopId") == 99]
    drafts = data.get("drafts") or []
    shop = data.get("shop") or {}
    with database() as connection:
        if not authenticated_user_id:
            connection.execute(
                "INSERT OR IGNORE INTO users (id, display_name, email, password_hash) VALUES (?, ?, ?, 'legacy-local-account')",
                (user_id, seller_name, f"{seller_id}@legacy.local"),
            )
        connection.execute("INSERT OR IGNORE INTO user_roles (user_id, role) VALUES (?, 'seller')", (user_id,))
        connection.execute(
            "INSERT OR IGNORE INTO seller_profiles (user_id, verification_status) VALUES (?, 'approved')",
            (user_id,),
        )
        existing_shop = connection.execute(
            "SELECT id FROM shops WHERE owner_user_id IN (?, ?) ORDER BY owner_user_id = ? DESC LIMIT 1",
            (user_id, f"legacy-seller-{seller_id}", user_id),
        ).fetchone()
        shop_id = existing_shop[0] if existing_shop else f"shop-{seller_id}"
        if authenticated_user_id and existing_shop:
            connection.execute("UPDATE shops SET owner_user_id = ? WHERE id = ?", (user_id, shop_id))
        connection.execute(
            """
            INSERT INTO shops (id, owner_user_id, name, description, location, banner_url, avatar_url, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              name = excluded.name, description = excluded.description, location = excluded.location,
              banner_url = excluded.banner_url, avatar_url = excluded.avatar_url, status = excluded.status,
              shipping_template_json = ?, coupons_json = ?, updated_at = CURRENT_TIMESTAMP
            """,
            (
                shop_id, user_id, shop.get("name") or f"{seller_name}的手作店", shop.get("description") or "", shop.get("shippingOrigin") or shop.get("location") or "", shop.get("banner"), shop.get("avatar"), shop.get("status") or "active",
                json.dumps(shop.get("shippingTemplate") or {"name": "标准快递", "firstFee": 0, "additionalFee": 0}, ensure_ascii=False),
                json.dumps(shop.get("coupons") or [], ensure_ascii=False),
            ),
        )
        product_ids = {str(product.get("catalogId") or f"legacy-product-{seller_id}-{product['id']}") for product in products}
        draft_ids = {str(draft.get("catalogId") or f"legacy-draft-{seller_id}-{draft['id']}") for draft in drafts}
        existing_ids = connection.execute(
            "SELECT id FROM products WHERE shop_id = ?", (shop_id,),
        ).fetchall()
        for (existing_id,) in existing_ids:
            if existing_id not in product_ids and existing_id not in draft_ids:
                connection.execute("UPDATE products SET status = 'archived', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (existing_id,))
        for product in products:
            status = "unlisted" if product.get("listed") is False else "published"
            upsert_product(connection, str(product.get("catalogId") or f"legacy-product-{seller_id}-{product['id']}"), shop_id, product, status)
        for draft in drafts:
            upsert_product(connection, str(draft.get("catalogId") or f"legacy-draft-{seller_id}-{draft['id']}"), shop_id, draft, "draft")
        connection.execute(
            """
            INSERT INTO legacy_migrations (seller_user_id, migrated_products, migrated_drafts, migrated_at)
            VALUES (?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(seller_user_id) DO UPDATE SET
              migrated_products = excluded.migrated_products,
              migrated_drafts = excluded.migrated_drafts,
              migrated_at = CURRENT_TIMESTAMP
            """,
            (user_id, len(products), len(drafts)),
        )
        settings_row = connection.execute("SELECT settings_json FROM shops WHERE id = ?", (shop_id,)).fetchone()
        try:
            settings = json.loads(settings_row[0] or "{}") if settings_row else {}
        except json.JSONDecodeError:
            settings = {}
        if not isinstance(settings, dict):
            settings = {}
        settings["featuredProductIds"] = featured_product_ids_for_shop(connection, shop_id, shop.get("featuredProductIds"))
        if isinstance(shop.get("brandSite"), dict):
            settings["brandSite"] = shop["brandSite"]
        if isinstance(shop.get("returnPolicy"), dict):
            settings["returnPolicy"] = shop["returnPolicy"]
        connection.execute("UPDATE shops SET settings_json = ? WHERE id = ?", (json.dumps(settings, ensure_ascii=False), shop_id))
    return {"products": len(products), "drafts": len(drafts)}


def catalog(shop_ids: tuple[str, ...] | None = None, statuses: tuple[str, ...] = ("published",)) -> list[dict]:
    with database() as connection:
        connection.row_factory = sqlite3.Row
        ensure_product_codes(connection)
        shop_filter = ""
        params: tuple[object, ...] = tuple(statuses)
        if shop_ids:
            shop_filter = f" AND products.shop_id IN ({','.join('?' for _ in shop_ids)})"
            params += tuple(shop_ids)
        products = connection.execute(
            f"""
            SELECT products.*, shops.name AS shop_name, shops.location AS shop_location,
                   shops.shipping_template_json AS shop_shipping_template_json
            FROM products JOIN shops ON shops.id = products.shop_id
            WHERE products.status IN ({','.join('?' for _ in statuses)}){shop_filter}
            ORDER BY products.published_at DESC, products.created_at DESC
            """,
            params,
        ).fetchall()
        result = []
        for product in products:
            legacy_id = catalog_product_number(product["id"])
            media = connection.execute(
                "SELECT media_type, public_url, asset_id FROM product_media WHERE product_id = ? ORDER BY sort_order",
                (product["id"],),
            ).fetchall()
            images = [item["public_url"] for item in media if item["media_type"] == "image"]
            video = next((item["public_url"] for item in media if item["media_type"] == "video"), None)
            options = connection.execute(
                "SELECT id, name FROM product_options WHERE product_id = ? ORDER BY sort_order",
                (product["id"],),
            ).fetchall()
            variants = []
            value_lookup = {}
            for option in options:
                values = connection.execute(
                    "SELECT id, value, image_url, asset_id FROM product_option_values WHERE option_id = ? ORDER BY sort_order",
                    (option["id"],),
                ).fetchall()
                variants.append(
                    {
                        "name": option["name"],
                        "values": [value["value"] for value in values],
                        "valueImages": {value["value"]: value["image_url"] for value in values if value["image_url"]},
                        "valueAssetIds": {value["value"]: value["asset_id"] for value in values if value["asset_id"]},
                    }
                )
                value_lookup.update({value["id"]: (option["name"], value["value"]) for value in values})
            skus = []
            for sku in connection.execute(
                "SELECT id, sku_code, price_cents, stock, option_value_ids, status FROM product_skus WHERE product_id = ?",
                (product["id"],),
            ):
                option_values = {
                    value_lookup[value_id][0]: value_lookup[value_id][1]
                    for value_id in json.loads(sku["option_value_ids"])
                    if value_id in value_lookup
                }
                skus.append({
                    "id": sku["id"], "code": sku["sku_code"] or "", "price": sku["price_cents"] / 100,
                    "currency": product["price_currency"],
                    "optionValues": option_values, "stock": sku["stock"], "status": sku["status"],
                })
            seo_tags = [
                row[0]
                for row in connection.execute(
                    "SELECT tag FROM product_seo_tags WHERE product_id = ? ORDER BY sort_order",
                    (product["id"],),
                )
            ]
            review_summary = connection.execute(
                """
                SELECT COUNT(*) AS review_count, AVG(reviews.rating) AS average_rating
                FROM reviews JOIN order_items ON order_items.id = reviews.order_item_id
                WHERE order_items.product_id = ?
                """,
                (product["id"],),
            ).fetchone()
            try:
                shipping_template = normalize_shipping_template(
                    json.loads(product["shop_shipping_template_json"] or "{}")
                )
            except (json.JSONDecodeError, TypeError):
                shipping_template = normalize_shipping_template({})
            result.append(
                {
                    "id": legacy_id,
                    "catalogId": product["id"],
                    "code": product["product_code"] or "",
                    "title": product["title"],
                    "category": product["category"],
                    "price": product["price_cents"] / 100,
                    "currency": product["price_currency"],
                    "image": images[0] if images else "",
                    "images": images or None,
                    "video": video,
                    "mediaAssetIds": [item["asset_id"] for item in media if item["asset_id"]],
                    "imageAssetIds": [item["asset_id"] for item in media if item["media_type"] == "image" and item["asset_id"]],
                    "videoAssetId": next((item["asset_id"] for item in media if item["media_type"] == "video" and item["asset_id"]), None),
                    "shopId": 99,
                    "analyticsShopId": product["shop_id"],
                    "shop": product["shop_name"],
                    "shippingOrigin": product["shop_location"] or "",
                    "shippingTemplate": shipping_template,
                    "rating": round(float(review_summary["average_rating"] or 5), 1),
                    "reviews": review_summary["review_count"],
                    "stock": product["stock"],
                    "weightGrams": product["weight_grams"],
                    "dimensions": product["dimensions"],
                    "lowStockThreshold": product["low_stock_threshold"],
                    "tags": ["原创手作"],
                    "seoTags": seo_tags,
                    "publishStatus": product["status"],
                    "listed": product["status"] == "published",
                    "reviewStatus": product["moderation_status"],
                    "moderationReason": product["moderation_reason"],
                    "custom": bool(product["supports_custom"]),
                    "description": product["description"],
                    "material": product["material"],
                    "craftsmanship": product["craftsmanship"] or "",
                    "buyerTitle": product["buyer_title"] or "",
                    "buyerDescription": product["buyer_description"] or "",
                    "buyerMaterial": product["buyer_material"] or "",
                    "buyerSeoTags": json.loads(product["buyer_seo_tags_json"] or "[]"),
                    "variants": variants or None,
                    "skus": skus or None,
                }
            )
        return result


def account_for_user(user_id: str) -> dict | None:
    with database() as connection:
        connection.row_factory = sqlite3.Row
        user = connection.execute(
            "SELECT id, display_name, phone, email, phone_verified_at, email_verified_at FROM users WHERE id = ? AND status = 'active'",
            (user_id,),
        ).fetchone()
        if not user:
            return None
        roles = [row[0] for row in connection.execute("SELECT role FROM user_roles WHERE user_id = ?", (user_id,))]
        return {
            "id": user["id"],
            "name": user["display_name"],
            "phone": user["phone"],
            "email": user["email"],
            "phoneVerified": bool(user["phone_verified_at"]),
            "emailVerified": bool(user["email_verified_at"]),
            "password": "",
            "role": "admin" if is_admin(connection, user_id) else ("seller" if "seller" in roles else "buyer"),
        }


def profile_for_user(connection: sqlite3.Connection, user_id: str) -> dict | None:
    connection.row_factory = sqlite3.Row
    user = connection.execute(
        """
        SELECT users.display_name, users.phone, users.email, users.phone_verified_at,
               users.email_verified_at, COALESCE(user_profiles.bio, '') AS bio
        FROM users
        LEFT JOIN user_profiles ON user_profiles.user_id = users.id
        WHERE users.id = ? AND users.status = 'active'
        """,
        (user_id,),
    ).fetchone()
    if not user:
        return None
    return {
        "name": user["display_name"],
        "bio": user["bio"],
        "phone": user["phone"],
        "email": user["email"],
        "phoneVerified": bool(user["phone_verified_at"]),
        "emailVerified": bool(user["email_verified_at"]),
    }


def session_token(handler: BaseHTTPRequestHandler) -> str | None:
    cookies = handler.headers.get("Cookie", "")
    return next((part.strip().split("=", 1)[1] for part in cookies.split(";") if part.strip().startswith("handicrafts_session=")), None)


def csrf_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def rotate_session_csrf_token(handler: BaseHTTPRequestHandler) -> str | None:
    """Issue a fresh CSRF token for the active cookie session."""
    token = session_token(handler)
    if not token:
        return None
    csrf_token = secrets.token_urlsafe(32)
    with database() as connection:
        updated = connection.execute(
            """
            UPDATE web_sessions
            SET csrf_token_hash = ?
            WHERE token = ? AND expires_at > CURRENT_TIMESTAMP
              AND EXISTS (SELECT 1 FROM users WHERE users.id = web_sessions.user_id AND users.status = 'active')
            """,
            (csrf_token_hash(csrf_token), token),
        ).rowcount
    return csrf_token if updated else None


def valid_session_csrf_token(handler: BaseHTTPRequestHandler) -> bool:
    """Check the CSRF header against the active cookie session, if any."""
    token = session_token(handler)
    if not token:
        return True
    supplied = handler.headers.get("X-CSRF-Token", "")
    if not supplied:
        return False
    with database() as connection:
        row = connection.execute(
            """
            SELECT web_sessions.csrf_token_hash
            FROM web_sessions JOIN users ON users.id = web_sessions.user_id
            WHERE web_sessions.token = ? AND web_sessions.expires_at > CURRENT_TIMESTAMP
              AND users.status = 'active'
            """,
            (token,),
        ).fetchone()
    # A stale cookie is rejected later by the endpoint's normal authentication
    # check; it is not a live session that needs CSRF coverage.
    if not row:
        return True
    expected = str(row[0] or "")
    return bool(expected) and hmac.compare_digest(expected, csrf_token_hash(supplied))


def session_user(handler: BaseHTTPRequestHandler) -> str | None:
    token = session_token(handler)
    if not token:
        return None
    with database() as connection:
        row = connection.execute(
            "SELECT web_sessions.user_id FROM web_sessions JOIN users ON users.id = web_sessions.user_id WHERE web_sessions.token = ? AND web_sessions.expires_at > CURRENT_TIMESTAMP AND users.status = 'active'",
            (token,),
        ).fetchone()
        if row:
            connection.execute("UPDATE web_sessions SET last_seen_at = CURRENT_TIMESTAMP WHERE token = ?", (token,))
        return row[0] if row else None


def create_session(user_id: str, handler: BaseHTTPRequestHandler | None = None) -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    csrf_token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
    user_agent = handler.headers.get("User-Agent", "")[:300] if handler else ""
    ip_address = handler.client_address[0] if handler else ""
    with database() as connection:
        connection.execute(
            "INSERT INTO web_sessions (token, id, user_id, expires_at, last_seen_at, user_agent, ip_address, csrf_token_hash) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?)",
            (token, f"session-{secrets.token_urlsafe(10)}", user_id, expires, user_agent, ip_address, csrf_token_hash(csrf_token)),
        )
    return token, csrf_token


def write_login_audit(connection: sqlite3.Connection, identifier: str, success: bool, handler: BaseHTTPRequestHandler, user_id: str | None = None, reason: str | None = None) -> None:
    connection.execute(
        "INSERT INTO login_audit_events (id, user_id, identifier, success, reason, ip_address, user_agent) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (f"login-{secrets.token_urlsafe(10)}", user_id, identifier[:160], int(success), reason, handler.client_address[0], handler.headers.get("User-Agent", "")[:300]),
    )


def shop_visitors(shop_id: str) -> int:
    with database() as connection:
        row = connection.execute(
            "SELECT visitor_count FROM shop_analytics WHERE shop_id = ?", (shop_id,)
        ).fetchone()
        return int(row[0]) if row else 0


def seller_analytics(user_id: str, days: int, start_date: str | None = None, end_date: str | None = None) -> dict:
    days = max(1, min(days, 365))
    today = datetime.now().date()
    if start_date or end_date:
        if not start_date or not end_date:
            raise ValueError("请选择完整的开始和结束日期")
        try:
            range_start = datetime.strptime(start_date, "%Y-%m-%d").date()
            range_end = datetime.strptime(end_date, "%Y-%m-%d").date()
        except ValueError as error:
            raise ValueError("日期格式无效") from error
        if range_start > range_end:
            raise ValueError("开始日期不能晚于结束日期")
        if range_end > today:
            raise ValueError("结束日期不能晚于当天")
        days = (range_end - range_start).days + 1
        if days > 365:
            raise ValueError("最多可查看 365 天的数据")
    else:
        range_end = today
        range_start = today - timedelta(days=days - 1)
    start_at = f"{range_start.isoformat()} 00:00:00"
    end_at = f"{(range_end + timedelta(days=1)).isoformat()} 00:00:00"
    with database() as connection:
        connection.row_factory = sqlite3.Row
        shop_ids = seller_accessible_shop_ids(connection, user_id, "settings")
        if not shop_ids:
            return {"days": days, "startDate": range_start.isoformat(), "endDate": range_end.isoformat(), "revenue": 0, "orders": 0, "visitors": 0, "conversionRate": 0, "pendingFulfillment": 0, "refundRate": 0, "lowStock": 0, "hotProducts": []}
        marks = ",".join("?" for _ in shop_ids)
        scope = tuple(shop_ids)
        order_stats = connection.execute(f"SELECT COUNT(*) AS orders, COALESCE(SUM(paid_amount_cents), 0) AS revenue, SUM(CASE WHEN status = 'refunded' THEN 1 ELSE 0 END) AS refunded, SUM(CASE WHEN status = 'pending_fulfillment' THEN 1 ELSE 0 END) AS pending FROM orders WHERE shop_id IN ({marks}) AND placed_at >= ? AND placed_at < ?", (*scope, start_at, end_at)).fetchone()
        visitors = connection.execute(f"SELECT COUNT(DISTINCT visitor_key) FROM shop_visit_events WHERE shop_id IN ({marks}) AND visited_on >= ? AND visited_on <= ?", (*scope, range_start.isoformat(), range_end.isoformat())).fetchone()[0]
        low_stock = connection.execute(f"SELECT COUNT(*) FROM products WHERE shop_id IN ({marks}) AND status = 'published' AND stock BETWEEN 1 AND low_stock_threshold", scope).fetchone()[0]
        hot = connection.execute(f"SELECT products.id, products.title, SUM(order_items.quantity) AS sales FROM order_items JOIN orders ON orders.id = order_items.order_id JOIN products ON products.id = order_items.product_id WHERE orders.shop_id IN ({marks}) AND orders.status NOT IN ('cancelled', 'refunded') AND orders.placed_at >= ? AND orders.placed_at < ? GROUP BY products.id ORDER BY sales DESC LIMIT 5", (*scope, start_at, end_at)).fetchall()
        count = int(order_stats["orders"] or 0)
        return {"days": days, "startDate": range_start.isoformat(), "endDate": range_end.isoformat(), "revenue": order_stats["revenue"] / 100, "orders": count, "visitors": visitors, "conversionRate": round(count / visitors * 100, 2) if visitors else 0, "pendingFulfillment": int(order_stats["pending"] or 0), "refundRate": round(int(order_stats["refunded"] or 0) / count * 100, 2) if count else 0, "lowStock": low_stock, "hotProducts": [{"id": row["id"], "title": row["title"], "sales": row["sales"]} for row in hot]}


def platform_analytics(days: int) -> dict:
    days = max(1, min(days, 365))
    period_start = "start of day" if days == 1 else f"-{days} days"
    daily_start = "start of day" if days == 1 else f"-{days - 1} days"
    with database() as connection:
        connection.row_factory = sqlite3.Row
        orders = connection.execute("SELECT COALESCE(SUM(paid_amount_cents), 0) AS revenue, COUNT(*) AS total FROM orders WHERE paid_at >= datetime('now', ?) AND status NOT IN ('cancelled', 'refunded', 'pending_payment')", (period_start,)).fetchone()
        statuses = {row["status"]: row["count"] for row in connection.execute("SELECT status, COUNT(*) AS count FROM orders WHERE placed_at >= datetime('now', ?) GROUP BY status", (period_start,))}
        active_shops = connection.execute("SELECT COUNT(DISTINCT shop_id) FROM orders WHERE paid_at >= datetime('now', ?) AND status NOT IN ('cancelled', 'refunded', 'pending_payment')", (period_start,)).fetchone()[0]
        pending_reports = connection.execute("SELECT COUNT(*) FROM content_reports WHERE status = 'pending'").fetchone()[0]
        pending_appeals = connection.execute("SELECT COUNT(*) FROM governance_appeals WHERE status = 'pending'").fetchone()[0]
        timing = connection.execute("SELECT AVG((julianday(handled_at) - julianday(created_at)) * 24) FROM governance_appeals WHERE status IN ('approved', 'rejected') AND handled_at IS NOT NULL AND created_at >= datetime('now', ?)", (period_start,)).fetchone()[0]
        daily_rows = connection.execute("SELECT date(paid_at) AS day, COALESCE(SUM(paid_amount_cents), 0) AS revenue, COUNT(*) AS orders FROM orders WHERE paid_at >= datetime('now', ?) AND status NOT IN ('cancelled', 'refunded', 'pending_payment') GROUP BY date(paid_at)", (daily_start,)).fetchall()
        daily_lookup = {row["day"]: {"revenue": row["revenue"] / 100, "orders": row["orders"]} for row in daily_rows}
        daily = []
        for offset in range(days - 1, -1, -1):
            day = (datetime.now().date() - timedelta(days=offset)).isoformat()
            daily.append({"date": day, **daily_lookup.get(day, {"revenue": 0, "orders": 0})})
        categories = connection.execute("SELECT products.category, COUNT(order_items.id) AS sales, COALESCE(SUM(order_items.subtotal_cents), 0) AS revenue FROM order_items JOIN orders ON orders.id = order_items.order_id JOIN products ON products.id = order_items.product_id WHERE orders.paid_at >= datetime('now', ?) AND orders.status NOT IN ('cancelled', 'refunded', 'pending_payment') GROUP BY products.category ORDER BY revenue DESC LIMIT 6", (period_start,)).fetchall()
        shops = connection.execute("SELECT shops.name, COUNT(orders.id) AS orders, COALESCE(SUM(orders.paid_amount_cents), 0) AS revenue FROM orders JOIN shops ON shops.id = orders.shop_id WHERE orders.paid_at >= datetime('now', ?) AND orders.status NOT IN ('cancelled', 'refunded', 'pending_payment') GROUP BY shops.id ORDER BY revenue DESC LIMIT 5", (period_start,)).fetchall()
        active_campaigns = connection.execute("SELECT COUNT(*) FROM platform_campaigns WHERE status = 'active' AND (starts_at IS NULL OR starts_at <= CURRENT_TIMESTAMP) AND (ends_at IS NULL OR ends_at > CURRENT_TIMESTAMP)").fetchone()[0]
        event_scope = (period_start,)
        funnel = connection.execute(
            """
            WITH actors AS (
              SELECT COALESCE(user_id, visitor_key) AS actor,
                MIN(CASE WHEN event_type = 'product_view' THEN created_at END) AS view_at,
                MIN(CASE WHEN event_type = 'add_cart' THEN created_at END) AS cart_at,
                MIN(CASE WHEN event_type = 'checkout_started' THEN created_at END) AS checkout_at,
                MIN(CASE WHEN event_type = 'order_paid' THEN created_at END) AS paid_at
              FROM analytics_events
              WHERE created_at >= datetime('now', ?) AND COALESCE(user_id, visitor_key) IS NOT NULL
              GROUP BY COALESCE(user_id, visitor_key)
            )
            SELECT COUNT(*) AS visitors,
              SUM(CASE WHEN view_at IS NOT NULL THEN 1 ELSE 0 END) AS views,
              SUM(CASE WHEN view_at IS NOT NULL AND cart_at >= view_at THEN 1 ELSE 0 END) AS carts,
              SUM(CASE WHEN view_at IS NOT NULL AND cart_at >= view_at AND checkout_at >= cart_at THEN 1 ELSE 0 END) AS checkouts,
              SUM(CASE WHEN view_at IS NOT NULL AND cart_at >= view_at AND checkout_at >= cart_at AND paid_at >= checkout_at THEN 1 ELSE 0 END) AS paid_buyers
            FROM actors
            """,
            event_scope,
        ).fetchone()
        viewers, carts, checkouts, paid_buyers = (int(funnel["views"] or 0), int(funnel["carts"] or 0), int(funnel["checkouts"] or 0), int(funnel["paid_buyers"] or 0))
        channel_events = {row["channel"]: row for row in connection.execute("SELECT channel, COUNT(DISTINCT COALESCE(user_id, visitor_key)) AS visitors, COUNT(DISTINCT CASE WHEN event_type = 'add_cart' THEN COALESCE(user_id, visitor_key) END) AS carts, COUNT(DISTINCT CASE WHEN event_type = 'checkout_started' THEN COALESCE(user_id, visitor_key) END) AS checkouts FROM analytics_events WHERE created_at >= datetime('now', ?) GROUP BY channel", event_scope)}
        channel_orders = {row["attribution_channel"]: row for row in connection.execute("SELECT attribution_channel, COUNT(*) AS orders, COALESCE(SUM(paid_amount_cents), 0) AS revenue FROM orders WHERE paid_at >= datetime('now', ?) AND status NOT IN ('cancelled', 'refunded', 'pending_payment') GROUP BY attribution_channel", event_scope)}
        repeat_stats = connection.execute("SELECT COUNT(DISTINCT current_orders.buyer_user_id) AS buyers, COUNT(*) AS orders, COALESCE(SUM(current_orders.paid_amount_cents), 0) AS revenue FROM orders AS current_orders WHERE current_orders.paid_at >= datetime('now', ?) AND current_orders.status NOT IN ('cancelled', 'refunded', 'pending_payment') AND EXISTS (SELECT 1 FROM orders AS prior_orders WHERE prior_orders.buyer_user_id = current_orders.buyer_user_id AND prior_orders.status NOT IN ('cancelled', 'refunded', 'pending_payment') AND (prior_orders.paid_at < current_orders.paid_at OR (prior_orders.paid_at = current_orders.paid_at AND prior_orders.id < current_orders.id)))", event_scope).fetchone()
        attribution = []
        for channel in set(channel_events) | set(channel_orders):
            events, paid = channel_events.get(channel), channel_orders.get(channel)
            visitors = int(events["visitors"] or 0) if events else 0
            channel_carts = int(events["carts"] or 0) if events else 0
            channel_checkouts = int(events["checkouts"] or 0) if events else 0
            paid_orders = int(paid["orders"] or 0) if paid else 0
            attribution.append({"channel": channel, "visitors": visitors, "addCarts": channel_carts, "checkouts": channel_checkouts, "paidOrders": paid_orders, "revenue": (paid["revenue"] or 0) / 100 if paid else 0, "visitorToCartRate": round(channel_carts / visitors * 100, 2) if visitors else 0, "checkoutToPaidRate": round(paid_orders / channel_checkouts * 100, 2) if channel_checkouts else 0})
        attribution.sort(key=lambda item: (item["revenue"], item["visitors"]), reverse=True)
        paid_stats = connection.execute("SELECT COUNT(*) AS orders, COALESCE(SUM(paid_amount_cents), 0) AS revenue, COALESCE(SUM(item_amount_cents), 0) AS items FROM orders WHERE paid_at >= datetime('now', ?) AND status NOT IN ('cancelled', 'refunded', 'pending_payment')", event_scope).fetchone()
        refunds = connection.execute("SELECT COUNT(*) AS count, COALESCE(SUM(paid_amount_cents), 0) AS amount FROM orders WHERE updated_at >= datetime('now', ?) AND status = 'refunded'", event_scope).fetchone()
        after_sale_count = connection.execute("SELECT COUNT(*) FROM after_sale_requests WHERE created_at >= datetime('now', ?)", event_scope).fetchone()[0]
        fulfillment = connection.execute("SELECT AVG((julianday(shipments.shipped_at) - julianday(orders.paid_at)) * 24) FROM shipments JOIN orders ON orders.id = shipments.order_id WHERE orders.paid_at >= datetime('now', ?) AND orders.paid_at IS NOT NULL", event_scope).fetchone()[0]
        new_customers = connection.execute("SELECT COUNT(*) FROM (SELECT buyer_user_id FROM orders WHERE status NOT IN ('cancelled', 'refunded', 'pending_payment') GROUP BY buyer_user_id HAVING MIN(paid_at) >= datetime('now', ?))", event_scope).fetchone()[0]
        product_views = {row["product_id"]: row["views"] for row in connection.execute("SELECT product_id, COUNT(DISTINCT COALESCE(user_id, visitor_key)) AS views FROM analytics_events WHERE event_type = 'product_view' AND product_id IS NOT NULL AND created_at >= datetime('now', ?) GROUP BY product_id", event_scope)}
        products = connection.execute(
            """
            SELECT products.id, products.title,
              COALESCE(sales.sales, 0) AS sales,
              COALESCE(sales.revenue, 0) AS revenue,
              COALESCE(views.views, 0) AS views
            FROM products
            LEFT JOIN (
              SELECT order_items.product_id, SUM(order_items.quantity) AS sales,
                SUM(order_items.subtotal_cents) AS revenue
              FROM order_items JOIN orders ON orders.id = order_items.order_id
              WHERE orders.paid_at >= datetime('now', ?)
                AND orders.status NOT IN ('cancelled', 'refunded', 'pending_payment')
              GROUP BY order_items.product_id
            ) AS sales ON sales.product_id = products.id
            LEFT JOIN (
              SELECT product_id, COUNT(DISTINCT COALESCE(user_id, visitor_key)) AS views
              FROM analytics_events
              WHERE event_type = 'product_view' AND product_id IS NOT NULL
                AND created_at >= datetime('now', ?)
              GROUP BY product_id
            ) AS views ON views.product_id = products.id
            ORDER BY sales.sales DESC, views.views DESC, sales.revenue DESC, products.created_at DESC
            LIMIT 6
            """,
            (period_start, period_start),
        ).fetchall()
        product_performance = [{"id": row["id"], "title": row["title"], "views": int(product_views.get(row["id"], 0)), "sales": int(row["sales"]), "revenue": row["revenue"] / 100, "conversionRate": round(int(row["sales"]) / product_views[row["id"]] * 100, 2) if product_views.get(row["id"]) else 0} for row in products]
        paid_order_count = int(paid_stats["orders"] or 0)
        repeat_buyers = int(repeat_stats["buyers"] or 0)
        return {"days": days, "revenue": orders["revenue"] / 100, "orders": orders["total"], "activeShops": active_shops, "orderStatuses": statuses, "pendingReports": pending_reports, "pendingAppeals": pending_appeals, "appealHours": round(float(timing or 0), 1), "daily": daily, "categories": [{"name": row["category"], "sales": row["sales"], "revenue": row["revenue"] / 100} for row in categories], "topShops": [{"name": row["name"], "orders": row["orders"], "revenue": row["revenue"] / 100} for row in shops], "activeCampaigns": active_campaigns, "campaignPerformance": campaign_performance(connection, days), "funnel": {"visitors": int(funnel["visitors"] or 0), "views": viewers, "addCarts": carts, "checkouts": checkouts, "paidBuyers": paid_buyers, "viewToCartRate": round(carts / viewers * 100, 2) if viewers else 0, "cartToCheckoutRate": round(checkouts / carts * 100, 2) if carts else 0, "checkoutToPaidRate": round(paid_buyers / checkouts * 100, 2) if checkouts else 0, "cartDropOff": max(0, viewers - carts), "checkoutDropOff": max(0, carts - checkouts), "paymentDropOff": max(0, checkouts - paid_buyers)}, "channels": attribution[:12], "repeatCustomers": repeat_buyers, "repeatRate": round(repeat_buyers / paid_buyers * 100, 2) if paid_buyers else 0, "quality": {"paidOrders": paid_order_count, "averageOrderValue": round(paid_stats["revenue"] / paid_order_count / 100, 2) if paid_order_count else 0, "averageItemValue": round(paid_stats["revenue"] / paid_stats["items"] / 100, 2) if paid_stats["items"] else 0, "refundOrders": int(refunds["count"]), "refundAmount": refunds["amount"] / 100, "refundRate": round(int(refunds["count"]) / paid_order_count * 100, 2) if paid_order_count else 0, "afterSaleRate": round(int(after_sale_count) / paid_order_count * 100, 2) if paid_order_count else 0, "fulfillmentHours": round(float(fulfillment or 0), 1)}, "customers": {"new": int(new_customers), "repeat": repeat_buyers, "repeatOrders": int(repeat_stats["orders"] or 0), "repeatRevenue": round((repeat_stats["revenue"] or 0) / 100, 2), "repeatRate": round(repeat_buyers / paid_buyers * 100, 2) if paid_buyers else 0}, "productPerformance": product_performance}


def analytics_export_sections(analytics: dict) -> list[dict]:
    return [
        {"name": "日交易趋势", "headers": ["日期", "交易额", "订单数"], "rows": [[item["date"], item["revenue"], item["orders"]] for item in analytics["daily"]]},
        {"name": "渠道归因", "headers": ["渠道", "访客", "加购", "结算", "支付订单", "交易额", "访客加购率", "结算支付率"], "rows": [[item["channel"], item["visitors"], item["addCarts"], item["checkouts"], item["paidOrders"], item["revenue"], f"{item['visitorToCartRate']}%", f"{item['checkoutToPaidRate']}%"] for item in analytics["channels"]]},
        {"name": "转化漏斗", "headers": ["阶段", "人数", "阶段转化率", "流失人数"], "rows": [["浏览作品", analytics["funnel"]["views"], "-", 0], ["加入购物车", analytics["funnel"]["addCarts"], f"{analytics['funnel']['viewToCartRate']}%", analytics["funnel"]["cartDropOff"]], ["进入结算", analytics["funnel"]["checkouts"], f"{analytics['funnel']['cartToCheckoutRate']}%", analytics["funnel"]["checkoutDropOff"]], ["完成支付", analytics["funnel"]["paidBuyers"], f"{analytics['funnel']['checkoutToPaidRate']}%", analytics["funnel"]["paymentDropOff"]]]},
        {"name": "复购分析", "headers": ["新客", "复购客", "复购订单", "复购交易额", "复购率"], "rows": [[analytics["customers"]["new"], analytics["customers"]["repeat"], analytics["customers"]["repeatOrders"], analytics["customers"]["repeatRevenue"], f"{analytics['customers']['repeatRate']}%"]]},
        {"name": "活动 ROI", "headers": ["活动", "状态", "领取量", "核销订单", "领取核销率", "优惠成本", "归因交易额", "归因 ROI", "归因客单价"], "rows": [[item["name"], item["status"], item["claimedQuantity"], item["attributedOrders"], f"{item['redemptionRate']}%", item["spent"], item["attributedRevenue"], "-" if item["roi"] is None else f"{item['roi']}x", item["averageOrderValue"]] for item in analytics["campaignPerformance"]]},
    ]


def record_shop_visit(shop_id: str, visitor_key: str) -> int:
    if not visitor_key:
        raise ValueError("Missing visitor key")
    with database() as connection:
        inserted = connection.execute(
            "INSERT OR IGNORE INTO shop_visit_events (shop_id, visitor_key) VALUES (?, ?)",
            (shop_id, visitor_key),
        ).rowcount
        if inserted:
            connection.execute(
                """
                INSERT INTO shop_analytics (shop_id, visitor_count, updated_at) VALUES (?, 1, CURRENT_TIMESTAMP)
                ON CONFLICT(shop_id) DO UPDATE SET
                  visitor_count = shop_analytics.visitor_count + 1,
                  updated_at = CURRENT_TIMESTAMP
                """,
                (shop_id,),
            )
        row = connection.execute(
            "SELECT visitor_count FROM shop_analytics WHERE shop_id = ?", (shop_id,)
        ).fetchone()
        return int(row[0]) if row else 0


def analytics_channel(value: object) -> str:
    channel = re.sub(r"[^a-zA-Z0-9_-]", "", str(value or "direct").lower())[:40]
    return channel or "direct"


ANALYTICS_EVENT_TYPES = {
    "product_view", "add_cart", "checkout_started", "order_paid",
    "product_impression", "product_click", "favorite_added",
}
ANALYTICS_PRODUCT_EVENT_TYPES = {"product_view", "product_impression", "product_click", "favorite_added"}
MAX_ANALYTICS_EVENT_BATCH = 50


def analytics_placement(value: object) -> str:
    placement = str(value or "unknown").strip().lower()
    if not re.fullmatch(r"[a-z0-9_-]{1,64}", placement):
        raise ValueError("Invalid analytics placement")
    return placement


def analytics_visitor_key(value: object, required: bool = False) -> str | None:
    visitor_key = str(value or "").strip()
    if not visitor_key:
        if required:
            raise ValueError("Missing visitor key")
        return None
    if not re.fullmatch(r"[A-Za-z0-9_.-]{6,128}", visitor_key):
        raise ValueError("Invalid visitor key")
    return visitor_key


def analytics_event_id(value: object) -> str:
    event_id = str(value or "").strip()
    if event_id:
        if not re.fullmatch(r"[A-Za-z0-9_.-]{6,128}", event_id):
            raise ValueError("Invalid analytics event id")
        return event_id
    return f"analytics-{secrets.token_urlsafe(16)}"


def record_analytics_event(connection: sqlite3.Connection, event_type: str, visitor_key: str | None = None, user_id: str | None = None, shop_id: str | None = None, product_id: str | None = None, campaign_id: str | None = None, channel: object = "direct", placement: object = "unknown", event_id: object = None) -> bool:
    if event_type not in ANALYTICS_EVENT_TYPES:
        raise ValueError("Invalid analytics event")
    inserted = connection.execute(
        "INSERT OR IGNORE INTO analytics_events (id, event_type, visitor_key, user_id, shop_id, product_id, campaign_id, channel, placement) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (analytics_event_id(event_id), event_type, analytics_visitor_key(visitor_key), user_id, shop_id, product_id, campaign_id, analytics_channel(channel), analytics_placement(placement)),
    ).rowcount
    return bool(inserted)


def record_public_analytics_events(connection: sqlite3.Connection, events: object, user_id: str | None = None) -> tuple[int, int]:
    if not isinstance(events, list) or not events or len(events) > MAX_ANALYTICS_EVENT_BATCH:
        raise ValueError("Invalid analytics event batch")
    accepted = duplicates = 0
    for event in events:
        if not isinstance(event, dict):
            raise ValueError("Invalid analytics event")
        event_type = str(event.get("type") or event.get("eventType") or "")
        if event_type not in ANALYTICS_PRODUCT_EVENT_TYPES:
            raise ValueError("Invalid analytics event")
        # Favorites are sourced from the authenticated favorite action below;
        # accepting them here would allow clients to fabricate favorite signals.
        if event_type == "favorite_added":
            raise ValueError("Favorite events are server recorded")
        product_id = str(event.get("productId") or "").strip()
        if not product_id or len(product_id) > 128:
            raise ValueError("Invalid product")
        visitor_key = analytics_visitor_key(event.get("visitorKey"), required=not user_id)
        product = connection.execute(
            "SELECT shop_id FROM products WHERE id = ? AND status = 'published'", (product_id,)
        ).fetchone()
        if not product:
            raise ValueError("Product not found")
        if record_analytics_event(
            connection, event_type, visitor_key=visitor_key, user_id=user_id,
            shop_id=product[0], product_id=product_id, channel=event.get("channel"),
            placement=event.get("placement") or "unknown", event_id=event.get("eventId"),
        ):
            accepted += 1
        else:
            duplicates += 1
    return accepted, duplicates


def _business_metric_period(connection: sqlite3.Connection, shop_ids: list[str], start_at: str, end_at: str) -> dict:
    marks = ",".join("?" for _ in shop_ids)
    scope = tuple(shop_ids)
    event_rows = connection.execute(
        f"""
        SELECT event_type, COUNT(DISTINCT COALESCE(user_id, visitor_key)) AS actors
        FROM analytics_events
        WHERE shop_id IN ({marks}) AND created_at >= ? AND created_at < ?
          AND COALESCE(user_id, visitor_key) IS NOT NULL
        GROUP BY event_type
        """, (*scope, start_at, end_at)
    ).fetchall()
    event_counts = {row["event_type"]: int(row["actors"] or 0) for row in event_rows}
    order = connection.execute(
        f"""
        SELECT COUNT(DISTINCT orders.id) AS orders, COALESCE(SUM(order_items.subtotal_cents), 0) AS revenue
        FROM order_items JOIN orders ON orders.id = order_items.order_id
        WHERE orders.shop_id IN ({marks}) AND orders.paid_at IS NOT NULL
          AND orders.status NOT IN ('cancelled', 'refunded')
          AND orders.paid_at >= ? AND orders.paid_at < ?
        """, (*scope, start_at, end_at)
    ).fetchone()
    impressions = event_counts.get("product_impression", 0)
    clicks = event_counts.get("product_click", 0) + event_counts.get("product_view", 0)
    favorites = event_counts.get("favorite_added", 0)
    add_carts = event_counts.get("add_cart", 0)
    orders = int(order["orders"] or 0)
    return {
        "impressions": impressions, "clicks": clicks, "favorites": favorites,
        "addCarts": add_carts, "orders": orders, "revenue": round((order["revenue"] or 0) / 100, 2),
        "clickThroughRate": round(clicks / impressions * 100, 2) if impressions else 0,
        "favoriteRate": round(favorites / clicks * 100, 2) if clicks else 0,
        "addCartRate": round(add_carts / clicks * 100, 2) if clicks else 0,
        "conversionRate": round(orders / clicks * 100, 2) if clicks else 0,
    }


def business_metric_aliases(metrics: dict) -> dict:
    """Keep the first dashboard's naming contract alongside readable metrics."""
    return {
        **metrics,
        "exposureUv": metrics["impressions"],
        "clickUv": metrics["clicks"],
        "favoriteAdds": metrics["favorites"],
        "addCartUv": metrics["addCarts"],
        "ctr": metrics["clickThroughRate"],
        "clickToOrderRate": metrics["conversionRate"],
    }


def seller_business_analytics(user_id: str, days: int) -> dict:
    if days not in (1, 7, 30):
        raise ValueError("days must be one of 1, 7, or 30")
    today = datetime.now().date()
    current_start = today - timedelta(days=days - 1)
    current_end = today + timedelta(days=1)
    previous_start = current_start - timedelta(days=days)
    previous_end = current_start
    with database() as connection:
        connection.row_factory = sqlite3.Row
        shop_ids = seller_accessible_shop_ids(connection, user_id, "settings")
        period = {
            "current": {"startDate": current_start.isoformat(), "endDate": today.isoformat()},
            "previous": {"startDate": previous_start.isoformat(), "endDate": (current_start - timedelta(days=1)).isoformat()},
        }
        if not shop_ids:
            empty = _business_metric_period(connection, [], "", "") if False else {"impressions": 0, "clicks": 0, "favorites": 0, "addCarts": 0, "orders": 0, "revenue": 0, "clickThroughRate": 0, "favoriteRate": 0, "addCartRate": 0, "conversionRate": 0}
            empty = business_metric_aliases(empty)
            empty_funnel = {"impressions": 0, "clicks": 0, "favorites": 0, "addCarts": 0, "paidOrders": 0, "clickRate": 0, "favoriteRate": 0, "addCartRate": 0, "paymentRate": 0, "exposureUv": 0, "clickUv": 0, "favoriteAdds": 0, "addCartUv": 0, "ctr": 0, "clickToOrderRate": 0}
            empty_current = {**period["current"], "overview": empty, "funnel": empty_funnel, "products": [], "insights": []}
            empty_previous = {**period["previous"], "overview": empty}
            return {"days": days, "current": empty_current, "previous": empty_previous, "overview": {**empty, "compare": {key: None for key in empty}}, "funnel": empty_funnel, "products": [], "insights": []}
        current = business_metric_aliases(_business_metric_period(connection, shop_ids, f"{current_start.isoformat()} 00:00:00", f"{current_end.isoformat()} 00:00:00"))
        previous = business_metric_aliases(_business_metric_period(connection, shop_ids, f"{previous_start.isoformat()} 00:00:00", f"{previous_end.isoformat()} 00:00:00"))
        compare = {
            key: round(current[key] - previous[key], 2) if previous[key] else (None if not current[key] else None)
            for key in current
        }
        # Rates are reported as percentage-point deltas; count and revenue values
        # intentionally use absolute deltas so a zero prior period remains useful.
        for key in ("impressions", "clicks", "favorites", "addCarts", "orders", "revenue"):
            compare[key] = round(current[key] - previous[key], 2)
        marks = ",".join("?" for _ in shop_ids)
        scope = tuple(shop_ids)
        products = connection.execute(
            f"""
            SELECT products.id, products.title, products.stock, products.low_stock_threshold, products.published_at,
              COALESCE(events.impressions, 0) AS impressions,
              COALESCE(events.clicks, 0) AS clicks,
              COALESCE(events.favorites, 0) AS favorites,
              COALESCE(events.add_carts, 0) AS add_carts,
              COALESCE(sales.orders, 0) AS orders,
              COALESCE(sales.revenue, 0) AS revenue
            FROM products
            LEFT JOIN (
              SELECT product_id,
                COUNT(DISTINCT CASE WHEN event_type = 'product_impression' THEN COALESCE(user_id, visitor_key) END) AS impressions,
                COUNT(DISTINCT CASE WHEN event_type IN ('product_click', 'product_view') THEN COALESCE(user_id, visitor_key) END) AS clicks,
                COUNT(DISTINCT CASE WHEN event_type = 'favorite_added' THEN COALESCE(user_id, visitor_key) END) AS favorites,
                COUNT(DISTINCT CASE WHEN event_type = 'add_cart' THEN COALESCE(user_id, visitor_key) END) AS add_carts
              FROM analytics_events
              WHERE shop_id IN ({marks}) AND created_at >= ? AND created_at < ?
              GROUP BY product_id
            ) events ON events.product_id = products.id
            LEFT JOIN (
              SELECT order_items.product_id, COUNT(DISTINCT orders.id) AS orders,
                SUM(order_items.subtotal_cents) AS revenue
              FROM order_items JOIN orders ON orders.id = order_items.order_id
              WHERE orders.shop_id IN ({marks}) AND orders.paid_at IS NOT NULL
                AND orders.status NOT IN ('cancelled', 'refunded')
                AND orders.paid_at >= ? AND orders.paid_at < ?
              GROUP BY order_items.product_id
            ) sales ON sales.product_id = products.id
            WHERE products.shop_id IN ({marks}) AND products.status = 'published'
            ORDER BY orders DESC, clicks DESC, impressions DESC, products.updated_at DESC
            """,
            (*scope, f"{current_start.isoformat()} 00:00:00", f"{current_end.isoformat()} 00:00:00", *scope, f"{current_start.isoformat()} 00:00:00", f"{current_end.isoformat()} 00:00:00", *scope),
        ).fetchall()
        product_rows = [{
            "id": row["id"], "title": row["title"], "stock": int(row["stock"] or 0),
            "lowStockThreshold": int(row["low_stock_threshold"] or 0), "publishedAt": row["published_at"],
            "impressions": int(row["impressions"] or 0), "clicks": int(row["clicks"] or 0),
            "favorites": int(row["favorites"] or 0), "addCarts": int(row["add_carts"] or 0),
            "orders": int(row["orders"] or 0), "revenue": round((row["revenue"] or 0) / 100, 2),
            "clickThroughRate": round((row["clicks"] or 0) / (row["impressions"] or 1) * 100, 2) if row["impressions"] else 0,
            "conversionRate": round((row["orders"] or 0) / (row["clicks"] or 1) * 100, 2) if row["clicks"] else 0,
            "exposureUv": int(row["impressions"] or 0), "clickUv": int(row["clicks"] or 0),
            "favoriteAdds": int(row["favorites"] or 0),
            "addCartUv": int(row["add_carts"] or 0),
            "ctr": round((row["clicks"] or 0) / (row["impressions"] or 1) * 100, 2) if row["impressions"] else 0,
            "clickToOrderRate": round((row["orders"] or 0) / (row["clicks"] or 1) * 100, 2) if row["clicks"] else 0,
        } for row in products]
        funnel = {"impressions": current["impressions"], "clicks": current["clicks"], "favorites": current["favorites"], "addCarts": current["addCarts"], "paidOrders": current["orders"], "clickRate": current["clickThroughRate"], "favoriteRate": current["favoriteRate"], "addCartRate": current["addCartRate"], "paymentRate": current["conversionRate"], "exposureUv": current["exposureUv"], "clickUv": current["clickUv"], "favoriteAdds": current["favoriteAdds"], "addCartUv": current["addCartUv"], "ctr": current["ctr"], "clickToOrderRate": current["clickToOrderRate"]}
        payload = {
            "days": days,
            "current": {**period["current"], "overview": current, "funnel": funnel, "products": product_rows},
            "previous": {**period["previous"], "overview": previous},
            "overview": {**current, "compare": compare}, "funnel": funnel, "products": product_rows,
        }
        try:
            from business_advisor import build_insights
            insights = build_insights(payload)
        except ImportError:
            insights = []
        normalised_insights = []
        for insight in insights if isinstance(insights, list) else []:
            if not isinstance(insight, dict):
                continue
            target = insight.get("actionTab") or insight.get("actionTarget") or "products"
            if target not in ("products", "promotions", "inventory"):
                target = "products"
            reason = str(insight.get("reason") or insight.get("description") or "")
            normalised_insights.append({
                **insight, "actionTab": target, "actionTarget": target,
                "description": str(insight.get("description") or reason),
                "recommendation": str(insight.get("recommendation") or insight.get("suggestion") or reason),
                "suggestion": str(insight.get("suggestion") or insight.get("recommendation") or reason),
                "actionLabel": str(insight.get("actionLabel") or "View details"),
            })
        payload["insights"] = normalised_insights
        payload["current"]["insights"] = normalised_insights
        return payload


def seller_ai_assistant_rate_allowed(user_id: str, limit: int = 20, window_seconds: int = 600) -> bool:
    """Atomically reserve an AI request quota across server processes.

    SQLite is the shared coordination point for this deployment.  An immediate
    write transaction prevents two HTTP worker threads (or processes) from both
    seeing the last remaining slot and admitting more than ``limit`` requests.
    """
    if not user_id or limit < 1 or window_seconds < 1:
        return False
    with database() as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "DELETE FROM ai_rate_limit_events WHERE created_at <= datetime('now', ?)",
            (f"-{int(window_seconds)} seconds",),
        )
        used = connection.execute(
            "SELECT COUNT(*) FROM ai_rate_limit_events WHERE user_id = ? AND scope = 'seller_ai'",
            (user_id,),
        ).fetchone()[0]
        if used >= limit:
            return False
        connection.execute(
            "INSERT INTO ai_rate_limit_events (user_id, scope) VALUES (?, 'seller_ai')",
            (user_id,),
        )
    return True


def seller_ai_assistant_endpoint() -> str:
    if not OPENAI_BASE_URL:
        raise ValueError("AI 服务尚未配置，请联系平台管理员设置 OPENAI_BASE_URL")
    if OPENAI_BASE_URL.endswith("/chat/completions"):
        return OPENAI_BASE_URL
    return f"{OPENAI_BASE_URL if OPENAI_BASE_URL.endswith('/v1') else f'{OPENAI_BASE_URL}/v1'}/chat/completions"


def seller_ai_title_endpoint() -> str:
    if not VISION_BASE_URL:
        raise ValueError("图片标题服务尚未配置，请设置 VISION_BASE_URL")
    if VISION_BASE_URL.endswith("/chat/completions"):
        return VISION_BASE_URL
    return f"{VISION_BASE_URL if VISION_BASE_URL.endswith('/v1') else f'{VISION_BASE_URL}/v1'}/chat/completions"


def seller_ai_assistant_reply(user_id: str, message: object, history: object) -> str:
    question = str(message or "").strip()
    if not 1 <= len(question) <= 2000:
        raise ValueError("请输入 1 到 2000 个字符的问题")
    if not OPENAI_API_KEY:
        raise ValueError("AI 服务尚未配置，请联系平台管理员设置 OPENAI_API_KEY")
    if not seller_ai_assistant_rate_allowed(user_id):
        raise ValueError("提问过于频繁，请 10 分钟后再试")

    safe_history = []
    for item in history[-8:] if isinstance(history, list) else []:
        if not isinstance(item, dict):
            continue
        role = str(item.get("role") or "")
        content = str(item.get("content") or "").strip()
        if role in ("user", "assistant") and content:
            safe_history.append({"role": role, "content": content[:2000]})

    analytics = seller_business_analytics(user_id, 30)
    overview = analytics.get("overview") or {}
    context = {
        "period": "最近30天",
        "overview": {
            key: overview.get(key, 0)
            for key in ("impressions", "clicks", "favorites", "addCarts", "orders", "revenue", "clickThroughRate", "conversionRate")
        },
        "insights": [
            {
                "title": item.get("title", ""),
                "description": item.get("description", ""),
                "recommendation": item.get("recommendation", ""),
            }
            for item in (analytics.get("insights") or [])[:5]
            if isinstance(item, dict)
        ],
        "products": [
            {
                key: product.get(key, 0)
                for key in ("title", "impressions", "clicks", "favorites", "addCarts", "orders", "revenue", "clickThroughRate", "conversionRate", "stock")
            }
            for product in (analytics.get("products") or [])[:8]
            if isinstance(product, dict)
        ],
    }
    system_prompt = """你是手作集卖家后台的 AI 运营助手。只基于提供的店铺数据回答，帮助卖家提升曝光、点击、收藏、加购和订单。回答使用简体中文，先给结论，再给不超过 3 条可执行措施；使用 Markdown 加粗每个小节标题，例如 **结论：**、**可执行措施：**。数据不足时明确说明，不能编造业绩、平台规则或执行结果。不要索取或输出支付、身份等敏感信息。"""
    request_body = {
        "model": OPENAI_MODEL,
        "temperature": 0.4,
        "max_tokens": 900,
        "messages": [
            {"role": "system", "content": f"{system_prompt}\n\n店铺经营数据：\n{json.dumps(context, ensure_ascii=False)}"},
            *safe_history,
            {"role": "user", "content": question},
        ],
    }
    request = Request(
        seller_ai_assistant_endpoint(),
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise ValueError("AI 服务暂时无法响应，请稍后重试") from error
    choices = payload.get("choices") if isinstance(payload, dict) else None
    content = choices[0].get("message", {}).get("content") if isinstance(choices, list) and choices and isinstance(choices[0], dict) else ""
    if isinstance(content, list):
        content = "".join(str(item.get("text") or "") for item in content if isinstance(item, dict))
    reply = str(content or "").strip()
    if not reply:
        raise ValueError("AI 服务未返回有效内容，请稍后重试")
    return reply[:8000]


def seller_ai_product_title(user_id: str, image_data: object) -> dict[str, str]:
    """Generate editable English and Chinese product titles from an uploaded image."""
    if not VISION_API_KEY:
        raise ValueError("图片标题服务尚未配置，请设置 VISION_API_KEY")
    if not seller_ai_assistant_rate_allowed(user_id):
        raise ValueError("标题生成过于频繁，请 10 分钟后再试")

    source_image = str(image_data or "").strip()
    matched = re.fullmatch(r"data:(image/(?:jpeg|png|webp));base64,([A-Za-z0-9+/=]+)", source_image)
    if not matched:
        raise ValueError("图片标题请求无效，请重新上传图片")
    encoded_image = matched.group(2)
    if len(encoded_image) > MAX_IMAGE_BYTES * 4 // 3 + 16:
        raise ValueError("图片过大，无法生成标题")
    try:
        decoded_image = base64.b64decode(encoded_image, validate=True)
    except (ValueError, binascii.Error):
        raise ValueError("图片标题请求无效，请重新上传图片") from None
    if not 0 < len(decoded_image) <= MAX_IMAGE_BYTES:
        raise ValueError("图片过大，无法生成标题")

    request_body = {
        "model": VISION_MODEL,
        "temperature": 0.35,
        "max_tokens": 180,
        "messages": [
            {
                "role": "system",
                "content": "You create product titles for an international handmade marketplace from the supplied image. Return exactly one valid JSON object and nothing else: {\"englishTitle\": \"...\", \"chineseTitle\": \"...\"}. englishTitle must be a natural, search-optimized English title of at most 125 English characters. Include the handmade craft or item type, a material only when visually supported, the visible design or style, and a likely decor, gift, or practical use when supported. chineseTitle must be a concise Simplified Chinese reference translation of the English title, at most 50 Chinese characters. Do not add explanations, Markdown, labels, a brand, exact material, measurements, or features that cannot be verified from the image.",
            },
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "请为这件手工艺作品生成标题。"},
                    {
                        "type": "image_url",
                        "image_url": {"url": source_image},
                    },
                ],
            },
        ],
    }
    request = Request(
        seller_ai_title_endpoint(),
        data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {VISION_API_KEY}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=45) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise ValueError("AI 标题生成暂时无法响应，请稍后重试") from error
    choices = payload.get("choices") if isinstance(payload, dict) else None
    content = choices[0].get("message", {}).get("content") if isinstance(choices, list) and choices and isinstance(choices[0], dict) else ""
    if isinstance(content, list):
        content = "".join(str(item.get("text") or "") for item in content if isinstance(item, dict))
    raw_content = str(content or "").strip()
    json_content = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw_content, flags=re.IGNORECASE).strip()
    try:
        generated = json.loads(json_content)
    except json.JSONDecodeError:
        generated = None
    if isinstance(generated, dict):
        english_title = str(generated.get("englishTitle") or "").strip()
        chinese_title = str(generated.get("chineseTitle") or "").strip()
    else:
        english_title = raw_content
        chinese_title = ""
    english_title = re.sub(r"\s+", " ", english_title).strip().strip("\"'“”‘’")
    english_title = re.sub(r"^(?:作品)?标题\s*[：:]\s*", "", english_title).strip()
    chinese_title = re.sub(r"\s+", " ", chinese_title).strip().strip("\"'“”‘’")
    if not english_title:
        raise ValueError("AI 服务未返回有效标题，请稍后重试")
    return {
        "englishTitle": truncate_product_title(english_title),
        "chineseTitle": chinese_title[:50],
    }


ORDER_STATUS_LABELS = {
    "pending_payment": "待付款",
    "pending_fulfillment": "待发货",
    "shipped": "待收货",
    "delivered": "待收货",
    "completed": "已完成",
    "cancelled": "已取消",
    "refunding": "待处理",
    "refunded": "已退款",
}


def public_brand_site(domain: str = "", shop_id: str = "", preview_owner_id: str | None = None) -> dict | None:
    """Return a published visitor storefront, or its owner's authenticated preview."""
    normalized_domain = str(domain or "").strip().lower().removeprefix("https://").removeprefix("http://").split("/", 1)[0].rstrip(".")
    with database() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute("SELECT * FROM shops WHERE status = 'active' ORDER BY updated_at DESC").fetchall()
        selected = None
        settings: dict = {}
        for row in rows:
            try:
                candidate_settings = json.loads(row["settings_json"] or "{}")
            except json.JSONDecodeError:
                candidate_settings = {}
            if not isinstance(candidate_settings, dict):
                candidate_settings = {}
            owner_preview = bool(
                preview_owner_id
                and shop_id
                and str(row["id"]) == shop_id
                and str(row["owner_user_id"]) == preview_owner_id
            )
            brand_site = candidate_settings.get("brandSite")
            if not isinstance(brand_site, dict):
                if not owner_preview:
                    continue
                brand_site = {
                    "enabled": False,
                    "template": "dawn",
                    "siteName": "",
                    "tagline": "",
                    "themeColor": "#e66020",
                    "logoUrl": "",
                    "domain": "",
                    "status": "draft",
                    "sections": [],
                }
                candidate_settings["brandSite"] = brand_site
            if brand_site.get("status") != "published" and not owner_preview:
                continue
            configured_domain = str(brand_site.get("domain") or "").strip().lower().removeprefix("https://").removeprefix("http://").split("/", 1)[0].rstrip(".")
            if (shop_id and str(row["id"]) == shop_id) or (
                not shop_id and normalized_domain and configured_domain == normalized_domain
            ):
                selected, settings = row, candidate_settings
                break
        if not selected:
            return None
        brand_site = settings["brandSite"]
        return_policy = settings.get("returnPolicy") if isinstance(settings.get("returnPolicy"), dict) else {}
        shop = {
            "id": 99,
            "analyticsShopId": selected["id"],
            "name": selected["name"],
            "location": selected["location"] or "",
            "banner": selected["banner_url"] or "",
            "avatar": selected["avatar_url"] or "",
            "description": selected["description"] or "",
            "status": "active",
            "returnPolicy": {
                "acceptsReturns": bool(return_policy.get("acceptsReturns", True)),
                "windowDays": max(1, min(30, int(return_policy.get("windowDays", 7) or 7))),
                "instructions": str(return_policy.get("instructions") or "")[:500],
            },
        }
    return {"shop": shop, "brandSite": brand_site, "products": catalog((str(selected["id"]),), ("published",))}


def catalog_product_number(product_id: str) -> int:
    try:
        return int(product_id.rsplit("-", 1)[-1])
    except ValueError:
        return int(hashlib.sha256(product_id.encode("utf-8")).hexdigest()[:8], 16)


def featured_product_ids_for_shop(connection: sqlite3.Connection, shop_id: str, raw_ids: object) -> list[str]:
    if not isinstance(raw_ids, list):
        return []
    published_ids = [
        str(row[0])
        for row in connection.execute(
            "SELECT id FROM products WHERE shop_id = ? AND status = 'published' ORDER BY published_at DESC, created_at DESC",
            (shop_id,),
        )
    ]
    published_set = set(published_ids)
    legacy_ids = {catalog_product_number(product_id): product_id for product_id in published_ids}
    featured: list[str] = []
    for raw_id in raw_ids:
        if isinstance(raw_id, bool):
            continue
        product_id = str(raw_id)
        if product_id not in published_set:
            try:
                product_id = legacy_ids[int(raw_id)]
            except (TypeError, ValueError, KeyError):
                continue
        if product_id not in featured:
            featured.append(product_id)
        if len(featured) == 2:
            break
    return featured


def seller_shop_ids(connection: sqlite3.Connection, user_id: str) -> list[str]:
    return list(seller_shop_permissions(connection, user_id))


SHOP_OWNER_PERMISSIONS = frozenset({"products", "inventory", "orders", "shipping", "messages", "after_sales", "reviews", "settings", "staff"})
SHOP_STAFF_CUSTOM_PERMISSIONS = frozenset(SHOP_OWNER_PERMISSIONS - {"staff"})
SHOP_STAFF_ROLE_PERMISSIONS = {
    "operator": frozenset({"products", "inventory", "settings"}),
    "fulfillment": frozenset({"orders", "shipping"}),
    "customer_service": frozenset({"messages", "after_sales", "reviews"}),
}


def seller_shop_permissions(connection: sqlite3.Connection, user_id: str) -> dict[str, set[str]]:
    """Return active shops visible to an owner or a delegated staff member."""
    permissions: dict[str, set[str]] = {}
    owners = (user_id, f"legacy-seller-{user_id}")
    for row in connection.execute("SELECT id FROM shops WHERE owner_user_id IN (?, ?)", owners):
        permissions[str(row[0])] = set(SHOP_OWNER_PERMISSIONS)
    for row in connection.execute(
        "SELECT shop_id, role, permissions_json FROM shop_staff WHERE user_id = ? AND status = 'active'",
        (user_id,),
    ):
        try:
            custom = {str(item) for item in json.loads(row[2] or "[]") if str(item) in SHOP_STAFF_CUSTOM_PERMISSIONS}
        except (TypeError, json.JSONDecodeError):
            custom = set()
        permissions.setdefault(str(row[0]), set()).update(SHOP_STAFF_ROLE_PERMISSIONS.get(str(row[1]), frozenset()) | custom)
    return permissions


def seller_accessible_shop_ids(connection: sqlite3.Connection, user_id: str, permission: str | None = None) -> list[str]:
    permissions = seller_shop_permissions(connection, user_id)
    return [shop_id for shop_id, granted in permissions.items() if permission is None or permission in granted]


def shop_message_recipient_user_ids(connection: sqlite3.Connection, shop_id: str) -> list[str]:
    """Return every active owner or staff account allowed to handle this shop's messages."""
    candidates = [str(row[0]) for row in connection.execute("SELECT owner_user_id FROM shops WHERE id = ?", (shop_id,))]
    candidates.extend(
        str(row[0])
        for row in connection.execute(
            "SELECT shop_staff.user_id FROM shop_staff JOIN users ON users.id = shop_staff.user_id WHERE shop_staff.shop_id = ? AND shop_staff.status = 'active' AND users.status = 'active'",
            (shop_id,),
        )
    )
    return [user_id for user_id in dict.fromkeys(candidates) if "messages" in seller_shop_permissions(connection, user_id).get(shop_id, set())]


def require_shop_permission(connection: sqlite3.Connection, user_id: str, shop_id: str, permission: str) -> None:
    if permission not in seller_shop_permissions(connection, user_id).get(shop_id, set()):
        raise ValueError("无权操作该店铺")


def require_shop_owner(connection: sqlite3.Connection, user_id: str, shop_id: str) -> None:
    if not connection.execute("SELECT 1 FROM shops WHERE id = ? AND owner_user_id IN (?, ?)", (shop_id, user_id, f"legacy-seller-{user_id}")).fetchone():
        raise ValueError("仅店主可管理成员")


def finance_fee_bps(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT service_fee_bps FROM platform_finance_settings WHERE id = 1").fetchone()
    return max(0, min(3000, int(row[0] if row else 500)))


def add_business_days(start: datetime, days: int) -> datetime:
    """Add weekday-only settlement hold days (Saturday and Sunday are skipped)."""
    current = start
    remaining = max(0, days)
    while remaining:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def database_datetime(value: str | None) -> datetime:
    if value:
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed.astimezone(timezone.utc)
        except ValueError:
            pass
    return datetime.now(timezone.utc)


def payout_schedule_next_at(schedule: str, now: datetime | None = None) -> str:
    """Return the next platform payout window; provider transfer execution is separate."""
    current = now or datetime.now(timezone.utc)
    if schedule == "daily":
        target = current + timedelta(days=1)
    elif schedule == "monthly":
        target = (current.replace(day=1) + timedelta(days=32)).replace(day=1)
    else:
        days_until_monday = (7 - current.weekday()) % 7
        target = current + timedelta(days=days_until_monday or 7)
        if schedule == "biweekly":
            anchor = datetime(2026, 1, 5, tzinfo=timezone.utc)
            if ((target.date() - anchor.date()).days // 7) % 2:
                target += timedelta(days=7)
    return target.strftime("%Y-%m-%d")


def settlement_hold_until(connection: sqlite3.Connection, order_id: str, completed_at: str | None) -> str:
    """Calculate a seller's hold deadline, with an explicit extension point for new-seller risk."""
    profile = connection.execute(
        """
        SELECT seller_profiles.payout_risk_hold_business_days, users.created_at
        FROM orders
        JOIN shops ON shops.id = orders.shop_id
        LEFT JOIN seller_profiles ON seller_profiles.user_id = shops.owner_user_id
        LEFT JOIN users ON users.id = shops.owner_user_id
        WHERE orders.id = ?
        """,
        (order_id,),
    ).fetchone()
    extra_days = 0
    if profile and profile[1]:
        seller_created_at = database_datetime(profile[1])
        if seller_created_at > datetime.now(timezone.utc) - timedelta(days=NEW_SELLER_RISK_WINDOW_DAYS):
            extra_days = max(0, int(profile[0] or 0))
    return add_business_days(database_datetime(completed_at), SETTLEMENT_HOLD_BUSINESS_DAYS + extra_days).strftime("%Y-%m-%d %H:%M:%S")


def ensure_shop_wallet(connection: sqlite3.Connection, shop_id: str) -> None:
    connection.execute("INSERT OR IGNORE INTO shop_wallets (shop_id) VALUES (?)", (shop_id,))


def write_wallet_ledger(
    connection: sqlite3.Connection,
    shop_id: str,
    entry_type: str,
    *,
    settlement_id: str | None = None,
    withdrawal_id: str | None = None,
    available: int = 0,
    pending: int = 0,
    withdrawing: int = 0,
    withdrawn: int = 0,
    note: str = "",
) -> None:
    connection.execute(
        """
        INSERT INTO shop_wallet_ledger
          (id, shop_id, settlement_id, withdrawal_id, entry_type, available_delta_cents,
           pending_delta_cents, withdrawing_delta_cents, withdrawn_delta_cents, note)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (f"wallet-ledger-{secrets.token_urlsafe(10)}", shop_id, settlement_id, withdrawal_id,
         entry_type, available, pending, withdrawing, withdrawn, note),
    )


def create_order_settlement(connection: sqlite3.Connection, order_id: str) -> bool:
    """Move a successful order into the seller's pending balance exactly once."""
    connection.row_factory = sqlite3.Row
    order = connection.execute("SELECT id, shop_id, paid_amount_cents, settlement_currency, settlement_exchange_rate, status, paid_at FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order or not order["paid_at"] or order["status"] in ("pending_payment", "cancelled", "refunded"):
        return False
    fee_bps = finance_fee_bps(connection)
    gross = max(0, int(order["paid_amount_cents"] or 0))
    fee = gross * fee_bps // 10000
    net = gross - fee
    settlement_id = f"settlement-{secrets.token_urlsafe(10)}"
    inserted = connection.execute(
        """
        INSERT OR IGNORE INTO shop_settlements
          (id, shop_id, order_id, gross_cents, platform_fee_cents, net_cents, fee_rate_bps, settlement_currency, settlement_exchange_rate)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (settlement_id, order["shop_id"], order_id, gross, fee, net, fee_bps, order["settlement_currency"], order["settlement_exchange_rate"]),
    ).rowcount
    if not inserted:
        return False
    ensure_shop_wallet(connection, order["shop_id"])
    connection.execute("UPDATE shop_wallets SET pending_cents = pending_cents + ?, updated_at = CURRENT_TIMESTAMP WHERE shop_id = ?", (net, order["shop_id"]))
    write_wallet_ledger(connection, order["shop_id"], "order_pending", settlement_id=settlement_id, pending=net, note=f"订单 {order_id} 待结算")
    return True


def schedule_order_settlement_hold(connection: sqlite3.Connection, order_id: str) -> bool:
    """Start the post-completion settlement hold exactly once."""
    connection.row_factory = sqlite3.Row
    order = connection.execute("SELECT id, status, completed_at FROM orders WHERE id = ?", (order_id,)).fetchone()
    settlement = connection.execute("SELECT * FROM shop_settlements WHERE order_id = ?", (order_id,)).fetchone()
    if not order or order["status"] != "completed" or not settlement or settlement["status"] != "pending" or settlement["hold_until"]:
        return False
    hold_until = settlement_hold_until(connection, order_id, order["completed_at"])
    changed = connection.execute(
        "UPDATE shop_settlements SET hold_started_at = COALESCE(hold_started_at, ?), hold_until = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'pending' AND hold_until IS NULL",
        (order["completed_at"] or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"), hold_until, settlement["id"]),
    ).rowcount
    return bool(changed)


def order_has_open_after_sale(connection: sqlite3.Connection, order_id: str) -> bool:
    row = connection.execute(
        "SELECT 1 FROM after_sale_requests WHERE order_id = ? AND status IN ('pending', 'approved') LIMIT 1",
        (order_id,),
    ).fetchone()
    return bool(row)


def release_order_settlement(connection: sqlite3.Connection, order_id: str) -> bool:
    """Release a completed, unfrozen order into the seller's available balance."""
    connection.row_factory = sqlite3.Row
    order = connection.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
    settlement = connection.execute("SELECT * FROM shop_settlements WHERE order_id = ?", (order_id,)).fetchone()
    if (
        not order
        or order["status"] != "completed"
        or not settlement
        or settlement["status"] != "pending"
        or not settlement["hold_until"]
        or settlement["hold_until"] > datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
        or order_has_open_after_sale(connection, order_id)
    ):
        return False
    changed = connection.execute("UPDATE shop_settlements SET status = 'available', available_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'pending'", (settlement["id"],)).rowcount
    if not changed:
        return False
    ensure_shop_wallet(connection, settlement["shop_id"])
    wallet = connection.execute("SELECT refund_debt_cents FROM shop_wallets WHERE shop_id = ?", (settlement["shop_id"],)).fetchone()
    releasable_net = max(0, int(settlement["net_cents"]) - int(settlement["refunded_net_cents"] or 0))
    debt_offset = min(releasable_net, int(wallet["refund_debt_cents"] if wallet else 0))
    available_delta = releasable_net - debt_offset
    connection.execute(
        "UPDATE shop_wallets SET pending_cents = pending_cents - ?, available_cents = available_cents + ?, refund_debt_cents = refund_debt_cents - ?, updated_at = CURRENT_TIMESTAMP WHERE shop_id = ?",
        (releasable_net, available_delta, debt_offset, settlement["shop_id"]),
    )
    note = f"订单 {order_id} 结算完成" + (f"，抵扣退款欠款 {debt_offset / 100:.2f} USD" if debt_offset else "")
    write_wallet_ledger(connection, settlement["shop_id"], "order_available", settlement_id=settlement["id"], available=available_delta, pending=-releasable_net, note=note)
    return True


def apply_settlement_refund(connection: sqlite3.Connection, order_id: str, amount_cents: int, refund_id: str | None = None) -> dict:
    """Reverse a whole or partial USD refund from the seller balance exactly once."""
    connection.row_factory = sqlite3.Row
    settlement = connection.execute("SELECT * FROM shop_settlements WHERE order_id = ?", (order_id,)).fetchone()
    if not settlement or settlement["status"] == "reversed":
        raise ValueError("订单结算单不可退款")
    amount = max(0, int(amount_cents))
    remaining = max(0, int(settlement["gross_cents"]) - int(settlement["refunded_gross_cents"] or 0))
    if amount <= 0 or amount > remaining:
        raise ValueError("退款金额超过订单可退款余额")
    current_fee = int(settlement["refunded_fee_cents"] or 0)
    target_refunded_gross = int(settlement["refunded_gross_cents"] or 0) + amount
    target_fee = target_refunded_gross * int(settlement["fee_rate_bps"]) // 10000
    fee_reversal = target_fee - current_fee
    seller_net_reversal = amount - fee_reversal
    target_refunded_net = int(settlement["refunded_net_cents"] or 0) + seller_net_reversal
    fully_refunded = target_refunded_gross == int(settlement["gross_cents"])
    connection.execute(
        """
        UPDATE shop_settlements
        SET refunded_gross_cents = ?, refunded_fee_cents = ?, refunded_net_cents = ?,
            status = CASE WHEN ? THEN 'reversed' ELSE status END,
            reversed_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE reversed_at END,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (target_refunded_gross, target_fee, target_refunded_net, fully_refunded, fully_refunded, settlement["id"]),
    )
    ensure_shop_wallet(connection, settlement["shop_id"])
    pending_delta = -seller_net_reversal if settlement["status"] == "pending" else 0
    available_delta = 0
    refund_debt_delta = 0
    if settlement["status"] == "available":
        wallet = connection.execute("SELECT available_cents FROM shop_wallets WHERE shop_id = ?", (settlement["shop_id"],)).fetchone()
        available_before = int(wallet["available_cents"] if wallet else 0)
        available_reversal = min(available_before, seller_net_reversal)
        available_delta = -available_reversal
        refund_debt_delta = seller_net_reversal - available_reversal
    connection.execute(
        "UPDATE shop_wallets SET pending_cents = pending_cents + ?, available_cents = available_cents + ?, refund_debt_cents = refund_debt_cents + ?, updated_at = CURRENT_TIMESTAMP WHERE shop_id = ?",
        (pending_delta, available_delta, refund_debt_delta, settlement["shop_id"]),
    )
    note = f"订单 {order_id} 退款冲回 {amount / 100:.2f} USD"
    if refund_debt_delta:
        note += f"，待后续结算抵扣 {refund_debt_delta / 100:.2f} USD"
    write_wallet_ledger(connection, settlement["shop_id"], "refund_reversal", settlement_id=settlement["id"], available=available_delta, pending=pending_delta, note=note)
    if refund_id:
        connection.execute(
            "UPDATE order_refunds SET platform_fee_reversal_cents = ?, seller_net_reversal_cents = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
            (fee_reversal, seller_net_reversal, refund_id),
        )
    return {
        "amountCents": amount,
        "platformFeeReversalCents": fee_reversal,
        "sellerNetReversalCents": seller_net_reversal,
        "fullyRefunded": fully_refunded,
    }


def record_after_sale_refund(connection: sqlite3.Connection, after_sale_id: str) -> dict:
    """Record an approved refund at its request-time currency and exchange-rate lock."""
    connection.row_factory = sqlite3.Row
    request = connection.execute("SELECT * FROM after_sale_requests WHERE id = ?", (after_sale_id,)).fetchone()
    if not request:
        raise ValueError("售后申请不存在")
    existing = connection.execute("SELECT * FROM order_refunds WHERE after_sale_id = ?", (after_sale_id,)).fetchone()
    if existing:
        return {"id": existing["id"], "amountCents": existing["amount_cents"], "fullyRefunded": False}
    order = connection.execute("SELECT * FROM orders WHERE id = ?", (request["order_id"],)).fetchone()
    if not order or not order["paid_at"]:
        raise ValueError("订单尚未支付，不能退款")
    if request["refund_currency"] != order["payment_currency"] or request["refund_exchange_rate"] != order["payment_exchange_rate"]:
        raise ValueError("退款币种或汇率与订单锁定值不一致")
    refund_id = f"refund-{secrets.token_urlsafe(10)}"
    connection.execute(
        "INSERT INTO order_refunds (id, order_id, after_sale_id, amount_cents, currency, exchange_rate) VALUES (?, ?, ?, ?, ?, ?)",
        (refund_id, order["id"], after_sale_id, request["requested_amount_cents"], request["refund_currency"], request["refund_exchange_rate"]),
    )
    result = apply_settlement_refund(connection, order["id"], int(request["requested_amount_cents"]), refund_id)
    return {"id": refund_id, **result}


def complete_order_and_start_settlement_hold(connection: sqlite3.Connection, order_id: str) -> bool:
    """Complete an order and begin its hold period; safe to call repeatedly."""
    connection.row_factory = sqlite3.Row
    order = connection.execute("SELECT id, status FROM orders WHERE id = ?", (order_id,)).fetchone()
    if not order or order["status"] in ("cancelled", "refunded", "refunding"):
        return False
    completed_now = False
    if order["status"] != "completed":
        completed_now = bool(connection.execute(
            "UPDATE orders SET status = 'completed', completed_at = COALESCE(completed_at, CURRENT_TIMESTAMP), updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status IN ('shipped', 'delivered')",
            (order_id,),
        ).rowcount)
    connection.execute(
        "UPDATE shipments SET status = 'delivered', delivered_at = COALESCE(delivered_at, CURRENT_TIMESTAMP) WHERE order_id = ?",
        (order_id,),
    )
    create_order_settlement(connection, order_id)
    hold_started = schedule_order_settlement_hold(connection, order_id)
    return completed_now or hold_started


def is_delivered_tracking_event(label: str, detail: str) -> bool:
    return bool(re.search(r"\bdelivered\b|已妥投|已投递|已签收", f"{label} {detail}", re.IGNORECASE))


def logistics_provider_for_carrier(carrier: str) -> str:
    value = str(carrier or "").strip().lower()
    if "sf" in value or "顺丰" in value:
        return "sf"
    if "dhl" in value:
        return "dhl"
    if "fedex" in value:
        return "fedex"
    if "ups" in value:
        return "ups"
    if "usps" in value:
        return "usps"
    return "manual"


def logistics_webhook_is_valid(raw_body: bytes, signature: str) -> bool:
    if not LOGISTICS_WEBHOOK_SECRET or not signature:
        return False
    expected = hmac.new(LOGISTICS_WEBHOOK_SECRET.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return secrets.compare_digest(expected, signature.strip().removeprefix("sha256="))


def record_logistics_webhook_event(connection: sqlite3.Connection, payload: dict) -> dict:
    """Process a signed provider callback idempotently; seller-entered text never completes an order."""
    provider = str(payload.get("provider") or "").strip().lower()
    event_id = str(payload.get("eventId") or "").strip()
    tracking_no = str(payload.get("trackingNo") or "").strip()
    status = str(payload.get("status") or "").strip().lower()
    if not re.fullmatch(r"[a-z0-9_-]{2,40}", provider) or not event_id or len(event_id) > 160 or not tracking_no or len(tracking_no) > 160:
        raise ValueError("物流回调参数无效")
    if status not in {"label_created", "in_transit", "exception", "returned", "delivered"}:
        raise ValueError("不支持的物流状态")
    connection.row_factory = sqlite3.Row
    shipment = connection.execute(
        "SELECT shipments.*, orders.order_no, orders.shop_id, orders.buyer_user_id FROM shipments JOIN orders ON orders.id = shipments.order_id WHERE shipments.logistics_provider = ? AND COALESCE(shipments.provider_tracking_id, shipments.tracking_no) = ?",
        (provider, tracking_no),
    ).fetchone()
    if not shipment:
        raise ValueError("未找到对应物流单")
    inserted = connection.execute(
        "INSERT OR IGNORE INTO logistics_webhook_events (id, provider, external_event_id, shipment_id, event_type, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
        (f"logistics-webhook-{secrets.token_urlsafe(10)}", provider, event_id, shipment["id"], status, json.dumps(payload, ensure_ascii=False)),
    ).rowcount
    if not inserted:
        return {"accepted": False, "duplicate": True, "orderNo": shipment["order_no"], "completed": False}
    label = str(payload.get("label") or status.replace("_", " ").title())[:240]
    detail = str(payload.get("detail") or "")[:1000]
    occurred_at = str(payload.get("occurredAt") or datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))[:40]
    connection.execute(
        "INSERT INTO shipment_events (id, shipment_id, event_at, label, detail) VALUES (?, ?, ?, ?, ?)",
        (f"event-{secrets.token_urlsafe(8)}", shipment["id"], occurred_at, label, detail),
    )
    connection.execute(
        "UPDATE shipments SET status = CASE WHEN ? = 'delivered' THEN 'delivered' WHEN ? = 'in_transit' THEN 'in_transit' ELSE status END, delivered_at = CASE WHEN ? = 'delivered' THEN COALESCE(delivered_at, ?) ELSE delivered_at END, last_tracking_status = ?, last_tracking_at = ? WHERE id = ?",
        (status, status, status, occurred_at, status, occurred_at, shipment["id"]),
    )
    completed = False
    if status == "delivered":
        completed = complete_order_and_start_settlement_hold(connection, shipment["order_id"])
        if completed:
            owner = connection.execute("SELECT owner_user_id FROM shops WHERE id = ?", (shipment["shop_id"],)).fetchone()
            if owner:
                notify_governance(connection, owner[0], "order_completed", "订单已完成", f"订单 {shipment['order_no']} 已由物流商妥投", "order", shipment["order_no"])
            notify_governance(connection, shipment["buyer_user_id"], "review_reminder", "订单已完成，等待评价", "分享你的使用感受，帮助更多手作爱好者", "order", shipment["order_no"])
    return {"accepted": True, "duplicate": False, "orderNo": shipment["order_no"], "completed": completed}


def reverse_order_settlement(connection: sqlite3.Connection, order_id: str) -> bool:
    """Reverse the remaining settlement amount for legacy full-refund callers."""
    connection.row_factory = sqlite3.Row
    settlement = connection.execute("SELECT * FROM shop_settlements WHERE order_id = ?", (order_id,)).fetchone()
    if not settlement or settlement["status"] == "reversed":
        return False
    remaining = int(settlement["gross_cents"]) - int(settlement["refunded_gross_cents"] or 0)
    if remaining <= 0:
        return False
    apply_settlement_refund(connection, order_id, remaining)
    return True


def ensure_finance_for_paid_orders(connection: sqlite3.Connection, shop_ids: list[str] | None = None) -> None:
    where, params = "paid_at IS NOT NULL AND status NOT IN ('pending_payment', 'cancelled', 'refunded')", []
    if shop_ids:
        where += f" AND shop_id IN ({','.join('?' for _ in shop_ids)})"
        params.extend(shop_ids)
    for row in connection.execute(f"SELECT id, status FROM orders WHERE {where}", tuple(params)).fetchall():
        create_order_settlement(connection, row[0])
        if row[1] == "completed":
            schedule_order_settlement_hold(connection, row[0])
            release_order_settlement(connection, row[0])


def seller_finance_payload(connection: sqlite3.Connection, user_id: str) -> dict:
    connection.row_factory = sqlite3.Row
    shop_ids = seller_accessible_shop_ids(connection, user_id)
    if not shop_ids:
        raise ValueError("暂无可结算的店铺")
    ensure_finance_for_paid_orders(connection, shop_ids)
    marks = ",".join("?" for _ in shop_ids)
    wallets = connection.execute(f"SELECT shop_wallets.*, shops.name AS shop_name FROM shop_wallets JOIN shops ON shops.id = shop_wallets.shop_id WHERE shop_wallets.shop_id IN ({marks})", tuple(shop_ids)).fetchall()
    settlements = connection.execute(f"SELECT shop_settlements.*, orders.order_no FROM shop_settlements JOIN orders ON orders.id = shop_settlements.order_id WHERE shop_settlements.shop_id IN ({marks}) ORDER BY shop_settlements.created_at DESC LIMIT 100", tuple(shop_ids)).fetchall()
    ledger = connection.execute(f"SELECT * FROM shop_wallet_ledger WHERE shop_id IN ({marks}) ORDER BY created_at DESC LIMIT 100", tuple(shop_ids)).fetchall()
    withdrawals = connection.execute(f"SELECT shop_withdrawal_requests.*, shops.name AS shop_name FROM shop_withdrawal_requests JOIN shops ON shops.id = shop_withdrawal_requests.shop_id WHERE shop_withdrawal_requests.shop_id IN ({marks}) ORDER BY shop_withdrawal_requests.created_at DESC LIMIT 100", tuple(shop_ids)).fetchall()
    totals = {key: sum(int(row[key] or 0) for row in wallets) for key in ("available_cents", "pending_cents", "withdrawing_cents", "withdrawn_cents", "refund_debt_cents")}
    profile = connection.execute("SELECT payout_schedule FROM seller_profiles WHERE user_id = ?", (user_id,)).fetchone()
    payout_schedule = (profile["payout_schedule"] if profile else "weekly") or "weekly"
    if payout_schedule not in SELLER_PAYOUT_SCHEDULES:
        payout_schedule = "weekly"
    return {
        "currency": PLATFORM_CURRENCY,
        "feeRateBps": finance_fee_bps(connection), "wallet": {"available": totals["available_cents"] / 100, "pending": totals["pending_cents"] / 100, "withdrawing": totals["withdrawing_cents"] / 100, "withdrawn": totals["withdrawn_cents"] / 100, "refundDebt": totals["refund_debt_cents"] / 100},
        "payoutSchedule": payout_schedule,
        "nextPayoutAt": payout_schedule_next_at(payout_schedule),
        "minimumPayout": SETTLEMENT_MIN_PAYOUT_CENTS / 100,
        "holdBusinessDays": SETTLEMENT_HOLD_BUSINESS_DAYS,
        "newSellerRiskWindowDays": NEW_SELLER_RISK_WINDOW_DAYS,
        "shops": [{"id": row["shop_id"], "name": row["shop_name"], "available": row["available_cents"] / 100, "pending": row["pending_cents"] / 100, "withdrawing": row["withdrawing_cents"] / 100, "withdrawn": row["withdrawn_cents"] / 100, "refundDebt": row["refund_debt_cents"] / 100} for row in wallets],
        "settlements": [{"id": row["id"], "orderNo": row["order_no"], "shopId": row["shop_id"], "gross": (row["gross_cents"] - row["refunded_gross_cents"]) / 100, "fee": (row["platform_fee_cents"] - row["refunded_fee_cents"]) / 100, "net": (row["net_cents"] - row["refunded_net_cents"]) / 100, "refundedAmount": row["refunded_gross_cents"] / 100, "currency": row["settlement_currency"], "exchangeRate": row["settlement_exchange_rate"], "status": row["status"], "createdAt": row["created_at"], "holdUntil": row["hold_until"], "availableAt": row["available_at"]} for row in settlements],
        "ledger": [{"id": row["id"], "type": row["entry_type"], "availableDelta": row["available_delta_cents"] / 100, "pendingDelta": row["pending_delta_cents"] / 100, "withdrawingDelta": row["withdrawing_delta_cents"] / 100, "withdrawnDelta": row["withdrawn_delta_cents"] / 100, "note": row["note"], "createdAt": row["created_at"]} for row in ledger],
        "withdrawals": [{"id": row["id"], "shopId": row["shop_id"], "shop": row["shop_name"], "amount": row["amount_cents"] / 100, "recipientType": row["recipient_type"], "recipient": row["recipient_snapshot"], "status": row["status"], "note": row["reviewer_note"], "createdAt": row["created_at"], "reviewedAt": row["reviewed_at"], "paidAt": row["paid_at"]} for row in withdrawals],
    }


def seller_payout_account_payload(connection: sqlite3.Connection, user_id: str) -> dict:
    row = connection.execute("SELECT payout_provider, payout_binding_status, payout_account_mask, payout_bound_at FROM seller_profiles WHERE user_id = ?", (user_id,)).fetchone()
    return {
        "provider": (row[0] if row else "lianlian") or "lianlian",
        "status": (row[1] if row else "unbound") or "unbound",
        "accountMask": row[2] if row else None,
        "boundAt": row[3] if row else None,
        "mode": LIANLIAN_MODE,
    }


def payout_account_mask(account: str) -> str:
    value = str(account or "").strip()
    return f"****{value[-4:]}" if len(value) >= 4 else "****"


def admin_finance_payload(connection: sqlite3.Connection) -> dict:
    connection.row_factory = sqlite3.Row
    ensure_finance_for_paid_orders(connection)
    wallet = connection.execute("SELECT COALESCE(SUM(available_cents), 0), COALESCE(SUM(pending_cents), 0), COALESCE(SUM(withdrawing_cents), 0), COALESCE(SUM(withdrawn_cents), 0), COALESCE(SUM(refund_debt_cents), 0) FROM shop_wallets").fetchone()
    fees = connection.execute("SELECT COALESCE(SUM(platform_fee_cents - refunded_fee_cents), 0) FROM shop_settlements").fetchone()[0]
    rows = connection.execute("SELECT shop_withdrawal_requests.*, shops.name AS shop_name, users.display_name AS applicant FROM shop_withdrawal_requests JOIN shops ON shops.id = shop_withdrawal_requests.shop_id JOIN users ON users.id = shop_withdrawal_requests.applicant_user_id ORDER BY CASE status WHEN 'pending' THEN 0 WHEN 'approved' THEN 1 ELSE 2 END, created_at DESC LIMIT 200").fetchall()
    return {"feeRateBps": finance_fee_bps(connection), "summary": {"available": wallet[0] / 100, "pending": wallet[1] / 100, "withdrawing": wallet[2] / 100, "withdrawn": wallet[3] / 100, "refundDebt": wallet[4] / 100, "platformFees": fees / 100}, "withdrawals": [{"id": row["id"], "shop": row["shop_name"], "applicant": row["applicant"], "amount": row["amount_cents"] / 100, "recipientType": row["recipient_type"], "recipient": row["recipient_snapshot"], "status": row["status"], "note": row["reviewer_note"], "createdAt": row["created_at"]} for row in rows]}


def write_shop_staff_audit(
    connection: sqlite3.Connection,
    shop_id: str,
    staff_user_id: str | None,
    actor_user_id: str,
    action: str,
    detail: dict | None = None,
) -> None:
    connection.execute(
        "INSERT INTO shop_staff_audit_logs (id, shop_id, staff_user_id, actor_user_id, action, detail_json) VALUES (?, ?, ?, ?, ?, ?)",
        (f"staff-audit-{secrets.token_urlsafe(8)}", shop_id, staff_user_id, actor_user_id, action, json.dumps(detail or {}, ensure_ascii=False)),
    )


def audit_delegated_shop_operation(connection: sqlite3.Connection, user_id: str, shop_id: str, action: str, detail: dict | None = None) -> None:
    row = connection.execute("SELECT id FROM shop_staff WHERE shop_id = ? AND user_id = ? AND status = 'active'", (shop_id, user_id)).fetchone()
    if row:
        write_shop_staff_audit(connection, shop_id, user_id, user_id, action, detail)


def is_seller(connection: sqlite3.Connection, user_id: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM user_roles WHERE user_id = ? AND role = 'seller'", (user_id,)
    ).fetchone() is not None or connection.execute(
        "SELECT 1 FROM shop_staff WHERE user_id = ? AND status = 'active'", (user_id,)
    ).fetchone() is not None


def is_admin(connection: sqlite3.Connection, user_id: str) -> bool:
    return connection.execute(
        "SELECT 1 FROM platform_admins WHERE user_id = ?", (user_id,)
    ).fetchone() is not None


def require_admin(user_id: str) -> None:
    with database() as connection:
        if not is_admin(connection, user_id):
            raise ValueError("需要平台管理员权限")


def admin_verification_destination(connection: sqlite3.Connection, user_id: str) -> str:
    row = connection.execute("SELECT email, phone FROM users WHERE id = ?", (user_id,)).fetchone()
    if not row:
        raise ValueError("管理员账号不存在")
    # Prefer the real mobile number: Tencent Cloud SMS cannot deliver to email.
    destination = str(row[1] or row[0] or "").strip().lower()
    if not destination:
        raise ValueError("管理员账号未设置邮箱或手机号")
    return destination


def require_admin_step_up(handler: BaseHTTPRequestHandler, user_id: str, *, force_fresh: bool = False) -> None:
    """Validate an administrator's recent identity verification.

    Standard tickets can be reused for one hour.  A high-risk ticket is
    issued only after an explicit fresh verification and is consumed on use.
    """
    ticket = str(handler.headers.get("X-Admin-Step-Up") or "").strip()
    current_session = session_token(handler)
    if not ticket or not current_session:
        raise StepUpRequiredError()
    with database() as connection:
        if force_fresh:
            valid = connection.execute(
                """
                UPDATE admin_step_up_tickets
                SET consumed_at = CURRENT_TIMESTAMP
                WHERE user_id = ? AND ticket_hash = ? AND session_token_hash = ? AND scope = 'high_risk'
                  AND consumed_at IS NULL AND expires_at > CURRENT_TIMESTAMP
                """,
                (user_id, token_hash(ticket), token_hash(current_session)),
            ).rowcount
        else:
            valid = connection.execute(
                """
                SELECT 1 FROM admin_step_up_tickets
                WHERE user_id = ? AND ticket_hash = ? AND session_token_hash = ? AND consumed_at IS NULL
                  AND expires_at > CURRENT_TIMESTAMP
                """,
                (user_id, token_hash(ticket), token_hash(current_session)),
            ).fetchone()
    if not valid:
        raise StepUpRequiredError()


def write_platform_audit(connection: sqlite3.Connection, actor_user_id: str, action: str, target_type: str, target_id: str, detail: dict | None = None) -> None:
    connection.execute(
        "INSERT INTO platform_audit_logs (id, actor_user_id, action, target_type, target_id, detail_json) VALUES (?, ?, ?, ?, ?, ?)",
        (f"audit-{secrets.token_urlsafe(10)}", actor_user_id, action, target_type, target_id, json.dumps(detail or {}, ensure_ascii=False)),
    )


def governance_case_event(connection: sqlite3.Connection, case_type: str, case_id: str, event_type: str, actor_user_id: str | None = None, payload: dict | None = None) -> None:
    connection.execute(
        "INSERT INTO governance_case_events (id, case_type, case_id, event_type, actor_user_id, payload_json) VALUES (?, ?, ?, ?, ?, ?)",
        (f"case-event-{secrets.token_urlsafe(10)}", case_type, case_id, event_type, actor_user_id, json.dumps(payload or {}, ensure_ascii=False)),
    )


def governance_case_type_for_task(task_type: str) -> str:
    return {"product_moderation": "product", "report": "report", "appeal": "appeal"}[task_type]


def default_task_due_sql(priority: str) -> str:
    return {"urgent": "+4 hours", "high": "+1 day", "normal": "+3 days", "low": "+5 days"}.get(priority, "+3 days")


def priority_rank(priority: str) -> int:
    return {"low": 0, "normal": 1, "high": 2, "urgent": 3}.get(priority, 1)


def governance_task_priority(connection: sqlite3.Connection, task_type: str, target_id: str) -> str:
    if task_type == "product_moderation":
        row = connection.execute("SELECT governance_rules.priority FROM governance_rule_hits JOIN governance_rules ON governance_rules.id = governance_rule_hits.rule_id WHERE governance_rule_hits.product_id = ? ORDER BY governance_rule_hits.created_at DESC LIMIT 1", (target_id,)).fetchone()
        if row:
            return "urgent" if row[0] <= 20 else "high" if row[0] <= 75 else "normal" if row[0] <= 250 else "low"
    table, column = ("content_reports", "reason || ' ' || detail") if task_type == "report" else ("governance_appeals", "content")
    row = connection.execute(f"SELECT lower(COALESCE({column}, '')) FROM {table} WHERE id = ?", (target_id,)).fetchone()
    content = str(row[0] or "") if row else ""
    if any(word in content for word in ("诈骗", "人身", "安全", "违禁", "侵权", "假货")):
        return "urgent"
    if any(word in content for word in ("退款", "投诉", "纠纷", "违规")):
        return "high"
    return "normal"


def least_loaded_admin(connection: sqlite3.Connection) -> str | None:
    row = connection.execute(
        """
        SELECT users.id
        FROM platform_admins JOIN users ON users.id = platform_admins.user_id
        LEFT JOIN governance_tasks ON governance_tasks.assigned_user_id = users.id AND governance_tasks.status != 'completed'
        WHERE users.status = 'active'
        GROUP BY users.id
        ORDER BY COUNT(governance_tasks.id), users.id
        LIMIT 1
        """
    ).fetchone()
    return str(row[0]) if row else None


def ensure_governance_tasks(connection: sqlite3.Connection) -> None:
    for task_type, table, predicate in (
        ("report", "content_reports", "status = 'pending'"),
        ("appeal", "governance_appeals", "status = 'pending'"),
    ):
        for row in connection.execute(f"SELECT id FROM {table} WHERE {predicate}"):
            task_id = f"governance-task-{secrets.token_urlsafe(10)}"
            priority = governance_task_priority(connection, task_type, row[0])
            assignee_id = least_loaded_admin(connection)
            created = connection.execute(
                "INSERT OR IGNORE INTO governance_tasks (id, task_type, target_id, status, assigned_user_id, priority, due_at) VALUES (?, ?, ?, ?, ?, ?, datetime('now', ?))",
                (task_id, task_type, row[0], "in_progress" if assignee_id else "pending", assignee_id, priority, default_task_due_sql(priority)),
            ).rowcount
            if created:
                governance_case_event(connection, governance_case_type_for_task(task_type), row[0], "task_created", payload={"taskId": task_id, "priority": priority, "autoAssignedUserId": assignee_id})
                if assignee_id:
                    notify_governance(connection, assignee_id, "governance_task_assigned", "已自动分派治理任务", f"任务优先级：{priority}", "governance_task", task_id)


def complete_governance_task(connection: sqlite3.Connection, task_type: str, target_id: str, actor_user_id: str | None = None) -> None:
    changed = connection.execute("UPDATE governance_tasks SET status = 'completed', completed_at = CURRENT_TIMESTAMP WHERE task_type = ? AND target_id = ? AND status != 'completed'", (task_type, target_id)).rowcount
    if changed:
        governance_case_event(connection, governance_case_type_for_task(task_type), target_id, "task_completed", actor_user_id)


def task_sla_status(row: sqlite3.Row) -> str:
    if row["status"] == "completed" or not row["due_at"]:
        return "met"
    due = datetime.fromisoformat(str(row["due_at"]).replace("Z", "+00:00")).replace(tzinfo=timezone.utc)
    remaining = due - datetime.now(timezone.utc)
    if remaining.total_seconds() < 0:
        return "overdue"
    if remaining <= timedelta(hours=4):
        return "warning"
    return "on_track"


def governance_task_rows(connection: sqlite3.Connection, filters: dict[str, str] | None = None) -> list[dict]:
    filters = filters or {}
    clauses, params = ["1 = 1"], []
    for key, column, allowed in (("status", "governance_tasks.status", {"pending", "in_progress", "completed"}), ("type", "governance_tasks.task_type", {"product_moderation", "report", "appeal"}), ("priority", "governance_tasks.priority", {"low", "normal", "high", "urgent"})):
        value = filters.get(key, "")
        if value in allowed:
            clauses.append(f"{column} = ?")
            params.append(value)
    if filters.get("assignee"):
        clauses.append("governance_tasks.assigned_user_id = ?")
        params.append(filters["assignee"])
    if filters.get("sla") == "overdue":
        clauses.append("governance_tasks.status != 'completed' AND governance_tasks.due_at < CURRENT_TIMESTAMP")
    elif filters.get("sla") == "warning":
        clauses.append("governance_tasks.status != 'completed' AND governance_tasks.due_at >= CURRENT_TIMESTAMP AND governance_tasks.due_at <= datetime('now', '+4 hours')")
    connection.row_factory = sqlite3.Row
    rows = connection.execute(f"SELECT governance_tasks.*, users.display_name AS assignee FROM governance_tasks LEFT JOIN users ON users.id = governance_tasks.assigned_user_id WHERE {' AND '.join(clauses)} ORDER BY CASE governance_tasks.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 WHEN 'normal' THEN 2 ELSE 3 END, governance_tasks.due_at ASC, governance_tasks.created_at DESC LIMIT 200", tuple(params)).fetchall()
    return [{"id": row["id"], "type": row["task_type"], "targetId": row["target_id"], "status": row["status"], "priority": row["priority"], "dueAt": row["due_at"], "sla": task_sla_status(row), "assigneeId": row["assigned_user_id"], "assignee": row["assignee"], "createdAt": row["created_at"], "completedAt": row["completed_at"]} for row in rows]


def governance_operation_data(connection: sqlite3.Connection) -> dict:
    connection.row_factory = sqlite3.Row
    ensure_governance_tasks(connection)
    tasks = governance_task_rows(connection)
    admins = connection.execute("SELECT users.id, users.display_name FROM platform_admins JOIN users ON users.id = platform_admins.user_id WHERE users.status = 'active' ORDER BY users.display_name").fetchall()
    rules = connection.execute("SELECT governance_rules.*, COUNT(governance_rule_hits.id) AS hit_count, MAX(governance_rule_hits.created_at) AS last_hit_at FROM governance_rules LEFT JOIN governance_rule_hits ON governance_rule_hits.rule_id = governance_rules.id GROUP BY governance_rules.id ORDER BY governance_rules.priority ASC, governance_rules.updated_at DESC").fetchall()
    templates = connection.execute("SELECT * FROM enforcement_templates ORDER BY enabled DESC, updated_at DESC").fetchall()
    return {
        "tasks": tasks,
        "admins": [{"id": row["id"], "name": row["display_name"]} for row in admins],
        "rules": [{"id": row["id"], "name": row["name"], "keyword": row["keyword"], "action": row["action"], "enabled": bool(row["enabled"]), "priority": row["priority"], "conditions": governance_rule_conditions(row)[0], "conditionLogic": row["condition_logic"], "rolloutPercent": row["rollout_percent"], "releaseStatus": row["release_status"], "version": row["version"], "hits": row["hit_count"], "lastHitAt": row["last_hit_at"]} for row in rules],
        "templates": [{"id": row["id"], "name": row["name"], "targetType": row["target_type"], "action": row["action_type"], "reason": row["reason"], "enabled": bool(row["enabled"])} for row in templates],
    }


def governance_service_insights(connection: sqlite3.Connection) -> dict:
    """Operational effectiveness and SLA metrics for governance and support queues."""
    connection.row_factory = sqlite3.Row
    ensure_governance_tasks(connection)
    run_support_automation(connection)
    tasks = governance_task_rows(connection)
    sla = {"backlog": 0, "unassigned": 0, "warning": 0, "overdue": 0, "completed": 0, "onTimeCompleted": 0, "breachedCompleted": 0, "averageResolutionHours": 0}
    completed_hours: list[float] = []
    for task in tasks:
        if task["status"] == "completed":
            sla["completed"] += 1
            row = connection.execute("SELECT created_at, due_at, completed_at FROM governance_tasks WHERE id = ?", (task["id"],)).fetchone()
            if row and row["completed_at"]:
                completed_hours.append(max(0, (datetime.fromisoformat(row["completed_at"]) - datetime.fromisoformat(row["created_at"])).total_seconds() / 3600))
                if row["due_at"] and row["completed_at"] <= row["due_at"]: sla["onTimeCompleted"] += 1
                elif row["due_at"]: sla["breachedCompleted"] += 1
            continue
        sla["backlog"] += 1
        if not task["assigneeId"]: sla["unassigned"] += 1
        if task["sla"] in ("warning", "overdue"): sla[task["sla"]] += 1
    sla["averageResolutionHours"] = round(sum(completed_hours) / len(completed_hours), 1) if completed_hours else 0
    rule_rows = connection.execute(
        """
        SELECT rules.id, rules.name, rules.version, rules.rollout_percent, rules.release_status,
          COUNT(hits.id) AS hits,
          SUM(CASE WHEN hits.action = 'reject' THEN 1 ELSE 0 END) AS auto_rejected,
          SUM(CASE WHEN products.moderation_status = 'approved' THEN 1 ELSE 0 END) AS approved,
          SUM(CASE WHEN products.moderation_status = 'rejected' THEN 1 ELSE 0 END) AS rejected,
          SUM(CASE WHEN products.moderation_status = 'pending' THEN 1 ELSE 0 END) AS pending,
          MAX(hits.created_at) AS last_hit_at
        FROM governance_rules AS rules
        LEFT JOIN governance_rule_hits AS hits ON hits.rule_id = rules.id
        LEFT JOIN products ON products.id = hits.product_id
        GROUP BY rules.id
        ORDER BY hits DESC, rules.priority ASC
        LIMIT 30
        """
    ).fetchall()
    rules = [{"id": row["id"], "name": row["name"], "version": row["version"], "rolloutPercent": row["rollout_percent"], "releaseStatus": row["release_status"], "hits": int(row["hits"] or 0), "autoRejected": int(row["auto_rejected"] or 0), "approved": int(row["approved"] or 0), "rejected": int(row["rejected"] or 0), "pending": int(row["pending"] or 0), "reviewPassRate": round(int(row["approved"] or 0) * 100 / int(row["hits"] or 1), 1) if row["hits"] else 0, "lastHitAt": row["last_hit_at"]} for row in rule_rows]
    tickets = connection.execute("SELECT * FROM support_tickets").fetchall()
    support = {"total": len(tickets), "open": 0, "inProgress": 0, "resolved": 0, "overdue": 0, "warning": 0, "unassigned": 0, "averageFirstResponseHours": 0, "averageResolutionHours": 0}
    first_response_hours: list[float] = []
    resolution_hours: list[float] = []
    for ticket in tickets:
        if ticket["status"] == "open": support["open"] += 1
        elif ticket["status"] == "in_progress": support["inProgress"] += 1
        elif ticket["status"] in ("resolved", "closed"): support["resolved"] += 1
        if ticket["status"] not in ("resolved", "closed"):
            if not ticket["assigned_user_id"]: support["unassigned"] += 1
            sla = support_sla_status(ticket)
            if sla == "overdue": support["overdue"] += 1
            elif sla == "warning": support["warning"] += 1
        first = connection.execute("SELECT created_at FROM support_ticket_messages WHERE ticket_id = ? AND sender_role IN ('seller', 'admin') ORDER BY created_at LIMIT 1", (ticket["id"],)).fetchone()
        if first: first_response_hours.append(max(0, (datetime.fromisoformat(first["created_at"]) - datetime.fromisoformat(ticket["created_at"])).total_seconds() / 3600))
        if ticket["resolved_at"]: resolution_hours.append(max(0, (datetime.fromisoformat(ticket["resolved_at"]) - datetime.fromisoformat(ticket["created_at"])).total_seconds() / 3600))
    support["averageFirstResponseHours"] = round(sum(first_response_hours) / len(first_response_hours), 1) if first_response_hours else 0
    support["averageResolutionHours"] = round(sum(resolution_hours) / len(resolution_hours), 1) if resolution_hours else 0
    admins = connection.execute("SELECT users.id, users.display_name FROM platform_admins JOIN users ON users.id = platform_admins.user_id WHERE users.status = 'active' ORDER BY users.display_name").fetchall()
    return {"governance": {"sla": sla, "rules": rules}, "support": support, "tasks": tasks, "tickets": [support_ticket_response(connection, row) for row in tickets], "admins": [{"id": row["id"], "name": row["display_name"]} for row in admins]}


def governance_case_payload(connection: sqlite3.Connection, case_type: str, case_id: str) -> dict:
    """Build a single, auditable view of a report, appeal, or product moderation case."""
    connection.row_factory = sqlite3.Row
    if case_type == "report":
        row = connection.execute("SELECT content_reports.*, users.display_name AS creator FROM content_reports JOIN users ON users.id = content_reports.reporter_user_id WHERE content_reports.id = ?", (case_id,)).fetchone()
        if not row:
            raise ValueError("案件不存在")
        target_type, target_id, status = row["target_type"], row["target_id"], row["status"]
        title = f"举报：{row['reason']}"
        description = row["detail"] or ""
        creator = row["creator"]
    elif case_type == "appeal":
        row = connection.execute("SELECT governance_appeals.*, users.display_name AS creator FROM governance_appeals JOIN users ON users.id = governance_appeals.appellant_user_id WHERE governance_appeals.id = ?", (case_id,)).fetchone()
        if not row:
            raise ValueError("案件不存在")
        target_type, target_id, status = row["target_type"], row["target_id"], row["status"]
        title = "治理申诉"
        description = row["content"]
        creator = row["creator"]
    elif case_type == "product":
        row = connection.execute("SELECT products.*, shops.name AS shop_name FROM products JOIN shops ON shops.id = products.shop_id WHERE products.id = ?", (case_id,)).fetchone()
        if not row:
            raise ValueError("案件不存在")
        target_type, target_id, status = "product", case_id, row["moderation_status"]
        title = f"作品审核：{row['title']}"
        description = row["moderation_reason"] or ""
        creator = row["shop_name"]
    else:
        raise ValueError("案件类型无效")
    notes = connection.execute(
        "SELECT governance_case_notes.*, users.display_name FROM governance_case_notes JOIN users ON users.id = governance_case_notes.author_user_id WHERE case_type = ? AND case_id = ? ORDER BY created_at",
        (case_type, case_id),
    ).fetchall()
    task_type = {"report": "report", "appeal": "appeal", "product": "product_moderation"}[case_type]
    task = connection.execute("SELECT governance_tasks.*, users.display_name AS assignee FROM governance_tasks LEFT JOIN users ON users.id = governance_tasks.assigned_user_id WHERE task_type = ? AND target_id = ?", (task_type, case_id)).fetchone()
    audits = connection.execute(
        "SELECT platform_audit_logs.*, users.display_name AS actor FROM platform_audit_logs JOIN users ON users.id = platform_audit_logs.actor_user_id WHERE (target_type = ? AND target_id = ?) OR detail_json LIKE ? ORDER BY created_at DESC LIMIT 50",
        (target_type, target_id, f'%{case_id}%'),
    ).fetchall()
    events = connection.execute(
        "SELECT governance_case_events.*, users.display_name AS actor FROM governance_case_events LEFT JOIN users ON users.id = governance_case_events.actor_user_id WHERE case_type = ? AND case_id = ? ORDER BY created_at",
        (case_type, case_id),
    ).fetchall()
    task_notes = connection.execute(
        "SELECT governance_task_notes.*, users.display_name AS actor FROM governance_task_notes JOIN users ON users.id = governance_task_notes.author_user_id WHERE governance_task_notes.task_id = ? ORDER BY created_at",
        (task["id"],),
    ).fetchall() if task else []
    transfers = connection.execute(
        "SELECT governance_task_transfers.*, from_users.display_name AS from_name, to_users.display_name AS to_name, actors.display_name AS actor FROM governance_task_transfers LEFT JOIN users AS from_users ON from_users.id = governance_task_transfers.from_user_id LEFT JOIN users AS to_users ON to_users.id = governance_task_transfers.to_user_id JOIN users AS actors ON actors.id = governance_task_transfers.transferred_by_user_id WHERE task_id = ? ORDER BY created_at",
        (task["id"],),
    ).fetchall() if task else []
    timeline = [
        {"type": "note", "content": note["content"], "visibility": note["visibility"], "actor": note["display_name"], "createdAt": note["created_at"]}
        for note in notes
    ] + [
        {"type": "action", "content": audit["action"], "actor": audit["actor"], "detail": json.loads(audit["detail_json"] or "{}"), "createdAt": audit["created_at"]}
        for audit in audits
    ] + [
        {"type": "event", "content": event["event_type"], "actor": event["actor"] or "系统", "detail": json.loads(event["payload_json"] or "{}"), "createdAt": event["created_at"]}
        for event in events
    ] + [
        {"type": "task_note", "content": note["content"], "actor": note["actor"], "createdAt": note["created_at"]}
        for note in task_notes
    ] + [
        {"type": "transfer", "content": f"{transfer['from_name'] or '未分派'} → {transfer['to_name'] or '未分派'}" + (f"：{transfer['note']}" if transfer["note"] else ""), "actor": transfer["actor"], "createdAt": transfer["created_at"]}
        for transfer in transfers
    ]
    timeline.sort(key=lambda item: item["createdAt"])
    return {
        "case": {"type": case_type, "id": case_id, "title": title, "description": description, "creator": creator, "status": status, "targetType": target_type, "targetId": target_id},
        "task": None if not task else {"id": task["id"], "status": task["status"], "priority": task["priority"], "dueAt": task["due_at"], "sla": task_sla_status(task), "assignee": task["assignee"], "createdAt": task["created_at"], "completedAt": task["completed_at"]},
        "timeline": timeline,
    }


def notify_governance(connection: sqlite3.Connection, user_id: str, notification_type: str, title: str, content: str, related_type: str, related_id: str) -> None:
    connection.execute(
        "INSERT INTO governance_notifications (id, user_id, notification_type, title, content, related_type, related_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (f"notice-{secrets.token_urlsafe(10)}", user_id, notification_type, title, content, related_type, related_id),
    )


def target_owner(connection: sqlite3.Connection, target_type: str, target_id: str) -> str | None:
    if target_type == "product":
        row = connection.execute("SELECT shops.owner_user_id FROM products JOIN shops ON shops.id = products.shop_id WHERE products.id = ?", (target_id,)).fetchone()
        return row[0] if row else None
    if target_type == "shop":
        row = connection.execute("SELECT owner_user_id FROM shops WHERE id = ?", (target_id,)).fetchone()
        return row[0] if row else None
    return target_id if connection.execute("SELECT 1 FROM users WHERE id = ?", (target_id,)).fetchone() else None


def execute_enforcement(connection: sqlite3.Connection, actor_user_id: str, target_type: str, target_id: str, action: str, reason: str, template_id: str | None = None) -> str:
    if (target_type, action) not in (("product", "unlist_product"), ("shop", "pause_shop"), ("user", "disable_user"), ("product", "warning"), ("shop", "warning"), ("user", "warning")) or not reason:
        raise ValueError("处罚参数无效")
    owner = target_owner(connection, target_type, target_id)
    if not owner:
        raise ValueError("处罚对象不存在")
    if action == "unlist_product":
        connection.execute("UPDATE products SET status = 'unlisted', moderation_status = 'rejected', moderation_reason = ? WHERE id = ?", (reason, target_id))
    elif action == "pause_shop":
        connection.execute("UPDATE shops SET status = 'paused' WHERE id = ?", (target_id,))
    elif action == "disable_user":
        connection.execute("UPDATE users SET status = 'disabled' WHERE id = ?", (target_id,))
    action_id = f"enforcement-{secrets.token_urlsafe(10)}"
    connection.execute("INSERT INTO enforcement_actions (id, target_type, target_id, action_type, reason, created_by_user_id) VALUES (?, ?, ?, ?, ?, ?)", (action_id, target_type, target_id, action, reason, actor_user_id))
    notify_governance(connection, owner, "enforcement", "平台处理通知", reason, target_type, target_id)
    write_platform_audit(connection, actor_user_id, action, target_type, target_id, {"reason": reason, "templateId": template_id})
    return action_id


def seller_workspace(user_id: str) -> dict:
    with database() as connection:
        connection.row_factory = sqlite3.Row
        shop_ids = seller_shop_ids(connection, user_id)
        if not shop_ids:
            user = connection.execute("SELECT display_name FROM users WHERE id = ?", (user_id,)).fetchone()
            if not user:
                raise ValueError("当前账号不存在")
            shop_id = f"shop-{user_id}"
            connection.execute(
                "INSERT INTO shops (id, owner_user_id, name) VALUES (?, ?, ?)",
                (shop_id, user_id, user["display_name"]),
            )
            connection.execute("INSERT OR IGNORE INTO seller_profiles (user_id, verification_status) VALUES (?, 'pending')", (user_id,))
            shop_ids = [shop_id]
        shop = connection.execute(
            f"SELECT * FROM shops WHERE id IN ({','.join('?' for _ in shop_ids)}) ORDER BY updated_at DESC LIMIT 1",
            tuple(shop_ids),
        ).fetchone()
        follower_count = connection.execute(
            "SELECT COUNT(*) FROM buyer_shop_follows WHERE shop_id = ?", (shop["id"],)
        ).fetchone()[0]
        try:
            shipping_template = json.loads(shop["shipping_template_json"] or "{}")
        except json.JSONDecodeError:
            shipping_template = {}
        shipping_template = normalize_shipping_template(shipping_template)
        try:
            coupons = json.loads(shop["coupons_json"] or "[]")
        except json.JSONDecodeError:
            coupons = []
        try:
            settings = json.loads(shop["settings_json"] or "{}")
        except json.JSONDecodeError:
            settings = {}
        if not isinstance(settings, dict):
            settings = {}
        stored_return_policy = settings.get("returnPolicy") if isinstance(settings.get("returnPolicy"), dict) else {}
        try:
            return_window_days = int(stored_return_policy.get("windowDays", 7) or 7)
        except (TypeError, ValueError):
            return_window_days = 7
        return_policy = {
            "acceptsReturns": bool(stored_return_policy.get("acceptsReturns", True)),
            "windowDays": max(1, min(30, return_window_days)),
            "recipientName": str(stored_return_policy.get("recipientName") or "")[:80],
            "recipientPhone": str(stored_return_policy.get("recipientPhone") or "")[:40],
            "address": str(stored_return_policy.get("address") or "")[:300],
            "instructions": str(stored_return_policy.get("instructions") or "")[:500],
        }
        shop_response = {
            "id": 99,
            "analyticsShopId": shop["id"],
            "name": shop["name"],
            "owner": connection.execute("SELECT display_name FROM users WHERE id = ?", (user_id,)).fetchone()[0],
            "location": shop["location"],
            "shippingOrigin": shop["location"],
            "since": (shop["created_at"] or "")[:4],
            "banner": shop["banner_url"] or "",
            "avatar": shop["avatar_url"] or "",
            "description": shop["description"],
            "followers": follower_count,
            "status": "paused" if shop["status"] == "paused" else "active",
            "shippingTemplate": shipping_template,
            "returnPolicy": return_policy,
            "coupons": coupons if isinstance(coupons, list) else [],
            "featuredProductIds": featured_product_ids_for_shop(connection, shop["id"], settings.get("featuredProductIds")),
            "brandSite": settings.get("brandSite") if isinstance(settings.get("brandSite"), dict) else None,
        }
    active_products = catalog(tuple(shop_ids), ("published", "unlisted", "archived"))
    draft_products = catalog(tuple(shop_ids), ("draft",))
    drafts = [
        {
            "id": product["id"],
            "catalogId": product["catalogId"],
            "title": product["title"],
            "price": str(product["price"]),
            "category": product["category"],
            "stock": str(product["stock"]),
            "weightGrams": str(product["weightGrams"]) if product["weightGrams"] is not None else "",
            "dimensions": product["dimensions"] or "",
            "lowStockThreshold": str(product["lowStockThreshold"]),
            "description": product["description"],
            "craftsmanship": product.get("craftsmanship") or "",
            "buyerTitle": product.get("buyerTitle") or "",
            "buyerDescription": product.get("buyerDescription") or "",
            "buyerMaterial": product.get("buyerMaterial") or "",
            "buyerSeoTags": product.get("buyerSeoTags") or [],
            "images": product["images"] or [],
            "video": product["video"] or "",
            "seoTags": product["seoTags"],
            "variants": product["variants"] or [],
            "skus": product["skus"] or [],
            "updatedAt": "已保存",
        }
        for product in draft_products
    ]
    return {"shop": shop_response, "products": active_products, "drafts": drafts}


def require_seller(user_id: str) -> None:
    with database() as connection:
        if not is_seller(connection, user_id):
            raise ValueError("需要卖家权限")


def seller_product_response(user_id: str, product_id: str) -> dict:
    with database() as connection:
        shop_ids = seller_shop_ids(connection, user_id)
    product = next(
        (
            item
            for item in catalog(tuple(shop_ids), ("published", "unlisted", "archived", "draft"))
            if item["catalogId"] == product_id
        ),
        None,
    )
    if not product:
        raise ValueError("作品不存在或无权操作")
    return product


def seller_is_verified(connection: sqlite3.Connection, user_id: str) -> bool:
    row = connection.execute("SELECT verification_status, verification_expires_at FROM seller_profiles WHERE user_id = ?", (user_id,)).fetchone()
    return bool(row and row[0] == "approved" and (not row[1] or row[1] > datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")))


def verification_expiry(value: object) -> str:
    raw = str(value or "").strip()
    if not raw:
        return (datetime.now(timezone.utc) + timedelta(days=365)).strftime("%Y-%m-%d 23:59:59")
    try:
        expires = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    except ValueError as error:
        raise ValueError("认证有效期格式无效") from error
    if expires.date() <= datetime.now(timezone.utc).date():
        raise ValueError("认证有效期必须晚于今天")
    return expires.strftime("%Y-%m-%d 23:59:59")


def verification_application_response(connection: sqlite3.Connection, application: sqlite3.Row) -> dict:
    documents = connection.execute(
        "SELECT id, document_type, file_url, status, reviewer_note, created_at FROM seller_verification_documents WHERE application_id = ? ORDER BY created_at",
        (application["id"],),
    ).fetchall()
    return {
        "id": application["id"], "status": application["status"], "reviewNote": application["review_note"],
        "rejectionCode": application["rejection_code"], "evidence": json.loads(application["evidence_json"] or "[]"),
        "businessType": application["business_type"], "legalRepresentative": application["legal_representative"],
        "businessLicenseNo": application["business_license_no"], "businessAddress": application["business_address"],
        "expiresAt": application["expires_at"], "supplementDueAt": application["supplement_due_at"],
        "supplementRequestedAt": application["supplement_requested_at"], "reviewRound": application["review_round"],
        "resubmissionOf": application["resubmission_of"], "createdAt": application["created_at"],
        "documents": [{"id": row["id"], "type": row["document_type"], "url": row["file_url"], "status": row["status"], "reviewNote": row["reviewer_note"], "createdAt": row["created_at"]} for row in documents],
    }


def refresh_product_stock(connection: sqlite3.Connection, product_id: str) -> int:
    total = int(connection.execute(
        "SELECT COALESCE(SUM(stock), 0) FROM product_skus WHERE product_id = ? AND status = 'active'",
        (product_id,),
    ).fetchone()[0])
    connection.execute(
        "UPDATE products SET stock = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
        (total, product_id),
    )
    return total


def inventory_adjustment_rows(connection: sqlite3.Connection, shop_ids: list[str], product_id: str | None = None) -> list[dict]:
    if not shop_ids:
        return []
    connection.row_factory = sqlite3.Row
    where = f"products.shop_id IN ({','.join('?' for _ in shop_ids)})"
    params: list[object] = list(shop_ids)
    if product_id:
        where += " AND inventory_adjustments.product_id = ?"
        params.append(product_id)
    rows = connection.execute(
        f"""
        SELECT inventory_adjustments.*, products.title AS product_title
        FROM inventory_adjustments JOIN products ON products.id = inventory_adjustments.product_id
        WHERE {where}
        ORDER BY inventory_adjustments.created_at DESC LIMIT 100
        """,
        tuple(params),
    ).fetchall()
    return [{
        "id": row["id"], "productId": row["product_id"], "productTitle": row["product_title"],
        "skuId": row["sku_id"], "type": row["adjustment_type"], "before": row["quantity_before"],
        "after": row["quantity_after"], "reason": row["reason"], "createdAt": row["created_at"],
    } for row in rows]


def save_seller_product(user_id: str, product: dict, status: str) -> dict:
    if status not in ("draft", "published", "unlisted"):
        raise ValueError("作品状态无效")
    product_id = str(product.get("catalogId") or f"product-{product.get('id') or secrets.token_urlsafe(10)}")
    with database() as connection:
        shop_ids = seller_accessible_shop_ids(connection, user_id, "products")
        if not shop_ids:
            seller_workspace(user_id)
            shop_ids = seller_accessible_shop_ids(connection, user_id, "products")
        shop_id = shop_ids[0]
        owner = connection.execute("SELECT owner_user_id FROM shops WHERE id = ?", (shop_id,)).fetchone()
        if status == "published" and (not owner or not seller_is_verified(connection, owner[0])):
            raise ValueError("完成卖家认证后才能发布作品")
        existing = connection.execute("SELECT shop_id FROM products WHERE id = ?", (product_id,)).fetchone()
        if existing and existing[0] not in shop_ids:
            raise ValueError("无权编辑该作品")
        resolve_product_media_assets(connection, user_id, product_id, product, status, bool(existing))
        resolve_product_variant_media_assets(connection, user_id, product, status)
        upsert_product(connection, product_id, shop_id, product, status)
        audit_delegated_shop_operation(connection, user_id, shop_id, "product_saved", {"productId": product_id, "status": status})
    return seller_product_response(user_id, product_id)


def update_seller_shop(user_id: str, shop: dict) -> dict:
    with database() as connection:
        connection.row_factory = sqlite3.Row
        shop_ids = seller_accessible_shop_ids(connection, user_id, "settings")
        if not shop_ids:
            seller_workspace(user_id)
            shop_ids = seller_accessible_shop_ids(connection, user_id, "settings")
        shop_id = shop_ids[0]
        current = connection.execute("SELECT * FROM shops WHERE id = ?", (shop_id,)).fetchone()
        if not current:
            raise ValueError("店铺不存在")
        shipping = shop.get("shippingTemplate")
        coupons = shop.get("coupons")
        featured = shop.get("featuredProductIds")
        brand_site = shop.get("brandSite")
        return_policy = shop.get("returnPolicy")
        try:
            current_settings = json.loads(current["settings_json"] or "{}")
        except json.JSONDecodeError:
            current_settings = {}
        if not isinstance(current_settings, dict):
            current_settings = {}
        if isinstance(featured, list):
            current_settings["featuredProductIds"] = featured_product_ids_for_shop(connection, shop_id, featured)
        if isinstance(brand_site, dict):
            current_settings["brandSite"] = brand_site
        if isinstance(return_policy, dict):
            try:
                return_window_days = int(return_policy.get("windowDays", 7))
            except (TypeError, ValueError):
                return_window_days = 7
            if not 1 <= return_window_days <= 30:
                raise ValueError("退货期限需在 1 至 30 天之间")
            return_address = str(return_policy.get("address") or "").strip()
            recipient_name = str(return_policy.get("recipientName") or "").strip()
            recipient_phone = str(return_policy.get("recipientPhone") or "").strip()
            return_instructions = str(return_policy.get("instructions") or "").strip()
            if len(recipient_name) > 80 or len(recipient_phone) > 40 or len(return_address) > 300 or len(return_instructions) > 500:
                raise ValueError("退货设置内容过长")
            current_settings["returnPolicy"] = {"acceptsReturns": bool(return_policy.get("acceptsReturns")), "windowDays": return_window_days, "recipientName": recipient_name, "recipientPhone": recipient_phone, "address": return_address, "instructions": return_instructions}
        connection.execute(
            """
            UPDATE shops
            SET name = ?, description = ?, location = ?, banner_url = ?, avatar_url = ?, status = ?,
                shipping_template_json = ?, coupons_json = ?, settings_json = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                str(shop.get("name", current["name"])).strip() or current["name"],
                str(shop.get("description", current["description"])),
                str(shop.get("shippingOrigin", shop.get("location", current["location"]))),
                shop.get("banner", current["banner_url"]),
                shop.get("avatar", current["avatar_url"]),
                shop.get("status") if shop.get("status") in ("active", "paused", "closed") else current["status"],
                json.dumps(normalize_shipping_template(shipping) if isinstance(shipping, dict) else normalize_shipping_template(json.loads(current["shipping_template_json"] or "{}")), ensure_ascii=False),
                json.dumps(coupons if isinstance(coupons, list) else json.loads(current["coupons_json"] or "[]"), ensure_ascii=False),
                json.dumps(current_settings, ensure_ascii=False),
                shop_id,
            ),
        )
    return seller_workspace(user_id)["shop"]


def order_items_for_response(connection: sqlite3.Connection, order_id: str) -> list[dict]:
    rows = connection.execute(
        """
        SELECT order_items.product_id, order_items.title_snapshot, order_items.image_url_snapshot,
               order_items.unit_price_cents, order_items.price_currency, order_items.quantity, order_items.specifications_snapshot,
               activity_order_allocations.status AS activity_status,
               platform_activities.id AS activity_id, platform_activities.name AS activity_name
        FROM order_items
        LEFT JOIN activity_order_allocations ON activity_order_allocations.order_item_id = order_items.id
        LEFT JOIN activity_products ON activity_products.id = activity_order_allocations.activity_product_id
        LEFT JOIN platform_activities ON platform_activities.id = activity_products.activity_id
        WHERE order_items.order_id = ?
        """,
        (order_id,),
    ).fetchall()
    return [
        {
            "productId": catalog_product_number(row["product_id"] or ""),
            "catalogId": row["product_id"],
            "title": row["title_snapshot"],
            "image": row["image_url_snapshot"],
            "unitPrice": row["unit_price_cents"] / 100,
            "currency": row["price_currency"],
            "quantity": row["quantity"],
            "variants": json.loads(row["specifications_snapshot"] or "{}"),
            "activity": (
                {"id": row["activity_id"], "name": row["activity_name"], "status": row["activity_status"]}
                if row["activity_id"]
                else None
            ),
        }
        for row in rows
    ]


def address_for_response(row: sqlite3.Row) -> dict:
    return {
        "id": row["id"],
        "recipient": row["recipient_name"],
        "phone": row["recipient_phone"],
        "province": row["province"],
        "city": row["city"],
        "district": row["district"],
        "detail": row["detail"],
        "postalCode": row["postal_code"] or "",
        "countryCode": row["country_code"] or "US",
        "country": row["country_name"] or SHIPPING_COUNTRIES.get(row["country_code"] or "US", "United States"),
        "isDefault": bool(row["is_default"]),
    }


def checkout_groups(connection: sqlite3.Connection, raw_items: list[dict]) -> dict[str, list[tuple[sqlite3.Row, sqlite3.Row, int, dict, str | None]]]:
    grouped: dict[str, list[tuple[sqlite3.Row, sqlite3.Row, int, dict, str | None]]] = {}
    for raw_item in raw_items:
        catalog_id = str(raw_item.get("catalogId") or "").strip()
        quantity = int(raw_item.get("quantity") or 0)
        variants = raw_item.get("variants") or {}
        if not catalog_id or quantity <= 0 or not isinstance(variants, dict):
            raise ValueError("订单商品数据无效")
        product = connection.execute(
            "SELECT * FROM products WHERE id = ? AND status = 'published'", (catalog_id,)
        ).fetchone()
        if not product:
            raise ValueError("商品已下架或不存在")
        sku = find_sku(connection, catalog_id, variants)
        if sku["stock"] < quantity:
            raise ValueError(f"{product['title']} 库存不足")
        activity_id = str(raw_item.get("activityId") or "").strip() or None
        grouped.setdefault(product["shop_id"], []).append((product, sku, quantity, variants, activity_id))
    return grouped


def campaign_performance(connection: sqlite3.Connection, days: int | None = None) -> list[dict]:
    scope = ""
    params: tuple[object, ...] = ()
    if days:
        scope = " AND redemptions.created_at >= datetime('now', ?)"
        params = (f"-{days} days",)
    rows = connection.execute(
        f"""
        SELECT campaigns.*, 
          COALESCE(SUM(CASE WHEN redemptions.status = 'reserved' THEN 1 ELSE 0 END), 0) AS reserved_count,
          COALESCE(SUM(CASE WHEN redemptions.status = 'redeemed' THEN 1 ELSE 0 END), 0) AS redemption_count,
          COALESCE(SUM(CASE WHEN redemptions.status = 'reversed' THEN 1 ELSE 0 END), 0) AS reversed_count,
          COALESCE(SUM(CASE WHEN redemptions.status IN ('reserved', 'redeemed') THEN redemptions.discount_amount_cents ELSE 0 END), 0) AS committed_cents,
          COALESCE(SUM(CASE WHEN redemptions.status = 'redeemed' THEN redemptions.discount_amount_cents ELSE 0 END), 0) AS spent_cents,
          COALESCE(SUM(CASE WHEN redemptions.status = 'redeemed' THEN redemptions.item_amount_cents ELSE 0 END), 0) AS attributed_revenue_cents
        FROM platform_campaigns AS campaigns
        LEFT JOIN platform_campaign_redemptions AS redemptions ON redemptions.campaign_id = campaigns.id {scope}
        GROUP BY campaigns.id
        ORDER BY CASE campaigns.status WHEN 'active' THEN 0 WHEN 'draft' THEN 1 ELSE 2 END, campaigns.created_at DESC
        """,
        params,
    ).fetchall()
    result = []
    for row in rows:
        committed = int(row["committed_cents"])
        spent = int(row["spent_cents"])
        revenue = int(row["attributed_revenue_cents"])
        used = int(row["reserved_count"]) + int(row["redemption_count"])
        claims = connection.execute("SELECT COUNT(*) AS users, COALESCE(SUM(claimed_quantity), 0) AS quantity, COALESCE(SUM(used_quantity), 0) AS used_quantity FROM platform_campaign_claims WHERE campaign_id = ?", (row["id"],)).fetchone()
        audiences = connection.execute("SELECT COUNT(*) FROM campaign_audiences WHERE campaign_id = ?", (row["id"],)).fetchone()[0]
        issuances = connection.execute("SELECT COUNT(*) AS batches, COALESCE(SUM(issued_quantity), 0) AS quantity FROM campaign_coupon_issuances WHERE campaign_id = ?", (row["id"],)).fetchone()
        codes = connection.execute("SELECT COUNT(*) AS total, COALESCE(SUM(CASE WHEN status = 'issued' THEN 1 ELSE 0 END), 0) AS issued, COALESCE(SUM(CASE WHEN status = 'redeemed' THEN 1 ELSE 0 END), 0) AS redeemed, COALESCE(SUM(CASE WHEN status = 'expired' THEN 1 ELSE 0 END), 0) AS expired FROM campaign_coupon_codes WHERE campaign_id = ?", (row["id"],)).fetchone()
        result.append({
            "id": row["id"], "name": row["name"], "type": row["campaign_type"], "status": row["status"],
            "rule": json.loads(row["rule_json"] or "{}"), "startsAt": row["starts_at"], "endsAt": row["ends_at"],
            "budget": row["budget_cents"] / 100 if row["budget_cents"] is not None else None,
            "budgetRemaining": max(0, row["budget_cents"] - committed) / 100 if row["budget_cents"] is not None else None,
            "totalUsageLimit": row["total_usage_limit"], "perUserUsageLimit": row["per_user_usage_limit"],
            "reserved": int(row["reserved_count"]), "redemptions": int(row["redemption_count"]), "reversed": int(row["reversed_count"]),
            "spent": spent / 100, "attributedRevenue": revenue / 100, "roi": round(revenue / spent, 2) if spent else None,
            "attributedOrders": int(row["redemption_count"]), "redemptionRate": round(int(row["redemption_count"]) / int(claims["quantity"]) * 100, 2) if claims["quantity"] else 0,
            "averageOrderValue": round(revenue / int(row["redemption_count"]) / 100, 2) if row["redemption_count"] else 0,
            "usageRemaining": max(0, row["total_usage_limit"] - used) if row["total_usage_limit"] is not None else None,
            "claimUsers": int(claims["users"]), "claimedQuantity": int(claims["quantity"]), "usedQuantity": int(claims["used_quantity"]),
            "audienceCount": int(audiences), "issuedBatches": int(issuances["batches"]), "directIssuedQuantity": int(issuances["quantity"]),
            "codeTotal": int(codes["total"]), "codeIssued": int(codes["issued"]), "codeRedeemed": int(codes["redeemed"]), "codeExpired": int(codes["expired"]),
            "claimToRedeemRate": round(int(row["redemption_count"]) / int(claims["quantity"]) * 100, 2) if claims["quantity"] else 0,
        })
    return result


def campaign_coupon_targets(connection: sqlite3.Connection, segment: str | None) -> list[str]:
    if not segment:
        return []
    if segment == "all_buyers":
        rows = connection.execute("SELECT DISTINCT user_id FROM user_roles WHERE role = 'buyer'").fetchall()
    elif segment == "new_buyers":
        rows = connection.execute("SELECT DISTINCT roles.user_id FROM user_roles AS roles WHERE roles.role = 'buyer' AND NOT EXISTS (SELECT 1 FROM orders WHERE orders.buyer_user_id = roles.user_id AND orders.status NOT IN ('cancelled', 'refunded', 'pending_payment'))").fetchall()
    elif segment == "repeat_buyers":
        rows = connection.execute("SELECT buyer_user_id FROM orders WHERE status NOT IN ('cancelled', 'refunded', 'pending_payment') GROUP BY buyer_user_id HAVING COUNT(*) >= 2").fetchall()
    elif segment == "inactive_30d":
        rows = connection.execute("SELECT DISTINCT roles.user_id FROM user_roles AS roles WHERE roles.role = 'buyer' AND EXISTS (SELECT 1 FROM orders WHERE orders.buyer_user_id = roles.user_id AND orders.status NOT IN ('cancelled', 'refunded', 'pending_payment')) AND NOT EXISTS (SELECT 1 FROM orders WHERE orders.buyer_user_id = roles.user_id AND orders.paid_at >= datetime('now', '-30 days') AND orders.status NOT IN ('cancelled', 'refunded', 'pending_payment'))").fetchall()
    else:
        raise ValueError("目标人群无效")
    return [str(row[0]) for row in rows]


def issue_campaign_coupons(
    connection: sqlite3.Connection,
    campaign_id: str,
    buyer_ids: list[str],
    quantity: int,
    source: str,
    operator_user_id: str,
) -> dict:
    campaign = connection.execute("SELECT campaign_type, per_user_claim_limit FROM platform_campaigns WHERE id = ?", (campaign_id,)).fetchone()
    if not campaign or campaign[0] != "coupon":
        raise ValueError("优惠券活动不存在")
    issued_users, issued_quantity, skipped = 0, 0, 0
    for buyer_id in buyer_ids:
        if not connection.execute("SELECT 1 FROM users JOIN user_roles ON user_roles.user_id = users.id WHERE users.id = ? AND users.status = 'active' AND user_roles.role = 'buyer'", (buyer_id,)).fetchone():
            skipped += 1
            continue
        claim = connection.execute("SELECT id, claimed_quantity FROM platform_campaign_claims WHERE campaign_id = ? AND buyer_user_id = ?", (campaign_id, buyer_id)).fetchone()
        claimed = int(claim[1]) if claim else 0
        grant = min(quantity, max(0, int(campaign[1]) - claimed))
        if not grant:
            skipped += 1
            continue
        if claim:
            connection.execute("UPDATE platform_campaign_claims SET claimed_quantity = claimed_quantity + ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (grant, claim[0]))
        else:
            connection.execute("INSERT INTO platform_campaign_claims (id, campaign_id, buyer_user_id, claimed_quantity) VALUES (?, ?, ?, ?)", (f"campaign-claim-{secrets.token_urlsafe(10)}", campaign_id, buyer_id, grant))
        connection.execute("INSERT INTO campaign_coupon_issuances (id, campaign_id, buyer_user_id, source, issued_quantity, created_by_user_id) VALUES (?, ?, ?, ?, ?, ?)", (f"coupon-issuance-{secrets.token_urlsafe(10)}", campaign_id, buyer_id, source, grant, operator_user_id))
        issued_users += 1
        issued_quantity += grant
    return {"users": issued_users, "quantity": issued_quantity, "skipped": skipped}


def run_coupon_expiry_reminders() -> int:
    connection = database()
    try:
        connection.row_factory = sqlite3.Row
        connection.execute("UPDATE campaign_coupon_codes SET status = 'expired' WHERE status = 'issued' AND expires_at IS NOT NULL AND expires_at <= CURRENT_TIMESTAMP")
        reminders = 0
        campaigns = connection.execute("SELECT id, name FROM platform_campaigns WHERE campaign_type = 'coupon' AND status = 'active' AND ends_at > CURRENT_TIMESTAMP AND ends_at <= datetime('now', '+3 days')").fetchall()
        for campaign in campaigns:
            buyers = connection.execute("SELECT buyer_user_id FROM platform_campaign_claims WHERE campaign_id = ? AND claimed_quantity > used_quantity", (campaign["id"],)).fetchall()
            for buyer in buyers:
                inserted = connection.execute("INSERT OR IGNORE INTO campaign_coupon_reminders (id, campaign_id, buyer_user_id, reminder_type) VALUES (?, ?, ?, 'campaign_expiring')", (f"coupon-reminder-{secrets.token_urlsafe(8)}", campaign["id"], buyer["buyer_user_id"])).rowcount
                if inserted:
                    notify_governance(connection, buyer["buyer_user_id"], "coupon_expiring", "优惠券即将失效", f"{campaign['name']} 将在 3 天内结束，请及时使用", "campaign", campaign["id"])
                    reminders += 1
        codes = connection.execute("SELECT codes.id, codes.campaign_id, codes.assigned_user_id, campaigns.name FROM campaign_coupon_codes AS codes JOIN platform_campaigns AS campaigns ON campaigns.id = codes.campaign_id WHERE codes.status = 'issued' AND codes.assigned_user_id IS NOT NULL AND codes.expires_at > CURRENT_TIMESTAMP AND codes.expires_at <= datetime('now', '+3 days')").fetchall()
        for code in codes:
            inserted = connection.execute("INSERT OR IGNORE INTO campaign_coupon_reminders (id, campaign_id, buyer_user_id, reminder_type, code_id) VALUES (?, ?, ?, 'code_expiring', ?)", (f"coupon-reminder-{secrets.token_urlsafe(8)}", code["campaign_id"], code["assigned_user_id"], code["id"])).rowcount
            if inserted:
                notify_governance(connection, code["assigned_user_id"], "coupon_code_expiring", "专属券码即将失效", f"{code['name']} 的专属券码将在 3 天内失效", "campaign", code["campaign_id"])
                reminders += 1
        connection.commit()
        return reminders
    finally:
        connection.close()


def normalize_search_term(value: str) -> str:
    """Normalize whitespace and punctuation without changing Chinese search intent."""
    return re.sub(r"[\s\-_./,，、]+", " ", value.strip().lower())[:50].strip()


def edit_distance(left: str, right: str, limit: int = 2) -> int:
    if abs(len(left) - len(right)) > limit:
        return limit + 1
    previous = list(range(len(right) + 1))
    for index, left_char in enumerate(left, 1):
        current = [index]
        smallest = current[0]
        for right_index, right_char in enumerate(right, 1):
            value = min(previous[right_index] + 1, current[right_index - 1] + 1, previous[right_index - 1] + (left_char != right_char))
            current.append(value)
            smallest = min(smallest, value)
        if smallest > limit:
            return limit + 1
        previous = current
    return previous[-1]


def automatic_search_correction(connection: sqlite3.Connection, term: str) -> str | None:
    """Use a conservative edit-distance match against searchable vocabulary."""
    if len(term) < 3:
        return None
    candidates = {str(row[0]).strip().lower() for row in connection.execute("SELECT typo FROM search_corrections WHERE enabled = 1 UNION SELECT corrected_term FROM search_corrections WHERE enabled = 1 UNION SELECT source_term FROM search_synonyms WHERE enabled = 1 UNION SELECT category FROM products WHERE status = 'published' UNION SELECT material FROM products WHERE status = 'published' LIMIT 300") if row[0]}
    candidates.update(str(row[0]).strip().lower() for row in connection.execute("SELECT DISTINCT tag FROM product_seo_tags LIMIT 300") if row[0])
    best, best_distance = None, 3
    for candidate in candidates:
        if not candidate or " " in candidate or len(candidate) > 24:
            continue
        distance = edit_distance(term, candidate, 1 if len(term) <= 5 else 2)
        if distance < best_distance:
            best, best_distance = candidate, distance
    return best


def expanded_search_terms(connection: sqlite3.Connection, normalized: str) -> list[str]:
    terms = [normalized]
    # Phrase and words are both useful for a query such as "handmade mug".
    terms.extend(token for token in re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]{2,}", normalized) if len(token) >= 2)
    for source in list(terms):
        row = connection.execute("SELECT target_terms_json FROM search_synonyms WHERE source_term = ? AND enabled = 1", (source,)).fetchone()
        if not row:
            continue
        try:
            terms.extend(normalize_search_term(str(item)) for item in json.loads(row[0]) if normalize_search_term(str(item)))
        except (TypeError, json.JSONDecodeError):
            continue
    return list(dict.fromkeys(term for term in terms if term))[:12]


def semantic_tokens(value: str) -> set[str]:
    """Small, deterministic semantic representation for a SQLite-only deployment."""
    normalized = normalize_search_term(value)
    latin = re.findall(r"[a-z0-9]{2,}", normalized)
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", normalized))
    grams = {chinese[index:index + 2] for index in range(max(0, len(chinese) - 1))}
    return set(latin) | grams | ({chinese} if 1 < len(chinese) <= 4 else set())


def semantic_similarity(query: str, document: str) -> float:
    query_tokens, document_tokens = semantic_tokens(query), semantic_tokens(document)
    if not query_tokens or not document_tokens:
        return 0.0
    return len(query_tokens & document_tokens) / len(query_tokens | document_tokens)


SEMANTIC_CONCEPTS = (
    ("杯", "杯子", "咖啡杯", "茶杯", "马克杯", "mug", "cup"),
    ("陶艺", "陶瓷", "瓷器", "ceramic", "pottery"),
    ("织物", "布艺", "纺织", "布料", "textile", "fabric"),
    ("首饰", "饰品", "项链", "耳环", "jewelry", "jewellery"),
    ("木作", "木工", "木器", "woodwork", "wood"),
)


def semantic_expanded_terms(terms: list[str]) -> list[str]:
    expanded = list(terms)
    for term in terms:
        for concept in SEMANTIC_CONCEPTS:
            if any(alias in term or term in alias for alias in concept):
                expanded.extend(concept)
    return list(dict.fromkeys(normalize_search_term(term) for term in expanded if normalize_search_term(term)))[:24]


def search_preference_profile(connection: sqlite3.Connection, user_id: str | None) -> tuple[dict[str, float], dict[str, float]]:
    """Derive a transparent preference profile from the user's persisted commerce activity."""
    if not user_id:
        return {}, {}
    category_weights: dict[str, float] = {}
    tag_weights: dict[str, float] = {}
    sources = (
        ("SELECT products.category, products.id, 1.0 AS weight FROM analytics_events JOIN products ON products.id = analytics_events.product_id WHERE analytics_events.user_id = ? AND analytics_events.event_type = 'product_view'", (user_id,)),
        ("SELECT products.category, products.id, 3.0 AS weight FROM analytics_events JOIN products ON products.id = analytics_events.product_id WHERE analytics_events.user_id = ? AND analytics_events.event_type = 'add_cart'", (user_id,)),
        ("SELECT products.category, products.id, 4.0 AS weight FROM buyer_favorites JOIN products ON products.id = buyer_favorites.product_id WHERE buyer_favorites.buyer_user_id = ?", (user_id,)),
        ("SELECT products.category, products.id, 6.0 AS weight FROM order_items JOIN orders ON orders.id = order_items.order_id JOIN products ON products.id = order_items.product_id WHERE orders.buyer_user_id = ? AND orders.status NOT IN ('cancelled', 'refunded', 'pending_payment')", (user_id,)),
    )
    for statement, params in sources:
        for row in connection.execute(statement, params):
            category_weights[row["category"]] = category_weights.get(row["category"], 0) + float(row["weight"])
            for tag in connection.execute("SELECT tag FROM product_seo_tags WHERE product_id = ?", (row["id"],)):
                tag_weights[tag[0]] = tag_weights.get(tag[0], 0) + float(row["weight"])
    return category_weights, tag_weights


def personal_recommendations(connection: sqlite3.Connection, user_id: str | None, limit: int = 8) -> list[dict]:
    connection.row_factory = sqlite3.Row
    categories, tags = search_preference_profile(connection, user_id)
    if not categories and not tags:
        return []
    rows = connection.execute(
        """
        SELECT products.id, products.category, products.published_at,
               COALESCE(GROUP_CONCAT(product_seo_tags.tag, ' '), '') AS tags,
               COALESCE((SELECT SUM(order_items.quantity) FROM order_items JOIN orders ON orders.id = order_items.order_id WHERE order_items.product_id = products.id AND orders.status NOT IN ('cancelled', 'refunded', 'pending_payment')), 0) AS sales
        FROM products LEFT JOIN product_seo_tags ON product_seo_tags.product_id = products.id
        WHERE products.status = 'published'
        GROUP BY products.id
        LIMIT 160
        """
    ).fetchall()
    catalog_items = {item["catalogId"]: item for item in catalog()}
    def score(row: sqlite3.Row) -> float:
        matched_tags = sum(tags.get(tag, 0) for tag in str(row["tags"] or "").split())
        return categories.get(row["category"], 0) * 8 + matched_tags * 4 + min(int(row["sales"] or 0), 100) * 0.15
    ranked = sorted(rows, key=lambda row: (score(row), str(row["published_at"] or "")), reverse=True)
    return [catalog_items[row["id"]] for row in ranked[:limit] if row["id"] in catalog_items and score(row) > 0]


def search_catalog(keyword: str, category: str, sort: str, terms: list[str] | None = None, user_id: str | None = None) -> list[dict]:
    keyword = normalize_search_term(keyword)
    with database() as connection:
        connection.row_factory = sqlite3.Row
        ensure_product_codes(connection)
        where, params = ["products.status = 'published'"], []
        if category and category != "全部":
            where.append("products.category = ?")
            params.append(category)
        search_terms = semantic_expanded_terms(list(dict.fromkeys(normalize_search_term(term) for term in (terms or [keyword]) if normalize_search_term(term)))[:12])
        rows = connection.execute(
            f"""
            SELECT products.id, products.product_code, products.title, products.description, products.material,
                   products.buyer_title, products.buyer_description, products.buyer_material, products.buyer_seo_tags_json,
                   products.category,
                   shops.name AS shop_name, products.price_cents, products.published_at,
                   COALESCE(GROUP_CONCAT(product_seo_tags.tag, ' '), '') AS tags,
                   COALESCE((SELECT SUM(order_items.quantity) FROM order_items JOIN orders ON orders.id = order_items.order_id WHERE order_items.product_id = products.id AND orders.status NOT IN ('cancelled', 'refunded', 'pending_payment')), 0) AS sales
            FROM products JOIN shops ON shops.id = products.shop_id
            LEFT JOIN product_seo_tags ON product_seo_tags.product_id = products.id
            WHERE {' AND '.join(where)}
            GROUP BY products.id
            LIMIT 120
            """,
            params,
        ).fetchall()
        preferred_categories, preferred_tags = search_preference_profile(connection, user_id)
    def score(row: sqlite3.Row) -> float:
        code, title, description, material, buyer_title, buyer_description, buyer_material, buyer_tags, product_category, shop, tags = (
            str(row[key] or "").lower()
            for key in (
                "product_code", "title", "description", "material", "buyer_title",
                "buyer_description", "buyer_material", "buyer_seo_tags_json",
                "category", "shop_name", "tags",
            )
        )
        value = min(int(row["sales"] or 0), 100) * 0.18
        for term in search_terms:
            if code == term:
                value += 180
            elif term in code:
                value += 80
            if title == term:
                value += 150
            elif title.startswith(term):
                value += 92
            elif term in title:
                value += 56
            if buyer_title == term:
                value += 150
            elif buyer_title.startswith(term):
                value += 92
            elif term in buyer_title:
                value += 56
            if term in tags:
                value += 38
            if term in buyer_tags:
                value += 38
            if term in product_category or term in material or term in buyer_material:
                value += 27
            if term in description or term in buyer_description:
                value += 14
            if term in shop:
                value += 9
        semantic_text = " ".join((
            code, title, description, material, buyer_title, buyer_description,
            buyer_material, buyer_tags, product_category, shop, tags,
        ))
        value += max((semantic_similarity(term, semantic_text) for term in search_terms), default=0) * 45
        value += preferred_categories.get(product_category, 0) * 2
        value += sum(preferred_tags.get(tag, 0) for tag in tags.split())
        return value
    records = list(rows)
    if sort == "latest":
        records.sort(key=lambda row: str(row["published_at"] or ""), reverse=True)
    elif sort == "price_asc":
        records.sort(key=lambda row: int(row["price_cents"] or 0))
    elif sort == "price_desc":
        records.sort(key=lambda row: int(row["price_cents"] or 0), reverse=True)
    elif sort == "sales":
        records.sort(key=lambda row: (int(row["sales"] or 0), score(row)), reverse=True)
    else:
        records.sort(key=lambda row: (score(row), int(row["sales"] or 0), str(row["published_at"] or "")), reverse=True)
    # Preserve strict keyword behavior for exact sorts, while allowing semantic recall for relevance.
    if search_terms and sort != "relevance":
        records = [
            row for row in records
            if any(
                term in " ".join(
                    str(row[key] or "").lower()
                    for key in (
                        "product_code", "title", "description", "material", "buyer_title",
                        "buyer_description", "buyer_material", "buyer_seo_tags_json",
                        "category", "shop_name", "tags",
                    )
                )
                for term in search_terms
            )
        ]
    items = {item["catalogId"]: item for item in catalog()}
    return [items[row["id"]] for row in records[:60] if row["id"] in items and (not search_terms or score(row) > 0)]


def search_suggestions(connection: sqlite3.Connection, keyword: str, user_id: str | None) -> list[dict]:
    connection.row_factory = sqlite3.Row
    term = normalize_search_term(keyword)
    suggestions: list[dict] = []
    seen: set[str] = set()
    def add(value: str, kind: str, hint: str = "") -> None:
        value = str(value or "").strip()
        key = value.lower()
        if value and key not in seen and key != term:
            seen.add(key)
            suggestions.append({"value": value, "type": kind, "hint": hint})
    if user_id:
        for row in connection.execute("SELECT keyword FROM search_history WHERE user_id = ? AND (? = '' OR lower(keyword) LIKE ?) GROUP BY keyword ORDER BY MAX(created_at) DESC LIMIT 5", (user_id, term, f"%{term}%")):
            add(row[0], "history", "最近搜索")
    if term:
        for row in connection.execute(
            "SELECT CASE WHEN TRIM(buyer_title) != '' THEN buyer_title ELSE title END AS title FROM products WHERE status = 'published' AND (lower(title) LIKE ? OR lower(buyer_title) LIKE ?) ORDER BY published_at DESC LIMIT 5",
            (f"%{term}%", f"%{term}%"),
        ):
            add(row[0], "product", "作品")
        for row in connection.execute("SELECT DISTINCT tag FROM product_seo_tags WHERE lower(tag) LIKE ? LIMIT 5", (f"%{term}%",)):
            add(row[0], "tag", "标签")
    for row in connection.execute("SELECT recommendation FROM search_recommendations WHERE enabled = 1 AND (? = '' OR lower(keyword) = ? OR lower(recommendation) LIKE ?) ORDER BY weight DESC LIMIT 6", (term, term, f"%{term}%")):
        add(row[0], "recommendation", "推荐搜索")
    for row in connection.execute("SELECT keyword FROM search_query_metrics WHERE keyword != '' AND (? = '' OR lower(keyword) LIKE ?) GROUP BY keyword ORDER BY COUNT(*) DESC, MAX(created_at) DESC LIMIT 8", (term, f"%{term}%")):
        add(row[0], "trending", "热门搜索")
    return suggestions[:10]


def search_operations(connection: sqlite3.Connection, keyword: str) -> dict:
    connection.row_factory = sqlite3.Row
    original = normalize_search_term(keyword)
    correction = connection.execute("SELECT corrected_term FROM search_corrections WHERE typo = ? AND enabled = 1", (original,)).fetchone()
    normalized, correction_source = (normalize_search_term(correction[0]), "rule") if correction else (original, None)
    if not correction and original:
        automatic = automatic_search_correction(connection, original)
        if automatic:
            normalized, correction_source = automatic, "automatic"
    terms = expanded_search_terms(connection, normalized)
    recommendations = [row[0] for row in connection.execute("SELECT recommendation FROM search_recommendations WHERE keyword IN (?, ?) AND enabled = 1 ORDER BY weight DESC LIMIT 8", (original, normalized))]
    return {"original": original, "normalized": normalized, "terms": terms, "corrected": normalized if correction_source else None, "correctionSource": correction_source, "recommendations": list(dict.fromkeys(recommendations))}


def search_operations_payload(connection: sqlite3.Connection, days: int = 30) -> dict:
    """Return search configuration and query metrics for the operations console."""
    connection.row_factory = sqlite3.Row
    days = days if days in (1, 7, 30) else 30
    since = f"-{days} days"
    synonym_rows = connection.execute("SELECT * FROM search_synonyms ORDER BY updated_at DESC LIMIT 100").fetchall()
    correction_rows = connection.execute("SELECT * FROM search_corrections ORDER BY updated_at DESC LIMIT 100").fetchall()
    recommendation_rows = connection.execute("SELECT * FROM search_recommendations ORDER BY weight DESC, updated_at DESC LIMIT 100").fetchall()
    zero_rows = connection.execute("SELECT rules.*, products.title AS product_title FROM search_zero_result_rules AS rules LEFT JOIN products ON products.id = rules.product_id ORDER BY rules.updated_at DESC LIMIT 100").fetchall()
    summary = connection.execute(
        "SELECT COUNT(*) AS searches, COALESCE(SUM(CASE WHEN result_count = 0 THEN 1 ELSE 0 END), 0) AS zero_results, COALESCE(SUM(CASE WHEN corrected_keyword IS NOT NULL AND corrected_keyword != '' THEN 1 ELSE 0 END), 0) AS corrections FROM search_query_metrics WHERE created_at >= datetime('now', ?)",
        (since,),
    ).fetchone()
    terms = connection.execute(
        "SELECT keyword, COUNT(*) AS searches, SUM(CASE WHEN result_count = 0 THEN 1 ELSE 0 END) AS zeroResults, SUM(CASE WHEN corrected_keyword IS NOT NULL AND corrected_keyword != '' THEN 1 ELSE 0 END) AS corrections FROM search_query_metrics WHERE keyword != '' AND created_at >= datetime('now', ?) GROUP BY keyword ORDER BY searches DESC, zeroResults DESC LIMIT 20",
        (since,),
    ).fetchall()
    zero_terms = connection.execute(
        "SELECT keyword, COUNT(*) AS searches FROM search_query_metrics WHERE keyword != '' AND result_count = 0 AND created_at >= datetime('now', ?) GROUP BY keyword ORDER BY searches DESC LIMIT 20",
        (since,),
    ).fetchall()
    daily = connection.execute(
        "SELECT substr(created_at, 1, 10) AS date, COUNT(*) AS searches, SUM(CASE WHEN result_count = 0 THEN 1 ELSE 0 END) AS zeroResults FROM search_query_metrics WHERE created_at >= datetime('now', ?) GROUP BY substr(created_at, 1, 10) ORDER BY date ASC",
        (since,),
    ).fetchall()
    return {
        "days": days,
        "rules": {
            "synonyms": [{"id": row["id"], "source": row["source_term"], "target": json.loads(row["target_terms_json"]), "enabled": bool(row["enabled"]), "updatedAt": row["updated_at"]} for row in synonym_rows],
            "corrections": [{"id": row["id"], "source": row["typo"], "target": row["corrected_term"], "enabled": bool(row["enabled"]), "updatedAt": row["updated_at"]} for row in correction_rows],
            "recommendations": [{"id": row["id"], "source": row["keyword"], "target": row["recommendation"], "weight": row["weight"], "enabled": bool(row["enabled"]), "updatedAt": row["updated_at"]} for row in recommendation_rows],
            "zeroResults": [{"id": row["id"], "source": row["keyword"], "message": row["message"], "productId": row["product_id"], "productTitle": row["product_title"], "enabled": bool(row["enabled"]), "updatedAt": row["updated_at"]} for row in zero_rows],
        },
        "summary": {"searches": summary["searches"], "zeroResults": summary["zero_results"], "corrections": summary["corrections"], "zeroRate": round(summary["zero_results"] * 100 / summary["searches"], 1) if summary["searches"] else 0},
        "terms": [dict(row) for row in terms],
        "zeroTerms": [dict(row) for row in zero_terms],
        "daily": [dict(row) for row in daily],
    }


def platform_campaign_for_charge(connection: sqlite3.Connection, buyer_user_id: str, item_amount: int, provisional_usage: dict[str, tuple[int, int]] | None = None) -> dict | None:
    rows = connection.execute("SELECT * FROM platform_campaigns WHERE status = 'active' AND (starts_at IS NULL OR starts_at <= CURRENT_TIMESTAMP) AND (ends_at IS NULL OR ends_at > CURRENT_TIMESTAMP)").fetchall()
    eligible: list[dict] = []
    for row in rows:
        try:
            rule = json.loads(row["rule_json"] or "{}")
            threshold = max(0, int(round(number(rule.get("threshold")) * 100)))
            discount = max(0, int(round(number(rule.get("discount")) * 100)))
            if item_amount < threshold or not discount:
                continue
            claim = None
            if row["campaign_type"] == "coupon":
                claim = connection.execute("SELECT * FROM platform_campaign_claims WHERE campaign_id = ? AND buyer_user_id = ? AND used_quantity < claimed_quantity", (row["id"], buyer_user_id)).fetchone()
                if not claim:
                    continue
            committed = connection.execute("SELECT COUNT(*) AS usage, COALESCE(SUM(discount_amount_cents), 0) AS amount FROM platform_campaign_redemptions WHERE campaign_id = ? AND status IN ('reserved', 'redeemed')", (row["id"],)).fetchone()
            buyer_usage = connection.execute("SELECT COUNT(*) FROM platform_campaign_redemptions WHERE campaign_id = ? AND buyer_user_id = ? AND status IN ('reserved', 'redeemed')", (row["id"], buyer_user_id)).fetchone()[0]
            extra_usage, extra_amount = (provisional_usage or {}).get(row["id"], (0, 0))
            if row["total_usage_limit"] is not None and int(committed["usage"]) + extra_usage >= row["total_usage_limit"]:
                continue
            if buyer_usage + extra_usage >= row["per_user_usage_limit"]:
                continue
            if row["budget_cents"] is not None and int(committed["amount"]) + extra_amount + discount > row["budget_cents"]:
                continue
            eligible.append({"id": row["id"], "name": row["name"], "discount": min(discount, item_amount), "claimId": claim["id"] if claim else None})
        except (TypeError, ValueError, json.JSONDecodeError):
            continue
    return max(eligible, key=lambda item: item["discount"], default=None)


def shop_promotion_is_current(promotion: dict) -> bool:
    if promotion.get("type") != "limited_time":
        return True
    try:
        now = datetime.now()
        starts_at = datetime.fromisoformat(str(promotion.get("startsAt") or ""))
        ends_at = datetime.fromisoformat(str(promotion.get("endsAt") or ""))
        return starts_at <= now <= ends_at
    except (TypeError, ValueError):
        return False


def shop_promotion_discount(promotion: dict, item_amount: int) -> int:
    try:
        threshold = max(0, int(round(number(promotion.get("threshold")) * 100)))
        if item_amount < threshold or not shop_promotion_is_current(promotion):
            return 0
        if promotion.get("type") == "full_discount":
            rate = number(promotion.get("rate"))
            if rate <= 0 or rate > 10:
                return 0
            return max(0, int(round(item_amount * (10 - rate) / 10)))
        return max(0, int(round(number(promotion.get("discount")) * 100)))
    except (TypeError, ValueError):
        return 0


def shipping_amount_cents(value: object, field: str) -> int:
    try:
        amount = float(value)
    except (TypeError, ValueError):
        raise ValueError(f"配送规则的{field}无效")
    if not math.isfinite(amount) or amount < 0 or amount > 100000:
        raise ValueError(f"配送规则的{field}必须在 0 到 100000 美元之间")
    return int(round(amount * 100))


def shipping_text(value: object, field: str, limit: int = 80) -> str:
    text = str(value or "").strip()
    if not text or len(text) > limit:
        raise ValueError(f"配送规则的{field}不能为空且不能超过 {limit} 个字符")
    return text


def default_shipping_template(template: dict) -> dict:
    """Convert the previous single-rate template into safe international defaults."""
    first_fee = max(0, number(template.get("firstFee")))
    additional_fee = max(0, number(template.get("additionalFee")))
    free_threshold = max(0, number(template.get("freeShippingThreshold")))
    carrier = str(template.get("carrier") or "顺丰国际").strip() or "顺丰国际"
    return {
        "name": str(template.get("name") or "国际配送")[:80] or "国际配送",
        "currency": PLATFORM_CURRENCY,
        "zones": [
            {
                "id": "north-america", "name": "北美地区", "countries": list(DEFAULT_NORTH_AMERICA_COUNTRIES),
                "carrier": carrier, "firstFee": first_fee, "additionalFee": additional_fee,
                "freeShippingThreshold": free_threshold, "minDeliveryDays": 7, "maxDeliveryDays": 12, "enabled": True,
            },
            {
                "id": "europe", "name": "欧洲地区", "countries": list(DEFAULT_EUROPE_COUNTRIES),
                "carrier": carrier, "firstFee": first_fee, "additionalFee": additional_fee,
                "freeShippingThreshold": free_threshold, "minDeliveryDays": 8, "maxDeliveryDays": 16, "enabled": True,
            },
        ],
        # Kept for API clients that have not yet upgraded to zone rendering.
        "firstFee": first_fee, "additionalFee": additional_fee, "freeShippingThreshold": free_threshold,
    }


def normalize_shipping_template(template: object) -> dict:
    if not isinstance(template, dict):
        raise ValueError("运费模板必须是对象")
    raw_zones = template.get("zones")
    if not isinstance(raw_zones, list):
        return default_shipping_template(template)
    if not raw_zones or len(raw_zones) > 8:
        raise ValueError("请设置 1 到 8 个配送区域")
    zones = []
    used_ids: set[str] = set()
    enabled_countries: set[str] = set()
    for index, raw_zone in enumerate(raw_zones):
        if not isinstance(raw_zone, dict):
            raise ValueError("配送区域格式无效")
        zone_id = str(raw_zone.get("id") or f"zone-{index + 1}").strip().lower()
        if not re.fullmatch(r"[a-z0-9-]{1,40}", zone_id) or zone_id in used_ids:
            raise ValueError("配送区域标识无效或重复")
        used_ids.add(zone_id)
        countries = []
        for country in raw_zone.get("countries") or []:
            code = str(country or "").strip().upper()
            if code not in SHIPPING_COUNTRIES or code in countries:
                raise ValueError("配送国家仅支持当前开放的北美和欧洲国家，且不能重复")
            countries.append(code)
        if not countries:
            raise ValueError("每个配送区域至少选择一个目的国家")
        enabled = bool(raw_zone.get("enabled", True))
        if enabled and enabled_countries.intersection(countries):
            raise ValueError("同一目的国家不能同时属于多个已启用配送区域")
        if enabled:
            enabled_countries.update(countries)
        try:
            min_days = int(raw_zone.get("minDeliveryDays", 7))
            max_days = int(raw_zone.get("maxDeliveryDays", 14))
        except (TypeError, ValueError):
            raise ValueError("预计送达时效必须是整数天")
        if not (1 <= min_days <= max_days <= 90):
            raise ValueError("预计送达时效必须在 1 到 90 天之间，且最短不大于最长")
        zones.append({
            "id": zone_id,
            "name": shipping_text(raw_zone.get("name"), "区域名称"),
            "countries": countries,
            "carrier": shipping_text(raw_zone.get("carrier") or "SF International", "物流商"),
            "firstFee": shipping_amount_cents(raw_zone.get("firstFee", 0), "首件运费") / 100,
            "additionalFee": shipping_amount_cents(raw_zone.get("additionalFee", 0), "续件运费") / 100,
            "freeShippingThreshold": shipping_amount_cents(raw_zone.get("freeShippingThreshold", 0), "免邮门槛") / 100,
            "minDeliveryDays": min_days, "maxDeliveryDays": max_days, "enabled": enabled,
        })
    first_zone = zones[0]
    return {
        "name": shipping_text(template.get("name") or "国际配送", "模板名称"),
        "currency": PLATFORM_CURRENCY,
        "zones": zones,
        "firstFee": first_zone["firstFee"], "additionalFee": first_zone["additionalFee"],
        "freeShippingThreshold": first_zone["freeShippingThreshold"],
    }


def shipping_quote_for_destination(template: object, country_code: str, item_amount: int, quantity: int) -> dict:
    normalized = normalize_shipping_template(template)
    country_code = str(country_code or "").strip().upper()
    zone = next((item for item in normalized["zones"] if item["enabled"] and country_code in item["countries"]), None)
    if not zone:
        destination = SHIPPING_COUNTRIES.get(country_code, country_code or "the selected destination")
        raise ValueError(f"该店铺暂不配送至 {destination}，请更换地址或移除该店商品")
    first_fee = int(round(zone["firstFee"] * 100))
    additional_fee = int(round(zone["additionalFee"] * 100))
    threshold = int(round(zone["freeShippingThreshold"] * 100))
    shipping_amount = 0 if threshold and item_amount >= threshold else first_fee + max(0, quantity - 1) * additional_fee
    return {
        "zoneId": zone["id"], "zoneName": zone["name"], "carrier": zone["carrier"],
        "minDeliveryDays": zone["minDeliveryDays"], "maxDeliveryDays": zone["maxDeliveryDays"],
        "destinationCountryCode": country_code, "destinationCountry": SHIPPING_COUNTRIES[country_code],
        "firstFee": zone["firstFee"], "additionalFee": zone["additionalFee"],
        "freeShippingThreshold": zone["freeShippingThreshold"], "shippingAmountCents": shipping_amount,
        "currency": PLATFORM_CURRENCY,
    }


def shop_charge(connection: sqlite3.Connection, shop_id: str, buyer_user_id: str, item_amount: int, quantity: int, country_code: str, provisional_usage: dict[str, tuple[int, int]] | None = None) -> tuple[int, int, dict | None, dict]:
    shop = connection.execute(
        "SELECT shipping_template_json, coupons_json FROM shops WHERE id = ?", (shop_id,)
    ).fetchone()
    try:
        shipping = json.loads(shop["shipping_template_json"] or "{}") if shop else {}
    except json.JSONDecodeError:
        shipping = {}
    shipping_rule = shipping_quote_for_destination(shipping, country_code, item_amount, quantity)
    shipping_amount = shipping_rule["shippingAmountCents"]
    try:
        coupons = json.loads(shop["coupons_json"] or "[]") if shop else []
    except json.JSONDecodeError:
        coupons = []
    discount = max((shop_promotion_discount(promotion, item_amount) for promotion in coupons if isinstance(promotion, dict)), default=0)
    campaign = platform_campaign_for_charge(connection, buyer_user_id, item_amount, provisional_usage)
    discount += campaign["discount"] if campaign else 0
    return shipping_amount, min(discount, item_amount + shipping_amount), campaign, shipping_rule


def record_order_resource_event(
    connection: sqlite3.Connection,
    order_id: str,
    resource_type: str,
    resource_id: str,
    action: str,
    quantity: int = 0,
    amount_cents: int = 0,
    detail: dict | None = None,
) -> None:
    connection.execute(
        """
        INSERT INTO order_resource_events
          (id, order_id, resource_type, resource_id, action, quantity, amount_cents, detail_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            f"resource-event-{secrets.token_urlsafe(10)}", order_id, resource_type, resource_id,
            action, max(0, quantity), max(0, amount_cents), json.dumps(detail or {}, ensure_ascii=False),
        ),
    )


def set_campaign_redemption_status(connection: sqlite3.Connection, order_id: str, status: str) -> None:
    redemption = connection.execute(
        "SELECT campaign_id, claim_id, discount_amount_cents FROM platform_campaign_redemptions WHERE order_id = ?",
        (order_id,),
    ).fetchone()
    if not redemption:
        return
    if status == "redeemed":
        changed = connection.execute("UPDATE platform_campaign_redemptions SET status = 'redeemed', redeemed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE order_id = ? AND status = 'reserved'", (order_id,)).rowcount
        if changed:
            record_order_resource_event(connection, order_id, "campaign_coupon", redemption["campaign_id"], "redeemed", amount_cents=redemption["discount_amount_cents"])
    elif status in ("released", "reversed"):
        changed = connection.execute("UPDATE platform_campaign_redemptions SET status = ?, released_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE order_id = ? AND status IN ('reserved', 'redeemed')", (status, order_id)).rowcount
        if changed:
            if redemption["claim_id"]:
                connection.execute("UPDATE platform_campaign_claims SET used_quantity = MAX(0, used_quantity - 1), updated_at = CURRENT_TIMESTAMP WHERE id = ?", (redemption["claim_id"],))
            record_order_resource_event(connection, order_id, "campaign_coupon", redemption["campaign_id"], status, amount_cents=redemption["discount_amount_cents"])


def activity_response(connection: sqlite3.Connection, activity: sqlite3.Row, shop_id: str | None = None, include_review_queue: bool = False) -> dict:
    page = connection.execute("SELECT banner_url, theme_json, modules_json, updated_at FROM activity_page_configs WHERE activity_id = ?", (activity["id"],)).fetchone()
    product_statuses = "('pending', 'active', 'disabled', 'rejected')" if include_review_queue else "('active')"
    products = connection.execute(
        f"""
        SELECT activity_products.*, products.title, products.stock, shops.name AS shop_name,
               (SELECT public_url FROM product_media WHERE product_media.product_id = products.id ORDER BY is_cover DESC, sort_order LIMIT 1) AS image_url
        FROM activity_products JOIN products ON products.id = activity_products.product_id
        JOIN shops ON shops.id = products.shop_id
        WHERE activity_products.activity_id = ? AND activity_products.status IN {product_statuses}
        ORDER BY activity_products.created_at DESC
        """,
        (activity["id"],),
    ).fetchall()
    application = connection.execute("SELECT * FROM activity_applications WHERE activity_id = ? AND shop_id = ?", (activity["id"], shop_id)).fetchone() if shop_id else None
    applications = connection.execute("SELECT activity_applications.*, shops.name AS shop_name, users.display_name AS applicant FROM activity_applications JOIN shops ON shops.id = activity_applications.shop_id JOIN users ON users.id = activity_applications.applicant_user_id WHERE activity_id = ? ORDER BY activity_applications.created_at DESC", (activity["id"],)).fetchall() if include_review_queue else []
    return {
        "id": activity["id"], "name": activity["name"], "description": activity["description"], "status": activity["status"], "startsAt": activity["starts_at"], "endsAt": activity["ends_at"],
        "page": {"banner": page["banner_url"] if page else None, "theme": json.loads(page["theme_json"] or "{}") if page else {}, "modules": json.loads(page["modules_json"] or "[]") if page else [], "updatedAt": page["updated_at"] if page else None},
        "application": None if not application else {"id": application["id"], "status": application["status"], "note": application["note"], "reviewNote": application["review_note"], "reviewedAt": application["reviewed_at"]},
        "products": [{"id": row["id"], "productId": row["product_id"], "title": row["title"], "shop": row["shop_name"], "image": row["image_url"], "quotaStock": row["quota_stock"], "reservedStock": row["reserved_stock"], "availableStock": max(0, row["quota_stock"] - row["reserved_stock"]), "productStock": row["stock"], "status": row["status"], "reviewNote": row["review_note"], "applicationId": row["application_id"]} for row in products],
        "applications": [{"id": row["id"], "shopId": row["shop_id"], "shop": row["shop_name"], "applicant": row["applicant"], "status": row["status"], "note": row["note"], "reviewNote": row["review_note"], "createdAt": row["created_at"]} for row in applications],
    }


def expire_ended_activities(connection: sqlite3.Connection) -> int:
    changed = connection.execute("UPDATE platform_activities SET status = 'ended', updated_at = CURRENT_TIMESTAMP WHERE status IN ('open', 'active') AND ends_at IS NOT NULL AND ends_at <= CURRENT_TIMESTAMP").rowcount
    if changed:
        connection.execute("UPDATE activity_products SET status = 'disabled', updated_at = CURRENT_TIMESTAMP WHERE status = 'active' AND activity_id IN (SELECT id FROM platform_activities WHERE status = 'ended')")
    return changed


def active_activity_product(connection: sqlite3.Connection, activity_id: str, product_id: str) -> sqlite3.Row:
    row = connection.execute(
        """
        SELECT activity_products.*, platform_activities.name AS activity_name
        FROM activity_products
        JOIN platform_activities ON platform_activities.id = activity_products.activity_id
        WHERE activity_products.activity_id = ? AND activity_products.product_id = ?
          AND activity_products.status = 'active' AND platform_activities.status = 'active'
          AND (platform_activities.starts_at IS NULL OR platform_activities.starts_at <= CURRENT_TIMESTAMP)
          AND (platform_activities.ends_at IS NULL OR platform_activities.ends_at > CURRENT_TIMESTAMP)
        """,
        (activity_id, product_id),
    ).fetchone()
    if not row:
        raise ValueError("活动作品不可用或活动已结束")
    return row


def reserve_activity_allocation(
    connection: sqlite3.Connection,
    activity_id: str,
    product_id: str,
    order_id: str,
    order_item_id: str,
    quantity: int,
) -> None:
    activity_product = active_activity_product(connection, activity_id, product_id)
    reserved = connection.execute(
        """
        UPDATE activity_products
        SET reserved_stock = reserved_stock + ?
        WHERE id = ? AND status = 'active' AND quota_stock - reserved_stock >= ?
        """,
        (quantity, activity_product["id"], quantity),
    ).rowcount
    if reserved != 1:
        raise ValueError("活动配额不足")
    connection.execute(
        """
        INSERT INTO activity_order_allocations
          (id, activity_product_id, order_id, order_item_id, quantity)
        VALUES (?, ?, ?, ?, ?)
        """,
        (f"activity-allocation-{secrets.token_urlsafe(10)}", activity_product["id"], order_id, order_item_id, quantity),
    )
    record_order_resource_event(connection, order_id, "activity_quota", activity_product["id"], "reserved", quantity, detail={"activityId": activity_id, "productId": product_id})


def set_activity_allocation_status(connection: sqlite3.Connection, order_id: str, status: str) -> None:
    if status not in ("redeemed", "released", "reversed"):
        return
    previous_statuses = ("reserved",) if status == "redeemed" else ("reserved", "redeemed")
    marks = ",".join("?" for _ in previous_statuses)
    rows = connection.execute(
        f"""
        SELECT activity_product_id, SUM(quantity) AS quantity
        FROM activity_order_allocations
        WHERE order_id = ? AND status IN ({marks})
        GROUP BY activity_product_id
        """,
        (order_id, *previous_statuses),
    ).fetchall()
    for row in rows:
        changed = connection.execute(
            f"UPDATE activity_order_allocations SET status = ?, {('redeemed_at' if status == 'redeemed' else 'released_at')} = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE order_id = ? AND activity_product_id = ? AND status IN ({marks})",
            (status, order_id, row["activity_product_id"], *previous_statuses),
        ).rowcount
        if changed:
            if status in ("released", "reversed"):
                connection.execute(
                    "UPDATE activity_products SET reserved_stock = MAX(0, reserved_stock - ?) WHERE id = ?",
                    (row["quantity"], row["activity_product_id"]),
                )
            record_order_resource_event(connection, order_id, "activity_quota", row["activity_product_id"], status, row["quantity"])


def buyer_coupons(connection: sqlite3.Connection, user_id: str) -> list[dict]:
    rows = connection.execute("SELECT platform_campaigns.*, platform_campaign_claims.id AS claim_id, platform_campaign_claims.claimed_quantity, platform_campaign_claims.used_quantity FROM platform_campaign_claims JOIN platform_campaigns ON platform_campaigns.id = platform_campaign_claims.campaign_id WHERE platform_campaign_claims.buyer_user_id = ? ORDER BY platform_campaign_claims.updated_at DESC", (user_id,)).fetchall()
    result = []
    for row in rows:
        rule = json.loads(row["rule_json"] or "{}")
        active = row["status"] == "active" and (not row["starts_at"] or row["starts_at"] <= datetime.now().isoformat()) and (not row["ends_at"] or row["ends_at"] > datetime.now().isoformat())
        result.append({"id": row["id"], "claimId": row["claim_id"], "name": row["name"], "threshold": number(rule.get("threshold")), "discount": number(rule.get("discount")), "remaining": row["claimed_quantity"] - row["used_quantity"], "claimed": row["claimed_quantity"], "used": row["used_quantity"], "available": bool(active and row["used_quantity"] < row["claimed_quantity"]), "endsAt": row["ends_at"]})
    return result


def reserve_order_inventory(
    connection: sqlite3.Connection,
    order_id: str,
    order_item_id: str,
    product_id: str,
    sku_id: str,
    quantity: int,
) -> None:
    sku_changed = connection.execute(
        "UPDATE product_skus SET stock = stock - ? WHERE id = ? AND stock >= ?",
        (quantity, sku_id, quantity),
    ).rowcount
    if sku_changed != 1:
        raise ValueError("SKU 库存不足")
    product_changed = connection.execute(
        "UPDATE products SET stock = stock - ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND stock >= ?",
        (quantity, product_id, quantity),
    ).rowcount
    if product_changed != 1:
        raise ValueError("作品库存不足")
    connection.execute(
        "INSERT INTO order_inventory_allocations (id, order_id, order_item_id, product_id, sku_id, quantity) VALUES (?, ?, ?, ?, ?, ?)",
        (f"inventory-allocation-{order_item_id}", order_id, order_item_id, product_id, sku_id, quantity),
    )
    record_order_resource_event(connection, order_id, "sku_inventory", sku_id, "reserved", quantity, detail={"productId": product_id})


def restore_order_inventory(connection: sqlite3.Connection, order_id: str, status: str = "released", force: bool = False) -> None:
    if status not in ("released", "reversed"):
        raise ValueError("库存回补状态无效")
    allocations = connection.execute(
        "SELECT * FROM order_inventory_allocations WHERE order_id = ? AND status = 'reserved'",
        (order_id,),
    ).fetchall()
    if allocations:
        for allocation in allocations:
            changed = connection.execute(
                "UPDATE order_inventory_allocations SET status = ?, released_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'reserved'",
                (status, allocation["id"]),
            ).rowcount
            if not changed:
                continue
            if allocation["sku_id"]:
                connection.execute("UPDATE product_skus SET stock = stock + ? WHERE id = ?", (allocation["quantity"], allocation["sku_id"]))
            if allocation["product_id"]:
                connection.execute("UPDATE products SET stock = stock + ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (allocation["quantity"], allocation["product_id"]))
            record_order_resource_event(connection, order_id, "sku_inventory", allocation["sku_id"] or allocation["product_id"] or "unknown", status, allocation["quantity"], detail={"productId": allocation["product_id"]})
        return
    marker = connection.execute("SELECT status FROM orders WHERE id = ?", (order_id,)).fetchone()
    if force or (marker and marker[0] not in ("cancelled", "refunded")):
        for item in connection.execute("SELECT product_id, sku_id, quantity FROM order_items WHERE order_id = ?", (order_id,)):
            if item["sku_id"]:
                connection.execute("UPDATE product_skus SET stock = stock + ? WHERE id = ?", (item["quantity"], item["sku_id"]))
            if item["product_id"]:
                connection.execute("UPDATE products SET stock = stock + ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (item["quantity"], item["product_id"]))


def expire_pending_orders(connection: sqlite3.Connection) -> int:
    connection.row_factory = sqlite3.Row
    expired = connection.execute(
        "SELECT id FROM orders WHERE status = 'pending_payment' AND expires_at IS NOT NULL AND expires_at <= CURRENT_TIMESTAMP"
    ).fetchall()
    expired_count = 0
    for order in expired:
        changed = connection.execute(
            "UPDATE orders SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'pending_payment' AND expires_at <= CURRENT_TIMESTAMP",
            (order["id"],),
        ).rowcount
        if not changed:
            continue
        expired_count += 1
        restore_order_inventory(connection, order["id"], status="released", force=True)
        set_campaign_redemption_status(connection, order["id"], "released")
        set_activity_allocation_status(connection, order["id"], "released")
        connection.execute(
            "UPDATE payment_transactions SET status = 'cancelled', failure_reason = 'payment_timeout', updated_at = CURRENT_TIMESTAMP WHERE order_id = ? AND status = 'pending'",
            (order["id"],),
        )
    return expired_count


def run_pending_order_expiry() -> int:
    connection = database()
    try:
        connection.execute("BEGIN IMMEDIATE")
        expired = expire_pending_orders(connection)
        connection.commit()
        return expired
    except sqlite3.OperationalError:
        connection.rollback()
        return 0
    finally:
        connection.close()


class OrderExpiryWorker(threading.Thread):
    def __init__(self, stop_event: threading.Event, interval_seconds: int = ORDER_EXPIRY_SCAN_SECONDS):
        super().__init__(name="order-expiry-worker", daemon=True)
        self.stop_event = stop_event
        self.interval_seconds = interval_seconds

    def run(self) -> None:
        while not self.stop_event.is_set():
            run_pending_order_expiry()
            run_coupon_expiry_reminders()
            with database() as connection:
                expire_ended_activities(connection)
                run_support_automation(connection)
            run_seller_message_automation()
            self.stop_event.wait(self.interval_seconds)


def message_display_time(value: object) -> str:
    """Render UTC SQLite message timestamps in the marketplace's local time."""
    raw = str(value or "")
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return raw


DEFAULT_MESSAGE_WEEKLY_HOURS = {
    "mon": [{"start": "09:00", "end": "18:00"}],
    "tue": [{"start": "09:00", "end": "18:00"}],
    "wed": [{"start": "09:00", "end": "18:00"}],
    "thu": [{"start": "09:00", "end": "18:00"}],
    "fri": [{"start": "09:00", "end": "18:00"}],
    "sat": [],
    "sun": [],
}


def normalise_message_weekly_hours(value: object) -> dict[str, list[dict[str, str]]]:
    source = value if isinstance(value, dict) else {}
    result: dict[str, list[dict[str, str]]] = {}
    for day in ("mon", "tue", "wed", "thu", "fri", "sat", "sun"):
        windows = source.get(day, DEFAULT_MESSAGE_WEEKLY_HOURS[day])
        if not isinstance(windows, list):
            windows = []
        valid: list[dict[str, str]] = []
        for window in windows[:2]:
            if not isinstance(window, dict):
                continue
            start, end = str(window.get("start") or "").strip(), str(window.get("end") or "").strip()
            if re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", start) and re.fullmatch(r"(?:[01]\d|2[0-3]):[0-5]\d", end) and start < end:
                valid.append({"start": start, "end": end})
        result[day] = valid
    return result


def message_settings_for_row(row: sqlite3.Row | None) -> dict[str, object]:
    if not row:
        return {
            "timezone": "Asia/Shanghai", "weeklyHours": DEFAULT_MESSAGE_WEEKLY_HOURS,
            "unansweredMinutes": 3, "offHoursAutoReplyEnabled": True,
            "offHoursReplyTemplate": "店主当前处于非工作时间，已收到您的消息，请耐心等待，我们会在工作时间尽快回复您。",
            "urgentEmailEnabled": True, "urgentSmsEnabled": False,
            "unansweredEmailEnabled": True, "aiReplyEnabled": True,
        }
    try:
        weekly = json.loads(row["weekly_hours_json"] or "{}")
    except (TypeError, ValueError, json.JSONDecodeError):
        weekly = {}
    timezone_name = str(row["timezone"] or "Asia/Shanghai")
    try:
        ZoneInfo(timezone_name)
    except ZoneInfoNotFoundError:
        timezone_name = "Asia/Shanghai"
    return {
        "timezone": timezone_name, "weeklyHours": normalise_message_weekly_hours(weekly),
        "unansweredMinutes": max(1, min(60, int(row["unanswered_minutes"] or 3))),
        "offHoursAutoReplyEnabled": bool(row["off_hours_auto_reply_enabled"]),
        "offHoursReplyTemplate": str(row["off_hours_reply_template"] or "")[:500],
        "urgentEmailEnabled": bool(row["urgent_email_enabled"]), "urgentSmsEnabled": bool(row["urgent_sms_enabled"]),
        "unansweredEmailEnabled": bool(row["unanswered_email_enabled"]), "aiReplyEnabled": bool(row["ai_reply_enabled"]),
    }


def shop_message_settings(connection: sqlite3.Connection, shop_id: str) -> dict[str, object]:
    connection.row_factory = sqlite3.Row
    row = connection.execute("SELECT * FROM seller_message_settings WHERE shop_id = ?", (shop_id,)).fetchone()
    return message_settings_for_row(row)


def message_working_now(settings: dict[str, object], now: datetime | None = None) -> bool:
    current = now or datetime.now(timezone.utc)
    try:
        local = current.astimezone(ZoneInfo(str(settings.get("timezone") or "Asia/Shanghai")))
    except ZoneInfoNotFoundError:
        local = current.astimezone(timezone(timedelta(hours=8)))
    day = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")[local.weekday()]
    minutes = local.hour * 60 + local.minute
    for window in (settings.get("weeklyHours") or {}).get(day, []):
        start_hour, start_minute = map(int, str(window["start"]).split(":"))
        end_hour, end_minute = map(int, str(window["end"]).split(":"))
        if start_hour * 60 + start_minute <= minutes < end_hour * 60 + end_minute:
            return True
    return False


def classify_buyer_message(content: str) -> tuple[str, str, float]:
    text = re.sub(r"\s+", " ", str(content or "").strip().lower())
    urgent_groups = (
        ("售后/退款/争议", ("退款", "退货", "争议", "拒付", "chargeback", "refund", "return", "dispute")),
        ("订单取消或地址修改时限", ("取消订单", "取消订单", "改地址", "修改地址", "cancel order", "change address")),
        ("支付或欺诈风险", ("支付失败", "付款失败", "欺诈", "诈骗", "fraud", "payment failed", "scam")),
        ("物流异常或丢件", ("丢件", "未收到", "物流异常", "包裹破损", "missing parcel", "not received", "damaged")),
        ("商品安全或人身风险", ("过敏", "受伤", "安全问题", "危险", "allergy", "injury", "unsafe")),
    )
    for reason, keywords in urgent_groups:
        if any(keyword in text for keyword in keywords):
            return "urgent", reason, 0.94
    high_keywords = ("今天发货", "截止", "deadline", "where is my order", "订单到哪", "什么时候到", "tracking")
    if any(keyword in text for keyword in high_keywords):
        return "high", "买家询问时效或物流进度", 0.78
    return "normal", "", 0.55


def email_is_configured() -> bool:
    return bool(SMTP_HOST and SMTP_FROM)


def send_seller_email(destination: str, subject: str, body: str) -> None:
    if not email_is_configured() or not destination:
        raise ValueError("SMTP email is not configured")
    message = EmailMessage()
    message["From"], message["To"], message["Subject"] = SMTP_FROM, destination, subject
    message.set_content(body)
    with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=15) as client:
        if SMTP_STARTTLS:
            client.starttls()
        if SMTP_USERNAME:
            client.login(SMTP_USERNAME, SMTP_PASSWORD)
        client.send_message(message)


def dispatch_seller_message_notification(notification_id: str) -> None:
    try:
        with database() as connection:
            connection.row_factory = sqlite3.Row
            row = connection.execute(
                """SELECT n.*, u.email, u.phone, s.name AS shop_name, m.content, m.buyer_user_id,
                          b.display_name AS buyer_name
                   FROM seller_message_notifications n
                   JOIN users u ON u.id = n.seller_user_id
                   JOIN shops s ON s.id = n.shop_id
                   JOIN shop_messages m ON m.id = n.message_id
                   JOIN users b ON b.id = m.buyer_user_id
                   WHERE n.id = ? AND n.status = 'queued' AND n.due_at <= CURRENT_TIMESTAMP""", (notification_id,)
            ).fetchone()
            if not row:
                return
            channel = row["channel"]
            if channel == "email":
                subject = "买家消息需要尽快处理" if row["notification_type"] == "urgent" else "买家消息超过 3 分钟未回复"
                send_seller_email(row["email"], f"[{row['shop_name']}] {subject}", f"买家：{row['buyer_name']}\n消息：{row['content']}\n请登录店铺消息面板处理。")
            elif channel == "sms":
                template_id = TENCENT_SMS_TEMPLATES.get("seller_message_urgent")
                if not TENCENT_SMS_ENABLED or not template_id:
                    raise ValueError("SMS notification is not configured")
                send_tencent_sms(row["phone"], template_id)
            connection.execute("UPDATE seller_message_notifications SET status = 'sent', sent_at = CURRENT_TIMESTAMP, attempts = attempts + 1 WHERE id = ?", (notification_id,))
    except Exception as error:
        with database() as connection:
            connection.execute("UPDATE seller_message_notifications SET status = 'failed', attempts = attempts + 1, last_error = ? WHERE id = ?", (str(error)[:300], notification_id))


def queue_seller_message_notification(connection: sqlite3.Connection, message_id: str, shop_id: str, notification_type: str, channel: str, due_at: str | None = None, delay_minutes: int | None = None) -> str | None:
    owner = connection.execute("SELECT owner_user_id FROM shops WHERE id = ?", (shop_id,)).fetchone()
    if not owner:
        return None
    notification_id = f"seller-message-notice-{secrets.token_urlsafe(10)}"
    due_expression = "datetime('now', ?)" if delay_minutes is not None else "COALESCE(?, CURRENT_TIMESTAMP)"
    due_value: object = f"+{max(0, int(delay_minutes))} minutes" if delay_minutes is not None else due_at
    inserted = connection.execute(
        f"""INSERT OR IGNORE INTO seller_message_notifications
           (id, message_id, shop_id, seller_user_id, notification_type, channel, due_at)
           VALUES (?, ?, ?, ?, ?, ?, {due_expression})""",
        (notification_id, message_id, shop_id, owner[0], notification_type, channel, due_value),
    ).rowcount
    return notification_id if inserted else None


def mark_message_attention(connection: sqlite3.Connection, message_id: str, shop_id: str, buyer_user_id: str, priority: str, reason: str, confidence: float) -> None:
    connection.execute(
        """INSERT INTO seller_message_attention (message_id, shop_id, buyer_user_id, priority, reason, confidence)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(message_id) DO UPDATE SET priority = excluded.priority, reason = excluded.reason, confidence = excluded.confidence, updated_at = CURRENT_TIMESTAMP""",
        (message_id, shop_id, buyer_user_id, priority, reason, max(0, min(1, confidence))),
    )


def message_row_for_response(row: sqlite3.Row) -> dict:
    message_type = row["message_type"] or "text"
    order = None
    product = None
    if row["order_id"]:
        order = {
            "id": row["order_id"],
            "orderNo": row["order_no"],
            "status": ORDER_STATUS_LABELS.get(row["order_status"], row["order_status"]),
            "amount": number(row["order_amount"]) / 100,
            "title": row["order_title"] or "订单作品",
            "image": row["order_image"],
        }
    if row["product_id"]:
        product = {
            "id": row["product_id"],
            "title": row["product_title"] or "Product",
            "price": number(row["product_price"]) / 100,
            "image": row["product_image"],
        }
    return {
        "id": row["id"], "cursor": row["message_cursor"], "shopId": row["shop_id"], "shop": row["shop_name"],
        "buyerUserId": row["buyer_user_id"], "buyer": row["buyer_name"],
        "sender": row["sender_role"], "senderUserId": row["sender_user_id"], "type": message_type, "content": row["content"],
        "attachmentUrl": row["attachment_url"], "order": order, "product": product,
        "read": bool(row["read_at"]), "createdAt": message_display_time(row["created_at"]),
        "automationKind": row["automation_kind"],
        "priority": row["attention_priority"] or "normal",
        "priorityReason": row["attention_reason"] or "",
    }


def message_rows(connection: sqlite3.Connection, where: str, params: tuple[object, ...], descending: bool = False) -> list[sqlite3.Row]:
    connection.row_factory = sqlite3.Row
    direction = "DESC" if descending else "ASC"
    return connection.execute(
        f"""
        SELECT shop_messages.*, shop_messages.rowid AS message_cursor,
               shops.name AS shop_name, users.display_name AS buyer_name,
               orders.order_no, orders.status AS order_status, orders.paid_amount_cents AS order_amount,
               (SELECT title_snapshot FROM order_items WHERE order_items.order_id = orders.id ORDER BY rowid LIMIT 1) AS order_title,
               (SELECT image_url_snapshot FROM order_items WHERE order_items.order_id = orders.id ORDER BY rowid LIMIT 1) AS order_image,
               products.title AS product_title, products.price_cents AS product_price,
               (SELECT public_url FROM product_media WHERE product_media.product_id = products.id AND product_media.media_type = 'image' ORDER BY sort_order LIMIT 1) AS product_image,
               seller_message_attention.priority AS attention_priority,
               seller_message_attention.reason AS attention_reason
        FROM shop_messages
        JOIN shops ON shops.id = shop_messages.shop_id
        JOIN users ON users.id = shop_messages.buyer_user_id
        LEFT JOIN orders ON orders.id = shop_messages.order_id
        LEFT JOIN products ON products.id = shop_messages.product_id
        LEFT JOIN seller_message_attention ON seller_message_attention.message_id = shop_messages.id
        WHERE {where}
        ORDER BY shop_messages.rowid {direction}
        """,
        params,
    ).fetchall()


def conversation_preview(message: dict) -> str:
    if message["type"] == "image":
        return "[图片]"
    if message["type"] == "order":
        return f"订单卡片：{message['order']['orderNo'] if message.get('order') else '订单'}"
    if message.get("product"):
        return f"商品卡片：{message['product']['title']}"
    return message["content"][:80]


def message_updates_payload(
    connection: sqlite3.Connection,
    user_id: str,
    audience: str,
    shop_id: str,
    buyer_id: str | None,
    after_cursor: int,
) -> dict:
    if not shop_id or after_cursor < 0:
        raise ValueError("Invalid message cursor")

    if audience == "buyer":
        conversation_where = "shop_messages.buyer_user_id = ? AND shop_messages.shop_id = ?"
        conversation_params: tuple[object, ...] = (user_id, shop_id)
        incoming_role = "seller"
    else:
        if not buyer_id:
            raise ValueError("Conversation is required")
        require_shop_permission(connection, user_id, shop_id, "messages")
        conversation_where = "shop_messages.shop_id = ? AND shop_messages.buyer_user_id = ?"
        conversation_params = (shop_id, buyer_id)
        incoming_role = "buyer"

    if not connection.execute(f"SELECT 1 FROM shop_messages WHERE {conversation_where} LIMIT 1", conversation_params).fetchone():
        raise ValueError("Conversation not found")

    connection.execute(
        f"UPDATE shop_messages SET read_at = CURRENT_TIMESTAMP WHERE {conversation_where} AND sender_role = ? AND read_at IS NULL",
        (*conversation_params, incoming_role),
    )
    rows = message_rows(
        connection,
        f"{conversation_where} AND shop_messages.rowid > ?",
        (*conversation_params, after_cursor),
    )
    messages = [message_row_for_response(row) for row in rows]
    cursor = messages[-1]["cursor"] if messages else after_cursor
    return {"messages": messages, "cursor": cursor}


def record_customer_service_webhook_event(
    connection: sqlite3.Connection,
    provider: str,
    external_event_id: str,
    event_type: str,
    payload: dict,
) -> bool:
    inserted = connection.execute(
        """
        INSERT OR IGNORE INTO customer_service_webhook_events
          (id, provider, external_event_id, event_type, payload_json)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            f"customer-service-webhook-{secrets.token_urlsafe(10)}", provider, external_event_id,
            event_type, json.dumps(payload, ensure_ascii=False),
        ),
    ).rowcount
    return inserted == 1


def buyer_messages_payload(connection: sqlite3.Connection, user_id: str, shop_id: str | None = None, search: str = "") -> dict:
    where, params = "shop_messages.buyer_user_id = ?", (user_id,)
    if search:
        where += " AND shop_messages.content LIKE ?"
        params = (*params, f"%{search[:50]}%")
    rows = message_rows(connection, where, params, descending=True)
    conversations: dict[str, dict] = {}
    for row in rows:
        message = message_row_for_response(row)
        key = str(message["shopId"])
        if key not in conversations:
            conversations[key] = {"shopId": message["shopId"], "shop": message["shop"], "preview": conversation_preview(message), "lastMessageAt": message["createdAt"], "unread": 0}
        if message["sender"] == "seller" and not message["read"]:
            conversations[key]["unread"] += 1
    messages: list[dict] = []
    if shop_id:
        if shop_id not in conversations:
            raise ValueError("会话不存在")
        connection.execute("UPDATE shop_messages SET read_at = CURRENT_TIMESTAMP WHERE buyer_user_id = ? AND shop_id = ? AND sender_role = 'seller' AND read_at IS NULL", (user_id, shop_id))
        messages = [message_row_for_response(row) for row in message_rows(connection, "shop_messages.buyer_user_id = ? AND shop_messages.shop_id = ?", (user_id, shop_id))]
    return {"conversations": list(conversations.values()), "messages": messages}


def seller_messages_payload(connection: sqlite3.Connection, user_id: str, shop_id: str | None = None, buyer_id: str | None = None, search: str = "") -> dict:
    shop_ids = seller_shop_ids(connection, user_id)
    if not shop_ids:
        return {"conversations": [], "messages": []}
    placeholders = ",".join("?" for _ in shop_ids)
    where, params = f"shop_messages.shop_id IN ({placeholders})", tuple(shop_ids)
    if search:
        where += " AND shop_messages.content LIKE ?"
        params = (*params, f"%{search[:50]}%")
    rows = message_rows(connection, where, params, descending=True)
    conversations: dict[tuple[str, str], dict] = {}
    for row in rows:
        message = message_row_for_response(row)
        key = (str(message["shopId"]), str(message["buyerUserId"]))
        if key not in conversations:
            conversations[key] = {"shopId": message["shopId"], "shop": message["shop"], "buyerUserId": message["buyerUserId"], "buyer": message["buyer"], "preview": conversation_preview(message), "lastMessageAt": message["createdAt"], "unread": 0, "priority": message.get("priority", "normal"), "priorityReason": message.get("priorityReason", "")}
        if message["sender"] == "buyer" and not message["read"]:
            conversations[key]["unread"] += 1
    messages: list[dict] = []
    if shop_id or buyer_id:
        if not shop_id or not buyer_id or shop_id not in shop_ids or (shop_id, buyer_id) not in conversations:
            raise ValueError("会话不存在")
        connection.execute("UPDATE shop_messages SET read_at = CURRENT_TIMESTAMP WHERE shop_id = ? AND buyer_user_id = ? AND sender_role = 'buyer' AND read_at IS NULL", (shop_id, buyer_id))
        messages = [message_row_for_response(row) for row in message_rows(connection, "shop_messages.shop_id = ? AND shop_messages.buyer_user_id = ?", (shop_id, buyer_id))]
    return {"conversations": list(conversations.values()), "messages": messages}


def apply_buyer_message_automation(connection: sqlite3.Connection, message_id: str, shop_id: str, buyer_user_id: str, content: str) -> dict[str, object]:
    """Classify an inbound buyer message and persist safe acknowledgement/escalation work.

    This function never lets AI or keyword matching approve refunds, price changes,
    or delivery promises.  Off-hours acknowledgements are fixed seller-controlled
    templates; anything urgent is escalated for a person to handle.
    """
    settings = shop_message_settings(connection, shop_id)
    priority, reason, confidence = classify_buyer_message(content)
    recipients = shop_message_recipient_user_ids(connection, shop_id)
    owner = connection.execute("SELECT owner_user_id FROM shops WHERE id = ?", (shop_id,)).fetchone()
    owner_id = owner[0] if owner else None
    auto_reply_id: str | None = None

    if priority in ("high", "urgent"):
        mark_message_attention(connection, message_id, shop_id, buyer_user_id, priority, reason, confidence)
        for recipient in recipients:
            notify_governance(connection, recipient, "buyer_message_urgent", "买家消息需要尽快处理", reason or "请尽快查看买家消息", "shop_message", message_id)
        if owner_id and bool(settings["urgentEmailEnabled"]):
            queue_seller_message_notification(connection, message_id, shop_id, "urgent", "email")
        if priority == "urgent" and owner_id and bool(settings["urgentSmsEnabled"]):
            queue_seller_message_notification(connection, message_id, shop_id, "urgent", "sms")

    if bool(settings["unansweredEmailEnabled"]) and owner_id and message_working_now(settings):
        queue_seller_message_notification(
            connection, message_id, shop_id, "unanswered", "email",
            delay_minutes=int(settings["unansweredMinutes"]),
        )

    if bool(settings["offHoursAutoReplyEnabled"]) and not message_working_now(settings):
        recent = connection.execute(
            """SELECT 1 FROM shop_messages WHERE shop_id = ? AND buyer_user_id = ?
               AND sender_role = 'seller' AND automation_kind = 'off_hours'
               AND created_at >= datetime('now', '-12 hours') LIMIT 1""",
            (shop_id, buyer_user_id),
        ).fetchone()
        if not recent:
            auto_reply_id = f"message-{secrets.token_urlsafe(10)}"
            template = str(settings["offHoursReplyTemplate"]).strip()[:500]
            connection.execute(
                """INSERT INTO shop_messages
                   (id, shop_id, buyer_user_id, sender_role, sender_user_id, content, message_type, automation_kind)
                   VALUES (?, ?, ?, 'seller', ?, ?, 'text', 'off_hours')""",
                (auto_reply_id, shop_id, buyer_user_id, owner_id, template),
            )
            notify_governance(connection, buyer_user_id, "seller_message", "店铺已收到你的消息", template[:80], "shop", shop_id)
    return {"priority": priority, "reason": reason, "autoReplyMessageId": auto_reply_id, "recipientUserIds": recipients}


def run_seller_message_automation() -> int:
    """Deliver due unattended-message reminders and avoid notifying after a reply."""
    with database() as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            """SELECT n.id, n.notification_type, n.message_id, m.shop_id, m.buyer_user_id, m.created_at
               FROM seller_message_notifications n
               JOIN shop_messages m ON m.id = n.message_id
               WHERE n.status = 'queued' AND n.due_at <= CURRENT_TIMESTAMP
               ORDER BY n.created_at LIMIT 50"""
        ).fetchall()
        ready: list[str] = []
        for row in rows:
            if row["notification_type"] == "unanswered":
                settings = shop_message_settings(connection, row["shop_id"])
                if not message_working_now(settings):
                    connection.execute("UPDATE seller_message_notifications SET status = 'skipped', sent_at = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],))
                    continue
                replied = connection.execute(
                    """SELECT 1 FROM shop_messages WHERE shop_id = ? AND buyer_user_id = ?
                       AND sender_role = 'seller' AND automation_kind IS NULL AND created_at > ? LIMIT 1""",
                    (row["shop_id"], row["buyer_user_id"], row["created_at"]),
                ).fetchone()
                newer_buyer_message = connection.execute(
                    """SELECT 1 FROM shop_messages WHERE shop_id = ? AND buyer_user_id = ?
                       AND sender_role = 'buyer' AND created_at > ? LIMIT 1""",
                    (row["shop_id"], row["buyer_user_id"], row["created_at"]),
                ).fetchone()
                if replied or newer_buyer_message:
                    connection.execute("UPDATE seller_message_notifications SET status = 'skipped', sent_at = CURRENT_TIMESTAMP WHERE id = ?", (row["id"],))
                    continue
                owner = connection.execute("SELECT owner_user_id FROM shops WHERE id = ?", (row["shop_id"],)).fetchone()
                if owner:
                    notify_governance(connection, owner[0], "buyer_message_unanswered", "买家消息等待回复", "一条工作时间内的买家消息超过设定时间未回复。", "shop_message", row["message_id"])
            ready.append(row["id"])
    for notification_id in ready:
        dispatch_seller_message_notification(notification_id)
    return len(ready)


def seller_ai_message_draft(connection: sqlite3.Connection, user_id: str, shop_id: str, buyer_user_id: str) -> str:
    settings = shop_message_settings(connection, shop_id)
    if not bool(settings["aiReplyEnabled"]):
        raise ValueError("店铺未启用 AI 回复建议")
    require_shop_permission(connection, user_id, shop_id, "messages")
    if not OPENAI_API_KEY:
        raise ValueError("AI 服务尚未配置")
    if not seller_ai_assistant_rate_allowed(user_id):
        raise ValueError("AI 请求过于频繁，请 10 分钟后再试")
    rows = connection.execute(
        """SELECT sender_role, content, message_type, created_at FROM shop_messages
           WHERE shop_id = ? AND buyer_user_id = ? ORDER BY rowid DESC LIMIT 12""",
        (shop_id, buyer_user_id),
    ).fetchall()
    if not rows or not any(row["sender_role"] == "buyer" for row in rows):
        raise ValueError("当前会话没有可回复的买家消息")
    history = [
        {"role": "user" if row["sender_role"] == "buyer" else "assistant", "content": str(row["content"] or "")[:500] or f"[{row['message_type']}]"}
        for row in reversed(rows)
    ]
    request_body = {
        "model": OPENAI_MODEL, "temperature": 0.25, "max_tokens": 360,
        "messages": [
            {"role": "system", "content": "你是跨境电商卖家的客服文案助手。仅根据对话中明确的信息起草一条简洁、礼貌的回复，可使用中文。不得承诺退款、赔偿、改价、库存、发货或到货日期；涉及付款、退款、纠纷、地址修改、商品安全、投诉时，只说明将优先核实并由人工处理。不要声称自己是 AI，不要添加标题或解释。"},
            *history,
            {"role": "user", "content": "请起草下一条卖家回复，供卖家审核后手动发送。"},
        ],
    }
    request = Request(
        seller_ai_assistant_endpoint(), data=json.dumps(request_body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {OPENAI_API_KEY}", "Content-Type": "application/json"}, method="POST",
    )
    try:
        with urlopen(request, timeout=35) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (HTTPError, URLError, TimeoutError, json.JSONDecodeError) as error:
        raise ValueError("AI 回复建议暂时无法生成，请稍后重试") from error
    choices = payload.get("choices") if isinstance(payload, dict) else None
    draft = str(choices[0].get("message", {}).get("content") or "").strip() if isinstance(choices, list) and choices else ""
    if not draft:
        raise ValueError("AI 未返回有效回复建议")
    return draft[:500]


def support_sla_hours(priority: str) -> tuple[int, int]:
    return {"urgent": (1, 8), "high": (4, 24), "normal": (12, 72), "low": (24, 120)}.get(priority, (12, 72))


def support_sla_status(ticket: sqlite3.Row) -> str:
    if ticket["status"] in ("resolved", "closed"):
        return "met"
    due = ticket["first_response_due_at"] or ticket["resolution_due_at"]
    if not due:
        return "on_track"
    remaining = datetime.fromisoformat(str(due).replace("Z", "+00:00")).replace(tzinfo=timezone.utc) - datetime.now(timezone.utc)
    return "overdue" if remaining.total_seconds() < 0 else "warning" if remaining <= timedelta(hours=4) else "on_track"


def write_support_ticket_event(connection: sqlite3.Connection, ticket_id: str, event_type: str, actor_user_id: str | None = None, payload: dict | None = None) -> None:
    connection.execute("INSERT INTO support_ticket_events (id, ticket_id, event_type, actor_user_id, payload_json) VALUES (?, ?, ?, ?, ?)", (f"support-event-{secrets.token_urlsafe(10)}", ticket_id, event_type, actor_user_id, json.dumps(payload or {}, ensure_ascii=False)))


def least_loaded_support_assignee(connection: sqlite3.Connection, route: str, shop_id: str | None) -> str | None:
    if route == "shop" and shop_id:
        candidates = [str(row[0]) for row in connection.execute("SELECT owner_user_id FROM shops WHERE id = ?", (shop_id,))]
        candidates.extend(str(row[0]) for row in connection.execute("SELECT shop_staff.user_id FROM shop_staff JOIN users ON users.id = shop_staff.user_id WHERE shop_staff.shop_id = ? AND shop_staff.status = 'active' AND users.status = 'active' AND shop_staff.role = 'customer_service'", (shop_id,)))
    else:
        candidates = [str(row[0]) for row in connection.execute("SELECT platform_admins.user_id FROM platform_admins JOIN users ON users.id = platform_admins.user_id WHERE users.status = 'active'")]
    candidates = list(dict.fromkeys(candidates))
    if not candidates:
        return None
    marks = ",".join("?" for _ in candidates)
    row = connection.execute(f"SELECT users.id, COUNT(support_tickets.id) AS workload FROM users LEFT JOIN support_tickets ON support_tickets.assigned_user_id = users.id AND support_tickets.status NOT IN ('resolved', 'closed') WHERE users.id IN ({marks}) GROUP BY users.id ORDER BY workload, users.id LIMIT 1", tuple(candidates)).fetchone()
    return str(row[0]) if row else None


def matching_service_automation_rule(connection: sqlite3.Connection, content: str) -> sqlite3.Row | None:
    connection.row_factory = sqlite3.Row
    for rule in connection.execute("SELECT * FROM service_automation_rules WHERE enabled = 1 ORDER BY sort_order, updated_at DESC"):
        try:
            keywords = [str(item).strip().lower() for item in json.loads(rule["keywords_json"] or "[]") if str(item).strip()]
        except (TypeError, json.JSONDecodeError):
            keywords = []
        if keywords and any(keyword in content.lower() for keyword in keywords):
            return rule
    return None


def apply_support_automation(connection: sqlite3.Connection, ticket_id: str, content: str) -> None:
    """Apply keyword routing, SLA deadlines and balanced queue assignment once."""
    connection.row_factory = sqlite3.Row
    ticket = connection.execute("SELECT * FROM support_tickets WHERE id = ?", (ticket_id,)).fetchone()
    if not ticket:
        return
    rule = matching_service_automation_rule(connection, f"{ticket['subject']} {content}")
    priority = ticket["priority"]
    route = "shop" if ticket["shop_id"] else "platform"
    if rule:
        if priority_rank(rule["priority"]) > priority_rank(priority):
            priority = rule["priority"]
        route = rule["route"] if rule["route"] == "platform" or ticket["shop_id"] else "platform"
    assignee_id = least_loaded_support_assignee(connection, route, ticket["shop_id"])
    first_hours, resolution_hours = support_sla_hours(priority)
    connection.execute("UPDATE support_tickets SET priority = ?, assigned_user_id = ?, status = CASE WHEN ? IS NULL THEN status WHEN status = 'open' THEN 'in_progress' ELSE status END, first_response_due_at = datetime('now', ?), resolution_due_at = datetime('now', ?), automation_rule_id = ?, auto_assigned_at = CASE WHEN ? IS NULL THEN NULL ELSE CURRENT_TIMESTAMP END, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (priority, assignee_id, assignee_id, f"+{first_hours} hours", f"+{resolution_hours} hours", rule["id"] if rule else None, assignee_id, ticket_id))
    write_support_ticket_event(connection, ticket_id, "automation_applied", payload={"ruleId": rule["id"] if rule else None, "priority": priority, "route": route, "assignedUserId": assignee_id})
    if assignee_id:
        notify_governance(connection, assignee_id, "support_ticket_assigned", "已自动分派客服工单", f"{ticket['subject']} · {priority}", "support_ticket", ticket_id)
    if rule and rule["reply_template"] and assignee_id:
        role = "admin" if route == "platform" else "seller"
        reply = str(rule["reply_template"]).replace("{subject}", str(ticket["subject"]))[:1000]
        if reply:
            connection.execute("INSERT INTO support_ticket_messages (id, ticket_id, sender_user_id, sender_role, content) VALUES (?, ?, ?, ?, ?)", (f"ticket-message-{secrets.token_urlsafe(10)}", ticket_id, assignee_id, role, reply))
            write_support_ticket_event(connection, ticket_id, "auto_replied", payload={"ruleId": rule["id"]})


def run_support_automation(connection: sqlite3.Connection) -> int:
    """Escalate overdue open tickets; invoked while queues and dashboards are read."""
    connection.row_factory = sqlite3.Row
    updated = 0
    rows = connection.execute("SELECT * FROM support_tickets WHERE status NOT IN ('resolved', 'closed') AND escalated_at IS NULL AND ((first_response_due_at IS NOT NULL AND first_response_due_at < CURRENT_TIMESTAMP) OR (resolution_due_at IS NOT NULL AND resolution_due_at < CURRENT_TIMESTAMP))").fetchall()
    for ticket in rows:
        assignee_id = ticket["assigned_user_id"] or least_loaded_support_assignee(connection, "platform", None)
        connection.execute("UPDATE support_tickets SET priority = 'urgent', assigned_user_id = COALESCE(assigned_user_id, ?), escalated_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (assignee_id, ticket["id"]))
        write_support_ticket_event(connection, ticket["id"], "sla_escalated", payload={"assignedUserId": assignee_id})
        if assignee_id:
            notify_governance(connection, assignee_id, "support_ticket_escalated", "客服工单 SLA 超时", ticket["subject"], "support_ticket", ticket["id"])
        notify_governance(connection, ticket["buyer_user_id"], "support_ticket_escalated", "工单已升级处理", "我们已提升该工单处理优先级", "support_ticket", ticket["id"])
        updated += 1
    return updated


def support_ticket_access(connection: sqlite3.Connection, ticket: sqlite3.Row, user_id: str, audience: str) -> str | None:
    if audience == "buyer" and ticket["buyer_user_id"] == user_id:
        return "buyer"
    if audience == "platform_seller" and ticket["buyer_user_id"] == user_id and ticket["requester_role"] == "seller":
        return "seller"
    if audience == "seller" and ticket["shop_id"] and "messages" in seller_shop_permissions(connection, user_id).get(ticket["shop_id"], set()):
        return "seller"
    if audience == "admin" and is_admin(connection, user_id):
        return "admin"
    return None


def support_ticket_response(connection: sqlite3.Connection, ticket: sqlite3.Row, include_messages: bool = False) -> dict:
    connection.row_factory = sqlite3.Row
    messages: list[dict] = []
    if include_messages:
        messages = [
            {"id": row["id"], "sender": row["sender_role"], "content": row["content"], "attachmentUrl": row["attachment_url"], "createdAt": row["created_at"]}
            for row in connection.execute("SELECT * FROM support_ticket_messages WHERE ticket_id = ? ORDER BY created_at", (ticket["id"],))
        ]
    buyer = connection.execute("SELECT display_name FROM users WHERE id = ?", (ticket["buyer_user_id"],)).fetchone()
    shop = connection.execute("SELECT name FROM shops WHERE id = ?", (ticket["shop_id"],)).fetchone() if ticket["shop_id"] else None
    assignee = connection.execute("SELECT display_name FROM users WHERE id = ?", (ticket["assigned_user_id"],)).fetchone() if ticket["assigned_user_id"] else None
    return {
        "id": ticket["id"], "subject": ticket["subject"], "status": ticket["status"], "priority": ticket["priority"],
        "buyer": buyer[0] if buyer else "", "shop": shop[0] if shop else "平台客服", "shopId": ticket["shop_id"], "orderId": ticket["order_id"],
        "assignee": assignee[0] if assignee else "", "assignedUserId": ticket["assigned_user_id"], "createdAt": ticket["created_at"], "updatedAt": ticket["updated_at"], "resolvedAt": ticket["resolved_at"],
        "firstResponseDueAt": ticket["first_response_due_at"], "resolutionDueAt": ticket["resolution_due_at"], "sla": support_sla_status(ticket), "escalatedAt": ticket["escalated_at"], "automationRuleId": ticket["automation_rule_id"], "messages": messages,
    }


def support_tickets_for(connection: sqlite3.Connection, user_id: str, audience: str) -> list[dict]:
    connection.row_factory = sqlite3.Row
    run_support_automation(connection)
    if audience == "buyer":
        rows = connection.execute("SELECT * FROM support_tickets WHERE buyer_user_id = ? AND requester_role = 'buyer' ORDER BY updated_at DESC", (user_id,)).fetchall()
    elif audience == "platform_seller":
        rows = connection.execute("SELECT * FROM support_tickets WHERE buyer_user_id = ? AND requester_role = 'seller' ORDER BY updated_at DESC", (user_id,)).fetchall()
    elif audience == "seller":
        shop_ids = seller_accessible_shop_ids(connection, user_id, "messages")
        if not shop_ids:
            return []
        rows = connection.execute(f"SELECT * FROM support_tickets WHERE shop_id IN ({','.join('?' for _ in shop_ids)}) ORDER BY updated_at DESC", tuple(shop_ids)).fetchall()
    elif audience == "admin":
        rows = connection.execute("SELECT * FROM support_tickets ORDER BY CASE status WHEN 'open' THEN 0 WHEN 'in_progress' THEN 1 ELSE 2 END, updated_at DESC").fetchall()
    else:
        return []
    return [support_ticket_response(connection, row) for row in rows]


def orders_for_response(connection: sqlite3.Connection, where: str, params: tuple[object, ...]) -> list[dict]:
    connection.row_factory = sqlite3.Row
    orders = connection.execute(
        f"SELECT * FROM orders WHERE {where} ORDER BY placed_at DESC", params
    ).fetchall()
    result = []
    for order in orders:
        campaign = connection.execute(
            "SELECT platform_campaigns.id, platform_campaigns.name, platform_campaign_redemptions.discount_amount_cents, platform_campaign_redemptions.status FROM platform_campaign_redemptions JOIN platform_campaigns ON platform_campaigns.id = platform_campaign_redemptions.campaign_id WHERE platform_campaign_redemptions.order_id = ?",
            (order["id"],),
        ).fetchone()
        payment = connection.execute(
            "SELECT payment_method, payment_currency, exchange_rate, status, provider_reference, paid_at, initiated_at, failure_reason FROM payment_transactions WHERE order_id = ?",
            (order["id"],),
        ).fetchone()
        shipment = connection.execute(
            "SELECT carrier, tracking_no FROM shipments WHERE order_id = ?", (order["id"],)
        ).fetchone()
        tracking_phone_last4 = None
        if shipment and ("顺丰" in shipment["carrier"] or "sf express" in shipment["carrier"].lower()):
            try:
                address_snapshot = json.loads(order["address_snapshot"] or "{}")
                recipient_phone = re.sub(r"\D", "", str(address_snapshot.get("phone") or ""))
                tracking_phone_last4 = recipient_phone[-4:] if len(recipient_phone) >= 4 else None
            except (TypeError, ValueError, json.JSONDecodeError):
                tracking_phone_last4 = None
        events = []
        if shipment:
            shipment_row = connection.execute(
                "SELECT id FROM shipments WHERE order_id = ?", (order["id"],)
            ).fetchone()
            events = [
                {"time": row["event_at"], "label": row["label"], "detail": row["detail"]}
                for row in connection.execute(
                    "SELECT event_at, label, detail FROM shipment_events WHERE shipment_id = ? ORDER BY event_at",
                    (shipment_row["id"],),
                )
            ]
        reviewed = connection.execute(
            "SELECT 1 FROM reviews WHERE order_item_id IN (SELECT id FROM order_items WHERE order_id = ?) LIMIT 1",
            (order["id"],),
        ).fetchone() is not None
        resource_events = [
            {
                "resourceType": row["resource_type"], "resourceId": row["resource_id"],
                "action": row["action"], "quantity": row["quantity"],
                "amount": row["amount_cents"] / 100, "detail": json.loads(row["detail_json"] or "{}"),
                "createdAt": row["created_at"],
            }
            for row in connection.execute(
                "SELECT resource_type, resource_id, action, quantity, amount_cents, detail_json, created_at FROM order_resource_events WHERE order_id = ? ORDER BY created_at, rowid",
                (order["id"],),
            )
        ]
        result.append(
            {
                "id": order["order_no"],
                "orderId": order["id"],
                "shopId": order["shop_id"],
                "buyerUserId": order["buyer_user_id"],
                "items": order_items_for_response(connection, order["id"]),
                "status": ORDER_STATUS_LABELS[order["status"]],
                "createdAt": order["placed_at"],
                "expiresAt": order["expires_at"],
                "itemAmount": order["item_amount_cents"] / 100,
                "shippingAmount": order["shipping_amount_cents"] / 100,
                "shippingRule": json.loads(order["shipping_rule_snapshot_json"] or "{}"),
                "discountAmount": order["discount_amount_cents"] / 100,
                "platformCampaign": ({"id": campaign["id"], "name": campaign["name"], "discountAmount": campaign["discount_amount_cents"] / 100, "status": campaign["status"]} if campaign else None),
                "resourceEvents": resource_events,
                "amount": order["paid_amount_cents"] / 100,
                "currency": order["pricing_currency"],
                "paymentCurrency": order["payment_currency"],
                "settlementCurrency": order["settlement_currency"],
                "paymentExchangeRate": order["payment_exchange_rate"],
                "settlementExchangeRate": order["settlement_exchange_rate"],
                "payment": (
                    {
                        "method": payment["payment_method"],
                        "currency": payment["payment_currency"],
                        "exchangeRate": payment["exchange_rate"],
                        "status": payment["status"],
                        "reference": payment["provider_reference"],
                        "paidAt": payment["paid_at"],
                        "initiatedAt": payment["initiated_at"],
                        "failureReason": payment["failure_reason"],
                    }
                    if payment
                    else None
                ),
                "reviewed": reviewed,
                "shipment": (
                    {
                        "carrier": shipment["carrier"],
                        "trackingNo": shipment["tracking_no"],
                        "trackingPhoneLast4": tracking_phone_last4,
                        "events": events,
                    }
                    if shipment
                    else None
                ),
            }
        )
    return result


def find_sku(connection: sqlite3.Connection, product_id: str, variants: dict) -> sqlite3.Row:
    rows = connection.execute(
        """
        SELECT product_options.name, product_option_values.id, product_option_values.value
        FROM product_options
        JOIN product_option_values ON product_option_values.option_id = product_options.id
        WHERE product_options.product_id = ?
        """,
        (product_id,),
    ).fetchall()
    option_ids = {
        row["id"]
        for row in rows
        if variants.get(row["name"]) == row["value"]
    }
    for sku in connection.execute(
        "SELECT * FROM product_skus WHERE product_id = ? AND status = 'active'", (product_id,)
    ).fetchall():
        if set(json.loads(sku["option_value_ids"] or "[]")) == option_ids:
            return sku
    raise ValueError("所选规格已失效，请重新选择")


def enforce_checkout_risk_controls(
    connection: sqlite3.Connection,
    user_id: str,
    grouped: dict[str, list[tuple[sqlite3.Row, sqlite3.Row, int, dict, str | None]]],
) -> None:
    """Block clear abuse while preserving a review trail for softer signals."""
    pending_count = connection.execute(
        "SELECT COUNT(*) FROM orders WHERE buyer_user_id = ? AND status = 'pending_payment' AND placed_at >= datetime('now', '-24 hours')",
        (user_id,),
    ).fetchone()[0]
    if pending_count >= 5:
        record_risk_case(connection, "order_anomaly", "high", "too_many_pending_orders", subject_user_id=user_id, detail={"pendingOrders24h": pending_count})
        raise ValueError("待支付订单过多，请先完成或取消现有订单后再试")
    recent_count = connection.execute(
        "SELECT COUNT(*) FROM orders WHERE buyer_user_id = ? AND placed_at >= datetime('now', '-10 minutes')",
        (user_id,),
    ).fetchone()[0]
    if recent_count >= 8:
        record_risk_case(connection, "order_anomaly", "high", "rapid_order_creation", subject_user_id=user_id, detail={"orders10m": recent_count})
        raise ValueError("下单操作过于频繁，请稍后再试")
    for shop_id in grouped:
        owner = connection.execute("SELECT owner_user_id FROM shops WHERE id = ?", (shop_id,)).fetchone()
        if owner and owner[0] == user_id:
            record_risk_case(connection, "wash_trading", "high", "self_dealing_attempt", subject_user_id=user_id, detail={"shopId": shop_id})
            raise ValueError("不能购买自己店铺的商品")
    history = connection.execute(
        "SELECT COUNT(*) AS orders, SUM(CASE WHEN status IN ('refunding', 'refunded') THEN 1 ELSE 0 END) AS refunds FROM orders WHERE buyer_user_id = ? AND placed_at >= datetime('now', '-90 days')",
        (user_id,),
    ).fetchone()
    if int(history["orders"] or 0) >= 4 and int(history["refunds"] or 0) * 2 >= int(history["orders"] or 0):
        record_risk_case(connection, "refund_dispute", "medium", "high_refund_ratio", subject_user_id=user_id, detail={"orders90d": history["orders"], "refunds90d": history["refunds"]})


def enforce_coupon_claim_risk_controls(connection: sqlite3.Connection, user_id: str) -> None:
    claims = connection.execute(
        "SELECT COUNT(*) FROM platform_campaign_claims WHERE buyer_user_id = ? AND updated_at >= datetime('now', '-10 minutes')",
        (user_id,),
    ).fetchone()[0]
    if claims >= 5:
        record_risk_case(connection, "coupon_abuse", "high", "rapid_coupon_claims", subject_user_id=user_id, detail={"claims10m": claims})
        raise ValueError("领券操作过于频繁，请稍后再试")


def create_orders(user_id: str, payload: dict) -> list[dict]:
    raw_items = payload.get("items") or []
    if not raw_items:
        raise ValueError("购物袋为空")
    with database() as connection:
        connection.row_factory = sqlite3.Row
        expire_pending_orders(connection)
        address_id = str(payload.get("addressId") or "")
        address = connection.execute(
            "SELECT * FROM buyer_addresses WHERE id = ? AND buyer_user_id = ?", (address_id, user_id)
        ).fetchone()
        if not address:
            raise ValueError("请选择收货地址")
        grouped = checkout_groups(connection, raw_items)
        enforce_checkout_risk_controls(connection, user_id, grouped)
        payment_method = str(payload.get("paymentMethod") or "alipay")
        channel = analytics_channel(payload.get("channel"))
        if payment_method not in ("alipay", "card"):
            raise ValueError("不支持的支付方式")

        created_ids: list[str] = []
        for shop_id, items in grouped.items():
            order_id = f"order-{secrets.token_urlsafe(12)}"
            order_no = f"SZ{datetime.now().strftime('%y%m%d%H%M%S')}{secrets.randbelow(900) + 100}"
            item_amount = sum(item[1]["price_cents"] * item[2] for item in items)
            shipping_amount, discount_amount, campaign, shipping_rule = shop_charge(
                connection, shop_id, user_id, item_amount, sum(item[2] for item in items), address["country_code"]
            )
            amount = item_amount + shipping_amount - discount_amount
            connection.execute(
                """
                INSERT INTO orders (id, order_no, buyer_user_id, shop_id, address_snapshot, shipping_rule_snapshot_json, item_amount_cents, shipping_amount_cents, discount_amount_cents, paid_amount_cents, pricing_currency, payment_currency, settlement_currency, payment_exchange_rate, settlement_exchange_rate, attribution_channel, status, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_payment', datetime('now', '+30 minutes'))
                """,
                (order_id, order_no, user_id, shop_id, json.dumps(address_for_response(address), ensure_ascii=False), json.dumps(shipping_rule, ensure_ascii=False), item_amount, shipping_amount, discount_amount, amount, PLATFORM_CURRENCY, PLATFORM_CURRENCY, PLATFORM_CURRENCY, USD_EXCHANGE_RATE, USD_EXCHANGE_RATE, channel),
            )
            recent_like_orders = connection.execute(
                "SELECT COUNT(*) FROM orders WHERE buyer_user_id = ? AND shop_id = ? AND item_amount_cents = ? AND placed_at >= datetime('now', '-10 minutes')",
                (user_id, shop_id, item_amount),
            ).fetchone()[0]
            if recent_like_orders >= 3:
                record_risk_case(connection, "wash_trading", "high", "repeated_same_shop_order", subject_user_id=user_id, order_id=order_id, detail={"shopId": shop_id, "itemAmountCents": item_amount, "orders10m": recent_like_orders})
            if campaign and item_amount and campaign["discount"] * 100 >= item_amount * 60:
                record_risk_case(connection, "coupon_abuse", "medium", "high_discount_ratio", subject_user_id=user_id, order_id=order_id, detail={"campaignId": campaign["id"], "discountCents": campaign["discount"], "itemAmountCents": item_amount})
            if campaign:
                if campaign.get("claimId"):
                    claimed = connection.execute(
                        "UPDATE platform_campaign_claims SET used_quantity = used_quantity + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND used_quantity < claimed_quantity",
                        (campaign["claimId"],),
                    ).rowcount
                    if claimed != 1:
                        raise ValueError("优惠券已被使用，请重新结算")
                connection.execute(
                    "INSERT INTO platform_campaign_redemptions (id, campaign_id, order_id, buyer_user_id, item_amount_cents, discount_amount_cents, claim_id) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (f"campaign-redemption-{secrets.token_urlsafe(10)}", campaign["id"], order_id, user_id, item_amount, campaign["discount"], campaign.get("claimId")),
                )
                record_order_resource_event(connection, order_id, "campaign_coupon", campaign["id"], "reserved", amount_cents=campaign["discount"])
            connection.execute(
                "INSERT INTO payment_transactions (id, order_id, payment_method, amount_cents, payment_currency, exchange_rate, payment_token) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (f"payment-{secrets.token_urlsafe(10)}", order_id, payment_method, amount, PLATFORM_CURRENCY, USD_EXCHANGE_RATE, f"pay-{secrets.token_urlsafe(18)}"),
            )
            for product, sku, quantity, variants, activity_id in items:
                order_item_id = f"item-{secrets.token_urlsafe(10)}"
                cover = connection.execute(
                    "SELECT public_url FROM product_media WHERE product_id = ? ORDER BY is_cover DESC, sort_order LIMIT 1",
                    (product["id"],),
                ).fetchone()
                connection.execute(
                    """
                    INSERT INTO order_items (id, order_id, product_id, sku_id, title_snapshot, image_url_snapshot, specifications_snapshot, unit_price_cents, price_currency, quantity, subtotal_cents)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        order_item_id, order_id, product["id"], sku["id"], product["title"],
                        cover[0] if cover else None, json.dumps(variants, ensure_ascii=False), sku["price_cents"], product["price_currency"], quantity,
                        sku["price_cents"] * quantity,
                    ),
                )
                reserve_order_inventory(connection, order_id, order_item_id, product["id"], sku["id"], quantity)
                if activity_id:
                    reserve_activity_allocation(connection, activity_id, product["id"], order_id, order_item_id, quantity)
            created_ids.append(order_id)
        placeholders = ",".join("?" for _ in created_ids)
        return orders_for_response(connection, f"id IN ({placeholders})", tuple(created_ids))


def checkout_quote(user_id: str, payload: dict) -> dict:
    raw_items = payload.get("items") or []
    if not raw_items:
        raise ValueError("购物袋为空")
    with database() as connection:
        connection.row_factory = sqlite3.Row
        address_id = str(payload.get("addressId") or "")
        address = connection.execute("SELECT * FROM buyer_addresses WHERE id = ? AND buyer_user_id = ?", (address_id, user_id)).fetchone()
        if not address:
            raise ValueError("请选择收货地址")
        groups = checkout_groups(connection, raw_items)
        record_analytics_event(connection, "checkout_started", user_id=user_id, channel=payload.get("channel"))
        shops = []
        provisional_usage: dict[str, tuple[int, int]] = {}
        provisional_activity_usage: dict[str, int] = {}
        item_total = shipping_total = discount_total = 0
        for shop_id, items in groups.items():
            amount = sum(item[1]["price_cents"] * item[2] for item in items)
            shipping, discount, campaign, shipping_rule = shop_charge(connection, shop_id, user_id, amount, sum(item[2] for item in items), address["country_code"], provisional_usage)
            if campaign:
                prior_usage, prior_amount = provisional_usage.get(campaign["id"], (0, 0))
                provisional_usage[campaign["id"]] = (prior_usage + 1, prior_amount + campaign["discount"])
            activity_items = []
            for product, _sku, quantity, _variants, activity_id in items:
                if not activity_id:
                    continue
                activity_product = active_activity_product(connection, activity_id, product["id"])
                reserved = provisional_activity_usage.get(activity_product["id"], 0)
                if activity_product["quota_stock"] - activity_product["reserved_stock"] - reserved < quantity:
                    raise ValueError("活动配额不足")
                provisional_activity_usage[activity_product["id"]] = reserved + quantity
                activity_items.append({"id": activity_product["activity_id"], "name": activity_product["activity_name"], "productId": product["id"], "quantity": quantity})
            shop_name = connection.execute("SELECT name FROM shops WHERE id = ?", (shop_id,)).fetchone()[0]
            shops.append({"shopId": shop_id, "shop": shop_name, "itemAmount": amount / 100, "shippingAmount": shipping / 100, "discountAmount": discount / 100, "amount": (amount + shipping - discount) / 100, "currency": PLATFORM_CURRENCY, "platformCampaign": campaign["name"] if campaign else None, "activities": activity_items, "shippingRule": shipping_rule})
            item_total += amount
            shipping_total += shipping
            discount_total += discount
        return {"shops": shops, "itemAmount": item_total / 100, "shippingAmount": shipping_total / 100, "discountAmount": discount_total / 100, "amount": (item_total + shipping_total - discount_total) / 100, "currency": PLATFORM_CURRENCY, "exchangeRate": USD_EXCHANGE_RATE}


def sku_variants(connection: sqlite3.Connection, sku_id: str | None) -> dict:
    if not sku_id:
        return {}
    row = connection.execute("SELECT option_value_ids FROM product_skus WHERE id = ?", (sku_id,)).fetchone()
    if not row:
        return {}
    value_ids = json.loads(row[0] or "[]")
    if not value_ids:
        return {}
    placeholders = ",".join("?" for _ in value_ids)
    return {
        item["name"]: item["value"]
        for item in connection.execute(
            f"SELECT product_options.name, product_option_values.value FROM product_option_values JOIN product_options ON product_options.id = product_option_values.option_id WHERE product_option_values.id IN ({placeholders})",
            tuple(value_ids),
        )
    }


def buyer_state(connection: sqlite3.Connection, user_id: str) -> dict:
    connection.row_factory = sqlite3.Row
    cart = []
    for row in connection.execute(
        "SELECT cart_items.product_id, cart_items.sku_id, cart_items.quantity FROM carts JOIN cart_items ON cart_items.cart_id = carts.id WHERE carts.buyer_user_id = ?",
        (user_id,),
    ):
        cart.append({"productId": catalog_product_number(row["product_id"]), "catalogId": row["product_id"], "quantity": row["quantity"], "variants": sku_variants(connection, row["sku_id"])})
    favorites = [catalog_product_number(row[0]) for row in connection.execute("SELECT product_id FROM buyer_favorites WHERE buyer_user_id = ?", (user_id,))]
    follows = [
        {"id": row["id"], "name": row["name"]}
        for row in connection.execute("SELECT shops.id, shops.name FROM buyer_shop_follows JOIN shops ON shops.id = buyer_shop_follows.shop_id WHERE buyer_user_id = ?", (user_id,))
    ]
    unread = connection.execute("SELECT COUNT(*) FROM shop_messages WHERE buyer_user_id = ? AND sender_role = 'seller' AND read_at IS NULL", (user_id,)).fetchone()[0]
    return {"cart": cart, "favorites": favorites, "followedShops": follows, "unreadMessages": unread}


def seller_can_manage_order(connection: sqlite3.Connection, user_id: str, order_no: str) -> sqlite3.Row:
    shop_ids = seller_shop_ids(connection, user_id)
    if not shop_ids:
        raise ValueError("当前账号没有店铺")
    placeholders = ",".join("?" for _ in shop_ids)
    order = connection.execute(
        f"SELECT * FROM orders WHERE order_no = ? AND shop_id IN ({placeholders})",
        (order_no, *shop_ids),
    ).fetchone()
    if not order:
        raise ValueError("无权操作该订单")
    return order


AFTER_SALE_STATUS_LABELS = {
    "pending": "待处理",
    "approved": "已同意",
    "rejected": "已拒绝",
    "completed": "已退款",
    "cancelled": "已取消",
}


def after_sales_for_response(connection: sqlite3.Connection, where: str, params: tuple[object, ...]) -> list[dict]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        f"""
        SELECT after_sale_requests.*, order_refunds.status AS refund_status, orders.order_no, shops.location AS return_address,
               shops.settings_json AS shop_settings_json
        FROM after_sale_requests
        JOIN orders ON orders.id = after_sale_requests.order_id
        JOIN shops ON shops.id = orders.shop_id
        LEFT JOIN order_refunds ON order_refunds.after_sale_id = after_sale_requests.id
        WHERE {where} ORDER BY after_sale_requests.created_at DESC
        """,
        params,
    ).fetchall()
    def status_label(row: sqlite3.Row) -> str:
        if row["status"] == "completed" and row["refund_status"] == "recorded":
            return "退款已记账"
        if row["status"] == "approved" and row["request_type"] == "return_refund":
            return "待收货" if row["returned_at"] else "待退货"
        return AFTER_SALE_STATUS_LABELS[row["status"]]

    def timeline(row: sqlite3.Row) -> list[dict]:
        events = [{"time": row["created_at"], "label": "买家提交售后申请", "detail": row["reason"]}]
        if row["seller_processed_at"]:
            if row["status"] == "rejected":
                label = "卖家已拒绝申请"
            elif row["request_type"] == "return_refund":
                label = "卖家同意退货退款"
            else:
                label = "卖家同意退款，退款已完成"
            events.append({"time": row["seller_processed_at"], "label": label, "detail": row["seller_response"] or ""})
        if row["returned_at"]:
            events.append({"time": row["returned_at"], "label": "买家已寄回作品", "detail": f"{row['return_carrier']} · {row['return_tracking_no']}"})
        if row["received_at"]:
            events.append({"time": row["received_at"], "label": "卖家确认收货，退款已完成", "detail": row["seller_response"] or ""})
        return events

    def return_details(row: sqlite3.Row) -> dict:
        try:
            settings = json.loads(row["shop_settings_json"] or "{}")
        except (TypeError, json.JSONDecodeError):
            settings = {}
        policy = settings.get("returnPolicy") if isinstance(settings, dict) else {}
        if not isinstance(policy, dict):
            policy = {}
        return {
            "address": str(policy.get("address") or row["return_address"] or "").strip(),
            "recipientName": str(policy.get("recipientName") or "").strip(),
            "recipientPhone": str(policy.get("recipientPhone") or "").strip(),
        }

    return [
        {
            "id": row["id"],
            "orderId": row["order_no"],
            "type": "退款" if row["request_type"] == "refund" else "退货退款",
            "reason": row["reason"],
            "status": status_label(row),
            "amount": row["requested_amount_cents"] / 100,
            "currency": row["refund_currency"],
            "exchangeRate": row["refund_exchange_rate"],
            "refundStatus": row["refund_status"],
            "sellerResponse": row["seller_response"],
            "evidence": [item[0] for item in connection.execute("SELECT image_url FROM after_sale_evidence WHERE after_sale_id = ? ORDER BY sort_order", (row["id"],))],
            "returnAddress": (details := return_details(row))["address"],
            "returnRecipientName": details["recipientName"],
            "returnRecipientPhone": details["recipientPhone"],
            "returnShipment": (
                {"carrier": row["return_carrier"], "trackingNo": row["return_tracking_no"], "shippedAt": row["returned_at"]}
                if row["returned_at"]
                else None
            ),
            "timeline": timeline(row),
            "createdAt": row["created_at"],
        }
        for row in rows
    ]


def reviews_for_response(connection: sqlite3.Connection, where: str, params: tuple[object, ...]) -> list[dict]:
    connection.row_factory = sqlite3.Row
    rows = connection.execute(
        f"""
        SELECT reviews.*, orders.order_no, order_items.product_id, users.display_name AS buyer_name
        FROM reviews
        JOIN order_items ON order_items.id = reviews.order_item_id
        JOIN orders ON orders.id = order_items.order_id
        LEFT JOIN users ON users.id = reviews.buyer_user_id
        WHERE {where} ORDER BY reviews.created_at DESC
        """,
        params,
    ).fetchall()
    return [
        {
            "id": row["id"],
            "orderId": row["order_no"],
            "productId": catalog_product_number(row["product_id"] or ""),
            "buyerName": row["buyer_name"] or "匿名买家",
            "rating": row["rating"],
            "content": row["content"],
            "sellerReply": row["seller_reply"],
            "images": [image[0] for image in connection.execute("SELECT image_url FROM review_images WHERE review_id = ? ORDER BY sort_order", (row["id"],))],
            "followup": (connection.execute("SELECT content FROM review_followups WHERE review_id = ?", (row["id"],)).fetchone() or [None])[0],
            "createdAt": row["created_at"],
        }
        for row in rows
    ]


def migrate_legacy_accounts(payload: dict) -> dict:
    accounts = payload.get("accounts") or []
    states = payload.get("states") or {}
    migrated = 0
    state_count = 0
    account_ids: dict[str, str] = {}
    with database() as connection:
        for account in accounts:
            account_id = str(account.get("id") or "").strip()
            name = str(account.get("name") or "").strip()
            phone = str(account.get("phone") or "").strip() or None
            email = str(account.get("email") or "").strip().lower() or None
            password = str(account.get("password") or "")
            role = account.get("role") if account.get("role") in ("buyer", "seller") else "buyer"
            if not account_id or not name or not password or not (phone or email):
                continue
            existing = connection.execute(
                "SELECT id FROM users WHERE id = ? OR phone = ? OR lower(email) = ?",
                (account_id, phone, email),
            ).fetchone()
            user_id = existing[0] if existing else account_id
            if not existing:
                connection.execute(
                    "INSERT INTO users (id, display_name, phone, email, password_hash) VALUES (?, ?, ?, ?, ?)",
                    (user_id, name, phone, email, password),
                )
                migrated += 1
            connection.execute("INSERT OR IGNORE INTO user_roles (user_id, role) VALUES (?, ?)", (user_id, role))
            account_ids[account_id] = user_id
            state = states.get(account_id)
            if isinstance(state, dict):
                connection.execute(
                    "INSERT OR IGNORE INTO application_states (user_id, state_json) VALUES (?, ?)",
                    (user_id, json.dumps(state, ensure_ascii=False)),
                )
                state_count += 1
    return {"accounts": migrated, "states": state_count, "accountIds": account_ids}


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def cors_origin(self) -> str | None:
        origin = self.headers.get("Origin", "").rstrip("/")
        if PRODUCTION_HTTPS:
            return origin if origin in ALLOWED_BROWSER_ORIGINS else None
        if origin.startswith("http://127.0.0.1:") or origin.startswith("http://localhost:"):
            return origin
        return "http://127.0.0.1:5174"

    def websocket_origin_is_allowed(self) -> bool:
        origin = self.headers.get("Origin", "")
        if not origin:
            return False
        normalized_origin = origin.rstrip("/")
        if PRODUCTION_HTTPS:
            return normalized_origin in ALLOWED_BROWSER_ORIGINS
        parsed = urlparse(origin)
        if parsed.scheme not in {"http", "https"}:
            return False
        if parsed.hostname in {"127.0.0.1", "localhost"}:
            return True
        return parsed.netloc.lower() == self.headers.get("Host", "").lower()

    def read_websocket_frame(self) -> tuple[int, bytes] | None:
        head = self.rfile.read(2)
        if len(head) != 2:
            return None
        opcode = head[0] & 0x0F
        masked, length = bool(head[1] & 0x80), head[1] & 0x7F
        if length == 126:
            raw_length = self.rfile.read(2)
            if len(raw_length) != 2:
                return None
            length = int.from_bytes(raw_length, "big")
        elif length == 127:
            raw_length = self.rfile.read(8)
            if len(raw_length) != 8:
                return None
            length = int.from_bytes(raw_length, "big")
        if not masked or length > 1024 * 1024:
            return None
        mask = self.rfile.read(4)
        body = self.rfile.read(length)
        if len(mask) != 4 or len(body) != length:
            return None
        return opcode, bytes(value ^ mask[index % 4] for index, value in enumerate(body))

    def handle_websocket(self) -> None:
        user_id = session_user(self)
        upgrade = self.headers.get("Upgrade", "").lower()
        connection = self.headers.get("Connection", "").lower()
        key = self.headers.get("Sec-WebSocket-Key", "")
        try:
            valid_key = len(base64.b64decode(key.encode("ascii"), validate=True)) == 16
        except (ValueError, binascii.Error, UnicodeEncodeError):
            valid_key = False
        if not user_id:
            self.send_json(401, {"error": "Unauthorized"})
            return
        if upgrade != "websocket" or "upgrade" not in connection or not valid_key:
            self.send_json(426, {"error": "WebSocket upgrade required"})
            return
        if not self.websocket_origin_is_allowed():
            self.send_json(403, {"error": "WebSocket origin denied"})
            return
        accept = base64.b64encode(hashlib.sha1(f"{key}258EAFA5-E914-47DA-95CA-C5AB0DC85B11".encode("ascii")).digest()).decode("ascii")
        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "websocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        self.wfile.flush()
        LIVE_MESSAGE_HUB.add(user_id, self.connection)
        try:
            while True:
                frame = self.read_websocket_frame()
                if frame is None:
                    break
                opcode, body = frame
                if opcode == 0x8:
                    self.connection.sendall(bytes((0x88, min(len(body), 125))) + body[:125])
                    break
                if opcode == 0x9:
                    self.connection.sendall(bytes((0x8A, min(len(body), 125))) + body[:125])
        except OSError:
            pass
        finally:
            LIVE_MESSAGE_HUB.remove(user_id, self.connection)
            self.close_connection = True

    def handle_community_websocket(self) -> None:
        visitor_id = str(parse_qs(urlparse(self.path).query).get("visitorId", [""])[0]).strip()
        upgrade = self.headers.get("Upgrade", "").lower()
        connection = self.headers.get("Connection", "").lower()
        key = self.headers.get("Sec-WebSocket-Key", "")
        try:
            valid_key = len(base64.b64decode(key.encode("ascii"), validate=True)) == 16
        except (ValueError, binascii.Error, UnicodeEncodeError):
            valid_key = False
        if not re.fullmatch(r"[A-Za-z0-9_-]{8,120}", visitor_id):
            self.send_json(400, {"error": "Community visitor identity is invalid"})
            return
        if upgrade != "websocket" or "upgrade" not in connection or not valid_key:
            self.send_json(426, {"error": "WebSocket upgrade required"})
            return
        if not self.websocket_origin_is_allowed():
            self.send_json(403, {"error": "WebSocket origin denied"})
            return
        accept = base64.b64encode(hashlib.sha1(f"{key}258EAFA5-E914-47DA-95CA-C5AB0DC85B11".encode("ascii")).digest()).decode("ascii")
        self.send_response(101, "Switching Protocols")
        self.send_header("Upgrade", "WebSocket")
        self.send_header("Connection", "Upgrade")
        self.send_header("Sec-WebSocket-Accept", accept)
        self.end_headers()
        self.wfile.flush()
        COMMUNITY_LIVE_HUB.add(self.connection)
        try:
            while True:
                frame = self.read_websocket_frame()
                if frame is None:
                    break
                opcode, body = frame
                if opcode == 0x8:
                    self.connection.sendall(bytes((0x88, min(len(body), 125))) + body[:125])
                    break
                if opcode == 0x9:
                    self.connection.sendall(bytes((0x8A, min(len(body), 125))) + body[:125])
        except OSError:
            pass
        finally:
            COMMUNITY_LIVE_HUB.remove(self.connection)
            self.close_connection = True

    def send_json(
        self,
        status: int,
        payload: dict,
        cookie: str | None = None,
        extra_headers: dict[str, str] | None = None,
    ) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        self.send_header("Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'; base-uri 'none'")
        if PRODUCTION_HTTPS:
            self.send_header("Strict-Transport-Security", "max-age=31536000; includeSubDomains")
        self.send_header("Cache-Control", "no-store")
        if origin := self.cors_origin():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Credentials", "true")
            self.send_header("Access-Control-Expose-Headers", "X-CSRF-Token")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        for name, value in (extra_headers or {}).items():
            self.send_header(name, value)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def enforce_rate_limit(
        self,
        action: str,
        user_id: str | None,
        *,
        per_ip: int,
        per_user: int | None,
        window_seconds: int,
    ) -> bool:
        """Limit a sensitive action by IP and, when signed in, by account."""
        subjects = [(f"ip:{client_ip(self)}", per_ip)]
        if user_id and per_user is not None:
            subjects.insert(0, (f"user:{user_id}", per_user))
        for subject, maximum in subjects:
            allowed, retry_after = REQUEST_RATE_LIMITER.allow(
                action, subject, maximum, window_seconds
            )
            if not allowed:
                self.send_json(
                    429,
                    {"error": "操作过于频繁，请稍后再试", "retryAfter": retry_after},
                    extra_headers={"Retry-After": str(retry_after)},
                )
                return False
        return True

    def request_body_length(self) -> int | None:
        """Return a safe request-body length or send the matching API error."""
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self.send_json(400, {"error": "Invalid Content-Length"})
            return None
        if length < 0:
            self.send_json(400, {"error": "Invalid Content-Length"})
            return None
        if length > MAX_REQUEST_BODY_BYTES:
            self.send_json(413, {"error": "请求内容过大"})
            return None
        return length

    def browser_origin_is_allowed(self) -> bool:
        origin = self.headers.get("Origin", "").rstrip("/")
        if not origin:
            return False
        if PRODUCTION_HTTPS:
            return origin in ALLOWED_BROWSER_ORIGINS
        parsed = urlparse(origin)
        return parsed.scheme in {"http", "https"} and parsed.hostname in {"127.0.0.1", "localhost"}

    def enforce_state_change_protection(self) -> bool:
        """Require a trusted browser origin and CSRF token for cookie writes."""
        path = urlparse(self.path).path
        # Provider webhooks verify a signed raw payload instead of browser headers.
        if path in {"/api/integrations/logistics/webhooks", "/api/integrations/customer-service/webhooks"}:
            return True
        if not self.browser_origin_is_allowed():
            self.send_json(403, {"error": "Untrusted request origin"})
            return False
        if not valid_session_csrf_token(self):
            self.send_json(403, {"error": "Invalid CSRF token"})
            return False
        return True

    def send_media(self, filename: str) -> None:
        safe_name = Path(filename).name
        path = MEDIA_DIR / safe_name
        if not path.is_file():
            path = LEGACY_MEDIA_DIR / safe_name
        if safe_name != filename or not path.is_file():
            self.send_json(404, {"error": "Media not found"})
            return
        suffix = path.suffix.lower()
        content_type = {
            ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp",
            ".mp4": "video/mp4", ".webm": "video/webm", ".mov": "video/quicktime",
        }.get(suffix, "application/octet-stream")
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "public, max-age=31536000, immutable")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def send_quarantined_product_media(self, asset_id: str) -> None:
        """Serve a verified temporary asset only to the seller who uploaded it."""
        user_id = session_user(self)
        if not user_id:
            self.send_json(401, {"error": "Unauthorized"})
            return
        with database() as connection:
            connection.row_factory = sqlite3.Row
            asset = connection.execute(
                "SELECT * FROM media_assets WHERE id = ? AND uploader_user_id = ? AND status = 'temporary' "
                "AND verified_at IS NOT NULL AND moderation_status = 'approved'",
                (asset_id, user_id),
            ).fetchone()
        if not asset:
            self.send_json(404, {"error": "Temporary media not found"})
            return
        try:
            body = quarantined_media_bytes(asset)
        except ValueError:
            self.send_json(404, {"error": "Temporary media not found"})
            return
        self.send_response(200)
        self.send_header("Content-Type", asset["mime_type"])
        self.send_header("Cache-Control", "private, no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        if origin := self.cors_origin():
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Admin-Step-Up, X-CSRF-Token")
            self.send_header("Access-Control-Allow-Credentials", "true")
        self.end_headers()

    def do_GET(self) -> None:
        if urlparse(self.path).path == "/ws":
            self.handle_websocket()
        elif urlparse(self.path).path == "/ws/community":
            self.handle_community_websocket()
        elif self.path == "/api/push/config":
            self.send_json(200, {"publicKey": VAPID_PUBLIC_KEY if web_push_is_configured() else None})
        elif self.path == "/health":
            self.send_json(200, {"ok": True})
        elif urlparse(self.path).path == "/api/community/posts":
            category = str(parse_qs(urlparse(self.path).query).get("category", [""])[0]).strip()
            if category and category not in COMMUNITY_CATEGORIES:
                self.send_json(400, {"error": "社区分类无效"})
                return
            with database() as connection:
                self.send_json(200, {"posts": community_posts_payload(connection, category)})
        elif self.path == "/api/admin/community/posts":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            require_admin(user_id)
            with database() as connection:
                self.send_json(200, {"posts": admin_community_posts_payload(connection)})
        elif urlparse(self.path).path.startswith("/api/seller/media/assets/") and urlparse(self.path).path.endswith("/preview"):
            asset_id = urlparse(self.path).path.removeprefix("/api/seller/media/assets/").removesuffix("/preview").strip("/")
            if not re.fullmatch(r"asset-[A-Za-z0-9_-]{8,120}", asset_id):
                self.send_json(404, {"error": "Temporary media not found"})
                return
            self.send_quarantined_product_media(asset_id)
        elif self.path.startswith("/media/"):
            self.send_media(self.path.removeprefix("/media/"))
        elif urlparse(self.path).path == "/api/brand-site":
            values = parse_qs(urlparse(self.path).query)
            requested_domain = str(values.get("domain", [self.headers.get("Host", "").split(":", 1)[0]])[0])[:255]
            requested_shop = str(values.get("shop", [""])[0])[:160]
            preview_requested = str(values.get("preview", [""])[0]).strip(" \t,，") == "1"
            payload = public_brand_site(
                requested_domain,
                requested_shop,
                session_user(self) if preview_requested else None,
            )
            if not payload:
                self.send_json(404, {"error": "独立站不存在、尚未启用，或域名未绑定"})
                return
            self.send_json(200, payload)
        elif self.path == "/api/catalog/products":
            self.send_json(200, {"products": catalog()})
        elif self.path == "/api/activities":
            with database() as connection:
                connection.row_factory = sqlite3.Row
                rows = connection.execute("SELECT * FROM platform_activities WHERE status = 'active' AND (starts_at IS NULL OR starts_at <= CURRENT_TIMESTAMP) AND (ends_at IS NULL OR ends_at > CURRENT_TIMESTAMP) ORDER BY starts_at, created_at DESC").fetchall()
                activities = [activity_response(connection, row) for row in rows]
            self.send_json(200, {"activities": activities})
        elif self.path.startswith("/api/activities/"):
            activity_id = self.path.removeprefix("/api/activities/").rstrip("/")
            with database() as connection:
                connection.row_factory = sqlite3.Row
                activity = connection.execute("SELECT * FROM platform_activities WHERE id = ? AND status = 'active' AND (starts_at IS NULL OR starts_at <= CURRENT_TIMESTAMP) AND (ends_at IS NULL OR ends_at > CURRENT_TIMESTAMP)", (activity_id,)).fetchone()
                if not activity:
                    self.send_json(404, {"error": "Activity not found"})
                    return
                payload = activity_response(connection, activity)
            self.send_json(200, {"activity": payload})
        elif urlparse(self.path).path == "/api/search/suggestions":
            values = parse_qs(urlparse(self.path).query)
            keyword = str(values.get("q", [""])[0])[:50]
            user_id = session_user(self)
            with database() as connection:
                suggestions = search_suggestions(connection, keyword, user_id)
            self.send_json(200, {"suggestions": suggestions})
        elif urlparse(self.path).path == "/api/search":
            values = parse_qs(urlparse(self.path).query)
            keyword = str(values.get("q", [""])[0]).strip()[:50]
            category = str(values.get("category", [""])[0]).strip()
            sort = str(values.get("sort", ["relevance"])[0])
            if sort not in ("relevance", "latest", "price_asc", "price_desc", "sales"):
                sort = "relevance"
            user_id = session_user(self)
            with database() as connection:
                operations = search_operations(connection, keyword)
                products = search_catalog(operations["normalized"], category, sort, operations["terms"], user_id)
                zero_rule = connection.execute("SELECT message, product_id FROM search_zero_result_rules WHERE keyword IN (?, ?) AND enabled = 1", (operations["original"], operations["normalized"])).fetchone() if not products and keyword else None
                suggestions = search_suggestions(connection, operations["normalized"], user_id)
                recommendations = list(dict.fromkeys([*operations["recommendations"], *(item["value"] for item in suggestions if item["type"] in ("recommendation", "tag", "trending"))]))[:8]
                personalized_products = personal_recommendations(connection, user_id) if not keyword and category == "" else []
                if keyword:
                    connection.execute("INSERT INTO search_query_metrics (id, keyword, corrected_keyword, result_count, user_id) VALUES (?, ?, ?, ?, ?)", (f"search-metric-{secrets.token_urlsafe(10)}", operations["original"], operations["corrected"], len(products), user_id))
                if keyword and user_id:
                    connection.execute("INSERT INTO search_history (id, user_id, keyword) VALUES (?, ?, ?)", (f"search-{secrets.token_urlsafe(8)}", user_id, operations["original"]))
                    connection.execute("DELETE FROM search_history WHERE id IN (SELECT id FROM search_history WHERE user_id = ? ORDER BY created_at DESC LIMIT -1 OFFSET 20)", (user_id,))
            self.send_json(200, {"products": products, "query": operations["normalized"], "originalQuery": keyword, "corrected": operations["corrected"], "correctionSource": operations["correctionSource"], "recommendations": recommendations, "personalizedProducts": personalized_products, "suggestions": suggestions, "zeroResult": ({"message": zero_rule[0], "productId": zero_rule[1]} if zero_rule else None), "sort": sort})
        elif self.path == "/api/search/history":
            user_id = session_user(self)
            if not user_id:
                self.send_json(200, {"history": []})
                return
            with database() as connection:
                history = [row[0] for row in connection.execute("SELECT keyword FROM search_history WHERE user_id = ? GROUP BY keyword ORDER BY MAX(created_at) DESC LIMIT 10", (user_id,))]
            self.send_json(200, {"history": history})
        elif urlparse(self.path).path == "/api/admin/search-operations":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                if not is_admin(connection, user_id):
                    self.send_json(403, {"error": "Administrator access required"})
                    return
                values = parse_qs(urlparse(self.path).query)
                try:
                    days = int(values.get("days", ["30"])[0])
                except ValueError:
                    days = 30
                payload = search_operations_payload(connection, days)
            self.send_json(200, payload)
        elif self.path == "/api/addresses":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                connection.row_factory = sqlite3.Row
                addresses = [
                    address_for_response(row)
                    for row in connection.execute(
                        "SELECT * FROM buyer_addresses WHERE buyer_user_id = ? ORDER BY is_default DESC, updated_at DESC",
                        (user_id,),
                    )
                ]
            self.send_json(200, {"addresses": addresses})
        elif self.path == "/api/buyer/coupons":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                connection.row_factory = sqlite3.Row
                claimable = connection.execute("SELECT platform_campaigns.*, platform_campaign_claims.claimed_quantity FROM platform_campaigns LEFT JOIN platform_campaign_claims ON platform_campaign_claims.campaign_id = platform_campaigns.id AND platform_campaign_claims.buyer_user_id = ? WHERE platform_campaigns.campaign_type = 'coupon' AND platform_campaigns.status = 'active' AND (platform_campaigns.starts_at IS NULL OR platform_campaigns.starts_at <= CURRENT_TIMESTAMP) AND (platform_campaigns.ends_at IS NULL OR platform_campaigns.ends_at > CURRENT_TIMESTAMP) AND COALESCE(platform_campaign_claims.claimed_quantity, 0) < platform_campaigns.per_user_claim_limit ORDER BY platform_campaigns.created_at DESC", (user_id,)).fetchall()
                self.send_json(200, {"coupons": buyer_coupons(connection, user_id), "claimable": [{"id": row["id"], "name": row["name"], "threshold": number(json.loads(row["rule_json"] or "{}").get("threshold")), "discount": number(json.loads(row["rule_json"] or "{}").get("discount")), "claimLimit": row["per_user_claim_limit"]} for row in claimable]})
        elif self.path == "/api/buyer/state":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                self.send_json(200, buyer_state(connection, user_id))
        elif urlparse(self.path).path == "/api/messages/buyer":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                values = parse_qs(urlparse(self.path).query)
                shop_id = str(values.get("shopId", [""])[0]) or None
                payload = buyer_messages_payload(connection, user_id, shop_id, str(values.get("q", [""])[0]).strip())
            self.send_json(200, payload)
        elif urlparse(self.path).path == "/api/messages/seller":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                values = parse_qs(urlparse(self.path).query)
                shop_id = str(values.get("shopId", [""])[0]) or None
                buyer_id = str(values.get("buyerUserId", [""])[0]) or None
                payload = seller_messages_payload(connection, user_id, shop_id, buyer_id, str(values.get("q", [""])[0]).strip())
            self.send_json(200, payload)
        elif urlparse(self.path).path == "/api/seller/message-automation":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            values = parse_qs(urlparse(self.path).query)
            shop_id = str(values.get("shopId", [""])[0]).strip()
            with database() as connection:
                shop_ids = seller_accessible_shop_ids(connection, user_id, "messages")
                if not shop_id:
                    shop_id = shop_ids[0] if shop_ids else ""
                if not shop_id or shop_id not in shop_ids:
                    self.send_json(403, {"error": "Seller message permission required"})
                    return
                self.send_json(200, {"shopId": shop_id, "settings": shop_message_settings(connection, shop_id)})
        elif urlparse(self.path).path == "/api/messages/buyer/updates":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            values = parse_qs(urlparse(self.path).query)
            with database() as connection:
                payload = message_updates_payload(
                    connection, user_id, "buyer", str(values.get("shopId", [""])[0]), None,
                    int(values.get("after", ["0"])[0]),
                )
            self.send_json(200, payload)
        elif urlparse(self.path).path == "/api/messages/seller/updates":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            values = parse_qs(urlparse(self.path).query)
            with database() as connection:
                payload = message_updates_payload(
                    connection, user_id, "seller", str(values.get("shopId", [""])[0]),
                    str(values.get("buyerUserId", [""])[0]) or None,
                    int(values.get("after", ["0"])[0]),
                )
            self.send_json(200, payload)
        elif self.path == "/api/messages/quick-replies":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                if not is_seller(connection, user_id):
                    self.send_json(403, {"error": "Seller access required"})
                    return
                replies = connection.execute("SELECT id, content, category FROM seller_quick_replies WHERE seller_user_id = ? ORDER BY category, updated_at DESC", (user_id,)).fetchall()
            self.send_json(200, {"quickReplies": [{"id": row[0], "content": row[1], "category": row[2]} for row in replies]})
        elif self.path == "/api/support/tickets":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                self.send_json(200, {"tickets": support_tickets_for(connection, user_id, "buyer")})
        elif self.path.startswith("/api/support/tickets/"):
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            ticket_id = self.path.removeprefix("/api/support/tickets/").rstrip("/")
            with database() as connection:
                connection.row_factory = sqlite3.Row
                ticket = connection.execute("SELECT * FROM support_tickets WHERE id = ?", (ticket_id,)).fetchone()
                if not ticket or not support_ticket_access(connection, ticket, user_id, "buyer"):
                    self.send_json(404, {"error": "Ticket not found"})
                    return
                self.send_json(200, {"ticket": support_ticket_response(connection, ticket, True)})
        elif self.path == "/api/seller/support/tickets":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                if not is_seller(connection, user_id):
                    self.send_json(403, {"error": "Seller access required"})
                    return
                self.send_json(200, {"tickets": support_tickets_for(connection, user_id, "seller")})
        elif self.path == "/api/seller/platform-support/tickets":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                if not is_seller(connection, user_id):
                    self.send_json(403, {"error": "Seller access required"})
                    return
                self.send_json(200, {"tickets": support_tickets_for(connection, user_id, "platform_seller")})
        elif self.path.startswith("/api/seller/platform-support/tickets/"):
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            ticket_id = self.path.removeprefix("/api/seller/platform-support/tickets/").rstrip("/")
            with database() as connection:
                connection.row_factory = sqlite3.Row
                if not is_seller(connection, user_id):
                    self.send_json(403, {"error": "Seller access required"})
                    return
                ticket = connection.execute("SELECT * FROM support_tickets WHERE id = ?", (ticket_id,)).fetchone()
                if not ticket or not support_ticket_access(connection, ticket, user_id, "platform_seller"):
                    self.send_json(404, {"error": "Ticket not found"})
                    return
                self.send_json(200, {"ticket": support_ticket_response(connection, ticket, True)})
        elif self.path.startswith("/api/seller/support/tickets/"):
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            ticket_id = self.path.removeprefix("/api/seller/support/tickets/").rstrip("/")
            with database() as connection:
                connection.row_factory = sqlite3.Row
                ticket = connection.execute("SELECT * FROM support_tickets WHERE id = ?", (ticket_id,)).fetchone()
                if not ticket or not support_ticket_access(connection, ticket, user_id, "seller"):
                    self.send_json(404, {"error": "Ticket not found"})
                    return
                self.send_json(200, {"ticket": support_ticket_response(connection, ticket, True)})
        elif self.path == "/api/seller/verification":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                connection.row_factory = sqlite3.Row
                if not is_seller(connection, user_id):
                    self.send_json(403, {"error": "Seller access required"})
                    return
                profile = connection.execute("SELECT verification_status, legal_name, identity_number, contact_phone, business_address, operating_categories_json, verification_expires_at, verification_expiry_notified_at FROM seller_profiles WHERE user_id = ?", (user_id,)).fetchone()
                application = connection.execute("SELECT * FROM seller_verification_applications WHERE seller_user_id = ? AND NOT (status = 'rejected' AND rejection_code = 'seller_withdrew') ORDER BY created_at DESC LIMIT 1", (user_id,)).fetchone()
                # Older registration builds created an empty pending application
                # before the seller had uploaded any materials. It was not a real
                # submission and must not lock the seller in an audit state.
                if application and application["status"] == "pending":
                    document_count = connection.execute("SELECT COUNT(*) FROM seller_verification_documents WHERE application_id = ?", (application["id"],)).fetchone()[0]
                    evidence = json.loads(application["evidence_json"] or "[]")
                    if not document_count and not evidence:
                        connection.execute("UPDATE seller_verification_applications SET status = 'rejected', rejection_code = 'seller_withdrew', review_note = '系统已清理旧版注册生成的空认证申请', reviewed_at = CURRENT_TIMESTAMP WHERE id = ?", (application["id"],))
                        connection.execute("UPDATE seller_profiles SET verification_status = 'pending' WHERE user_id = ?", (user_id,))
                        profile = connection.execute("SELECT verification_status, legal_name, identity_number, contact_phone, business_address, operating_categories_json, verification_expires_at, verification_expiry_notified_at FROM seller_profiles WHERE user_id = ?", (user_id,)).fetchone()
                        application = None
                expired = bool(profile and profile["verification_status"] == "approved" and profile["verification_expires_at"] and profile["verification_expires_at"] <= datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
                if expired and not profile["verification_expiry_notified_at"]:
                    connection.execute("UPDATE seller_profiles SET verification_expiry_notified_at = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,))
                    notify_governance(connection, user_id, "seller_verification_expired", "卖家认证已到期", "请提交新的认证资料后继续经营", "seller_verification", application["id"] if application else user_id)
                verification = {"status": "expired" if expired else (profile["verification_status"] if profile else "pending"), "legalName": profile["legal_name"] if profile else "", "identityNumber": profile["identity_number"] if profile else "", "contactPhone": profile["contact_phone"] if profile else "", "businessAddress": profile["business_address"] if profile else "", "operatingCategories": json.loads(profile["operating_categories_json"] or "[]") if profile else [], "expiresAt": profile["verification_expires_at"] if profile else None, "application": None if not application else verification_application_response(connection, application)}
            self.send_json(200, {"verification": verification})
        elif self.path == "/api/seller/staff/audit":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                connection.row_factory = sqlite3.Row
                shop_ids = [row[0] for row in connection.execute("SELECT id FROM shops WHERE owner_user_id IN (?, ?)", (user_id, f"legacy-seller-{user_id}"))]
                if not shop_ids:
                    self.send_json(403, {"error": "Staff management requires shop owner permission"})
                    return
                rows = connection.execute(f"SELECT shop_staff_audit_logs.*, users.display_name AS actor FROM shop_staff_audit_logs JOIN users ON users.id = shop_staff_audit_logs.actor_user_id WHERE shop_id IN ({','.join('?' for _ in shop_ids)}) ORDER BY created_at DESC LIMIT 100", tuple(shop_ids)).fetchall()
            self.send_json(200, {"logs": [{"id": row["id"], "shopId": row["shop_id"], "staffUserId": row["staff_user_id"], "action": row["action"], "detail": json.loads(row["detail_json"]), "actor": row["actor"], "createdAt": row["created_at"]} for row in rows]})
        elif self.path == "/api/seller/staff":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                connection.row_factory = sqlite3.Row
                shop_ids = [row[0] for row in connection.execute("SELECT id FROM shops WHERE owner_user_id IN (?, ?)", (user_id, f"legacy-seller-{user_id}"))]
                if not shop_ids:
                    self.send_json(403, {"error": "Staff management requires shop owner permission"})
                    return
                rows = connection.execute(f"SELECT shop_staff.*, users.display_name, users.phone, users.email FROM shop_staff JOIN users ON users.id = shop_staff.user_id WHERE shop_staff.shop_id IN ({','.join('?' for _ in shop_ids)}) ORDER BY shop_staff.created_at DESC", tuple(shop_ids)).fetchall()
            self.send_json(200, {"staff": [{"id": row["id"], "shopId": row["shop_id"], "name": row["display_name"], "phone": row["phone"], "email": row["email"], "role": row["role"], "permissions": json.loads(row["permissions_json"] or "[]"), "status": row["status"], "createdAt": row["created_at"]} for row in rows]})
        elif self.path == "/api/notifications":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                connection.row_factory = sqlite3.Row
                rows = connection.execute("SELECT * FROM governance_notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 50", (user_id,)).fetchall()
                unread = connection.execute("SELECT COUNT(*) FROM governance_notifications WHERE user_id = ? AND read_at IS NULL", (user_id,)).fetchone()[0]
            self.send_json(200, {"unread": unread, "notifications": [{"id": row["id"], "type": row["notification_type"], "title": row["title"], "content": row["content"], "relatedType": row["related_type"], "relatedId": row["related_id"], "read": bool(row["read_at"]), "createdAt": row["created_at"]} for row in rows]})
        elif self.path == "/api/seller/products":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                if not is_seller(connection, user_id):
                    self.send_json(403, {"error": "Seller access required"})
                    return
                self.send_json(200, {"products": catalog(tuple(seller_accessible_shop_ids(connection, user_id, "products")))})
        elif self.path == "/api/seller/workspace":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                if not is_seller(connection, user_id):
                    self.send_json(403, {"error": "Seller access required"})
                    return
            self.send_json(200, seller_workspace(user_id))
        elif self.path == "/api/seller/finance":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                if not is_seller(connection, user_id):
                    self.send_json(403, {"error": "Seller access required"})
                    return
                payload = seller_finance_payload(connection, user_id)
            self.send_json(200, payload)
        elif self.path == "/api/seller/payout-account":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                if not is_seller(connection, user_id):
                    self.send_json(403, {"error": "Seller access required"})
                    return
                self.send_json(200, {"payoutAccount": seller_payout_account_payload(connection, user_id)})
        elif urlparse(self.path).path == "/api/seller/inventory/adjustments":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                if not is_seller(connection, user_id):
                    self.send_json(403, {"error": "Seller access required"})
                    return
                product_id = str(parse_qs(urlparse(self.path).query).get("productId", [""])[0]).strip() or None
                self.send_json(200, {"adjustments": inventory_adjustment_rows(connection, seller_accessible_shop_ids(connection, user_id, "inventory"), product_id)})
        elif self.path == "/api/orders/buyer":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                expire_pending_orders(connection)
                self.send_json(200, {"orders": orders_for_response(connection, "buyer_user_id = ?", (user_id,))})
        elif self.path == "/api/orders/seller":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                expire_pending_orders(connection)
                shop_ids = seller_accessible_shop_ids(connection, user_id, "orders")
                if not shop_ids:
                    self.send_json(200, {"orders": []})
                    return
                placeholders = ",".join("?" for _ in shop_ids)
                self.send_json(200, {"orders": orders_for_response(connection, f"shop_id IN ({placeholders})", tuple(shop_ids))})
        elif self.path in ("/api/after-sales/buyer", "/api/after-sales/seller"):
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                if self.path.endswith("buyer"):
                    requests = after_sales_for_response(connection, "after_sale_requests.buyer_user_id = ?", (user_id,))
                else:
                    shop_ids = seller_accessible_shop_ids(connection, user_id, "after_sales")
                    if not shop_ids:
                        requests = []
                    else:
                        placeholders = ",".join("?" for _ in shop_ids)
                        requests = after_sales_for_response(connection, f"orders.shop_id IN ({placeholders})", tuple(shop_ids))
                self.send_json(200, {"afterSales": requests})
        elif self.path == "/api/reviews/seller":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                shop_ids = seller_accessible_shop_ids(connection, user_id, "reviews")
                if not shop_ids:
                    reviews = []
                else:
                    placeholders = ",".join("?" for _ in shop_ids)
                    reviews = reviews_for_response(connection, f"reviews.shop_id IN ({placeholders})", tuple(shop_ids))
                self.send_json(200, {"reviews": reviews})
        elif self.path == "/api/reviews/buyer":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                reviews = reviews_for_response(connection, "reviews.buyer_user_id = ?", (user_id,))
            self.send_json(200, {"reviews": reviews})
        elif self.path.startswith("/api/catalog/products/") and self.path.endswith("/reviews"):
            product_id = self.path.removeprefix("/api/catalog/products/").removesuffix("/reviews").rstrip("/")
            with database() as connection:
                reviews = reviews_for_response(connection, "order_items.product_id = ?", (product_id,))
            self.send_json(200, {"reviews": reviews})
        elif self.path.startswith("/api/admin/governance/cases/"):
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            parts = self.path.removeprefix("/api/admin/governance/cases/").strip("/").split("/")
            if len(parts) != 2:
                self.send_json(404, {"error": "Not found"})
                return
            with database() as connection:
                if not is_admin(connection, user_id):
                    self.send_json(403, {"error": "Administrator access required"})
                    return
                self.send_json(200, governance_case_payload(connection, parts[0], parts[1]))
        elif self.path == "/api/admin/support/tickets":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                if not is_admin(connection, user_id):
                    self.send_json(403, {"error": "Administrator access required"})
                    return
                self.send_json(200, {"tickets": support_tickets_for(connection, user_id, "admin")})
        elif self.path.startswith("/api/admin/support/tickets/"):
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            ticket_id = self.path.removeprefix("/api/admin/support/tickets/").rstrip("/")
            with database() as connection:
                connection.row_factory = sqlite3.Row
                ticket = connection.execute("SELECT * FROM support_tickets WHERE id = ?", (ticket_id,)).fetchone()
                if not ticket or not support_ticket_access(connection, ticket, user_id, "admin"):
                    self.send_json(404, {"error": "Ticket not found"})
                    return
                self.send_json(200, {"ticket": support_ticket_response(connection, ticket, True)})
        elif self.path == "/api/admin/seller-verifications":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                connection.row_factory = sqlite3.Row
                if not is_admin(connection, user_id):
                    self.send_json(403, {"error": "Administrator access required"})
                    return
                rows = connection.execute("SELECT seller_verification_applications.*, users.display_name FROM seller_verification_applications JOIN users ON users.id = seller_verification_applications.seller_user_id ORDER BY CASE status WHEN 'pending' THEN 0 ELSE 1 END, created_at DESC").fetchall()
                applications = [{"sellerUserId": row["seller_user_id"], "seller": row["display_name"], "legalName": row["legal_name"], "identityNumber": row["identity_number"], "contactPhone": row["contact_phone"], **verification_application_response(connection, row)} for row in rows]
            self.send_json(200, {"applications": applications})
        elif self.path == "/api/admin/reports":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                connection.row_factory = sqlite3.Row
                if not is_admin(connection, user_id):
                    self.send_json(403, {"error": "Administrator access required"})
                    return
                rows = connection.execute(
                    """
                    SELECT content_reports.*, users.display_name AS reporter_name,
                           handlers.display_name AS handler_name
                    FROM content_reports
                    JOIN users ON users.id = content_reports.reporter_user_id
                    LEFT JOIN users AS handlers ON handlers.id = content_reports.handled_by_user_id
                    ORDER BY CASE content_reports.status WHEN 'pending' THEN 0 ELSE 1 END, content_reports.created_at DESC
                    """
                ).fetchall()
            self.send_json(200, {"reports": [
                {
                    "id": row["id"], "targetType": row["target_type"], "targetId": row["target_id"],
                    "reason": row["reason"], "detail": row["detail"], "evidence": json.loads(row["evidence_json"]),
                    "status": row["status"], "reporter": row["reporter_name"], "createdAt": row["created_at"],
                    "handler": row["handler_name"], "resolutionNote": row["resolution_note"],
                }
                for row in rows
            ]})
        elif self.path == "/api/admin/moderation/products":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                connection.row_factory = sqlite3.Row
                if not is_admin(connection, user_id):
                    self.send_json(403, {"error": "Administrator access required"})
                    return
                rows = connection.execute(
                    """
                    SELECT products.id, products.title, products.status, products.moderation_status,
                           products.moderation_reason, products.moderated_at, shops.name AS shop_name
                    FROM products JOIN shops ON shops.id = products.shop_id
                    WHERE products.status = 'published'
                    ORDER BY products.updated_at DESC
                    """
                ).fetchall()
            self.send_json(200, {"products": [
                {
                    "id": row["id"], "title": row["title"], "shop": row["shop_name"],
                    "status": row["status"], "moderationStatus": row["moderation_status"],
                    "reason": row["moderation_reason"], "moderatedAt": row["moderated_at"],
                }
                for row in rows
            ]})
        elif self.path == "/api/governance/notifications":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                connection.row_factory = sqlite3.Row
                rows = connection.execute(
                    "SELECT * FROM governance_notifications WHERE user_id = ? ORDER BY created_at DESC LIMIT 50", (user_id,)
                ).fetchall()
                connection.execute("UPDATE governance_notifications SET read_at = CURRENT_TIMESTAMP WHERE user_id = ? AND read_at IS NULL", (user_id,))
            self.send_json(200, {"notifications": [
                {"id": row["id"], "type": row["notification_type"], "title": row["title"], "content": row["content"], "relatedType": row["related_type"], "relatedId": row["related_id"], "createdAt": row["created_at"]}
                for row in rows
            ]})
        elif self.path in ("/api/admin/appeals", "/api/admin/audit-logs"):
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                connection.row_factory = sqlite3.Row
                if not is_admin(connection, user_id):
                    self.send_json(403, {"error": "Administrator access required"})
                    return
                if self.path.endswith("appeals"):
                    rows = connection.execute(
                        "SELECT governance_appeals.*, users.display_name AS appellant FROM governance_appeals JOIN users ON users.id = governance_appeals.appellant_user_id ORDER BY CASE status WHEN 'pending' THEN 0 ELSE 1 END, created_at DESC"
                    ).fetchall()
                    payload = {"appeals": [{"id": row["id"], "targetType": row["target_type"], "targetId": row["target_id"], "content": row["content"], "evidence": json.loads(row["evidence_json"]), "status": row["status"], "appellant": row["appellant"], "createdAt": row["created_at"]} for row in rows]}
                else:
                    rows = connection.execute("SELECT platform_audit_logs.*, users.display_name AS actor FROM platform_audit_logs JOIN users ON users.id = platform_audit_logs.actor_user_id ORDER BY created_at DESC LIMIT 100").fetchall()
                    payload = {"logs": [{"id": row["id"], "actor": row["actor"], "action": row["action"], "targetType": row["target_type"], "targetId": row["target_id"], "detail": json.loads(row["detail_json"]), "createdAt": row["created_at"]} for row in rows]}
            self.send_json(200, payload)
        elif self.path == "/api/admin/risk-cases":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                if not is_admin(connection, user_id):
                    self.send_json(403, {"error": "Administrator access required"})
                    return
                cases = risk_cases_payload(connection)
            self.send_json(200, {"riskCases": cases})
        elif self.path == "/api/admin/media/assets":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                connection.row_factory = sqlite3.Row
                if not is_admin(connection, user_id):
                    self.send_json(403, {"error": "Administrator access required"})
                    return
                rows = connection.execute(
                    "SELECT media_assets.*, COUNT(media_asset_links.id) AS link_count FROM media_assets LEFT JOIN media_asset_links ON media_asset_links.asset_id = media_assets.id GROUP BY media_assets.id ORDER BY media_assets.created_at DESC LIMIT 100"
                ).fetchall()
            self.send_json(200, {"assets": [{"id": row["id"], "url": row["public_url"], "type": row["media_type"], "mimeType": row["mime_type"], "size": row["byte_size"], "status": row["status"], "links": row["link_count"], "createdAt": row["created_at"]} for row in rows]})
        elif self.path == "/api/platform/announcements":
            user_id = session_user(self)
            with database() as connection:
                connection.row_factory = sqlite3.Row
                rows = connection.execute(
                    "SELECT id, title, content, image_url, audience, published_at FROM platform_announcements WHERE status = 'published' ORDER BY published_at DESC LIMIT 10"
                ).fetchall()
                roles = {row[0] for row in connection.execute("SELECT role FROM user_roles WHERE user_id = ?", (user_id,))} if user_id else set()
            audiences = {"all"}
            if "buyer" in roles:
                audiences.add("buyer")
            if "seller" in roles:
                audiences.add("seller")
            self.send_json(200, {"announcements": [{"id": row["id"], "title": row["title"], "content": row["content"], "imageUrl": row["image_url"], "audience": row["audience"], "publishedAt": row["published_at"]} for row in rows if row["audience"] in audiences]})
        elif self.path.startswith("/api/admin/campaigns/") and self.path.endswith("/coupon-operations"):
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            campaign_id = self.path.removeprefix("/api/admin/campaigns/").removesuffix("/coupon-operations").rstrip("/")
            with database() as connection:
                connection.row_factory = sqlite3.Row
                if not is_admin(connection, user_id):
                    self.send_json(403, {"error": "Administrator access required"})
                    return
                campaign = next((item for item in campaign_performance(connection) if item["id"] == campaign_id), None)
                if not campaign:
                    self.send_json(404, {"error": "Campaign not found"})
                    return
                issuances = connection.execute("SELECT campaign_coupon_issuances.*, users.display_name FROM campaign_coupon_issuances JOIN users ON users.id = campaign_coupon_issuances.buyer_user_id WHERE campaign_id = ? ORDER BY created_at DESC LIMIT 100", (campaign_id,)).fetchall()
                codes = connection.execute("SELECT campaign_coupon_codes.*, users.display_name FROM campaign_coupon_codes LEFT JOIN users ON users.id = campaign_coupon_codes.assigned_user_id WHERE campaign_id = ? ORDER BY created_at DESC LIMIT 100", (campaign_id,)).fetchall()
            self.send_json(200, {"campaign": campaign, "issuances": [{"id": row["id"], "buyerUserId": row["buyer_user_id"], "buyer": row["display_name"], "source": row["source"], "quantity": row["issued_quantity"], "createdAt": row["created_at"]} for row in issuances], "codes": [{"id": row["id"], "code": row["code"], "status": row["status"], "buyer": row["display_name"], "expiresAt": row["expires_at"], "redeemedAt": row["redeemed_at"], "createdAt": row["created_at"]} for row in codes]})
        elif self.path == "/api/admin/activities":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                connection.row_factory = sqlite3.Row
                if not is_admin(connection, user_id):
                    self.send_json(403, {"error": "Administrator access required"})
                    return
                rows = connection.execute("SELECT * FROM platform_activities ORDER BY CASE status WHEN 'active' THEN 0 WHEN 'open' THEN 1 WHEN 'draft' THEN 2 ELSE 3 END, created_at DESC").fetchall()
                activities = [activity_response(connection, row, include_review_queue=True) for row in rows]
            self.send_json(200, {"activities": activities})
        elif urlparse(self.path).path == "/api/seller/activities":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                connection.row_factory = sqlite3.Row
                shop_ids = seller_accessible_shop_ids(connection, user_id, "products")
                if not shop_ids:
                    self.send_json(403, {"error": "Seller access required"})
                    return
                shop_id = str(parse_qs(urlparse(self.path).query).get("shopId", [shop_ids[0]])[0])
                if shop_id not in shop_ids:
                    self.send_json(403, {"error": "Shop access required"})
                    return
                rows = connection.execute("SELECT activities.* FROM platform_activities AS activities WHERE activities.status IN ('open', 'active') OR EXISTS (SELECT 1 FROM activity_applications WHERE activity_applications.activity_id = activities.id AND activity_applications.shop_id = ?) ORDER BY activities.created_at DESC", (shop_id,)).fetchall()
                activities = []
                for row in rows:
                    payload = activity_response(connection, row, shop_id=shop_id)
                    own_products = connection.execute("SELECT activity_products.*, products.title, products.stock FROM activity_products JOIN products ON products.id = activity_products.product_id WHERE activity_products.activity_id = ? AND products.shop_id = ? ORDER BY activity_products.created_at DESC", (row["id"], shop_id)).fetchall()
                    payload["myProducts"] = [{"id": product["id"], "productId": product["product_id"], "title": product["title"], "quotaStock": product["quota_stock"], "reservedStock": product["reserved_stock"], "productStock": product["stock"], "status": product["status"], "reviewNote": product["review_note"]} for product in own_products]
                    activities.append(payload)
            self.send_json(200, {"activities": activities})
        elif self.path == "/api/admin/operations/insights":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                if not is_admin(connection, user_id):
                    self.send_json(403, {"error": "Administrator access required"})
                    return
                self.send_json(200, governance_service_insights(connection))
        elif self.path == "/api/admin/service-automation":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                connection.row_factory = sqlite3.Row
                if not is_admin(connection, user_id):
                    self.send_json(403, {"error": "Administrator access required"})
                    return
                run_support_automation(connection)
                rules = connection.execute("SELECT * FROM service_automation_rules ORDER BY enabled DESC, sort_order, updated_at DESC").fetchall()
            self.send_json(200, {"rules": [{"id": row["id"], "name": row["name"], "keywords": json.loads(row["keywords_json"] or "[]"), "priority": row["priority"], "route": row["route"], "replyTemplate": row["reply_template"], "enabled": bool(row["enabled"]), "sortOrder": row["sort_order"], "updatedAt": row["updated_at"]} for row in rules]})
        elif self.path == "/api/admin/operations":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                connection.row_factory = sqlite3.Row
                if not is_admin(connection, user_id):
                    self.send_json(403, {"error": "Administrator access required"})
                    return
                announcements = connection.execute("SELECT * FROM platform_announcements ORDER BY created_at DESC LIMIT 50").fetchall()
                campaigns = campaign_performance(connection)[:50]
            self.send_json(200, {"announcements": [{"id": row["id"], "title": row["title"], "content": row["content"], "imageUrl": row["image_url"], "audience": row["audience"], "status": row["status"], "publishedAt": row["published_at"]} for row in announcements], "campaigns": campaigns})
        elif self.path == "/api/admin/finance":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                if not is_admin(connection, user_id):
                    self.send_json(403, {"error": "Administrator access required"})
                    return
                payload = admin_finance_payload(connection)
            self.send_json(200, payload)
        elif urlparse(self.path).path == "/api/admin/governance/tasks":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                if not is_admin(connection, user_id):
                    self.send_json(403, {"error": "Administrator access required"})
                    return
                ensure_governance_tasks(connection)
                values = parse_qs(urlparse(self.path).query)
                filters = {key: str(values.get(key, [""])[0]) for key in ("status", "type", "priority", "assignee", "sla")}
                self.send_json(200, {"tasks": governance_task_rows(connection, filters)})
        elif urlparse(self.path).path == "/api/admin/governance":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                if not is_admin(connection, user_id):
                    self.send_json(403, {"error": "Administrator access required"})
                    return
                payload = governance_operation_data(connection)
            self.send_json(200, payload)
        elif urlparse(self.path).path == "/api/admin/governance/export":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                if not is_admin(connection, user_id):
                    self.send_json(403, {"error": "Administrator access required"})
                    return
                ensure_governance_tasks(connection)
                rows = connection.execute(
                    """
                    SELECT governance_tasks.task_type, governance_tasks.target_id, governance_tasks.status,
                           users.display_name, governance_tasks.created_at, governance_tasks.completed_at
                    FROM governance_tasks LEFT JOIN users ON users.id = governance_tasks.assigned_user_id
                    ORDER BY governance_tasks.created_at DESC
                    """
                ).fetchall()
                actions = connection.execute("SELECT action_type, target_type, target_id, reason, status, created_at FROM enforcement_actions ORDER BY created_at DESC").fetchall()
            self.send_json(200, {"tasks": [{"type": row[0], "targetId": row[1], "status": row[2], "assignee": row[3] or "", "createdAt": row[4], "completedAt": row[5] or ""} for row in rows], "enforcements": [{"action": row[0], "targetType": row[1], "targetId": row[2], "reason": row[3], "status": row[4], "createdAt": row[5]} for row in actions]})
        elif self.path == "/api/auth/security":
            user_id = session_user(self)
            current_token = session_token(self)
            if not user_id or not current_token:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                connection.row_factory = sqlite3.Row
                user = connection.execute("SELECT phone, email, phone_verified_at, email_verified_at, password_changed_at, last_login_at FROM users WHERE id = ?", (user_id,)).fetchone()
                sessions = connection.execute("SELECT id, token, created_at, last_seen_at, expires_at, user_agent, ip_address FROM web_sessions WHERE user_id = ? AND expires_at > CURRENT_TIMESTAMP ORDER BY last_seen_at DESC", (user_id,)).fetchall()
                events = connection.execute("SELECT success, reason, ip_address, created_at FROM login_audit_events WHERE user_id = ? ORDER BY created_at DESC LIMIT 20", (user_id,)).fetchall()
            self.send_json(200, {"security": {"phone": user["phone"], "email": user["email"], "phoneVerified": bool(user["phone_verified_at"]), "emailVerified": bool(user["email_verified_at"]), "passwordChangedAt": user["password_changed_at"], "lastLoginAt": user["last_login_at"]}, "sessions": [{"id": row["id"], "current": secrets.compare_digest(row["token"], current_token), "createdAt": row["created_at"], "lastSeenAt": row["last_seen_at"], "expiresAt": row["expires_at"], "userAgent": row["user_agent"], "ipAddress": row["ip_address"]} for row in sessions], "loginEvents": [{"success": bool(row["success"]), "reason": row["reason"], "ipAddress": row["ip_address"], "createdAt": row["created_at"]} for row in events]})
        elif self.path == "/api/profile":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                profile = profile_for_user(connection, user_id)
            self.send_json(200, {"profile": profile})
        elif self.path == "/api/auth/session":
            account = account_for_user(session_user(self) or "")
            csrf_token = rotate_session_csrf_token(self) if account else None
            self.send_json(200, {"account": account}, extra_headers={"X-CSRF-Token": csrf_token} if csrf_token else None)
        elif self.path == "/api/auth/csrf":
            csrf_token = rotate_session_csrf_token(self)
            self.send_json(200, {"csrf": bool(csrf_token)}, extra_headers={"X-CSRF-Token": csrf_token} if csrf_token else None)
        elif urlparse(self.path).path == "/api/analytics/admin/export":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                if not is_admin(connection, user_id):
                    self.send_json(403, {"error": "Administrator access required"})
                    return
            try:
                days = int(parse_qs(urlparse(self.path).query).get("days", ["30"])[0])
            except ValueError:
                days = 30
            analytics = platform_analytics(days)
            self.send_json(200, {"days": analytics["days"], "sections": analytics_export_sections(analytics)})
        elif urlparse(self.path).path == "/api/analytics/admin":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                if not is_admin(connection, user_id):
                    self.send_json(403, {"error": "Administrator access required"})
                    return
            try:
                days = int(parse_qs(urlparse(self.path).query).get("days", ["30"])[0])
            except ValueError:
                days = 30
            self.send_json(200, {"analytics": platform_analytics(days)})
        elif self.path.startswith("/api/analytics/shops/"):
            shop_id = self.path.rsplit("/", 1)[-1]
            self.send_json(200, {"visitors": shop_visitors(shop_id)})
        elif urlparse(self.path).path == "/api/analytics/seller/business":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                if not is_seller(connection, user_id):
                    self.send_json(403, {"error": "Seller access required"})
                    return
            try:
                days = int(parse_qs(urlparse(self.path).query).get("days", ["30"])[0])
                business = seller_business_analytics(user_id, days)
            except ValueError as error:
                self.send_json(400, {"error": str(error)})
                return
            self.send_json(200, business)
        elif urlparse(self.path).path == "/api/analytics/seller":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                if not is_seller(connection, user_id):
                    self.send_json(403, {"error": "Seller access required"})
                    return
            query = parse_qs(urlparse(self.path).query)
            try:
                days = int(query.get("days", ["30"])[0])
                analytics = seller_analytics(user_id, days, query.get("start", [None])[0], query.get("end", [None])[0])
            except ValueError as error:
                self.send_json(400, {"error": str(error)})
                return
            self.send_json(200, {"analytics": analytics})
        elif self.path.startswith("/api/states/"):
            user_id = self.path.rsplit("/", 1)[-1]
            if session_user(self) != user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                row = connection.execute("SELECT state_json FROM application_states WHERE user_id = ?", (user_id,)).fetchone()
            self.send_json(200, {"state": json.loads(row[0]) if row else None})
        else:
            self.send_json(404, {"error": "Not found"})

    def do_POST(self) -> None:
        if not self.enforce_state_change_protection():
            return
        try:
            # Reject unauthenticated or over-quota upload attempts before
            # reading a base64 payload into memory. COS direct uploads are
            # limited here as well because their signed tickets authorize
            # billable storage operations.
            if self.path in {"/api/seller/media/direct-upload", "/api/seller/media/complete", "/api/seller/media/upload"}:
                upload_user_id = session_user(self)
                if not upload_user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_seller(upload_user_id)
                if not self.enforce_rate_limit(
                    "product-media-upload", upload_user_id, per_ip=80, per_user=40, window_seconds=600
                ):
                    return
            elif self.path == "/api/media":
                upload_user_id = session_user(self)
                if not upload_user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                if not self.enforce_rate_limit(
                    "media-upload", upload_user_id, per_ip=60, per_user=30, window_seconds=600
                ):
                    return
            length = int(self.headers.get("Content-Length", "0"))
            if length < 0 or length > MAX_REQUEST_BODY_BYTES:
                self.send_json(413, {"error": "请求内容过大"})
                return
            raw_body = self.rfile.read(length)
            payload = json.loads(raw_body.decode("utf-8"))
            if self.path == "/api/seller/message-automation/settings":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                shop_id = str(payload.get("shopId") or "").strip()
                with database() as connection:
                    require_shop_permission(connection, user_id, shop_id, "messages")
                    timezone_name = str(payload.get("timezone") or "Asia/Shanghai").strip()
                    try:
                        ZoneInfo(timezone_name)
                    except ZoneInfoNotFoundError:
                        raise ValueError("时区无效")
                    weekly = normalise_message_weekly_hours(payload.get("weeklyHours"))
                    template = str(payload.get("offHoursReplyTemplate") or "").strip()[:500]
                    if not template:
                        raise ValueError("非工作时间自动回复不能为空")
                    minutes = max(1, min(60, int(payload.get("unansweredMinutes") or 3)))
                    connection.execute(
                        """INSERT INTO seller_message_settings
                           (shop_id, timezone, weekly_hours_json, unanswered_minutes, off_hours_auto_reply_enabled,
                            off_hours_reply_template, urgent_email_enabled, urgent_sms_enabled,
                            unanswered_email_enabled, ai_reply_enabled)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                           ON CONFLICT(shop_id) DO UPDATE SET timezone = excluded.timezone,
                           weekly_hours_json = excluded.weekly_hours_json, unanswered_minutes = excluded.unanswered_minutes,
                           off_hours_auto_reply_enabled = excluded.off_hours_auto_reply_enabled,
                           off_hours_reply_template = excluded.off_hours_reply_template,
                           urgent_email_enabled = excluded.urgent_email_enabled, urgent_sms_enabled = excluded.urgent_sms_enabled,
                           unanswered_email_enabled = excluded.unanswered_email_enabled, ai_reply_enabled = excluded.ai_reply_enabled,
                           updated_at = CURRENT_TIMESTAMP""",
                        (shop_id, timezone_name, json.dumps(weekly, ensure_ascii=False), minutes,
                         int(bool(payload.get("offHoursAutoReplyEnabled", True))), template,
                         int(bool(payload.get("urgentEmailEnabled", True))), int(bool(payload.get("urgentSmsEnabled", False))),
                         int(bool(payload.get("unansweredEmailEnabled", True))), int(bool(payload.get("aiReplyEnabled", True)))),
                    )
                    self.send_json(200, {"settings": shop_message_settings(connection, shop_id)})
                return
            if self.path == "/api/seller/message-automation/ai-draft":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                shop_id, buyer_id = str(payload.get("shopId") or "").strip(), str(payload.get("buyerUserId") or "").strip()
                with database() as connection:
                    draft = seller_ai_message_draft(connection, user_id, shop_id, buyer_id)
                self.send_json(200, {"draft": draft})
                return
            if self.path == "/api/seller/ai-assistant/chat":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                with database() as connection:
                    if not is_seller(connection, user_id):
                        self.send_json(403, {"error": "Seller access required"})
                        return
                if not isinstance(payload, dict):
                    raise ValueError("对话内容无效")
                reply = seller_ai_assistant_reply(
                    user_id,
                    payload.get("message"),
                    payload.get("history"),
                )
                self.send_json(200, {"reply": reply})
                return
            if self.path == "/api/generate-title":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                with database() as connection:
                    if not is_seller(connection, user_id):
                        self.send_json(403, {"error": "Seller access required"})
                        return
                if not isinstance(payload, dict):
                    raise ValueError("标题生成请求无效")
                generated = seller_ai_product_title(user_id, payload.get("imageData"))
                self.send_json(200, {
                    "title": generated["englishTitle"],
                    "titleZh": generated["chineseTitle"],
                })
                return
            if self.path.startswith("/api/admin/risk-cases/") and self.path.endswith("/resolve"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin_step_up(self, user_id)
                case_id = self.path.removeprefix("/api/admin/risk-cases/").removesuffix("/resolve").rstrip("/")
                status = str(payload.get("status") or "resolved")
                note = str(payload.get("note") or "").strip()[:1000]
                if status not in ("resolved", "dismissed", "reviewing"):
                    raise ValueError("Invalid risk case status")
                with database() as connection:
                    if not is_admin(connection, user_id):
                        self.send_json(403, {"error": "Administrator access required"})
                        return
                    updated = connection.execute(
                        "UPDATE risk_cases SET status = ?, resolved_at = CASE WHEN ? IN ('resolved', 'dismissed') THEN CURRENT_TIMESTAMP ELSE NULL END, resolved_by_user_id = CASE WHEN ? IN ('resolved', 'dismissed') THEN ? ELSE NULL END, resolution_note = ? WHERE id = ?",
                        (status, status, status, user_id, note or None, case_id),
                    ).rowcount
                    if not updated:
                        raise ValueError("Risk case not found")
                    write_platform_audit(connection, user_id, "risk_case_updated", "risk_case", case_id, {"status": status, "note": note})
                    cases = risk_cases_payload(connection)
                self.send_json(200, {"riskCases": cases})
                return
            if self.path == "/api/brand-site/subscribers":
                if not isinstance(payload, dict):
                    raise ValueError("订阅内容无效")
                shop_id = str(payload.get("shopId") or "").strip()[:160]
                email = str(payload.get("email") or "").strip().lower()[:254]
                if not shop_id or not re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", email):
                    raise ValueError("请输入正确的邮箱地址")
                with database() as connection:
                    row = connection.execute("SELECT settings_json FROM shops WHERE id = ? AND status = 'active'", (shop_id,)).fetchone()
                    if not row:
                        self.send_json(404, {"error": "独立站不存在或尚未启用"})
                        return
                    try:
                        settings = json.loads(row[0] or "{}")
                    except json.JSONDecodeError:
                        settings = {}
                    if not isinstance(settings, dict) or not isinstance(settings.get("brandSite"), dict) or settings["brandSite"].get("status") != "published":
                        self.send_json(404, {"error": "独立站尚未启用"})
                        return
                    connection.execute(
                        "INSERT INTO brand_site_subscribers (id, shop_id, email) VALUES (?, ?, ?) ON CONFLICT(shop_id, email) DO UPDATE SET status = 'subscribed', updated_at = CURRENT_TIMESTAMP",
                        (f"brand-sub-{secrets.token_urlsafe(10)}", shop_id, email),
                    )
                self.send_json(201, {"ok": True})
            elif self.path == "/api/community/media":
                if not isinstance(payload, dict):
                    raise ValueError("图片内容无效")
                visitor_id = str(payload.get("visitorId") or "").strip()
                if not re.fullmatch(r"[A-Za-z0-9_-]{8,120}", visitor_id):
                    raise ValueError("访客身份无效，请刷新页面后重试")
                if not community_rate_allowed(self, visitor_id, "media", 12, 600):
                    self.send_json(429, {"error": "图片上传过于频繁，请稍后再试"})
                    return
                mime_type, binary = decode_media_data_url(payload.get("data"), "image")
                MEDIA_DIR.mkdir(parents=True, exist_ok=True)
                filename = f"community-{secrets.token_urlsafe(16)}{IMAGE_MIME_TYPES[mime_type]}"
                (MEDIA_DIR / filename).write_bytes(binary)
                self.send_json(201, {"url": f"/media/{filename}"})
            elif self.path == "/api/community/posts":
                if not isinstance(payload, dict):
                    raise ValueError("发帖内容无效")
                visitor_id, nickname = community_identity(self, payload)
                category = str(payload.get("category") or "").strip()
                title = re.sub(r"\s+", " ", str(payload.get("title") or "").strip())
                content = str(payload.get("content") or "").strip()
                image_url = str(payload.get("imageUrl") or "").strip() or None
                if image_url and not image_url.startswith(("/media/", "http://", "https://")):
                    raise ValueError("图片地址无效")
                attachment_urls = community_attachment_urls(payload)
                if category not in COMMUNITY_CATEGORIES:
                    raise ValueError("请选择社区分类")
                if category == "平台公告":
                    raise ValueError("平台公告仅可由管理员发布")
                if not 2 <= len(title) <= 80:
                    raise ValueError("标题请填写 2 到 80 个字符")
                if not 2 <= len(content) <= 2000:
                    raise ValueError("正文请填写 2 到 2000 个字符")
                if next((word for word in SENSITIVE_CONTENT_WORDS if word in f"{title}\n{content}"), None):
                    raise ValueError("内容未通过基础审核，请调整后再发布")
                if not community_rate_allowed(self, visitor_id, "post", 4, 600):
                    self.send_json(429, {"error": "发帖过于频繁，请稍后再试"})
                    return
                post_id = f"community-post-{secrets.token_urlsafe(10)}"
                with database() as connection:
                    connection.execute(
                        "INSERT INTO community_posts (id, visitor_id, nickname, category, title, content, attachment_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (post_id, visitor_id, nickname, category, title, content, attachment_urls[0] if attachment_urls else None),
                    )
                    connection.executemany("INSERT INTO community_post_images (id, post_id, image_url, sort_order) VALUES (?, ?, ?, ?)", [(f"community-post-image-{secrets.token_urlsafe(8)}", post_id, url, index) for index, url in enumerate(attachment_urls)])
                    post = next(item for item in community_posts_payload(connection) if item["id"] == post_id)
                COMMUNITY_LIVE_HUB.publish({"type": "community_post_created", "postId": post_id})
                self.send_json(201, {"post": post})
            elif self.path.startswith("/api/community/posts/") and self.path.endswith("/comments"):
                if not isinstance(payload, dict):
                    raise ValueError("评论内容无效")
                visitor_id, nickname = community_identity(self, payload)
                post_id = self.path.removeprefix("/api/community/posts/").removesuffix("/comments").rstrip("/")
                parent_comment_id = str(payload.get("parentCommentId") or "").strip() or None
                content = str(payload.get("content") or "").strip()
                attachment_urls = community_attachment_urls(payload)
                if not post_id or not 1 <= len(content) <= 500:
                    raise ValueError("评论请填写 1 到 500 个字符")
                if next((word for word in SENSITIVE_CONTENT_WORDS if word in content), None):
                    raise ValueError("内容未通过基础审核，请调整后再发布")
                if not community_rate_allowed(self, visitor_id, "comment", 12, 600):
                    self.send_json(429, {"error": "评论过于频繁，请稍后再试"})
                    return
                comment_id = f"community-comment-{secrets.token_urlsafe(10)}"
                with database() as connection:
                    post = connection.execute("SELECT id FROM community_posts WHERE id = ? AND status = 'published'", (post_id,)).fetchone()
                    if not post:
                        self.send_json(404, {"error": "帖子不存在或已隐藏"})
                        return
                    if parent_comment_id and not connection.execute("SELECT 1 FROM community_comments WHERE id = ? AND post_id = ? AND status = 'published'", (parent_comment_id, post_id)).fetchone():
                        raise ValueError("回复的评论不存在或已隐藏")
                    connection.execute(
                        "INSERT INTO community_comments (id, post_id, visitor_id, nickname, content, parent_comment_id, attachment_url) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (comment_id, post_id, visitor_id, nickname, content, parent_comment_id, attachment_urls[0] if attachment_urls else None),
                    )
                    connection.executemany("INSERT INTO community_comment_images (id, comment_id, image_url, sort_order) VALUES (?, ?, ?, ?)", [(f"community-comment-image-{secrets.token_urlsafe(8)}", comment_id, url, index) for index, url in enumerate(attachment_urls)])
                    comment = connection.execute("SELECT id, nickname, content, created_at, parent_comment_id, attachment_url FROM community_comments WHERE id = ?", (comment_id,)).fetchone()
                COMMUNITY_LIVE_HUB.publish({"type": "community_comment_created", "postId": post_id, "commentId": comment_id})
                self.send_json(201, {"comment": {"id": comment[0], "nickname": comment[1], "content": comment[2], "createdAt": comment[3], "parentCommentId": comment[4], "imageUrl": comment[5], "imageUrls": attachment_urls}})
            elif self.path.startswith("/api/admin/community/posts/") and self.path.endswith("/pin"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id)
                post_id = self.path.removeprefix("/api/admin/community/posts/").removesuffix("/pin").rstrip("/")
                pinned = payload.get("pinned") is True
                with database() as connection:
                    updated = connection.execute(
                        """
                        UPDATE community_posts
                        SET is_pinned = ?, pinned_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE NULL END,
                            pinned_by_user_id = CASE WHEN ? THEN ? ELSE NULL END, updated_at = CURRENT_TIMESTAMP
                        WHERE id = ? AND status = 'published'
                        """,
                        (int(pinned), int(pinned), int(pinned), user_id, post_id),
                    ).rowcount
                    if not updated:
                        raise ValueError("帖子不存在或已隐藏")
                    write_platform_audit(connection, user_id, "community_post_pinned" if pinned else "community_post_unpinned", "community_post", post_id)
                COMMUNITY_LIVE_HUB.publish({"type": "community_post_updated", "postId": post_id})
                self.send_json(200, {"ok": True, "pinned": pinned})
            elif self.path == "/api/community/reports":
                if not isinstance(payload, dict):
                    raise ValueError("举报内容无效")
                visitor_id, _ = community_identity(self, payload)
                target_type = str(payload.get("targetType") or "")
                target_id = str(payload.get("targetId") or "").strip()
                reason = str(payload.get("reason") or "").strip()
                if target_type not in ("post", "comment") or not target_id or not 2 <= len(reason) <= 120:
                    raise ValueError("请填写举报对象和原因")
                if not community_rate_allowed(self, visitor_id, "report", 8, 3600):
                    self.send_json(429, {"error": "举报提交过于频繁，请稍后再试"})
                    return
                table = "community_posts" if target_type == "post" else "community_comments"
                with database() as connection:
                    if not connection.execute(f"SELECT 1 FROM {table} WHERE id = ?", (target_id,)).fetchone():
                        self.send_json(404, {"error": "举报对象不存在"})
                        return
                    if connection.execute("SELECT 1 FROM community_reports WHERE visitor_id = ? AND target_type = ? AND target_id = ? AND status = 'pending'", (visitor_id, target_type, target_id)).fetchone():
                        raise ValueError("你已经举报过该内容，请等待处理")
                    report_id = f"community-report-{secrets.token_urlsafe(10)}"
                    connection.execute("INSERT INTO community_reports (id, visitor_id, target_type, target_id, reason) VALUES (?, ?, ?, ?, ?)", (report_id, visitor_id, target_type, target_id, reason))
                self.send_json(201, {"report": {"id": report_id, "status": "pending"}})
            elif self.path == "/api/integrations/logistics/webhooks":
                if not LOGISTICS_WEBHOOK_SECRET:
                    self.send_json(503, {"error": "Logistics webhook is not configured"})
                    return
                if not logistics_webhook_is_valid(raw_body, self.headers.get("X-Logistics-Signature", "")):
                    self.send_json(403, {"error": "Invalid logistics webhook signature"})
                    return
                if not isinstance(payload, dict):
                    raise ValueError("物流回调内容无效")
                with database() as connection:
                    result = record_logistics_webhook_event(connection, payload)
                self.send_json(202, result)
            elif self.path == "/api/integrations/customer-service/webhooks":
                if not CUSTOMER_SERVICE_WEBHOOK_SECRET:
                    self.send_json(503, {"error": "Customer service webhook is not configured"})
                    return
                supplied_secret = self.headers.get("X-Customer-Service-Webhook-Secret", "")
                if not secrets.compare_digest(supplied_secret, CUSTOMER_SERVICE_WEBHOOK_SECRET):
                    self.send_json(403, {"error": "Invalid webhook signature"})
                    return
                provider = str(payload.get("provider") or "")
                event_id = str(payload.get("eventId") or "").strip()
                event_type = str(payload.get("eventType") or "").strip()
                if provider not in ("chaskiq", "tiledesk", "papercups") or not event_id or not event_type:
                    raise ValueError("Customer service webhook payload is invalid")
                with database() as connection:
                    accepted = record_customer_service_webhook_event(connection, provider, event_id[:160], event_type[:100], payload)
                self.send_json(202, {"accepted": accepted, "duplicate": not accepted})
            elif self.path == "/api/push/subscriptions":
                user_id = session_user(self)
                subscription = payload.get("subscription") if isinstance(payload, dict) else None
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                if not web_push_is_configured():
                    self.send_json(503, {"error": "Browser push is not configured"})
                    return
                if not isinstance(subscription, dict):
                    raise ValueError("Invalid push subscription")
                endpoint = str(subscription.get("endpoint") or "").strip()
                keys = subscription.get("keys")
                if not endpoint.startswith("https://") or len(endpoint) > 2000 or not isinstance(keys, dict) or not str(keys.get("p256dh") or "") or not str(keys.get("auth") or ""):
                    raise ValueError("Invalid push subscription")
                with database() as connection:
                    connection.execute(
                        "INSERT INTO push_subscriptions (id, user_id, endpoint, subscription_json, user_agent) VALUES (?, ?, ?, ?, ?) ON CONFLICT(endpoint) DO UPDATE SET user_id = excluded.user_id, subscription_json = excluded.subscription_json, user_agent = excluded.user_agent, updated_at = CURRENT_TIMESTAMP",
                        (f"push-{secrets.token_urlsafe(10)}", user_id, endpoint, json.dumps(subscription, ensure_ascii=False), self.headers.get("User-Agent", "")[:300]),
                    )
                self.send_json(201, {"ok": True})
            elif self.path == "/api/campaign-codes/redeem":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                code = re.sub(r"\s+", "", str(payload.get("code") or "").upper())
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    enforce_coupon_claim_risk_controls(connection, user_id)
                    coupon = connection.execute("SELECT * FROM campaign_coupon_codes WHERE code = ? AND status = 'issued' AND (expires_at IS NULL OR expires_at > CURRENT_TIMESTAMP)", (code,)).fetchone()
                    if not coupon or (coupon["assigned_user_id"] and coupon["assigned_user_id"] != user_id): raise ValueError("券码无效或已失效")
                    connection.execute("INSERT INTO platform_campaign_claims (id, campaign_id, buyer_user_id) VALUES (?, ?, ?) ON CONFLICT(campaign_id, buyer_user_id) DO UPDATE SET claimed_quantity = claimed_quantity + 1, updated_at = CURRENT_TIMESTAMP", (f"campaign-claim-{secrets.token_urlsafe(10)}", coupon["campaign_id"], user_id))
                    connection.execute("UPDATE campaign_coupon_codes SET status = 'redeemed', assigned_user_id = ?, redeemed_at = CURRENT_TIMESTAMP WHERE id = ?", (user_id, coupon["id"]))
                    coupons = buyer_coupons(connection, user_id)
                self.send_json(200, {"coupons": coupons})
            elif self.path.startswith("/api/campaigns/") and self.path.endswith("/claim"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                campaign_id = self.path.removeprefix("/api/campaigns/").removesuffix("/claim").rstrip("/")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    enforce_coupon_claim_risk_controls(connection, user_id)
                    campaign = connection.execute("SELECT * FROM platform_campaigns WHERE id = ? AND campaign_type = 'coupon' AND status = 'active' AND (starts_at IS NULL OR starts_at <= CURRENT_TIMESTAMP) AND (ends_at IS NULL OR ends_at > CURRENT_TIMESTAMP)", (campaign_id,)).fetchone()
                    if not campaign:
                        raise ValueError("Coupon is unavailable")
                    claim = connection.execute("SELECT * FROM platform_campaign_claims WHERE campaign_id = ? AND buyer_user_id = ?", (campaign_id, user_id)).fetchone()
                    if claim and claim["claimed_quantity"] >= campaign["per_user_claim_limit"]:
                        raise ValueError("Claim limit reached")
                    if claim:
                        connection.execute("UPDATE platform_campaign_claims SET claimed_quantity = claimed_quantity + 1, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (claim["id"],))
                    else:
                        connection.execute("INSERT INTO platform_campaign_claims (id, campaign_id, buyer_user_id) VALUES (?, ?, ?)", (f"campaign-claim-{secrets.token_urlsafe(10)}", campaign_id, user_id))
                    self.send_json(201, {"coupons": buyer_coupons(connection, user_id)})
            elif self.path == "/api/analytics/events":
                if not isinstance(payload, dict):
                    raise ValueError("Invalid analytics event batch")
                events = payload.get("events") if "events" in payload else [payload]
                with database() as connection:
                    accepted, duplicates = record_public_analytics_events(connection, events, session_user(self))
                self.send_json(201, {"ok": True, "accepted": accepted, "duplicates": duplicates})
            elif self.path == "/api/seller/media/direct-upload":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_seller(user_id)
                mime_type = str(payload.get("mimeType") or "").strip().lower()
                try:
                    byte_size = int(payload.get("size") or 0)
                except (TypeError, ValueError):
                    byte_size = 0
                content_hash = str(payload.get("contentHash") or "").strip().lower() or None
                media_type = str(payload.get("mediaType") or "image").strip().lower()
                self.send_json(201, create_public_cos_upload_ticket(user_id, mime_type, byte_size, content_hash, media_type))
            elif self.path == "/api/seller/media/complete":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_seller(user_id)
                if not isinstance(payload, dict):
                    raise ValueError("Invalid media completion request")
                asset_id = str(payload.get("assetId") or "").strip()
                if not re.fullmatch(r"asset-[A-Za-z0-9_-]{8,120}", asset_id):
                    raise ValueError("Invalid media asset")
                self.send_json(200, complete_product_media_upload(user_id, asset_id))
            elif self.path == "/api/seller/media/upload":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_seller(user_id)
                if not isinstance(payload, dict):
                    raise ValueError("Invalid media upload")
                self.send_json(201, create_quarantined_product_media(user_id, str(payload.get("mediaType") or ""), payload.get("data")))
            elif self.path == "/api/media":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                media_type = str(payload.get("mediaType") or "")
                if media_type not in ("image", "video"):
                    raise ValueError("媒体类型无效")
                mime_type, binary = decode_media_data_url(payload.get("data"), media_type)
                filename = f"{media_type}-{secrets.token_urlsafe(16)}{(IMAGE_MIME_TYPES if media_type == 'image' else VIDEO_MIME_TYPES)[mime_type]}"
                public_upload = payload.get("visibility") == "public"
                uploaded = upload_public_media_to_cos(filename, mime_type, binary) if public_upload else None
                if uploaded:
                    storage_key, public_url = uploaded
                else:
                    MEDIA_DIR.mkdir(parents=True, exist_ok=True)
                    (MEDIA_DIR / filename).write_bytes(binary)
                    storage_key, public_url = filename, f"/media/{filename}"
                asset_id = f"asset-{secrets.token_urlsafe(12)}"
                with database() as connection:
                    connection.execute(
                        "INSERT INTO media_assets (id, uploader_user_id, media_type, mime_type, storage_key, public_url, byte_size, content_hash) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (asset_id, user_id, media_type, mime_type, storage_key, public_url, len(binary), hashlib.sha256(binary).hexdigest()),
                    )
                self.send_json(201, {"id": asset_id, "url": public_url, "mediaType": media_type, "size": len(binary)})
            elif self.path == "/api/reports":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                target_type = str(payload.get("targetType") or "")
                target_id = str(payload.get("targetId") or "")
                reason = str(payload.get("reason") or "").strip()
                detail = str(payload.get("detail") or "").strip()
                evidence = [str(item) for item in payload.get("evidence") or [] if str(item).startswith(("/media/", "http://", "https://"))][:6]
                if target_type not in ("product", "shop", "review", "message") or not target_id or not reason:
                    raise ValueError("请完整填写举报对象和原因")
                with database() as connection:
                    target_tables = {"product": "products", "shop": "shops", "review": "reviews", "message": "shop_messages"}
                    if not connection.execute(f"SELECT 1 FROM {target_tables[target_type]} WHERE id = ?", (target_id,)).fetchone():
                        raise ValueError("举报对象不存在")
                    duplicate = connection.execute(
                        "SELECT 1 FROM content_reports WHERE reporter_user_id = ? AND target_type = ? AND target_id = ? AND status = 'pending'",
                        (user_id, target_type, target_id),
                    ).fetchone()
                    if duplicate:
                        raise ValueError("该内容已有待处理举报")
                    report_id = f"report-{secrets.token_urlsafe(10)}"
                    connection.execute(
                        "INSERT INTO content_reports (id, reporter_user_id, target_type, target_id, reason, detail, evidence_json) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (report_id, user_id, target_type, target_id, reason, detail, json.dumps(evidence, ensure_ascii=False)),
                    )
                    link_media_assets(connection, evidence, "report", report_id)
                    write_platform_audit(connection, user_id, "report_created", target_type, target_id, {"reportId": report_id, "reason": reason})
                    governance_case_event(connection, "report", report_id, "case_created", user_id, {"targetType": target_type, "targetId": target_id, "reason": reason})
                self.send_json(201, {"report": {"id": report_id, "status": "pending"}})
            elif self.path == "/api/governance/appeals":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                target_type, target_id = str(payload.get("targetType") or ""), str(payload.get("targetId") or "")
                content = str(payload.get("content") or "").strip()
                if target_type not in ("product", "shop", "user") or not content:
                    raise ValueError("请填写申诉内容")
                with database() as connection:
                    if target_owner(connection, target_type, target_id) != user_id:
                        raise ValueError("无权申诉该处罚")
                    appeal_id = f"appeal-{secrets.token_urlsafe(10)}"
                    evidence = [str(item) for item in payload.get("evidence") or [] if str(item).startswith(("/media/", "http://", "https://"))][:6]
                    connection.execute("INSERT INTO governance_appeals (id, appellant_user_id, target_type, target_id, content, evidence_json) VALUES (?, ?, ?, ?, ?, ?)", (appeal_id, user_id, target_type, target_id, content, json.dumps(evidence, ensure_ascii=False)))
                    link_media_assets(connection, evidence, "appeal", appeal_id)
                    write_platform_audit(connection, user_id, "appeal_created", target_type, target_id, {"appealId": appeal_id})
                    governance_case_event(connection, "appeal", appeal_id, "case_created", user_id, {"targetType": target_type, "targetId": target_id})
                self.send_json(201, {"appeal": {"id": appeal_id, "status": "pending"}})
            elif self.path == "/api/admin/media/cleanup":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id)
                require_admin_step_up(self, user_id)
                with database() as connection:
                    removed = cleanup_temporary_media(connection)
                    write_platform_audit(connection, user_id, "media_cleanup", "media_asset", "temporary", {"removed": removed})
                self.send_json(200, {"removed": removed})
            elif self.path == "/api/admin/announcements":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id)
                announcement_id = str(payload.get("id") or f"announcement-{secrets.token_urlsafe(10)}")
                title, content = str(payload.get("title") or "").strip(), str(payload.get("content") or "").strip()
                audience, status = str(payload.get("audience") or "all"), str(payload.get("status") or "draft")
                image_url = str(payload.get("imageUrl") or "").strip()
                if image_url and not image_url.startswith(("/media/", "http://", "https://")):
                    raise ValueError("公告图片地址无效")
                if not title or not content or len(title) > 80 or len(content) > 500 or audience not in ("all", "buyer", "seller") or status not in ("draft", "published", "archived"):
                    raise ValueError("公告内容或状态无效")
                with database() as connection:
                    connection.execute(
                        """
                        INSERT INTO platform_announcements (id, title, content, image_url, audience, status, published_at, created_by_user_id)
                        VALUES (?, ?, ?, ?, ?, ?, CASE WHEN ? = 'published' THEN CURRENT_TIMESTAMP END, ?)
                        ON CONFLICT(id) DO UPDATE SET title = excluded.title, content = excluded.content, image_url = excluded.image_url, audience = excluded.audience,
                          status = excluded.status, published_at = CASE WHEN excluded.status = 'published' THEN COALESCE(platform_announcements.published_at, CURRENT_TIMESTAMP) ELSE platform_announcements.published_at END,
                          updated_at = CURRENT_TIMESTAMP
                        """,
                        (announcement_id, title, content, image_url or None, audience, status, status, user_id),
                    )
                    community_post_id = f"community-announcement-{announcement_id}"
                    if status == "published":
                        connection.execute(
                            """
                            INSERT INTO community_posts (id, visitor_id, nickname, category, title, content, attachment_url, status)
                            VALUES (?, ?, '平台管理员', '平台公告', ?, ?, ?, 'published')
                            ON CONFLICT(id) DO UPDATE SET nickname = excluded.nickname, title = excluded.title, content = excluded.content, attachment_url = excluded.attachment_url,
                              status = 'published', updated_at = CURRENT_TIMESTAMP
                            """,
                            (community_post_id, f"platform-{user_id}", title, content, image_url or None),
                        )
                        connection.execute("DELETE FROM community_post_images WHERE post_id = ?", (community_post_id,))
                    else:
                        connection.execute(
                            "UPDATE community_posts SET status = 'deleted', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                            (community_post_id,),
                        )
                    write_platform_audit(connection, user_id, f"announcement_{status}", "announcement", announcement_id, {"audience": audience, "communityPostId": community_post_id})
                COMMUNITY_LIVE_HUB.publish({"type": "community_post_updated", "postId": community_post_id})
                self.send_json(200, {"ok": True, "id": announcement_id})
            elif self.path.startswith("/api/admin/campaigns/") and self.path.endswith("/end"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id)
                require_admin_step_up(self, user_id)
                campaign_id = self.path.removeprefix("/api/admin/campaigns/").removesuffix("/end").rstrip("/")
                with database() as connection:
                    campaign = connection.execute("SELECT id, status FROM platform_campaigns WHERE id = ?", (campaign_id,)).fetchone()
                    if not campaign:
                        raise ValueError("Campaign not found")
                    connection.execute("UPDATE platform_campaigns SET status = 'ended', ends_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (campaign_id,))
                    write_platform_audit(connection, user_id, "campaign_ended", "campaign", campaign_id, {"previousStatus": campaign["status"]})
                self.send_json(200, {"ok": True, "id": campaign_id})
            elif self.path == "/api/admin/activities":
                user_id = session_user(self)
                if not user_id: self.send_json(401, {"error": "Unauthorized"}); return
                require_admin(user_id); require_admin_step_up(self, user_id)
                activity_id, name, status = str(payload.get("id") or f"activity-{secrets.token_urlsafe(10)}"), str(payload.get("name") or "").strip(), str(payload.get("status") or "draft")
                starts_at = str(payload.get("startsAt") or "").strip().replace("T", " ") or None
                ends_at = str(payload.get("endsAt") or "").strip().replace("T", " ") or None
                if not name or len(name) > 80 or status not in ("draft", "open", "active", "ended"): raise ValueError("活动配置无效")
                if starts_at and ends_at and ends_at <= starts_at: raise ValueError("活动结束时间必须晚于开始时间")
                with database() as connection:
                    connection.execute("INSERT INTO platform_activities (id, name, description, status, starts_at, ends_at, created_by_user_id) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET name = excluded.name, description = excluded.description, status = excluded.status, starts_at = excluded.starts_at, ends_at = excluded.ends_at, updated_at = CURRENT_TIMESTAMP", (activity_id, name, str(payload.get("description") or "")[:500], status, starts_at, ends_at, user_id))
                    page = payload.get("page") if isinstance(payload.get("page"), dict) else {}
                    connection.execute("INSERT INTO activity_page_configs (id, activity_id, banner_url, theme_json, modules_json, updated_by_user_id) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(activity_id) DO UPDATE SET banner_url = excluded.banner_url, theme_json = excluded.theme_json, modules_json = excluded.modules_json, updated_by_user_id = excluded.updated_by_user_id, updated_at = CURRENT_TIMESTAMP", (f"activity-page-{secrets.token_urlsafe(8)}", activity_id, page.get("banner") or None, json.dumps(page.get("theme") or {}, ensure_ascii=False), json.dumps(page.get("modules") or [], ensure_ascii=False), user_id))
                self.send_json(200, {"id": activity_id})
            elif self.path.startswith("/api/admin/activities/") and self.path.endswith("/applications"):
                user_id = session_user(self)
                if not user_id: self.send_json(401, {"error": "Unauthorized"}); return
                require_admin(user_id); require_admin_step_up(self, user_id)
                activity_id = self.path.removeprefix("/api/admin/activities/").removesuffix("/applications").rstrip("/")
                application_id, decision = str(payload.get("applicationId") or ""), str(payload.get("decision") or "")
                if decision not in ("approved", "rejected"): raise ValueError("审核决定无效")
                with database() as connection:
                    if not connection.execute("UPDATE activity_applications SET status = ?, reviewer_user_id = ?, review_note = ?, reviewed_at = CURRENT_TIMESTAMP WHERE id = ? AND activity_id = ? AND status = 'pending'", (decision, user_id, str(payload.get("note") or "")[:500] or None, application_id, activity_id)).rowcount:
                        raise ValueError("报名不存在或已审核")
                    write_platform_audit(connection, user_id, f"activity_application_{decision}", "activity", activity_id, {"applicationId": application_id})
                self.send_json(200, {"ok": True})
            elif self.path.startswith("/api/admin/activities/") and self.path.endswith("/products"):
                user_id = session_user(self)
                if not user_id: self.send_json(401, {"error": "Unauthorized"}); return
                require_admin(user_id); require_admin_step_up(self, user_id)
                activity_id = self.path.removeprefix("/api/admin/activities/").removesuffix("/products").rstrip("/")
                activity_product_id, decision = str(payload.get("activityProductId") or ""), str(payload.get("decision") or "")
                if decision not in ("active", "rejected", "disabled"):
                    raise ValueError("活动作品审核决定无效")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    activity = connection.execute("SELECT status FROM platform_activities WHERE id = ?", (activity_id,)).fetchone()
                    product = connection.execute("SELECT activity_products.*, products.stock FROM activity_products JOIN products ON products.id = activity_products.product_id WHERE activity_products.id = ? AND activity_products.activity_id = ?", (activity_product_id, activity_id)).fetchone()
                    if not activity or not product:
                        raise ValueError("活动作品不存在")
                    if decision == "active" and activity["status"] not in ("open", "active"):
                        raise ValueError("活动未开放，不能启用作品")
                    if decision == "active" and product["quota_stock"] > product["stock"]:
                        raise ValueError("作品当前库存不足以覆盖活动配额")
                    connection.execute("UPDATE activity_products SET status = ?, reviewer_user_id = ?, review_note = ?, reviewed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (decision, user_id, str(payload.get("note") or "")[:500] or None, activity_product_id))
                    write_platform_audit(connection, user_id, f"activity_product_{decision}", "activity", activity_id, {"activityProductId": activity_product_id, "productId": product["product_id"]})
                self.send_json(200, {"ok": True})
            elif self.path == "/api/seller/activity-applications":
                user_id = session_user(self)
                if not user_id: self.send_json(401, {"error": "Unauthorized"}); return
                activity_id, shop_id = str(payload.get("activityId") or ""), str(payload.get("shopId") or "")
                with database() as connection:
                    require_shop_permission(connection, user_id, shop_id, "products")
                    activity = connection.execute("SELECT status FROM platform_activities WHERE id = ?", (activity_id,)).fetchone()
                    if not activity or activity[0] != "open":
                        raise ValueError("活动当前不接受报名")
                    application_id = f"activity-application-{secrets.token_urlsafe(10)}"
                    connection.execute("INSERT INTO activity_applications (id, activity_id, shop_id, applicant_user_id, note) VALUES (?, ?, ?, ?, ?) ON CONFLICT(activity_id, shop_id) DO UPDATE SET note = excluded.note, status = 'pending', applicant_user_id = excluded.applicant_user_id", (application_id, activity_id, shop_id, user_id, str(payload.get("note") or "")[:500]))
                    audit_delegated_shop_operation(connection, user_id, shop_id, "activity_application_saved", {"activityId": activity_id})
                self.send_json(201, {"id": application_id})
            elif self.path == "/api/seller/activity-products":
                user_id = session_user(self)
                if not user_id: self.send_json(401, {"error": "Unauthorized"}); return
                application_id, product_id, quota = str(payload.get("applicationId") or ""), str(payload.get("productId") or ""), int(number(payload.get("quotaStock")))
                if not application_id or not product_id or quota < 0: raise ValueError("活动作品配置无效")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    application = connection.execute("SELECT * FROM activity_applications WHERE id = ? AND status = 'approved'", (application_id,)).fetchone()
                    if not application: raise ValueError("活动报名尚未通过")
                    activity = connection.execute("SELECT status FROM platform_activities WHERE id = ?", (application["activity_id"],)).fetchone()
                    if not activity or activity["status"] not in ("open", "active"):
                        raise ValueError("活动当前不能管理报名作品")
                    require_shop_permission(connection, user_id, application["shop_id"], "products")
                    product = connection.execute("SELECT stock FROM products WHERE id = ? AND shop_id = ?", (product_id, application["shop_id"])).fetchone()
                    if not product or quota > product["stock"]: raise ValueError("活动配额不能超过作品库存")
                    existing = connection.execute("SELECT reserved_stock FROM activity_products WHERE activity_id = ? AND product_id = ?", (application["activity_id"], product_id)).fetchone()
                    if existing and quota < existing["reserved_stock"]:
                        raise ValueError("活动配额不能低于已预占数量")
                    connection.execute("INSERT INTO activity_products (id, activity_id, application_id, product_id, quota_stock, status) VALUES (?, ?, ?, ?, ?, 'pending') ON CONFLICT(activity_id, product_id) DO UPDATE SET quota_stock = excluded.quota_stock, application_id = excluded.application_id, status = 'pending', reviewer_user_id = NULL, review_note = NULL, reviewed_at = NULL, updated_at = CURRENT_TIMESTAMP", (f"activity-product-{secrets.token_urlsafe(8)}", application["activity_id"], application_id, product_id, quota))
                    audit_delegated_shop_operation(connection, user_id, application["shop_id"], "activity_product_saved", {"productId": product_id, "quotaStock": quota})
                self.send_json(201, {"ok": True})
            elif self.path == "/api/admin/search-operations":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id)
                require_admin_step_up(self, user_id)
                kind, source, target = str(payload.get("kind") or ""), str(payload.get("source") or "").strip().lower()[:50], payload.get("target")
                if not source or kind not in ("synonym", "correction", "recommendation", "zero_result"):
                    raise ValueError("搜索运营配置无效")
                with database() as connection:
                    if kind == "synonym":
                        terms = [str(item).strip().lower() for item in target or [] if str(item).strip()][:8]
                        if not terms: raise ValueError("请填写同义词")
                        connection.execute("INSERT INTO search_synonyms (id, source_term, target_terms_json, created_by_user_id) VALUES (?, ?, ?, ?) ON CONFLICT(source_term) DO UPDATE SET target_terms_json = excluded.target_terms_json, updated_at = CURRENT_TIMESTAMP", (f"search-synonym-{secrets.token_urlsafe(8)}", source, json.dumps(terms, ensure_ascii=False), user_id))
                    elif kind == "correction":
                        corrected = str(target or "").strip().lower()[:50]
                        if not corrected: raise ValueError("请填写纠错词")
                        connection.execute("INSERT INTO search_corrections (id, typo, corrected_term, created_by_user_id) VALUES (?, ?, ?, ?) ON CONFLICT(typo) DO UPDATE SET corrected_term = excluded.corrected_term, updated_at = CURRENT_TIMESTAMP", (f"search-correction-{secrets.token_urlsafe(8)}", source, corrected, user_id))
                    elif kind == "recommendation":
                        recommendation = str(target or "").strip()[:50]
                        if not recommendation: raise ValueError("请填写推荐词")
                        weight = max(1, min(10000, int(payload.get("weight") or 100)))
                        connection.execute("INSERT INTO search_recommendations (id, keyword, recommendation, weight, created_by_user_id) VALUES (?, ?, ?, ?, ?) ON CONFLICT(keyword, recommendation) DO UPDATE SET enabled = 1, weight = excluded.weight, updated_at = CURRENT_TIMESTAMP", (f"search-recommendation-{secrets.token_urlsafe(8)}", source, recommendation, weight, user_id))
                    else:
                        config = target if isinstance(target, dict) else {}
                        message = str(config.get("message") or "").strip()[:200]
                        if not message: raise ValueError("请填写无结果提示")
                        connection.execute("INSERT INTO search_zero_result_rules (id, keyword, message, product_id, created_by_user_id) VALUES (?, ?, ?, ?, ?) ON CONFLICT(keyword) DO UPDATE SET message = excluded.message, product_id = excluded.product_id, updated_at = CURRENT_TIMESTAMP", (f"search-zero-{secrets.token_urlsafe(8)}", source, message, str(config.get("productId") or "") or None, user_id))
                    write_platform_audit(connection, user_id, "search_operation_saved", "search", source, {"kind": kind})
                self.send_json(200, {"ok": True})
            elif self.path.startswith("/api/admin/campaigns/") and self.path.endswith("/audience"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id); require_admin_step_up(self, user_id)
                campaign_id = self.path.removeprefix("/api/admin/campaigns/").removesuffix("/audience").rstrip("/")
                user_ids = list(dict.fromkeys(str(item) for item in payload.get("userIds") or [] if str(item)))[:200]
                segment = str(payload.get("segment") or "").strip()[:50] or None
                if not user_ids and not segment: raise ValueError("请填写发放名单或人群")
                with database() as connection:
                    for buyer_id in user_ids:
                        connection.execute("INSERT OR IGNORE INTO campaign_audiences (id, campaign_id, buyer_user_id, created_by_user_id) VALUES (?, ?, ?, ?)", (f"campaign-audience-{secrets.token_urlsafe(8)}", campaign_id, buyer_id, user_id))
                    if segment: connection.execute("INSERT OR IGNORE INTO campaign_audiences (id, campaign_id, segment, created_by_user_id) VALUES (?, ?, ?, ?)", (f"campaign-audience-{secrets.token_urlsafe(8)}", campaign_id, segment, user_id))
                self.send_json(200, {"ok": True, "count": len(user_ids)})
            elif self.path.startswith("/api/admin/campaigns/") and self.path.endswith("/issue"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id); require_admin_step_up(self, user_id)
                campaign_id = self.path.removeprefix("/api/admin/campaigns/").removesuffix("/issue").rstrip("/")
                direct_ids = list(dict.fromkeys(str(item) for item in payload.get("userIds") or [] if str(item)))[:500]
                segment = str(payload.get("segment") or "").strip() or None
                quantity = max(1, min(20, int(number(payload.get("quantity") or 1))))
                if not direct_ids and not segment:
                    raise ValueError("请填写发放名单或目标人群")
                with database() as connection:
                    target_ids = list(dict.fromkeys([*direct_ids, *campaign_coupon_targets(connection, segment)]))[:1000]
                    if not target_ids:
                        raise ValueError("目标人群中没有可发放的买家")
                    for buyer_id in target_ids:
                        connection.execute("INSERT OR IGNORE INTO campaign_audiences (id, campaign_id, buyer_user_id, segment, created_by_user_id) VALUES (?, ?, ?, ?, ?)", (f"campaign-audience-{secrets.token_urlsafe(8)}", campaign_id, buyer_id, segment, user_id))
                    result = issue_campaign_coupons(connection, campaign_id, target_ids, quantity, "segment" if segment else "direct", user_id)
                    write_platform_audit(connection, user_id, "campaign_coupon_issued", "campaign", campaign_id, {"segment": segment, "targeted": len(target_ids), **result})
                self.send_json(201, result)
            elif self.path.startswith("/api/admin/campaigns/") and self.path.endswith("/codes"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id); require_admin_step_up(self, user_id)
                campaign_id = self.path.removeprefix("/api/admin/campaigns/").removesuffix("/codes").rstrip("/")
                count, prefix = max(1, min(500, int(number(payload.get("count") or 1)))), re.sub(r"[^A-Z0-9]", "", str(payload.get("prefix") or "HC").upper())[:8] or "HC"
                assigned_user_ids = list(dict.fromkeys(str(item) for item in payload.get("assignedUserIds") or [] if str(item)))[:500]
                if assigned_user_ids:
                    count = len(assigned_user_ids)
                with database() as connection:
                    campaign = connection.execute("SELECT campaign_type FROM platform_campaigns WHERE id = ?", (campaign_id,)).fetchone()
                    if not campaign or campaign[0] != "coupon":
                        raise ValueError("优惠券活动不存在")
                    codes = []
                    for index in range(count):
                        code = f"{prefix}{secrets.token_hex(4).upper()}"; codes.append(code)
                        assigned_user_id = assigned_user_ids[index] if assigned_user_ids else None
                        if assigned_user_id and not connection.execute("SELECT 1 FROM users JOIN user_roles ON user_roles.user_id = users.id WHERE users.id = ? AND users.status = 'active' AND user_roles.role = 'buyer'", (assigned_user_id,)).fetchone():
                            raise ValueError("专属券买家不存在")
                        connection.execute("INSERT INTO campaign_coupon_codes (id, campaign_id, code, assigned_user_id, expires_at) VALUES (?, ?, ?, ?, ?)", (f"coupon-code-{secrets.token_urlsafe(8)}", campaign_id, code, assigned_user_id, payload.get("expiresAt") or None))
                    write_platform_audit(connection, user_id, "campaign_coupon_codes_generated", "campaign", campaign_id, {"count": count, "assigned": len(assigned_user_ids), "expiresAt": payload.get("expiresAt") or None})
                self.send_json(201, {"codes": codes, "assigned": len(assigned_user_ids)})
            elif self.path == "/api/admin/coupons/reminders/run":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id); require_admin_step_up(self, user_id)
                reminders = run_coupon_expiry_reminders()
                self.send_json(200, {"reminders": reminders})
            elif self.path == "/api/admin/campaigns":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id)
                require_admin_step_up(self, user_id)
                campaign_id = str(payload.get("id") or f"campaign-{secrets.token_urlsafe(10)}")
                name, campaign_type, status = str(payload.get("name") or "").strip(), str(payload.get("type") or ""), str(payload.get("status") or "draft")
                rule = payload.get("rule") if isinstance(payload.get("rule"), dict) else {}
                threshold, discount = number(rule.get("threshold")), number(rule.get("discount"))
                budget = number(payload.get("budget"))
                total_limit = int(number(payload.get("totalUsageLimit")))
                per_user_limit = int(number(payload.get("perUserUsageLimit")) or 1)
                if not name or len(name) > 80 or campaign_type not in ("coupon", "full_reduction") or status not in ("draft", "active", "ended") or threshold < 0 or discount <= 0 or (threshold and discount > threshold) or budget < 0 or total_limit < 0 or per_user_limit < 1:
                    raise ValueError("活动配置无效")
                with database() as connection:
                    connection.execute(
                        """
                        INSERT INTO platform_campaigns (id, name, campaign_type, rule_json, status, starts_at, ends_at, budget_cents, total_usage_limit, per_user_usage_limit, created_by_user_id)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ON CONFLICT(id) DO UPDATE SET name = excluded.name, campaign_type = excluded.campaign_type, rule_json = excluded.rule_json,
                          status = excluded.status, starts_at = excluded.starts_at, ends_at = excluded.ends_at, budget_cents = excluded.budget_cents,
                          total_usage_limit = excluded.total_usage_limit, per_user_usage_limit = excluded.per_user_usage_limit, updated_at = CURRENT_TIMESTAMP
                        """,
                        (campaign_id, name, campaign_type, json.dumps(rule, ensure_ascii=False), status, payload.get("startsAt") or None, payload.get("endsAt") or None, int(round(budget * 100)) if budget else None, total_limit or None, per_user_limit, user_id),
                    )
                    write_platform_audit(connection, user_id, f"campaign_{status}", "campaign", campaign_id, {"type": campaign_type})
                self.send_json(200, {"ok": True, "id": campaign_id})
            elif self.path.startswith("/api/admin/appeals/"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id)
                require_admin_step_up(self, user_id)
                appeal_id, decision = self.path.removeprefix("/api/admin/appeals/").rstrip("/"), str(payload.get("decision") or "")
                if decision not in ("approved", "rejected"):
                    raise ValueError("申诉处理决定无效")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    appeal = connection.execute("SELECT * FROM governance_appeals WHERE id = ? AND status = 'pending'", (appeal_id,)).fetchone()
                    if not appeal:
                        raise ValueError("申诉不存在或已处理")
                    note = str(payload.get("note") or "").strip()
                    connection.execute("UPDATE governance_appeals SET status = ?, handled_by_user_id = ?, resolution_note = ?, handled_at = CURRENT_TIMESTAMP WHERE id = ?", (decision, user_id, note or None, appeal_id))
                    if decision == "approved" and appeal["target_type"] == "product":
                        connection.execute("UPDATE products SET moderation_status = 'approved', moderation_reason = NULL, status = 'published', moderated_at = CURRENT_TIMESTAMP WHERE id = ?", (appeal["target_id"],))
                    complete_governance_task(connection, "appeal", appeal_id, user_id)
                    notify_governance(connection, appeal["appellant_user_id"], "appeal_result", "申诉处理结果", "申诉已通过" if decision == "approved" else "申诉未通过", "appeal", appeal_id)
                    write_platform_audit(connection, user_id, f"appeal_{decision}", appeal["target_type"], appeal["target_id"], {"appealId": appeal_id, "note": note})
                self.send_json(200, {"ok": True})
            elif self.path == "/api/admin/finance/settings":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id)
                require_admin_step_up(self, user_id, force_fresh=True)
                fee_bps = int(number(payload.get("serviceFeeBps")))
                if not 0 <= fee_bps <= 3000:
                    raise ValueError("平台服务费率必须为 0-30%")
                with database() as connection:
                    connection.execute("INSERT INTO platform_finance_settings (id, service_fee_bps, updated_by_user_id) VALUES (1, ?, ?) ON CONFLICT(id) DO UPDATE SET service_fee_bps = excluded.service_fee_bps, updated_by_user_id = excluded.updated_by_user_id, updated_at = CURRENT_TIMESTAMP", (fee_bps, user_id))
                    write_platform_audit(connection, user_id, "finance_fee_rate_updated", "platform_finance", "settings", {"serviceFeeBps": fee_bps})
                self.send_json(200, {"feeRateBps": fee_bps})
            elif self.path.startswith("/api/admin/withdrawals/"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id)
                require_admin_step_up(self, user_id, force_fresh=True)
                withdrawal_id = self.path.removeprefix("/api/admin/withdrawals/").rstrip("/")
                decision = str(payload.get("decision") or "")
                note = str(payload.get("note") or "").strip()[:500]
                if decision not in ("approved", "rejected", "paid"):
                    raise ValueError("提现处理决定无效")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    request = connection.execute("SELECT * FROM shop_withdrawal_requests WHERE id = ?", (withdrawal_id,)).fetchone()
                    if not request:
                        raise ValueError("提现申请不存在")
                    old_status = request["status"]
                    valid = (decision == "approved" and old_status == "pending") or (decision == "rejected" and old_status in ("pending", "approved")) or (decision == "paid" and old_status == "approved")
                    if not valid:
                        raise ValueError("该提现申请当前不能执行此操作")
                    ensure_shop_wallet(connection, request["shop_id"])
                    if decision == "approved":
                        connection.execute("UPDATE shop_withdrawal_requests SET status = 'approved', reviewer_user_id = ?, reviewer_note = ?, reviewed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (user_id, note or None, withdrawal_id))
                    elif decision == "rejected":
                        connection.execute("UPDATE shop_withdrawal_requests SET status = 'rejected', reviewer_user_id = ?, reviewer_note = ?, reviewed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (user_id, note or None, withdrawal_id))
                        connection.execute("UPDATE shop_wallets SET withdrawing_cents = withdrawing_cents - ?, available_cents = available_cents + ?, updated_at = CURRENT_TIMESTAMP WHERE shop_id = ?", (request["amount_cents"], request["amount_cents"], request["shop_id"]))
                        write_wallet_ledger(connection, request["shop_id"], "withdrawal_rejected", withdrawal_id=withdrawal_id, available=request["amount_cents"], withdrawing=-request["amount_cents"], note=note or "提现申请已驳回")
                    else:
                        connection.execute("UPDATE shop_withdrawal_requests SET status = 'paid', reviewer_user_id = ?, reviewer_note = ?, reviewed_at = CURRENT_TIMESTAMP, paid_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (user_id, note or None, withdrawal_id))
                        connection.execute("UPDATE shop_wallets SET withdrawing_cents = withdrawing_cents - ?, withdrawn_cents = withdrawn_cents + ?, updated_at = CURRENT_TIMESTAMP WHERE shop_id = ?", (request["amount_cents"], request["amount_cents"], request["shop_id"]))
                        write_wallet_ledger(connection, request["shop_id"], "withdrawal_paid", withdrawal_id=withdrawal_id, withdrawing=-request["amount_cents"], withdrawn=request["amount_cents"], note=note or "提现已打款")
                    write_platform_audit(connection, user_id, f"withdrawal_{decision}", "withdrawal", withdrawal_id, {"note": note})
                self.send_json(200, {"ok": True})
            elif self.path == "/api/admin/governance/rules":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id)
                require_admin_step_up(self, user_id)
                rule_id = str(payload.get("id") or f"governance-rule-{secrets.token_urlsafe(10)}")
                name, keyword, action = str(payload.get("name") or "").strip(), str(payload.get("keyword") or "").strip().lower(), str(payload.get("action") or "manual_review")
                enabled = int(bool(payload.get("enabled", True)))
                priority, rollout = int(number(payload.get("priority") or 100)), int(number(payload.get("rolloutPercent") if payload.get("rolloutPercent") is not None else 100))
                release_status, condition_logic = str(payload.get("releaseStatus") or ("active" if enabled else "paused")), str(payload.get("conditionLogic") or "all")
                conditions = normalized_governance_conditions(payload.get("conditions"), keyword)
                if not name or len(name) > 80 or len(keyword) > 80 or action not in ("manual_review", "reject") or not 1 <= priority <= 999 or not 0 <= rollout <= 100 or release_status not in ("draft", "active", "paused") or condition_logic not in ("all", "any"):
                    raise ValueError("审核规则参数无效")
                with database() as connection:
                    existing = connection.execute("SELECT version FROM governance_rules WHERE id = ?", (rule_id,)).fetchone()
                    version = int(existing[0]) + 1 if existing else 1
                    connection.execute("INSERT INTO governance_rules (id, name, keyword, action, enabled, priority, conditions_json, condition_logic, rollout_percent, release_status, version, created_by_user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET name = excluded.name, keyword = excluded.keyword, action = excluded.action, enabled = excluded.enabled, priority = excluded.priority, conditions_json = excluded.conditions_json, condition_logic = excluded.condition_logic, rollout_percent = excluded.rollout_percent, release_status = excluded.release_status, version = excluded.version, updated_at = CURRENT_TIMESTAMP", (rule_id, name, keyword, action, enabled, priority, json.dumps(conditions, ensure_ascii=False), condition_logic, rollout, release_status, version, user_id))
                    snapshot = {"name": name, "keyword": keyword, "action": action, "enabled": bool(enabled), "priority": priority, "conditions": conditions, "conditionLogic": condition_logic, "rolloutPercent": rollout, "releaseStatus": release_status}
                    connection.execute("INSERT INTO governance_rule_versions (id, rule_id, version, snapshot_json, created_by_user_id) VALUES (?, ?, ?, ?, ?)", (f"rule-version-{secrets.token_urlsafe(10)}", rule_id, version, json.dumps(snapshot, ensure_ascii=False), user_id))
                    write_platform_audit(connection, user_id, "governance_rule_saved", "governance_rule", rule_id, {"version": version, **snapshot})
                self.send_json(200, {"ok": True, "id": rule_id, "version": version})
            elif self.path == "/api/admin/governance/templates":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id)
                require_admin_step_up(self, user_id)
                template_id = str(payload.get("id") or f"enforcement-template-{secrets.token_urlsafe(10)}")
                name, target_type, action, reason = str(payload.get("name") or "").strip(), str(payload.get("targetType") or ""), str(payload.get("action") or ""), str(payload.get("reason") or "").strip()
                enabled = int(bool(payload.get("enabled", True)))
                if not name or not reason or len(name) > 80 or len(reason) > 300 or (target_type, action) not in (("product", "unlist_product"), ("shop", "pause_shop"), ("user", "disable_user"), ("product", "warning"), ("shop", "warning"), ("user", "warning")):
                    raise ValueError("处罚模板参数无效")
                with database() as connection:
                    connection.execute("INSERT INTO enforcement_templates (id, name, target_type, action_type, reason, enabled, created_by_user_id) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET name = excluded.name, target_type = excluded.target_type, action_type = excluded.action_type, reason = excluded.reason, enabled = excluded.enabled, updated_at = CURRENT_TIMESTAMP", (template_id, name, target_type, action, reason, enabled, user_id))
                    write_platform_audit(connection, user_id, "enforcement_template_saved", "enforcement_template", template_id, {"action": action, "enabled": bool(enabled)})
                self.send_json(200, {"ok": True, "id": template_id})
            elif self.path == "/api/admin/governance/tasks/bulk":
                user_id = session_user(self)
                if not user_id: self.send_json(401, {"error": "Unauthorized"}); return
                require_admin(user_id); require_admin_step_up(self, user_id)
                task_ids = list(dict.fromkeys(str(item) for item in payload.get("taskIds") or [] if str(item)))[:100]
                action = str(payload.get("action") or "")
                if not task_ids or action not in ("assign", "priority"): raise ValueError("批量任务操作无效")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    placeholders = ",".join("?" for _ in task_ids)
                    rows = connection.execute(f"SELECT * FROM governance_tasks WHERE id IN ({placeholders})", tuple(task_ids)).fetchall()
                    if len(rows) != len(task_ids): raise ValueError("包含不存在的治理任务")
                    if action == "assign":
                        assignee_id = str(payload.get("assigneeId") or "").strip() or None
                        if assignee_id and not is_admin(connection, assignee_id): raise ValueError("处理人必须是平台管理员")
                        for row in rows:
                            connection.execute("UPDATE governance_tasks SET assigned_user_id = ?, status = CASE WHEN ? IS NULL THEN status WHEN status = 'pending' THEN 'in_progress' ELSE status END, last_transferred_at = CURRENT_TIMESTAMP WHERE id = ?", (assignee_id, assignee_id, row["id"]))
                            connection.execute("INSERT INTO governance_task_transfers (id, task_id, from_user_id, to_user_id, transferred_by_user_id, note) VALUES (?, ?, ?, ?, ?, ?)", (f"task-transfer-{secrets.token_urlsafe(8)}", row["id"], row["assigned_user_id"], assignee_id, user_id, "批量分派"))
                    elif action == "priority":
                        priority = str(payload.get("priority") or "")
                        if priority not in ("low", "normal", "high", "urgent"): raise ValueError("任务优先级无效")
                        for row in rows:
                            connection.execute("UPDATE governance_tasks SET priority = ?, due_at = datetime('now', ?) WHERE id = ? AND status != 'completed'", (priority, default_task_due_sql(priority), row["id"]))
                            governance_case_event(connection, governance_case_type_for_task(row["task_type"]), row["target_id"], "task_priority_updated", user_id, {"priority": priority, "bulk": True})
                    write_platform_audit(connection, user_id, f"governance_tasks_bulk_{action}", "governance_task", ",".join(task_ids), {"count": len(task_ids)})
                self.send_json(200, {"ok": True, "count": len(task_ids)})
            elif self.path.startswith("/api/admin/governance/tasks/") and self.path.endswith("/assign"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id)
                require_admin_step_up(self, user_id)
                task_id = self.path.removeprefix("/api/admin/governance/tasks/").removesuffix("/assign").rstrip("/")
                assignee_id = str(payload.get("assigneeId") or "").strip() or None
                transfer_note = str(payload.get("note") or "").strip()[:1000]
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    if assignee_id and not is_admin(connection, assignee_id):
                        raise ValueError("处理人必须是管理员")
                    task = connection.execute("SELECT * FROM governance_tasks WHERE id = ?", (task_id,)).fetchone()
                    if not task:
                        raise ValueError("治理任务不存在")
                    connection.execute("UPDATE governance_tasks SET assigned_user_id = ?, status = CASE WHEN ? IS NULL THEN 'pending' WHEN status = 'completed' THEN 'completed' ELSE 'in_progress' END, last_transferred_at = CURRENT_TIMESTAMP WHERE id = ?", (assignee_id, assignee_id, task_id))
                    if task["assigned_user_id"] != assignee_id:
                        connection.execute("INSERT INTO governance_task_transfers (id, task_id, from_user_id, to_user_id, transferred_by_user_id, note) VALUES (?, ?, ?, ?, ?, ?)", (f"task-transfer-{secrets.token_urlsafe(10)}", task_id, task["assigned_user_id"], assignee_id, user_id, transfer_note or None))
                        governance_case_event(connection, governance_case_type_for_task(task["task_type"]), task["target_id"], "task_transferred", user_id, {"taskId": task_id, "fromUserId": task["assigned_user_id"], "toUserId": assignee_id, "note": transfer_note})
                    write_platform_audit(connection, user_id, "governance_task_assigned", "governance_task", task_id, {"assigneeId": assignee_id, "note": transfer_note})
                self.send_json(200, {"ok": True})
            elif self.path.startswith("/api/admin/governance/tasks/") and self.path.endswith("/config"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id)
                require_admin_step_up(self, user_id)
                task_id = self.path.removeprefix("/api/admin/governance/tasks/").removesuffix("/config").rstrip("/")
                priority, due_at = str(payload.get("priority") or "normal"), str(payload.get("dueAt") or "").strip() or None
                if priority not in ("low", "normal", "high", "urgent") or (due_at and len(due_at) > 40):
                    raise ValueError("任务配置无效")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    task = connection.execute("SELECT * FROM governance_tasks WHERE id = ?", (task_id,)).fetchone()
                    if not task:
                        raise ValueError("治理任务不存在")
                    if due_at:
                        connection.execute("UPDATE governance_tasks SET priority = ?, due_at = ? WHERE id = ?", (priority, due_at, task_id))
                    else:
                        connection.execute(f"UPDATE governance_tasks SET priority = ?, due_at = datetime('now', '{default_task_due_sql(priority)}') WHERE id = ?", (priority, task_id))
                    governance_case_event(connection, governance_case_type_for_task(task["task_type"]), task["target_id"], "task_sla_updated", user_id, {"taskId": task_id, "priority": priority, "dueAt": due_at})
                self.send_json(200, {"ok": True})
            elif self.path.startswith("/api/admin/governance/tasks/") and self.path.endswith("/notes"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id)
                task_id = self.path.removeprefix("/api/admin/governance/tasks/").removesuffix("/notes").rstrip("/")
                content = str(payload.get("content") or "").strip()
                if not 1 <= len(content) <= 1000:
                    raise ValueError("任务备注长度应为 1-1000 个字符")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    task = connection.execute("SELECT * FROM governance_tasks WHERE id = ?", (task_id,)).fetchone()
                    if not task:
                        raise ValueError("治理任务不存在")
                    connection.execute("INSERT INTO governance_task_notes (id, task_id, author_user_id, content) VALUES (?, ?, ?, ?)", (f"task-note-{secrets.token_urlsafe(10)}", task_id, user_id, content))
                    governance_case_event(connection, governance_case_type_for_task(task["task_type"]), task["target_id"], "task_note_added", user_id, {"taskId": task_id})
                self.send_json(201, {"ok": True})
            elif self.path.startswith("/api/admin/governance/cases/") and self.path.endswith("/notes"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id)
                parts = self.path.removeprefix("/api/admin/governance/cases/").removesuffix("/notes").strip("/").split("/")
                content, visibility = str(payload.get("content") or "").strip(), str(payload.get("visibility") or "internal")
                if len(parts) != 2 or not 1 <= len(content) <= 1000 or visibility not in ("internal", "external"):
                    raise ValueError("案件备注无效")
                with database() as connection:
                    governance_case_payload(connection, parts[0], parts[1])
                    note_id = f"case-note-{secrets.token_urlsafe(10)}"
                    connection.execute("INSERT INTO governance_case_notes (id, case_type, case_id, author_user_id, content, visibility) VALUES (?, ?, ?, ?, ?, ?)", (note_id, parts[0], parts[1], user_id, content, visibility))
                    write_platform_audit(connection, user_id, "governance_case_note", "governance_case", f"{parts[0]}:{parts[1]}", {"visibility": visibility})
                self.send_json(201, {"id": note_id})
            elif self.path.startswith("/api/admin/seller-verifications/"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id)
                require_admin_step_up(self, user_id)
                application_id = self.path.removeprefix("/api/admin/seller-verifications/").rstrip("/")
                decision, note = str(payload.get("decision") or ""), str(payload.get("note") or "").strip()
                document_reviews = [item for item in payload.get("documents") or [] if isinstance(item, dict)]
                if decision not in ("approved", "rejected", "supplement_required"):
                    raise ValueError("认证审核决定无效")
                if decision in ("rejected", "supplement_required") and not note:
                    raise ValueError("请填写审核说明")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    application = connection.execute("SELECT * FROM seller_verification_applications WHERE id = ? AND status = 'pending'", (application_id,)).fetchone()
                    if not application:
                        raise ValueError("认证申请不存在或已处理")
                    valid_document_ids = {row[0] for row in connection.execute("SELECT id FROM seller_verification_documents WHERE application_id = ?", (application_id,))}
                    for review in document_reviews:
                        document_id, document_status = str(review.get("id") or ""), str(review.get("status") or "")
                        if document_id not in valid_document_ids or document_status not in ("accepted", "rejected"):
                            raise ValueError("材料审核结果无效")
                        connection.execute("UPDATE seller_verification_documents SET status = ?, reviewer_note = ? WHERE id = ?", (document_status, str(review.get("note") or "").strip()[:500] or None, document_id))
                    status = "rejected" if decision == "supplement_required" else decision
                    expiry = verification_expiry(payload.get("expiresAt")) if decision == "approved" else None
                    rejection_code = "supplement_required" if decision == "supplement_required" else ("rejected" if decision == "rejected" else None)
                    supplement_due = (datetime.now(timezone.utc) + timedelta(days=15)).strftime("%Y-%m-%d 23:59:59") if decision == "supplement_required" else None
                    connection.execute("UPDATE seller_verification_applications SET status = ?, reviewer_user_id = ?, review_note = ?, rejection_code = ?, expires_at = ?, supplement_requested_at = CASE WHEN ? THEN CURRENT_TIMESTAMP ELSE supplement_requested_at END, supplement_due_at = ?, reviewed_at = CURRENT_TIMESTAMP WHERE id = ?", (status, user_id, note or None, rejection_code, expiry, decision == "supplement_required", supplement_due, application_id))
                    profile_status = "approved" if decision == "approved" else "rejected"
                    connection.execute("INSERT INTO seller_profiles (user_id, verification_status, legal_name, identity_number, contact_phone, verification_expires_at, verification_expiry_notified_at) VALUES (?, ?, ?, ?, ?, ?, NULL) ON CONFLICT(user_id) DO UPDATE SET verification_status = excluded.verification_status, legal_name = excluded.legal_name, identity_number = excluded.identity_number, contact_phone = excluded.contact_phone, verification_expires_at = excluded.verification_expires_at, verification_expiry_notified_at = NULL", (application["seller_user_id"], profile_status, application["legal_name"], application["identity_number"], application["contact_phone"], expiry))
                    message = "认证已通过" if decision == "approved" else ("请在截止日前补充认证材料" if decision == "supplement_required" else note)
                    notify_governance(connection, application["seller_user_id"], "seller_verification", "卖家认证结果", message, "seller_verification", application_id)
                    write_platform_audit(connection, user_id, f"seller_verification_{decision}", "seller_verification", application_id, {"sellerUserId": application["seller_user_id"], "expiresAt": expiry, "documentReviewCount": len(document_reviews)})
                if decision in ("rejected", "supplement_required"):
                    enqueue_tencent_sms_notification(application["contact_phone"], "seller_rejected")
                self.send_json(200, {"ok": True})
            elif self.path == "/api/admin/service-automation":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id)
                require_admin_step_up(self, user_id)
                rule_id = str(payload.get("id") or f"service-rule-{secrets.token_urlsafe(10)}")
                name = str(payload.get("name") or "").strip()[:80]
                keywords = list(dict.fromkeys(str(item).strip().lower()[:50] for item in payload.get("keywords") or [] if str(item).strip()))[:12]
                priority, route = str(payload.get("priority") or "normal"), str(payload.get("route") or "shop")
                reply_template = str(payload.get("replyTemplate") or "").strip()[:1000] or None
                sort_order = max(1, min(9999, int(number(payload.get("sortOrder") or 100))))
                if not name or not keywords or priority not in ("low", "normal", "high", "urgent") or route not in ("shop", "platform"):
                    raise ValueError("客服自动化规则参数无效")
                with database() as connection:
                    connection.execute("INSERT INTO service_automation_rules (id, name, keywords_json, priority, route, reply_template, enabled, sort_order, created_by_user_id) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?) ON CONFLICT(id) DO UPDATE SET name = excluded.name, keywords_json = excluded.keywords_json, priority = excluded.priority, route = excluded.route, reply_template = excluded.reply_template, enabled = excluded.enabled, sort_order = excluded.sort_order, updated_at = CURRENT_TIMESTAMP", (rule_id, name, json.dumps(keywords, ensure_ascii=False), priority, route, reply_template, int(bool(payload.get("enabled", True))), sort_order, user_id))
                    write_platform_audit(connection, user_id, "service_automation_rule_saved", "service_automation_rule", rule_id, {"priority": priority, "route": route, "keywords": keywords})
                self.send_json(200, {"id": rule_id})
            elif self.path == "/api/admin/support/tickets/bulk":
                user_id = session_user(self)
                if not user_id: self.send_json(401, {"error": "Unauthorized"}); return
                require_admin(user_id); require_admin_step_up(self, user_id)
                ticket_ids = list(dict.fromkeys(str(item) for item in payload.get("ticketIds") or [] if str(item)))[:100]
                action = str(payload.get("action") or "")
                if not ticket_ids or action not in ("assign", "status"): raise ValueError("批量工单操作无效")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    placeholders = ",".join("?" for _ in ticket_ids)
                    tickets = connection.execute(f"SELECT * FROM support_tickets WHERE id IN ({placeholders})", tuple(ticket_ids)).fetchall()
                    if len(tickets) != len(ticket_ids): raise ValueError("包含不存在的客服工单")
                    if action == "assign":
                        assignee_id = str(payload.get("assigneeId") or "").strip() or None
                        if assignee_id and not is_admin(connection, assignee_id): raise ValueError("处理人必须是平台管理员")
                        for ticket in tickets:
                            connection.execute("UPDATE support_tickets SET assigned_user_id = ?, status = CASE WHEN ? IS NULL THEN status WHEN status = 'open' THEN 'in_progress' ELSE status END, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (assignee_id, assignee_id, ticket["id"]))
                    else:
                        status = str(payload.get("status") or "")
                        if status not in ("open", "in_progress", "resolved", "closed"): raise ValueError("工单状态无效")
                        for ticket in tickets:
                            connection.execute("UPDATE support_tickets SET status = ?, resolved_at = CASE WHEN ? IN ('resolved', 'closed') THEN CURRENT_TIMESTAMP ELSE NULL END, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (status, status, ticket["id"]))
                    for ticket in tickets:
                        notify_governance(connection, ticket["buyer_user_id"], "support_ticket", "客服工单更新", ticket["subject"], "support_ticket", ticket["id"])
                    write_platform_audit(connection, user_id, f"support_tickets_bulk_{action}", "support_ticket", ",".join(ticket_ids), {"count": len(ticket_ids)})
                self.send_json(200, {"ok": True, "count": len(ticket_ids)})
            elif self.path.startswith("/api/admin/support/tickets/"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id)
                parts = self.path.removeprefix("/api/admin/support/tickets/").strip("/").split("/")
                ticket_id = parts[0]
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    ticket = connection.execute("SELECT * FROM support_tickets WHERE id = ?", (ticket_id,)).fetchone()
                    if not ticket:
                        raise ValueError("工单不存在")
                    if len(parts) == 2 and parts[1] == "assign":
                        assignee_id = str(payload.get("assigneeId") or "").strip() or None
                        if assignee_id and not is_admin(connection, assignee_id):
                            raise ValueError("处理人必须是平台管理员")
                        connection.execute("UPDATE support_tickets SET assigned_user_id = ?, status = CASE WHEN ? IS NULL THEN status WHEN status = 'open' THEN 'in_progress' ELSE status END, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (assignee_id, assignee_id, ticket_id))
                    elif len(parts) == 2 and parts[1] == "status":
                        status = str(payload.get("status") or "")
                        if status not in ("open", "in_progress", "resolved", "closed"):
                            raise ValueError("工单状态无效")
                        connection.execute("UPDATE support_tickets SET status = ?, resolved_at = CASE WHEN ? IN ('resolved', 'closed') THEN CURRENT_TIMESTAMP ELSE NULL END, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (status, status, ticket_id))
                    elif len(parts) == 2 and parts[1] == "messages":
                        content, attachment = str(payload.get("content") or "").strip(), str(payload.get("attachmentUrl") or "").strip() or None
                        if not 1 <= len(content) <= 1000:
                            raise ValueError("工单回复长度应为 1-1000 个字符")
                        connection.execute("INSERT INTO support_ticket_messages (id, ticket_id, sender_user_id, sender_role, content, attachment_url) VALUES (?, ?, ?, 'admin', ?, ?)", (f"ticket-message-{secrets.token_urlsafe(10)}", ticket_id, user_id, content, attachment))
                        connection.execute("UPDATE support_tickets SET status = 'in_progress', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (ticket_id,))
                        if attachment:
                            link_media_assets(connection, [attachment], "support_ticket", ticket_id)
                    else:
                        raise ValueError("工单操作无效")
                    notify_governance(connection, ticket["buyer_user_id"], "support_ticket", "客服工单更新", ticket["subject"], "support_ticket", ticket_id)
                    write_platform_audit(connection, user_id, "support_ticket_updated", "support_ticket", ticket_id, {"operation": parts[1] if len(parts) > 1 else ""})
                self.send_json(200, {"ok": True})
            elif self.path == "/api/admin/moderation/products/bulk":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id)
                require_admin_step_up(self, user_id, force_fresh=True)
                product_ids = list(dict.fromkeys(str(item) for item in payload.get("productIds") or [] if str(item)))[:100]
                decision, reason = str(payload.get("decision") or ""), str(payload.get("reason") or "").strip()
                if not product_ids or decision != "rejected" or not reason:
                    raise ValueError("批量审核参数无效")
                with database() as connection:
                    placeholders = ",".join("?" for _ in product_ids)
                    found = {row[0] for row in connection.execute(f"SELECT id FROM products WHERE id IN ({placeholders})", tuple(product_ids))}
                    if len(found) != len(product_ids):
                        raise ValueError("包含不存在的作品")
                    for product_id in product_ids:
                        connection.execute("UPDATE products SET moderation_status = 'rejected', moderation_reason = ?, moderated_at = CURRENT_TIMESTAMP, status = 'unlisted', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'published'", (reason, product_id))
                        write_moderation_log(connection, product_id, f"bulk:rejected:{reason}", "rejected", reason)
                        complete_governance_task(connection, "product_moderation", product_id, user_id)
                    write_platform_audit(connection, user_id, "products_bulk_unlisted", "product", ",".join(product_ids), {"count": len(product_ids), "reason": reason})
                self.send_json(200, {"ok": True, "count": len(product_ids)})
            elif self.path.startswith("/api/admin/enforcement/templates/") and self.path.endswith("/apply"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id)
                require_admin_step_up(self, user_id, force_fresh=True)
                template_id = self.path.removeprefix("/api/admin/enforcement/templates/").removesuffix("/apply").rstrip("/")
                target_id = str(payload.get("targetId") or "").strip()
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    template = connection.execute("SELECT * FROM enforcement_templates WHERE id = ? AND enabled = 1", (template_id,)).fetchone()
                    if not template or not target_id:
                        raise ValueError("处罚模板或对象不存在")
                    action_id = execute_enforcement(connection, user_id, template["target_type"], target_id, template["action_type"], template["reason"], template_id)
                    write_platform_audit(connection, user_id, "enforcement_template_applied", "enforcement_template", template_id, {"targetId": target_id, "actionId": action_id})
                self.send_json(201, {"action": {"id": action_id, "templateId": template_id}})
            elif self.path == "/api/admin/enforcement":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id)
                require_admin_step_up(self, user_id, force_fresh=True)
                target_type, target_id, action, reason = str(payload.get("targetType") or ""), str(payload.get("targetId") or ""), str(payload.get("action") or ""), str(payload.get("reason") or "").strip()
                if (target_type, action) not in (("product", "unlist_product"), ("shop", "pause_shop"), ("user", "disable_user")) or not reason:
                    raise ValueError("处罚参数无效")
                with database() as connection:
                    owner = target_owner(connection, target_type, target_id)
                    if not owner:
                        raise ValueError("处罚对象不存在")
                    if target_type == "product": connection.execute("UPDATE products SET status = 'unlisted', moderation_status = 'rejected', moderation_reason = ? WHERE id = ?", (reason, target_id))
                    elif target_type == "shop": connection.execute("UPDATE shops SET status = 'paused' WHERE id = ?", (target_id,))
                    else: connection.execute("UPDATE users SET status = 'disabled' WHERE id = ?", (target_id,))
                    action_id = f"enforcement-{secrets.token_urlsafe(10)}"
                    connection.execute("INSERT INTO enforcement_actions (id, target_type, target_id, action_type, reason, created_by_user_id) VALUES (?, ?, ?, ?, ?, ?)", (action_id, target_type, target_id, action, reason, user_id))
                    notify_governance(connection, owner, "enforcement", "平台处理通知", reason, target_type, target_id)
                    write_platform_audit(connection, user_id, action, target_type, target_id, {"reason": reason})
                self.send_json(201, {"action": {"id": action_id}})
            elif self.path.startswith("/api/admin/moderation/products/"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id)
                require_admin_step_up(self, user_id, force_fresh=True)
                product_id = self.path.removeprefix("/api/admin/moderation/products/").rstrip("/")
                decision = str(payload.get("decision") or "")
                reason = str(payload.get("reason") or "").strip()
                if decision != "rejected":
                    raise ValueError("审核决定无效")
                if not reason:
                    raise ValueError("请填写驳回原因")
                with database() as connection:
                    product = connection.execute("SELECT id FROM products WHERE id = ?", (product_id,)).fetchone()
                    if not product:
                        raise ValueError("作品不存在")
                    updated = connection.execute(
                        "UPDATE products SET moderation_status = 'rejected', moderation_reason = ?, moderated_at = CURRENT_TIMESTAMP, status = 'unlisted', updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'published'",
                        (reason, product_id),
                    ).rowcount
                    if not updated:
                        raise ValueError("作品未上架或已被处理")
                    write_moderation_log(connection, product_id, f"manual:rejected:{reason}", "rejected", reason)
                    complete_governance_task(connection, "product_moderation", product_id, user_id)
                    write_platform_audit(connection, user_id, "product_unlisted", "product", product_id, {"reason": reason})
                self.send_json(200, {"ok": True})
            elif self.path.startswith("/api/admin/reports/"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id)
                require_admin_step_up(self, user_id)
                report_id = self.path.removeprefix("/api/admin/reports/").rstrip("/")
                decision = str(payload.get("decision") or "")
                note = str(payload.get("note") or "").strip()
                if decision not in ("resolved", "dismissed"):
                    raise ValueError("举报处理决定无效")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    report = connection.execute("SELECT * FROM content_reports WHERE id = ?", (report_id,)).fetchone()
                    if not report or report["status"] != "pending":
                        raise ValueError("举报不存在或已处理")
                    connection.execute(
                        "UPDATE content_reports SET status = ?, handled_by_user_id = ?, resolution_note = ?, handled_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (decision, user_id, note or None, report_id),
                    )
                    if decision == "resolved" and report["target_type"] == "product" and bool(payload.get("unlistProduct")):
                        connection.execute("UPDATE products SET status = 'unlisted', moderation_status = 'rejected', moderation_reason = ?, moderated_at = CURRENT_TIMESTAMP WHERE id = ?", (note or "举报处理下架", report["target_id"]))
                        owner = target_owner(connection, "product", report["target_id"])
                        if owner:
                            notify_governance(connection, owner, "report_result", "作品已被平台下架", note or "作品因举报处理被下架，可在卖家中心发起申诉", "product", report["target_id"])
                    complete_governance_task(connection, "report", report_id, user_id)
                    write_platform_audit(connection, user_id, f"report_{decision}", report["target_type"], report["target_id"], {"reportId": report_id, "note": note})
                self.send_json(200, {"ok": True})
            elif self.path == "/api/seller/withdrawals":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                shop_id = str(payload.get("shopId") or "").strip()
                amount_cents = int(round(number(payload.get("amount")) * 100))
                recipient_type = str(payload.get("recipientType") or "")
                recipient = str(payload.get("recipient") or "").strip()
                if not shop_id or amount_cents <= 0 or recipient_type not in ("bank", "wallet") or not recipient or len(recipient) > 500:
                    raise ValueError("提现申请参数无效")
                if amount_cents < SETTLEMENT_MIN_PAYOUT_CENTS:
                    raise ValueError(f"单次结算金额不得低于 ${SETTLEMENT_MIN_PAYOUT_CENTS / 100:.2f}")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    require_shop_owner(connection, user_id, shop_id)
                    ensure_finance_for_paid_orders(connection, [shop_id])
                    ensure_shop_wallet(connection, shop_id)
                    wallet = connection.execute("SELECT available_cents FROM shop_wallets WHERE shop_id = ?", (shop_id,)).fetchone()
                    if not wallet or int(wallet["available_cents"]) < amount_cents:
                        raise ValueError("可提现余额不足")
                    withdrawal_id = f"withdrawal-{secrets.token_urlsafe(10)}"
                    connection.execute("INSERT INTO shop_withdrawal_requests (id, shop_id, applicant_user_id, amount_cents, recipient_type, recipient_snapshot) VALUES (?, ?, ?, ?, ?, ?)", (withdrawal_id, shop_id, user_id, amount_cents, recipient_type, recipient))
                    connection.execute("UPDATE shop_wallets SET available_cents = available_cents - ?, withdrawing_cents = withdrawing_cents + ?, updated_at = CURRENT_TIMESTAMP WHERE shop_id = ?", (amount_cents, amount_cents, shop_id))
                    write_wallet_ledger(connection, shop_id, "withdrawal_requested", withdrawal_id=withdrawal_id, available=-amount_cents, withdrawing=amount_cents, note="提现申请已提交")
                    write_platform_audit(connection, user_id, "seller_withdrawal_requested", "withdrawal", withdrawal_id, {"shopId": shop_id, "amountCents": amount_cents})
                self.send_json(201, {"withdrawalId": withdrawal_id})
            elif self.path == "/api/seller/finance/schedule":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                schedule = str(payload.get("schedule") or "").strip()
                if schedule not in SELLER_PAYOUT_SCHEDULES:
                    raise ValueError("结算周期仅支持每日、每周、双周或每月")
                with database() as connection:
                    if not is_seller(connection, user_id):
                        self.send_json(403, {"error": "Seller access required"})
                        return
                    connection.execute("INSERT OR IGNORE INTO seller_profiles (user_id, verification_status) VALUES (?, 'pending')", (user_id,))
                    connection.execute(
                        "UPDATE seller_profiles SET payout_schedule = ?, payout_schedule_updated_at = CURRENT_TIMESTAMP WHERE user_id = ?",
                        (schedule, user_id),
                    )
                    write_platform_audit(connection, user_id, "seller_payout_schedule_updated", "seller_finance", user_id, {"schedule": schedule})
                self.send_json(200, {"payoutSchedule": schedule, "nextPayoutAt": payout_schedule_next_at(schedule)})
            elif self.path == "/api/seller/payout-account/onboarding":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                if LIANLIAN_MODE != "mock":
                    self.send_json(503, {"error": "连连支付尚未配置商户参数，暂时无法发起绑卡"})
                    return
                account_name = str(payload.get("accountName") or "").strip()
                bank_card = str(payload.get("bankCard") or "").replace(" ", "").strip()
                if not 2 <= len(account_name) <= 80 or not re.fullmatch(r"\d{12,19}", bank_card):
                    raise ValueError("请填写真实姓名和有效银行卡号")
                with database() as connection:
                    if not is_seller(connection, user_id):
                        self.send_json(403, {"error": "Seller access required"})
                        return
                    connection.execute("UPDATE seller_profiles SET payout_provider = 'lianlian', payout_binding_status = 'bound', payout_account_id = ?, payout_account_mask = ?, payout_bound_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE user_id = ?", (f"mock-{secrets.token_urlsafe(10)}", payout_account_mask(bank_card), user_id))
                    write_platform_audit(connection, user_id, "lianlian_payout_bound_mock", "seller_payout_account", user_id, {"accountMask": payout_account_mask(bank_card)})
                    self.send_json(200, {"payoutAccount": seller_payout_account_payload(connection, user_id)})
            elif self.path in ("/api/seller/products", "/api/seller/drafts"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_seller(user_id)
                product = payload.get("product")
                if not isinstance(product, dict):
                    raise ValueError("作品数据无效")
                status = "draft" if self.path.endswith("drafts") else str(payload.get("status") or "published")
                self.send_json(201, {"product": save_seller_product(user_id, product, status)})
            elif self.path == "/api/seller/inventory/adjustments":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_seller(user_id)
                product_id = str(payload.get("productId") or "").strip()
                sku_id = str(payload.get("skuId") or "").strip()
                adjustment_type = str(payload.get("type") or "")
                quantity = int(number(payload.get("quantity")))
                reason = str(payload.get("reason") or "").strip()[:120]
                if adjustment_type not in ("set", "increase", "decrease") or quantity < 0 or not reason:
                    raise ValueError("库存调整参数无效")
                if not product_id or not sku_id:
                    raise ValueError("请选择需要调整的 SKU")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    shop_ids = seller_accessible_shop_ids(connection, user_id, "inventory")
                    product = connection.execute(
                        f"SELECT id, shop_id FROM products WHERE id = ? AND shop_id IN ({','.join('?' for _ in shop_ids)})",
                        (product_id, *shop_ids),
                    ).fetchone()
                    sku = connection.execute(
                        "SELECT id, stock FROM product_skus WHERE id = ? AND product_id = ? AND status = 'active'",
                        (sku_id, product_id),
                    ).fetchone()
                    if not product or not sku:
                        raise ValueError("作品或 SKU 不存在，或已不可售")
                    before = int(sku["stock"])
                    after = quantity if adjustment_type == "set" else before + quantity if adjustment_type == "increase" else before - quantity
                    if after < 0:
                        raise ValueError("减少数量不能超过当前库存")
                    connection.execute("UPDATE product_skus SET stock = ? WHERE id = ?", (after, sku_id))
                    refresh_product_stock(connection, product_id)
                    connection.execute(
                        "INSERT INTO inventory_adjustments (id, product_id, sku_id, operator_user_id, adjustment_type, quantity_before, quantity_after, reason) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (f"inventory-{secrets.token_urlsafe(10)}", product_id, sku_id, user_id, adjustment_type, before, after, reason),
                    )
                    audit_delegated_shop_operation(connection, user_id, product["shop_id"], "inventory_adjusted", {"productId": product_id, "skuId": sku_id, "type": adjustment_type, "before": before, "after": after})
                self.send_json(200, {"product": seller_product_response(user_id, product_id)})
            elif self.path == "/api/seller/inventory/thresholds":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_seller(user_id)
                product_id = str(payload.get("productId") or "").strip()
                threshold = int(number(payload.get("lowStockThreshold")))
                if not product_id or threshold < 0:
                    raise ValueError("库存预警阈值无效")
                with database() as connection:
                    shop_ids = seller_accessible_shop_ids(connection, user_id, "inventory")
                    product = connection.execute(f"SELECT shop_id FROM products WHERE id = ? AND shop_id IN ({','.join('?' for _ in shop_ids)})", (product_id, *shop_ids)).fetchone()
                    if not product:
                        raise ValueError("作品不存在或无权操作")
                    updated = connection.execute(
                        f"UPDATE products SET low_stock_threshold = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND shop_id IN ({','.join('?' for _ in shop_ids)})",
                        (threshold, product_id, *shop_ids),
                    ).rowcount
                    if not updated:
                        raise ValueError("作品不存在或无权操作")
                    audit_delegated_shop_operation(connection, user_id, product[0], "inventory_threshold_updated", {"productId": product_id, "threshold": threshold})
                self.send_json(200, {"product": seller_product_response(user_id, product_id)})
            elif self.path.startswith("/api/seller/inventory/skus/") and self.path.endswith("/status"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_seller(user_id)
                sku_id = self.path.removeprefix("/api/seller/inventory/skus/").removesuffix("/status").rstrip("/")
                status = str(payload.get("status") or "")
                if status not in ("active", "disabled"):
                    raise ValueError("SKU 状态无效")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    shop_ids = seller_accessible_shop_ids(connection, user_id, "inventory")
                    sku = connection.execute(
                        f"SELECT product_skus.product_id, products.shop_id FROM product_skus JOIN products ON products.id = product_skus.product_id WHERE product_skus.id = ? AND products.shop_id IN ({','.join('?' for _ in shop_ids)})",
                        (sku_id, *shop_ids),
                    ).fetchone()
                    if not sku:
                        raise ValueError("SKU 不存在或无权操作")
                    connection.execute("UPDATE product_skus SET status = ? WHERE id = ?", (status, sku_id))
                    refresh_product_stock(connection, sku["product_id"])
                    write_platform_audit(connection, user_id, f"sku_{status}", "product_sku", sku_id)
                    audit_delegated_shop_operation(connection, user_id, sku["shop_id"], "sku_status_updated", {"skuId": sku_id, "status": status})
                    product_id = sku["product_id"]
                self.send_json(200, {"product": seller_product_response(user_id, product_id)})
            elif self.path == "/api/seller/products/bulk":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_seller(user_id)
                product_ids = [str(item) for item in payload.get("productIds") or []]
                if not product_ids:
                    raise ValueError("请选择作品")
                with database() as connection:
                    shop_ids = seller_accessible_shop_ids(connection, user_id, "products")
                    placeholders = ",".join("?" for _ in product_ids)
                    allowed = connection.execute(
                        f"SELECT id FROM products WHERE id IN ({placeholders}) AND shop_id IN ({','.join('?' for _ in shop_ids)})",
                        (*product_ids, *shop_ids),
                    ).fetchall()
                    if len(allowed) != len(product_ids):
                        raise ValueError("包含无权操作的作品")
                    fields, values = [], []
                    if payload.get("price") is not None:
                        fields.append("price_cents = ?")
                        values.append(max(0, int(round(number(payload["price"]) * 100))))
                    stock_value = max(0, int(number(payload["stock"]))) if payload.get("stock") is not None else None
                    if not fields:
                        if stock_value is None:
                            raise ValueError("请填写价格或库存")
                    if fields:
                        connection.execute(
                            f"UPDATE products SET {', '.join(fields)}, updated_at = CURRENT_TIMESTAMP WHERE id IN ({placeholders})",
                            (*values, *product_ids),
                        )
                        if payload.get("price") is not None:
                            connection.execute(
                                f"UPDATE product_skus SET price_cents = ? WHERE product_id IN ({placeholders})",
                                (values[0], *product_ids),
                            )
                    if stock_value is not None:
                        multi_sku = connection.execute(
                            f"SELECT product_id FROM product_skus WHERE product_id IN ({placeholders}) AND status = 'active' GROUP BY product_id HAVING COUNT(*) <> 1",
                            tuple(product_ids),
                        ).fetchall()
                        if multi_sku:
                            raise ValueError("含有多规格作品，请在库存管理中按 SKU 调整")
                        for product_id in product_ids:
                            sku = connection.execute("SELECT id, stock FROM product_skus WHERE product_id = ? AND status = 'active'", (product_id,)).fetchone()
                            if not sku:
                                raise ValueError("作品没有可售 SKU")
                            connection.execute("UPDATE product_skus SET stock = ? WHERE id = ?", (stock_value, sku[0]))
                            connection.execute("UPDATE products SET stock = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (stock_value, product_id))
                            connection.execute(
                                "INSERT INTO inventory_adjustments (id, product_id, sku_id, operator_user_id, adjustment_type, quantity_before, quantity_after, reason) VALUES (?, ?, ?, ?, 'bulk_set', ?, ?, ?)",
                                (f"inventory-{secrets.token_urlsafe(10)}", product_id, sku[0], user_id, sku[1], stock_value, "批量设置库存"),
                            )
                self.send_json(200, {"products": [seller_product_response(user_id, product_id) for product_id in product_ids]})
            elif self.path.startswith("/api/seller/products/") and self.path.endswith("/status"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_seller(user_id)
                product_id = self.path.removeprefix("/api/seller/products/").removesuffix("/status").rstrip("/")
                status = str(payload.get("status") or "")
                if status not in ("published", "unlisted", "archived"):
                    raise ValueError("作品状态无效")
                with database() as connection:
                    shop_ids = seller_accessible_shop_ids(connection, user_id, "products")
                    updated = connection.execute(
                        f"UPDATE products SET status = ?, published_at = CASE WHEN ? = 'published' THEN COALESCE(published_at, CURRENT_TIMESTAMP) ELSE published_at END, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND shop_id IN ({','.join('?' for _ in shop_ids)})",
                        (status, status, product_id, *shop_ids),
                    ).rowcount
                    if not updated:
                        raise ValueError("作品不存在或无权操作")
                self.send_json(200, {"product": seller_product_response(user_id, product_id)})
            elif self.path == "/api/seller/shop":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_seller(user_id)
                self.send_json(200, {"shop": update_seller_shop(user_id, payload.get("shop") or {})})
            elif self.path == "/api/orders":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                self.send_json(201, {"orders": create_orders(user_id, payload)})
            elif self.path == "/api/cart":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                catalog_id = str(payload.get("catalogId") or "")
                quantity = int(payload.get("quantity") or 0)
                variants = payload.get("variants") or {}
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    cart_id = f"cart-{user_id}"
                    connection.execute("INSERT OR IGNORE INTO carts (id, buyer_user_id) VALUES (?, ?)", (cart_id, user_id))
                    sku = find_sku(connection, catalog_id, variants)
                    if quantity > sku["stock"]:
                        raise ValueError("库存不足")
                    if quantity <= 0:
                        connection.execute("DELETE FROM cart_items WHERE cart_id = ? AND product_id = ? AND sku_id = ?", (cart_id, catalog_id, sku["id"]))
                    else:
                        connection.execute("INSERT INTO cart_items (id, cart_id, product_id, sku_id, quantity) VALUES (?, ?, ?, ?, ?) ON CONFLICT(cart_id, product_id, sku_id) DO UPDATE SET quantity = excluded.quantity, updated_at = CURRENT_TIMESTAMP", (f"cart-item-{secrets.token_urlsafe(8)}", cart_id, catalog_id, sku["id"], quantity))
                        shop = connection.execute("SELECT shop_id FROM products WHERE id = ?", (catalog_id,)).fetchone()
                        record_analytics_event(connection, "add_cart", user_id=user_id, shop_id=shop[0] if shop else None, product_id=catalog_id, channel=payload.get("channel"))
                    self.send_json(200, buyer_state(connection, user_id))
            elif self.path.startswith("/api/favorites/") or self.path.startswith("/api/follows/"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                target = self.path.rsplit("/", 1)[-1]
                with database() as connection:
                    if self.path.startswith("/api/favorites/"):
                        table, field = "buyer_favorites", "product_id"
                    else:
                        table, field = "buyer_shop_follows", "shop_id"
                    existing = connection.execute(f"SELECT 1 FROM {table} WHERE buyer_user_id = ? AND {field} = ?", (user_id, target)).fetchone()
                    if existing:
                        connection.execute(f"DELETE FROM {table} WHERE buyer_user_id = ? AND {field} = ?", (user_id, target))
                    else:
                        if table == "buyer_favorites":
                            product = connection.execute("SELECT shop_id FROM products WHERE id = ? AND status = 'published'", (target,)).fetchone()
                            if not product:
                                raise ValueError("Product not found")
                            connection.execute(f"INSERT INTO {table} (buyer_user_id, {field}) VALUES (?, ?)", (user_id, target))
                            record_analytics_event(connection, "favorite_added", user_id=user_id, shop_id=product[0], product_id=target, placement="product_detail")
                        else:
                            connection.execute(f"INSERT INTO {table} (buyer_user_id, {field}) VALUES (?, ?)", (user_id, target))
                    self.send_json(200, buyer_state(connection, user_id))
            elif self.path == "/api/messages/buyer":
                user_id = session_user(self)
                shop_id, content = str(payload.get("shopId") or ""), str(payload.get("content") or "").strip()
                message_type = str(payload.get("type") or "text")
                attachment_url = str(payload.get("attachmentUrl") or "").strip() or None
                order_id = str(payload.get("orderId") or "").strip() or None
                product_id = str(payload.get("productId") or "").strip() or None
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                if not self.enforce_rate_limit(
                    "shop-message", user_id, per_ip=120, per_user=40, window_seconds=60
                ):
                    return
                if not shop_id or message_type not in ("text", "image", "order", "product"):
                    raise ValueError("消息参数无效")
                if message_type == "text" and not content:
                    raise ValueError("请输入消息内容")
                if message_type == "image" and not attachment_url:
                    raise ValueError("请上传图片")
                if message_type == "order" and not order_id:
                    raise ValueError("请选择订单")
                if message_type == "product" and not product_id:
                    raise ValueError("请选择商品")
                if len(content) > 500:
                    raise ValueError("消息不能超过 500 个字符")
                seller_recipients: list[str] = []
                notification_ids: list[str] = []
                auto_reply_id: str | None = None
                with database() as connection:
                    if not connection.execute("SELECT 1 FROM shops WHERE id = ?", (shop_id,)).fetchone():
                        raise ValueError("店铺不存在")
                    if order_id and not connection.execute("SELECT 1 FROM orders WHERE id = ? AND buyer_user_id = ? AND shop_id = ?", (order_id, user_id, shop_id)).fetchone():
                        raise ValueError("只能发送当前店铺的订单卡片")
                    if product_id and not connection.execute("SELECT 1 FROM products WHERE id = ? AND shop_id = ? AND status = 'published'", (product_id, shop_id)).fetchone():
                        raise ValueError("只能发送当前店铺的在售商品卡片")
                    message_id = f"message-{secrets.token_urlsafe(10)}"
                    stored_type = "text" if message_type == "product" else message_type
                    connection.execute("INSERT INTO shop_messages (id, shop_id, buyer_user_id, sender_role, sender_user_id, content, message_type, attachment_url, order_id, product_id) VALUES (?, ?, ?, 'buyer', ?, ?, ?, ?, ?, ?)", (message_id, shop_id, user_id, user_id, content, stored_type, attachment_url, order_id, product_id))
                    if attachment_url:
                        link_media_assets(connection, [attachment_url], "message", message_id)
                    buyer = connection.execute("SELECT display_name FROM users WHERE id = ?", (user_id,)).fetchone()
                    buyer_name = (buyer[0] if buyer and buyer[0] else "买家")
                    owner = connection.execute("SELECT owner_user_id FROM shops WHERE id = ?", (shop_id,)).fetchone()
                    if owner: notify_governance(connection, owner[0], "buyer_message", f"{buyer_name} 发来消息", content[:80], "shop", shop_id)
                    automation = apply_buyer_message_automation(connection, message_id, shop_id, user_id, content)
                    auto_reply_id = automation.get("autoReplyMessageId") if isinstance(automation, dict) else None
                    notification_ids = [row[0] for row in connection.execute("SELECT id FROM seller_message_notifications WHERE message_id = ? AND status = 'queued'", (message_id,)).fetchall()]
                    seller_recipients = shop_message_recipient_user_ids(connection, shop_id)
                for notification_id in notification_ids:
                    threading.Thread(target=dispatch_seller_message_notification, args=(notification_id,), daemon=True).start()
                LIVE_MESSAGE_HUB.publish(seller_recipients, {"type": "message.new", "audience": "seller", "shopId": shop_id, "buyerUserId": user_id, "messageId": message_id})
                enqueue_web_push_notifications(seller_recipients, {"title": f"{buyer_name} 发来消息", "body": content[:80] or f"{buyer_name} 发送了一条消息", "tag": f"shop-message-{shop_id}-{user_id}", "url": "/"})
                if auto_reply_id:
                    LIVE_MESSAGE_HUB.publish([user_id], {"type": "message.new", "audience": "buyer", "shopId": shop_id, "buyerUserId": user_id, "messageId": auto_reply_id})
                    enqueue_web_push_notifications([user_id], {"title": "店铺已收到你的消息", "body": "店主当前处于非工作时间，请耐心等待。", "tag": f"shop-message-{shop_id}", "url": "/"})
                self.send_json(201, {"ok": True})
            elif self.path == "/api/messages/seller":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                if not self.enforce_rate_limit(
                    "shop-message", user_id, per_ip=120, per_user=40, window_seconds=60
                ):
                    return
                shop_id, buyer_id, content = str(payload.get("shopId") or ""), str(payload.get("buyerUserId") or ""), str(payload.get("content") or "").strip()
                message_type = str(payload.get("type") or "text")
                attachment_url = str(payload.get("attachmentUrl") or "").strip() or None
                order_id = str(payload.get("orderId") or "").strip() or None
                product_id = str(payload.get("productId") or "").strip() or None
                if not shop_id or not buyer_id or message_type not in ("text", "image", "order", "product"):
                    raise ValueError("消息参数无效")
                if message_type == "text" and not content:
                    raise ValueError("请输入回复内容")
                if message_type == "image" and not attachment_url:
                    raise ValueError("请上传图片")
                if message_type == "order" and not order_id:
                    raise ValueError("请选择订单")
                if message_type == "product" and not product_id:
                    raise ValueError("请选择商品")
                if len(content) > 500:
                    raise ValueError("消息不能超过 500 个字符")
                with database() as connection:
                    require_shop_permission(connection, user_id, shop_id, "messages")
                    if order_id and not connection.execute("SELECT 1 FROM orders WHERE id = ? AND buyer_user_id = ? AND shop_id = ?", (order_id, buyer_id, shop_id)).fetchone():
                        raise ValueError("只能发送当前会话买家的订单卡片")
                    if product_id and not connection.execute("SELECT 1 FROM products WHERE id = ? AND shop_id = ? AND status = 'published'", (product_id, shop_id)).fetchone():
                        raise ValueError("只能发送当前店铺的在售商品卡片")
                    message_id = f"message-{secrets.token_urlsafe(10)}"
                    stored_type = "text" if message_type == "product" else message_type
                    connection.execute("INSERT INTO shop_messages (id, shop_id, buyer_user_id, sender_role, sender_user_id, content, message_type, attachment_url, order_id, product_id) VALUES (?, ?, ?, 'seller', ?, ?, ?, ?, ?, ?)", (message_id, shop_id, buyer_id, user_id, content, stored_type, attachment_url, order_id, product_id))
                    connection.execute("UPDATE seller_message_attention SET status = 'acknowledged', updated_at = CURRENT_TIMESTAMP WHERE shop_id = ? AND buyer_user_id = ? AND status = 'open'", (shop_id, buyer_id))
                    if attachment_url:
                        link_media_assets(connection, [attachment_url], "message", message_id)
                    notify_governance(connection, buyer_id, "seller_message", "收到店铺回复", content[:80], "shop", shop_id)
                    audit_delegated_shop_operation(connection, user_id, shop_id, "buyer_message_sent", {"messageType": message_type, "buyerUserId": buyer_id})
                LIVE_MESSAGE_HUB.publish([buyer_id], {"type": "message.new", "audience": "buyer", "shopId": shop_id, "buyerUserId": buyer_id, "messageId": message_id})
                enqueue_web_push_notifications([buyer_id], {"title": "收到店铺回复", "body": content[:80] or "店铺发送了一条消息", "tag": f"shop-message-{shop_id}", "url": "/"})
                self.send_json(201, {"ok": True})
            elif self.path == "/api/messages/quick-replies":
                user_id = session_user(self)
                content = str(payload.get("content") or "").strip()
                category = str(payload.get("category") or "general").strip()[:30] or "general"
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                if not content or len(content) > 500:
                    raise ValueError("快捷回复长度应为 1-500 个字符")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    if not is_seller(connection, user_id):
                        self.send_json(403, {"error": "Seller access required"})
                        return
                    reply_id = f"quick-reply-{secrets.token_urlsafe(10)}"
                    connection.execute("INSERT INTO seller_quick_replies (id, seller_user_id, content, category) VALUES (?, ?, ?, ?)", (reply_id, user_id, content, category))
                self.send_json(201, {"quickReply": {"id": reply_id, "content": content, "category": category}})
            elif self.path == "/api/support/tickets":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                subject, content = str(payload.get("subject") or "").strip(), str(payload.get("content") or "").strip()
                shop_id, order_id = str(payload.get("shopId") or "").strip() or None, str(payload.get("orderId") or "").strip() or None
                priority = str(payload.get("priority") or "normal")
                attachment = str(payload.get("attachmentUrl") or "").strip() or None
                if not 1 <= len(subject) <= 120 or not 1 <= len(content) <= 1000 or priority not in ("low", "normal", "high", "urgent"):
                    raise ValueError("工单内容或优先级无效")
                with database() as connection:
                    if shop_id and not connection.execute("SELECT 1 FROM shops WHERE id = ?", (shop_id,)).fetchone():
                        raise ValueError("店铺不存在")
                    if order_id:
                        order = connection.execute("SELECT shop_id FROM orders WHERE id = ? AND buyer_user_id = ?", (order_id, user_id)).fetchone()
                        if not order:
                            raise ValueError("订单不存在")
                        shop_id = shop_id or order[0]
                    ticket_id = f"ticket-{secrets.token_urlsafe(10)}"
                    message_id = f"ticket-message-{secrets.token_urlsafe(10)}"
                    connection.execute("INSERT INTO support_tickets (id, buyer_user_id, shop_id, order_id, subject, priority) VALUES (?, ?, ?, ?, ?, ?)", (ticket_id, user_id, shop_id, order_id, subject, priority))
                    connection.execute("INSERT INTO support_ticket_messages (id, ticket_id, sender_user_id, sender_role, content, attachment_url) VALUES (?, ?, ?, 'buyer', ?, ?)", (message_id, ticket_id, user_id, content, attachment))
                    write_support_ticket_event(connection, ticket_id, "created", user_id, {"priority": priority, "shopId": shop_id, "orderId": order_id})
                    apply_support_automation(connection, ticket_id, content)
                    if attachment:
                        link_media_assets(connection, [attachment], "support_ticket", ticket_id)
                    if shop_id:
                        owner = connection.execute("SELECT owner_user_id FROM shops WHERE id = ?", (shop_id,)).fetchone()
                        if owner:
                            notify_governance(connection, owner[0], "support_ticket", "收到客服工单", subject, "support_ticket", ticket_id)
                self.send_json(201, {"id": ticket_id})
            elif self.path == "/api/seller/platform-support/tickets":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                subject, content = str(payload.get("subject") or "").strip(), str(payload.get("content") or "").strip()
                priority = str(payload.get("priority") or "normal")
                if not 1 <= len(subject) <= 120 or not 1 <= len(content) <= 1000 or priority not in ("low", "normal", "high", "urgent"):
                    raise ValueError("工单内容或优先级无效")
                with database() as connection:
                    if not is_seller(connection, user_id):
                        self.send_json(403, {"error": "Seller access required"})
                        return
                    ticket_id = f"ticket-{secrets.token_urlsafe(10)}"
                    message_id = f"ticket-message-{secrets.token_urlsafe(10)}"
                    connection.execute("INSERT INTO support_tickets (id, buyer_user_id, subject, priority, requester_role) VALUES (?, ?, ?, ?, 'seller')", (ticket_id, user_id, subject, priority))
                    connection.execute("INSERT INTO support_ticket_messages (id, ticket_id, sender_user_id, sender_role, content) VALUES (?, ?, ?, 'seller', ?)", (message_id, ticket_id, user_id, content))
                    write_support_ticket_event(connection, ticket_id, "seller_platform_ticket_created", user_id, {"priority": priority})
                    apply_support_automation(connection, ticket_id, content)
                self.send_json(201, {"id": ticket_id})
            elif self.path.startswith("/api/support/tickets/") and self.path.endswith("/messages"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                ticket_id = self.path.removeprefix("/api/support/tickets/").removesuffix("/messages").rstrip("/")
                content, attachment = str(payload.get("content") or "").strip(), str(payload.get("attachmentUrl") or "").strip() or None
                if not 1 <= len(content) <= 1000:
                    raise ValueError("工单回复长度应为 1-1000 个字符")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    ticket = connection.execute("SELECT * FROM support_tickets WHERE id = ?", (ticket_id,)).fetchone()
                    if not ticket or not support_ticket_access(connection, ticket, user_id, "buyer"):
                        raise ValueError("工单不存在或无权回复")
                    message_id = f"ticket-message-{secrets.token_urlsafe(10)}"
                    connection.execute("INSERT INTO support_ticket_messages (id, ticket_id, sender_user_id, sender_role, content, attachment_url) VALUES (?, ?, ?, 'buyer', ?, ?)", (message_id, ticket_id, user_id, content, attachment))
                    connection.execute("UPDATE support_tickets SET status = CASE WHEN status IN ('resolved', 'closed') THEN 'open' ELSE status END, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (ticket_id,))
                    write_support_ticket_event(connection, ticket_id, "buyer_replied", user_id)
                    if attachment:
                        link_media_assets(connection, [attachment], "support_ticket", ticket_id)
                self.send_json(201, {"ok": True})
            elif self.path.startswith("/api/seller/support/tickets/"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                parts = self.path.removeprefix("/api/seller/support/tickets/").strip("/").split("/")
                ticket_id = parts[0]
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    ticket = connection.execute("SELECT * FROM support_tickets WHERE id = ?", (ticket_id,)).fetchone()
                    if not ticket or not support_ticket_access(connection, ticket, user_id, "seller"):
                        raise ValueError("工单不存在或无权处理")
                    if len(parts) == 2 and parts[1] == "resolve":
                        connection.execute("UPDATE support_tickets SET status = 'resolved', resolved_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (ticket_id,))
                    elif len(parts) == 2 and parts[1] == "messages":
                        content, attachment = str(payload.get("content") or "").strip(), str(payload.get("attachmentUrl") or "").strip() or None
                        if not 1 <= len(content) <= 1000:
                            raise ValueError("工单回复长度应为 1-1000 个字符")
                        connection.execute("INSERT INTO support_ticket_messages (id, ticket_id, sender_user_id, sender_role, content, attachment_url) VALUES (?, ?, ?, 'seller', ?, ?)", (f"ticket-message-{secrets.token_urlsafe(10)}", ticket_id, user_id, content, attachment))
                        connection.execute("UPDATE support_tickets SET status = 'in_progress', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (ticket_id,))
                        write_support_ticket_event(connection, ticket_id, "seller_replied", user_id)
                        if attachment:
                            link_media_assets(connection, [attachment], "support_ticket", ticket_id)
                    else:
                        raise ValueError("工单操作无效")
                self.send_json(200, {"ok": True})
            elif self.path == "/api/seller/verification":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                legal_name, identity_number, contact_phone = str(payload.get("legalName") or "").strip(), str(payload.get("identityNumber") or "").strip(), str(payload.get("contactPhone") or "").strip()
                evidence = [str(item) for item in payload.get("evidence") or [] if str(item).startswith(("/media/", "http://", "https://"))][:6]
                business_type = str(payload.get("businessType") or "individual")
                representative, license_no, address = str(payload.get("legalRepresentative") or "").strip(), str(payload.get("businessLicenseNo") or "").strip(), str(payload.get("businessAddress") or "").strip()
                categories = []
                for category in payload.get("operatingCategories") or []:
                    value = str(category).strip()
                    if value and value not in categories:
                        categories.append(value)
                documents = [item for item in payload.get("documents") or [] if isinstance(item, dict) and str(item.get("url") or "").startswith(("/media/", "http://", "https://"))][:8]
                if not 2 <= len(legal_name) <= 80 or not re.fullmatch(r"[A-Za-z0-9]{6,32}", identity_number) or not re.fullmatch(r"\d{6,20}", contact_phone) or not 5 <= len(address) <= 300 or not categories or len(categories) > 10 or any(category not in SELLER_OPERATING_CATEGORIES for category in categories) or business_type not in ("individual", "enterprise") or (business_type == "enterprise" and (not representative or not license_no)):
                    raise ValueError("请完整填写认证信息")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    if not is_seller(connection, user_id):
                        self.send_json(403, {"error": "Seller access required"})
                        return
                    pending = connection.execute("SELECT id FROM seller_verification_applications WHERE seller_user_id = ? AND status = 'pending'", (user_id,)).fetchone()
                    if pending:
                        application_id = pending[0]
                        connection.execute("UPDATE seller_verification_applications SET legal_name = ?, identity_number = ?, contact_phone = ?, evidence_json = ?, business_type = ?, legal_representative = ?, business_license_no = ?, business_address = ?, reviewer_user_id = NULL, review_note = NULL, rejection_code = NULL, expires_at = NULL, supplement_requested_at = NULL, supplement_due_at = NULL, reviewed_at = NULL WHERE id = ?", (legal_name, identity_number, contact_phone, json.dumps(evidence, ensure_ascii=False), business_type, representative or None, license_no or None, address or None, application_id))
                        connection.execute("DELETE FROM seller_verification_documents WHERE application_id = ?", (application_id,))
                    else:
                        application_id = f"verification-{secrets.token_urlsafe(10)}"
                        prior = connection.execute("SELECT id, review_round FROM seller_verification_applications WHERE seller_user_id = ? AND status = 'rejected' AND COALESCE(rejection_code, '') != 'seller_withdrew' ORDER BY reviewed_at DESC LIMIT 1", (user_id,)).fetchone()
                        review_round = int(prior["review_round"] or 1) + 1 if prior else 1
                        connection.execute("INSERT INTO seller_verification_applications (id, seller_user_id, legal_name, identity_number, contact_phone, evidence_json, business_type, legal_representative, business_license_no, business_address, resubmission_of, review_round) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (application_id, user_id, legal_name, identity_number, contact_phone, json.dumps(evidence, ensure_ascii=False), business_type, representative or None, license_no or None, address or None, prior["id"] if prior else None, review_round))
                    for document in documents:
                        document_type = str(document.get("type") or "other")
                        connection.execute("INSERT INTO seller_verification_documents (id, application_id, document_type, file_url) VALUES (?, ?, ?, ?)", (f"verification-document-{secrets.token_urlsafe(8)}", application_id, document_type if document_type in ("identity_front", "identity_back", "business_license", "authorization", "other") else "other", str(document["url"])))
                    verification_status = "approved" if AUTO_APPROVE_SELLER_VERIFICATION else "pending"
                    connection.execute("INSERT INTO seller_profiles (user_id, verification_status, legal_name, identity_number, contact_phone, business_address, operating_categories_json) VALUES (?, ?, ?, ?, ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET verification_status = excluded.verification_status, legal_name = excluded.legal_name, identity_number = excluded.identity_number, contact_phone = excluded.contact_phone, business_address = excluded.business_address, operating_categories_json = excluded.operating_categories_json", (user_id, verification_status, legal_name, identity_number, contact_phone, address, json.dumps(categories, ensure_ascii=False)))
                    if AUTO_APPROVE_SELLER_VERIFICATION:
                        connection.execute("UPDATE seller_verification_applications SET status = 'approved', review_note = '测试环境：资料格式校验通过，已自动认证', reviewed_at = CURRENT_TIMESTAMP WHERE id = ?", (application_id,))
                        connection.execute("UPDATE seller_verification_documents SET status = 'accepted' WHERE application_id = ?", (application_id,))
                    link_media_assets(connection, evidence, "seller_verification", application_id)
                    write_platform_audit(connection, user_id, "seller_verification_submitted", "seller_verification", application_id)
                self.send_json(201, {"id": application_id, "status": "approved" if AUTO_APPROVE_SELLER_VERIFICATION else "submitted"})
            elif self.path == "/api/seller/staff":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                shop_id, member_id, role = str(payload.get("shopId") or "").strip(), str(payload.get("userId") or "").strip(), str(payload.get("role") or "")
                custom = [str(item) for item in payload.get("permissions") or [] if str(item) in SHOP_STAFF_CUSTOM_PERMISSIONS]
                if role not in SHOP_STAFF_ROLE_PERMISSIONS or not shop_id or not member_id:
                    raise ValueError("成员信息无效")
                with database() as connection:
                    require_shop_owner(connection, user_id, shop_id)
                    if not connection.execute("SELECT 1 FROM users WHERE id = ? AND status = 'active'", (member_id,)).fetchone():
                        raise ValueError("成员账号不存在或已停用")
                    staff_id = f"staff-{secrets.token_urlsafe(10)}"
                    connection.execute("INSERT INTO shop_staff (id, shop_id, user_id, role, permissions_json, invited_by_user_id) VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(shop_id, user_id) DO UPDATE SET role = excluded.role, permissions_json = excluded.permissions_json, status = 'active', updated_at = CURRENT_TIMESTAMP", (staff_id, shop_id, member_id, role, json.dumps(custom, ensure_ascii=False), user_id))
                    connection.execute("INSERT OR IGNORE INTO user_roles (user_id, role) VALUES (?, 'seller')", (member_id,))
                    write_shop_staff_audit(connection, shop_id, member_id, user_id, "member_saved", {"role": role, "permissions": custom})
                    write_platform_audit(connection, user_id, "shop_staff_saved", "shop", shop_id, {"memberId": member_id, "role": role})
                self.send_json(201, {"ok": True})
            elif self.path == "/api/notifications/read":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                ids = [str(item) for item in payload.get("ids") or []]
                with database() as connection:
                    if ids: connection.execute(f"UPDATE governance_notifications SET read_at = CURRENT_TIMESTAMP WHERE user_id = ? AND id IN ({','.join('?' for _ in ids)})", (user_id, *ids))
                    else: connection.execute("UPDATE governance_notifications SET read_at = CURRENT_TIMESTAMP WHERE user_id = ? AND read_at IS NULL", (user_id,))
                self.send_json(200, {"ok": True})
            elif self.path == "/api/checkout/quote":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                self.send_json(200, {"quote": checkout_quote(user_id, payload)})
            elif self.path == "/api/addresses":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                recipient = str(payload.get("recipient") or "").strip()
                phone = str(payload.get("phone") or "").strip()
                province = str(payload.get("province") or "").strip()
                city = str(payload.get("city") or "").strip()
                district = str(payload.get("district") or "").strip()
                detail = str(payload.get("detail") or "").strip()
                country_code = str(payload.get("countryCode") or "").strip().upper()
                if country_code not in SHIPPING_COUNTRIES:
                    raise ValueError("请选择平台当前支持配送的国家或地区")
                if not all((recipient, phone, province, city, district, detail)):
                    raise ValueError("请完整填写收货地址")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    existing_count = connection.execute("SELECT COUNT(*) FROM buyer_addresses WHERE buyer_user_id = ?", (user_id,)).fetchone()[0]
                    make_default = bool(payload.get("isDefault")) or existing_count == 0
                    if make_default:
                        connection.execute("UPDATE buyer_addresses SET is_default = 0 WHERE buyer_user_id = ?", (user_id,))
                    address_id = f"address-{secrets.token_urlsafe(10)}"
                    connection.execute(
                        """
                        INSERT INTO buyer_addresses (id, buyer_user_id, recipient_name, recipient_phone, province, city, district, detail, postal_code, country_code, country_name, is_default)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (address_id, user_id, recipient, phone, province, city, district, detail, str(payload.get("postalCode") or "").strip() or None, country_code, SHIPPING_COUNTRIES[country_code], int(make_default)),
                    )
                    row = connection.execute("SELECT * FROM buyer_addresses WHERE id = ?", (address_id,)).fetchone()
                self.send_json(201, {"address": address_for_response(row)})
            elif self.path.startswith("/api/orders/") and self.path.endswith("/payment-confirm"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                order_no = self.path.removeprefix("/api/orders/").removesuffix("/payment-confirm").rstrip("/")
                payment_token = str(payload.get("paymentToken") or "")
                if not payment_token:
                    raise ValueError("支付确认令牌缺失")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    expire_pending_orders(connection)
                    order = connection.execute("SELECT * FROM orders WHERE order_no = ? AND buyer_user_id = ?", (order_no, user_id)).fetchone()
                    if not order:
                        raise ValueError("无权操作该订单")
                    payment = connection.execute("SELECT * FROM payment_transactions WHERE order_id = ?", (order["id"],)).fetchone()
                    if not payment or payment["payment_token"] != payment_token:
                        raise ValueError("支付确认令牌无效")
                    if payment["status"] == "succeeded":
                        self.send_json(200, {"orders": orders_for_response(connection, "id = ?", (order["id"],))})
                        return
                    if order["status"] != "pending_payment" or payment["status"] != "pending":
                        raise ValueError("该支付单当前不可确认")
                    reference = f"PAY{datetime.now().strftime('%y%m%d%H%M%S')}{secrets.randbelow(9000) + 1000}"
                    connection.execute("UPDATE payment_transactions SET status = 'succeeded', provider_reference = ?, paid_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE order_id = ?", (reference, order["id"]))
                    connection.execute("UPDATE orders SET status = 'pending_fulfillment', paid_at = CURRENT_TIMESTAMP, expires_at = NULL, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (order["id"],))
                    create_order_settlement(connection, order["id"])
                    set_campaign_redemption_status(connection, order["id"], "redeemed")
                    set_activity_allocation_status(connection, order["id"], "redeemed")
                    campaign = connection.execute("SELECT campaign_id FROM platform_campaign_redemptions WHERE order_id = ?", (order["id"],)).fetchone()
                    record_analytics_event(connection, "order_paid", user_id=user_id, shop_id=order["shop_id"], campaign_id=campaign[0] if campaign else None, channel=order["attribution_channel"])
                    owner = connection.execute("SELECT owner_user_id FROM shops WHERE id = ?", (order["shop_id"],)).fetchone()
                    if owner: notify_governance(connection, owner[0], "order_paid", "有新订单待发货", f"订单 {order['order_no']} 已支付", "order", order["order_no"])
                    self.send_json(200, {"orders": orders_for_response(connection, "id = ?", (order["id"],))})
            elif self.path.startswith("/api/orders/") and self.path.endswith("/pay"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                order_no = self.path.removeprefix("/api/orders/").removesuffix("/pay").rstrip("/")
                payment_method = str(payload.get("paymentMethod") or "")
                if payment_method not in ("alipay", "card"):
                    raise ValueError("请选择支付方式")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    expire_pending_orders(connection)
                    order = connection.execute("SELECT * FROM orders WHERE order_no = ? AND buyer_user_id = ?", (order_no, user_id)).fetchone()
                    if not order or order["status"] != "pending_payment":
                        raise ValueError("该订单当前不能支付")
                    payment = connection.execute("SELECT * FROM payment_transactions WHERE order_id = ?", (order["id"],)).fetchone()
                    if not payment or payment["status"] != "pending":
                        raise ValueError("该支付单当前不可用")
                    connection.execute("UPDATE payment_transactions SET payment_method = ?, initiated_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE order_id = ?", (payment_method, order["id"]))
                    self.send_json(200, {
                        "orders": orders_for_response(connection, "id = ?", (order["id"],)),
                        "payment": {"token": payment["payment_token"], "method": payment_method, "amount": payment["amount_cents"] / 100},
                    })
            elif self.path.startswith("/api/orders/") and self.path.endswith("/ship"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                order_no = self.path.removeprefix("/api/orders/").removesuffix("/ship").rstrip("/")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    order = seller_can_manage_order(connection, user_id, order_no)
                    if order["status"] != "pending_fulfillment":
                        raise ValueError("该订单当前不能发货")
                    carrier = str(payload.get("carrier") or "").strip()
                    tracking_no = str(payload.get("trackingNo") or "").strip()
                    if not carrier or not tracking_no:
                        raise ValueError("请填写快递公司和运单号")
                    shipment_id = f"shipment-{secrets.token_urlsafe(10)}"
                    logistics_provider = logistics_provider_for_carrier(carrier)
                    connection.execute("UPDATE orders SET status = 'shipped', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (order["id"],))
                    connection.execute("INSERT INTO shipments (id, order_id, carrier, tracking_no, logistics_provider, provider_tracking_id, status) VALUES (?, ?, ?, ?, ?, ?, 'in_transit')", (shipment_id, order["id"], carrier, tracking_no, logistics_provider, tracking_no))
                    connection.execute("INSERT INTO shipment_events (id, shipment_id, event_at, label, detail) VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?)", (f"event-{secrets.token_urlsafe(8)}", shipment_id, "卖家已发货", f"{carrier} 已揽收"))
                    notify_governance(connection, order["buyer_user_id"], "order_shipped", "订单已发货", f"订单 {order['order_no']} 已由 {carrier} 发出", "order", order["order_no"])
                    self.send_json(200, {"orders": orders_for_response(connection, "id = ?", (order["id"],))})
            elif self.path.startswith("/api/orders/") and self.path.endswith("/shipment-events"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                order_no = self.path.removeprefix("/api/orders/").removesuffix("/shipment-events").rstrip("/")
                label = str(payload.get("label") or "").strip()
                detail = str(payload.get("detail") or "").strip()
                if not label:
                    raise ValueError("请填写物流节点")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    order = seller_can_manage_order(connection, user_id, order_no)
                    shipment = connection.execute("SELECT * FROM shipments WHERE order_id = ?", (order["id"],)).fetchone()
                    if not shipment or order["status"] not in ("shipped", "delivered"):
                        raise ValueError("该订单尚未发货")
                    connection.execute("INSERT INTO shipment_events (id, shipment_id, event_at, label, detail) VALUES (?, ?, CURRENT_TIMESTAMP, ?, ?)", (f"event-{secrets.token_urlsafe(8)}", shipment["id"], label, detail))
                    if re.search(r"异常|滞留|延误|退回|拒收|丢件", f"{label} {detail}"):
                        buyer_phone = connection.execute("SELECT phone FROM users WHERE id = ?", (order["buyer_user_id"],)).fetchone()
                        if buyer_phone:
                            enqueue_tencent_sms_notification(buyer_phone[0], "logistics_alert")
                    self.send_json(200, {"orders": orders_for_response(connection, "id = ?", (order["id"],))})
            elif self.path.startswith("/api/orders/") and self.path.endswith("/receive"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                order_no = self.path.removeprefix("/api/orders/").removesuffix("/receive").rstrip("/")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    order = connection.execute("SELECT * FROM orders WHERE order_no = ? AND buyer_user_id = ?", (order_no, user_id)).fetchone()
                    if not order:
                        raise ValueError("无权操作该订单")
                    if order["status"] == "completed":
                        self.send_json(200, {"orders": orders_for_response(connection, "id = ?", (order["id"],))})
                        return
                    if order["status"] not in ("shipped", "delivered"):
                        raise ValueError("该订单尚未发货")
                    completed = complete_order_and_start_settlement_hold(connection, order["id"])
                    owner = connection.execute("SELECT owner_user_id FROM shops WHERE id = ?", (order["shop_id"],)).fetchone()
                    if completed:
                        if owner: notify_governance(connection, owner[0], "order_completed", "订单已完成", f"订单 {order['order_no']} 已确认收货", "order", order["order_no"])
                        notify_governance(connection, order["buyer_user_id"], "review_reminder", "订单已完成，等待评价", "分享你的使用感受，帮助更多手作爱好者", "order", order["order_no"])
                    self.send_json(200, {"orders": orders_for_response(connection, "id = ?", (order["id"],))})
            elif self.path.startswith("/api/orders/") and self.path.endswith("/cancel"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                order_no = self.path.removeprefix("/api/orders/").removesuffix("/cancel").rstrip("/")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    order = connection.execute("SELECT * FROM orders WHERE order_no = ? AND buyer_user_id = ?", (order_no, user_id)).fetchone()
                    if not order:
                        raise ValueError("无权操作该订单")
                    if order["status"] != "pending_payment":
                        raise ValueError("该订单当前不能取消")
                    restore_order_inventory(connection, order["id"], status="released")
                    connection.execute("UPDATE orders SET status = 'cancelled', cancelled_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (order["id"],))
                    set_campaign_redemption_status(connection, order["id"], "released")
                    set_activity_allocation_status(connection, order["id"], "released")
                    if order["status"] == "pending_payment":
                        connection.execute("UPDATE payment_transactions SET status = 'cancelled', updated_at = CURRENT_TIMESTAMP WHERE order_id = ? AND status = 'pending'", (order["id"],))
                    self.send_json(200, {"orders": orders_for_response(connection, "id = ?", (order["id"],))})
            elif self.path.startswith("/api/orders/") and self.path.endswith("/after-sales"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                order_no = self.path.removeprefix("/api/orders/").removesuffix("/after-sales").rstrip("/")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    order = connection.execute("SELECT * FROM orders WHERE order_no = ? AND buyer_user_id = ?", (order_no, user_id)).fetchone()
                    if not order:
                        raise ValueError("无权操作该订单")
                    if order["status"] in ("cancelled", "refunded"):
                        raise ValueError("该订单不能申请售后")
                    item = connection.execute("SELECT id FROM order_items WHERE order_id = ? LIMIT 1", (order["id"],)).fetchone()
                    request_id = f"after-sale-{secrets.token_urlsafe(10)}"
                    request_type = payload.get("type") if payload.get("type") in ("refund", "return_refund") else "refund"
                    amount = min(order["paid_amount_cents"], max(1, int(round(number(payload.get("amount")) * 100))))
                    evidence = [str(image) for image in payload.get("evidence") or [] if str(image).startswith("data:image/")][:6]
                    connection.execute(
                        """
                        INSERT INTO after_sale_requests (id, order_id, order_item_id, buyer_user_id, request_type, reason, requested_amount_cents, refund_currency, refund_exchange_rate, order_status_before)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (request_id, order["id"], item["id"] if item else None, user_id, request_type, str(payload.get("reason") or "七天无理由退款"), amount, order["payment_currency"], order["payment_exchange_rate"], order["status"]),
                    )
                    connection.executemany(
                        "INSERT INTO after_sale_evidence (id, after_sale_id, image_url, sort_order, content_hash, byte_size) VALUES (?, ?, ?, ?, ?, ?)",
                        [
                            (f"evidence-{secrets.token_urlsafe(8)}", request_id, image, index, hashlib.sha256(image.encode("utf-8")).hexdigest(), len(image.encode("utf-8")))
                            for index, image in enumerate(evidence)
                        ],
                    )
                    write_after_sale_case_event(
                        connection, request_id, "buyer_submitted", actor_user_id=user_id,
                        detail={"type": request_type, "amountCents": amount, "reason": str(payload.get("reason") or "")[:500]}, evidence=evidence,
                    )
                    recent_requests = connection.execute(
                        "SELECT COUNT(*) FROM after_sale_requests WHERE buyer_user_id = ? AND created_at >= datetime('now', '-90 days')",
                        (user_id,),
                    ).fetchone()[0]
                    if recent_requests >= 3:
                        record_risk_case(connection, "refund_dispute", "medium", "repeated_after_sale_requests", subject_user_id=user_id, order_id=order["id"], detail={"requests90d": recent_requests})
                    connection.execute("UPDATE orders SET status = 'refunding', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (order["id"],))
                    owner = connection.execute("SELECT owner_user_id FROM shops WHERE id = ?", (order["shop_id"],)).fetchone()
                    if owner: notify_governance(connection, owner[0], "after_sale", "收到售后申请", f"订单 {order['order_no']} 需要处理", "after_sale", request_id)
                    self.send_json(201, {"afterSales": after_sales_for_response(connection, "after_sale_requests.id = ?", (request_id,))})
            elif self.path.startswith("/api/after-sales/") and self.path.endswith("/return-shipment"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                request_id = self.path.removeprefix("/api/after-sales/").removesuffix("/return-shipment").rstrip("/")
                carrier = str(payload.get("carrier") or "").strip()
                tracking_no = str(payload.get("trackingNo") or "").strip()
                if not carrier or not tracking_no:
                    raise ValueError("请填写退货快递公司和运单号")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    request = connection.execute("SELECT * FROM after_sale_requests WHERE id = ? AND buyer_user_id = ?", (request_id, user_id)).fetchone()
                    if not request or request["request_type"] != "return_refund":
                        raise ValueError("无权提交该退货信息")
                    if request["status"] != "approved" or request["returned_at"]:
                        raise ValueError("该售后当前不能提交退货物流")
                    connection.execute("UPDATE after_sale_requests SET return_carrier = ?, return_tracking_no = ?, returned_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (carrier, tracking_no, request_id))
                    write_after_sale_case_event(connection, request_id, "buyer_return_shipment_submitted", actor_user_id=user_id, detail={"carrier": carrier, "trackingNo": tracking_no})
                    order = connection.execute("SELECT shop_id, order_no FROM orders WHERE id = ?", (request["order_id"],)).fetchone()
                    owner = connection.execute("SELECT owner_user_id FROM shops WHERE id = ?", (order["shop_id"],)).fetchone()
                    if owner: notify_governance(connection, owner[0], "return_shipment", "买家已寄回作品", f"订单 {order['order_no']} 的退货物流已提交", "after_sale", request_id)
                    self.send_json(200, {"afterSales": after_sales_for_response(connection, "after_sale_requests.id = ?", (request_id,))})
            elif self.path.startswith("/api/after-sales/") and self.path.endswith("/receive-return"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                request_id = self.path.removeprefix("/api/after-sales/").removesuffix("/receive-return").rstrip("/")
                response_text = str(payload.get("response") or "已确认收到退回作品，退款已完成").strip()
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    shop_ids = seller_accessible_shop_ids(connection, user_id, "after_sales")
                    if not shop_ids:
                        raise ValueError("当前账号没有店铺")
                    placeholders = ",".join("?" for _ in shop_ids)
                    request = connection.execute(f"SELECT after_sale_requests.* FROM after_sale_requests JOIN orders ON orders.id = after_sale_requests.order_id WHERE after_sale_requests.id = ? AND orders.shop_id IN ({placeholders})", (request_id, *shop_ids)).fetchone()
                    if not request or request["request_type"] != "return_refund" or request["status"] != "approved" or not request["returned_at"]:
                        raise ValueError("该售后当前不能确认收货")
                    connection.execute("UPDATE after_sale_requests SET status = 'completed', seller_response = ?, received_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (response_text, request_id))
                    write_after_sale_case_event(connection, request_id, "seller_received_return", actor_user_id=user_id, detail={"response": response_text[:1000]})
                    refund = record_after_sale_refund(connection, request_id)
                    if refund["fullyRefunded"]:
                        restore_order_inventory(connection, request["order_id"], status="reversed")
                        connection.execute("UPDATE orders SET status = 'refunded', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (request["order_id"],))
                        set_campaign_redemption_status(connection, request["order_id"], "reversed")
                        set_activity_allocation_status(connection, request["order_id"], "reversed")
                    else:
                        connection.execute("UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (request["order_status_before"] or "completed", request["order_id"]))
                    notify_governance(connection, request["buyer_user_id"], "refund_completed", "退款已完成", response_text, "after_sale", request_id)
                    self.send_json(200, {"afterSales": after_sales_for_response(connection, "after_sale_requests.id = ?", (request_id,))})
            elif self.path.startswith("/api/after-sales/") and self.path.endswith(("/approve", "/reject")):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                action = "approve" if self.path.endswith("/approve") else "reject"
                request_id = self.path.removeprefix("/api/after-sales/").removesuffix(f"/{action}")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    shop_ids = seller_accessible_shop_ids(connection, user_id, "after_sales")
                    if not shop_ids:
                        raise ValueError("当前账号没有店铺")
                    placeholders = ",".join("?" for _ in shop_ids)
                    request = connection.execute(
                        f"""
                        SELECT after_sale_requests.* FROM after_sale_requests
                        JOIN orders ON orders.id = after_sale_requests.order_id
                        WHERE after_sale_requests.id = ? AND orders.shop_id IN ({placeholders})
                        """,
                        (request_id, *shop_ids),
                    ).fetchone()
                    if not request:
                        raise ValueError("无权处理该售后申请")
                    if request["status"] != "pending":
                        raise ValueError("该售后申请已处理")
                    response_text = str(payload.get("response") or ("已同意退款" if action == "approve" else "已拒绝退款")).strip()
                    if action == "reject":
                        connection.execute("UPDATE after_sale_requests SET status = 'rejected', seller_response = ?, seller_processed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (response_text, request_id))
                        connection.execute("UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (request["order_status_before"] or "completed", request["order_id"]))
                    elif request["request_type"] == "return_refund":
                        connection.execute("UPDATE after_sale_requests SET status = 'approved', seller_response = ?, seller_processed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (response_text, request_id))
                    else:
                        connection.execute("UPDATE after_sale_requests SET status = 'completed', seller_response = ?, seller_processed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (response_text, request_id))
                        refund = record_after_sale_refund(connection, request_id)
                        if refund["fullyRefunded"]:
                            connection.execute("UPDATE orders SET status = 'refunded', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (request["order_id"],))
                            set_campaign_redemption_status(connection, request["order_id"], "reversed")
                            set_activity_allocation_status(connection, request["order_id"], "reversed")
                        else:
                            connection.execute("UPDATE orders SET status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (request["order_status_before"] or "completed", request["order_id"]))
                    write_after_sale_case_event(connection, request_id, f"seller_{action}", actor_user_id=user_id, detail={"response": response_text[:1000], "requestType": request["request_type"]})
                    notify_governance(connection, request["buyer_user_id"], "after_sale_result", "售后申请处理结果", response_text, "after_sale", request_id)
                    self.send_json(200, {"afterSales": after_sales_for_response(connection, "after_sale_requests.id = ?", (request_id,))})
            elif self.path.startswith("/api/orders/") and self.path.endswith("/review"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                order_no = self.path.removeprefix("/api/orders/").removesuffix("/review").rstrip("/")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    order = connection.execute("SELECT * FROM orders WHERE order_no = ? AND buyer_user_id = ?", (order_no, user_id)).fetchone()
                    if not order or order["status"] != "completed":
                        raise ValueError("该订单暂不能评价")
                    content = str(payload.get("content") or "").strip()
                    if not content:
                        raise ValueError("评价内容不能为空")
                    rating = max(1, min(5, int(payload.get("rating") or 5)))
                    items = connection.execute("SELECT id FROM order_items WHERE order_id = ?", (order["id"],)).fetchall()
                    images = [str(image) for image in payload.get("images") or [] if str(image).startswith("data:image/")][:6]
                    for item in items:
                        review_id = f"review-{secrets.token_urlsafe(10)}"
                        connection.execute(
                            "INSERT OR IGNORE INTO reviews (id, order_item_id, buyer_user_id, shop_id, rating, content) VALUES (?, ?, ?, ?, ?, ?)",
                            (review_id, item["id"], user_id, order["shop_id"], rating, content),
                        )
                        connection.executemany("INSERT OR IGNORE INTO review_images (id, review_id, image_url, sort_order) VALUES (?, ?, ?, ?)", [(f"review-image-{secrets.token_urlsafe(8)}", review_id, image, index) for index, image in enumerate(images)])
                    self.send_json(201, {"orders": orders_for_response(connection, "id = ?", (order["id"],))})
            elif self.path.startswith("/api/reviews/") and self.path.endswith("/reply"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                review_id = self.path.removeprefix("/api/reviews/").removesuffix("/reply").rstrip("/")
                reply = str(payload.get("reply") or "").strip()
                if not reply:
                    raise ValueError("回复内容不能为空")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    shop_ids = seller_accessible_shop_ids(connection, user_id, "reviews")
                    if not shop_ids:
                        raise ValueError("当前账号没有店铺")
                    placeholders = ",".join("?" for _ in shop_ids)
                    review = connection.execute(f"SELECT * FROM reviews WHERE id = ? AND shop_id IN ({placeholders})", (review_id, *shop_ids)).fetchone()
                    if not review:
                        raise ValueError("无权回复该评价")
                    connection.execute("UPDATE reviews SET seller_reply = ?, replied_at = CURRENT_TIMESTAMP WHERE id = ?", (reply, review_id))
                    self.send_json(200, {"reviews": reviews_for_response(connection, "reviews.id = ?", (review_id,))})
            elif self.path.startswith("/api/reviews/") and self.path.endswith("/followup"):
                user_id = session_user(self)
                review_id = self.path.removeprefix("/api/reviews/").removesuffix("/followup").rstrip("/")
                content = str(payload.get("content") or "").strip()
                if not user_id or not content:
                    raise ValueError("追评内容不能为空")
                with database() as connection:
                    review = connection.execute("SELECT id FROM reviews WHERE id = ? AND buyer_user_id = ?", (review_id, user_id)).fetchone()
                    if not review: raise ValueError("无权追评")
                    connection.execute("INSERT INTO review_followups (id, review_id, content) VALUES (?, ?, ?) ON CONFLICT(review_id) DO UPDATE SET content = excluded.content, created_at = CURRENT_TIMESTAMP", (f"followup-{secrets.token_urlsafe(8)}", review_id, content))
                    self.send_json(200, {"ok": True})
            elif self.path == "/api/sellers/sync":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                with database() as connection:
                    if not is_seller(connection, user_id):
                        self.send_json(403, {"error": "Seller access required"})
                        return
                self.send_json(200, migrate(payload, user_id))
            elif self.path == "/api/migrations/legacy-seller":
                self.send_json(200, migrate(payload))
            elif self.path.startswith("/api/analytics/shops/") and self.path.endswith("/visits"):
                shop_id = self.path.removeprefix("/api/analytics/shops/").removesuffix("/visits")
                self.send_json(200, {"visitors": record_shop_visit(shop_id, str(payload.get("visitorKey") or ""))})
            elif self.path == "/api/migrations/legacy-accounts":
                self.send_json(200, migrate_legacy_accounts(payload))
            elif self.path == "/api/auth/logout":
                token = next((part.strip().split("=", 1)[1] for part in self.headers.get("Cookie", "").split(";") if part.strip().startswith("handicrafts_session=")), None)
                if token:
                    with database() as connection:
                        connection.execute("DELETE FROM admin_step_up_tickets WHERE session_token_hash = ?", (token_hash(token),))
                        connection.execute("DELETE FROM web_sessions WHERE token = ?", (token,))
                self.send_json(200, {"ok": True}, "handicrafts_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax")
            elif self.path == "/api/auth/delete-account":
                user_id = session_user(self)
                password = str(payload.get("currentPassword") or "")
                confirmation = str(payload.get("confirmation") or "").strip()
                reason = str(payload.get("reason") or "").strip()
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                if confirmation not in ("注销账号", "CLOSE ACCOUNT"):
                    raise ValueError("请输入“注销账号”或 “CLOSE ACCOUNT” 确认操作")
                if len(reason) > 300:
                    raise ValueError("注销原因不能超过 300 个字符")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    user = connection.execute("SELECT password_hash FROM users WHERE id = ? AND status = 'active'", (user_id,)).fetchone()
                    valid, _ = verify_password(password, user["password_hash"] if user else "")
                    if not valid:
                        raise ValueError("当前密码不正确")
                    if is_admin(connection, user_id):
                        raise ValueError("管理员账号不能自行注销")
                    active_orders = connection.execute(
                        """
                        SELECT COUNT(*) FROM orders
                        WHERE (buyer_user_id = ? OR shop_id IN (SELECT id FROM shops WHERE owner_user_id = ?))
                          AND status IN ('pending_payment', 'pending_fulfillment', 'shipped', 'delivered', 'refunding')
                        """,
                        (user_id, user_id),
                    ).fetchone()[0]
                    active_after_sales = connection.execute(
                        """
                        SELECT COUNT(*) FROM after_sale_requests
                        JOIN orders ON orders.id = after_sale_requests.order_id
                        WHERE (after_sale_requests.buyer_user_id = ? OR orders.shop_id IN (SELECT id FROM shops WHERE owner_user_id = ?))
                          AND after_sale_requests.status IN ('pending', 'approved')
                        """,
                        (user_id, user_id),
                    ).fetchone()[0]
                    if active_orders or active_after_sales:
                        raise ValueError("存在进行中的订单或售后，暂时不能注销账号")
                    connection.execute("INSERT INTO account_deletions (id, user_id, reason) VALUES (?, ?, ?)", (f"account-deletion-{secrets.token_urlsafe(10)}", user_id, reason))
                    connection.execute("UPDATE shops SET status = 'closed', updated_at = CURRENT_TIMESTAMP WHERE owner_user_id = ?", (user_id,))
                    connection.execute("UPDATE products SET status = 'unlisted', updated_at = CURRENT_TIMESTAMP WHERE shop_id IN (SELECT id FROM shops WHERE owner_user_id = ?) AND status != 'archived'", (user_id,))
                    connection.execute("DELETE FROM buyer_addresses WHERE buyer_user_id = ?", (user_id,))
                    connection.execute("DELETE FROM verification_tokens WHERE user_id = ?", (user_id,))
                    connection.execute("UPDATE user_profiles SET bio = '', updated_at = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,))
                    connection.execute(
                        "UPDATE users SET display_name = '已注销用户', phone = NULL, email = ?, password_hash = ?, phone_verified_at = NULL, email_verified_at = NULL, status = 'disabled', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (f"deleted-{user_id}@invalid.local", hash_password(secrets.token_urlsafe(32)), user_id),
                    )
                    connection.execute("DELETE FROM web_sessions WHERE user_id = ?", (user_id,))
                    write_platform_audit(connection, user_id, "account_deleted", "user", user_id, {"reason": reason})
                self.send_json(200, {"ok": True}, "handicrafts_session=; Path=/; Max-Age=0; HttpOnly; SameSite=Lax")
            elif self.path == "/api/auth/login":
                identifier = (payload.get("identifier") or "").lower()
                password = payload.get("password") or ""
                identifier_subject = f"login:{hashlib.sha256(identifier.encode('utf-8')).hexdigest()[:24]}"
                if not self.enforce_rate_limit(
                    "login", identifier_subject, per_ip=30, per_user=10, window_seconds=600
                ):
                    return
                visitor_ip = client_ip(self)
                if not login_allowed(visitor_ip):
                    self.send_json(
                        429,
                        {"error": "登录失败次数过多，请 10 分钟后再试", "retryAfter": 600},
                        extra_headers={"Retry-After": "600"},
                    )
                    return
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    user = connection.execute("SELECT * FROM users WHERE status = 'active' AND (phone = ? OR lower(email) = ?)", (identifier, identifier)).fetchone()
                valid, legacy = verify_password(password, user["password_hash"]) if user else (False, False)
                if not user or not valid:
                    register_login_failure(visitor_ip)
                    with database() as connection:
                        write_login_audit(connection, identifier, False, self, user["id"] if user else None, "invalid_credentials")
                    self.send_json(401, {"error": "账号或密码不正确"})
                    return
                clear_login_failures(visitor_ip)
                if legacy:
                    with database() as connection:
                        connection.execute("UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (hash_password(password), user["id"]))
                with database() as connection:
                    connection.execute("UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?", (user["id"],))
                    write_login_audit(connection, identifier, True, self, user["id"])
                token, csrf_token = create_session(user["id"], self)
                self.send_json(200, {"account": account_for_user(user["id"])}, session_cookie(token), {"X-CSRF-Token": csrf_token})
            elif self.path == "/api/auth/request-verification":
                destination = str(payload.get("destination") or "").strip().lower()
                purpose = str(payload.get("purpose") or "")
                registration = bool(payload.get("registration"))
                if purpose not in ("contact_verify", "password_reset") or not destination:
                    raise ValueError("验证请求无效")
                authenticated_user_id = session_user(self)
                if not sms_request_allowed(self, destination, purpose):
                    raise ValueError("发送过于频繁，请 1 分钟后再试")
                with database() as connection:
                    user = connection.execute("SELECT id FROM users WHERE phone = ? OR lower(email) = ?", (destination, destination)).fetchone()
                    if purpose == "password_reset" and not user:
                        self.send_json(200, {"ok": True})
                        return
                    if purpose == "contact_verify":
                        if registration and not authenticated_user_id and (not re.fullmatch(r"1\d{10}", destination) or user):
                            raise ValueError("手机号已注册或格式无效")
                        if not authenticated_user_id and not registration:
                            self.send_json(401, {"error": "Unauthorized"})
                            return
                        if authenticated_user_id:
                            owned = connection.execute("SELECT id FROM users WHERE id = ? AND (phone = ? OR lower(email) = ?)", (authenticated_user_id, destination, destination)).fetchone()
                            if not owned:
                                raise ValueError("只能验证当前账号已绑定的联系方式")
                    code = issue_verification(connection, user[0] if user else authenticated_user_id, destination, purpose)
                    registration_test_code = REGISTRATION_TEST_MODE and registration and purpose == "contact_verify"
                    sms_sent = False if registration_test_code else deliver_verification_code(destination, purpose, code)
                response = {"ok": True}
                if registration_test_code:
                    response["testingCode"] = code
                elif not sms_sent and not PRODUCTION_HTTPS:
                    response["developmentCode"] = code
                self.send_json(200, response)
            elif self.path == "/api/auth/request-admin-step-up":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                if not sms_request_allowed(self, user_id, "admin_step_up"):
                    raise ValueError("发送过于频繁，请 1 分钟后再试")
                with database() as connection:
                    if not is_admin(connection, user_id):
                        self.send_json(403, {"error": "Administrator access required"})
                        return
                    destination = admin_verification_destination(connection, user_id)
                    code = issue_verification(connection, user_id, destination, "admin_step_up")
                    sms_sent = deliver_verification_code(destination, "admin_step_up", code)
                self.send_json(200, {"ok": True, **({"developmentCode": code} if not sms_sent and not PRODUCTION_HTTPS else {})})
            elif self.path == "/api/auth/confirm-admin-step-up":
                user_id = session_user(self)
                current_session = session_token(self)
                code = str(payload.get("code") or "").strip()
                # Older deployed admin screens do not send a scope. Treat those
                # requests as high-risk so they remain compatible without
                # weakening the fresh-verification requirement.
                scope = str(payload.get("scope") or "high_risk")
                if not user_id or not current_session:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                if scope not in ("standard", "high_risk"):
                    raise ValueError("Invalid administrator verification scope")
                with database() as connection:
                    if not is_admin(connection, user_id):
                        self.send_json(403, {"error": "Administrator access required"})
                        return
                    destination = admin_verification_destination(connection, user_id)
                    verification = consume_verification(connection, destination, "admin_step_up", code)
                    if not verification or verification["user_id"] != user_id:
                        raise ValueError("验证码无效或已过期")
                    connection.execute(
                        "UPDATE admin_step_up_tickets SET consumed_at = CURRENT_TIMESTAMP WHERE user_id = ? AND consumed_at IS NULL",
                        (user_id,),
                    )
                    ticket = secrets.token_urlsafe(32)
                    connection.execute(
                        "INSERT INTO admin_step_up_tickets (id, user_id, ticket_hash, session_token_hash, scope, expires_at) VALUES (?, ?, ?, ?, ?, datetime('now', '+1 hour'))",
                        (f"step-up-{secrets.token_urlsafe(10)}", user_id, token_hash(ticket), token_hash(current_session), scope),
                    )
                self.send_json(200, {"ticket": ticket, "expiresIn": 3600, "scope": scope})
            elif self.path == "/api/auth/reset-password":
                destination = str(payload.get("destination") or "").strip().lower()
                code, password = str(payload.get("code") or ""), str(payload.get("password") or "")
                if len(password) < 8:
                    raise ValueError("密码至少需要 8 位")
                with database() as connection:
                    verification = consume_verification(connection, destination, "password_reset", code)
                    if not verification or not verification["user_id"]:
                        raise ValueError("验证码无效或已过期")
                    connection.execute("UPDATE users SET password_hash = ?, password_changed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (hash_password(password), verification["user_id"]))
                    connection.execute("DELETE FROM web_sessions WHERE user_id = ?", (verification["user_id"],))
                    write_platform_audit(connection, verification["user_id"], "password_reset", "user", verification["user_id"])
                self.send_json(200, {"ok": True})
            elif self.path == "/api/auth/change-password":
                user_id = session_user(self)
                current_token = session_token(self)
                current_password = str(payload.get("currentPassword") or "")
                password = str(payload.get("password") or "")
                if not user_id or not current_token:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                if len(password) < 8:
                    raise ValueError("密码至少需要 8 位")
                with database() as connection:
                    row = connection.execute("SELECT password_hash FROM users WHERE id = ?", (user_id,)).fetchone()
                    valid, _ = verify_password(current_password, row[0] if row else "")
                    if not valid:
                        raise ValueError("当前密码不正确")
                    connection.execute("UPDATE users SET password_hash = ?, password_changed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (hash_password(password), user_id))
                    connection.execute("DELETE FROM web_sessions WHERE user_id = ? AND token <> ?", (user_id, current_token))
                    write_platform_audit(connection, user_id, "password_changed", "user", user_id)
                self.send_json(200, {"ok": True})
            elif self.path == "/api/auth/sessions/revoke":
                user_id = session_user(self)
                current_token = session_token(self)
                session_id = str(payload.get("sessionId") or "")
                if not user_id or not current_token:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                with database() as connection:
                    target = connection.execute("SELECT token FROM web_sessions WHERE id = ? AND user_id = ?", (session_id, user_id)).fetchone()
                    if not target:
                        raise ValueError("登录会话不存在")
                    if secrets.compare_digest(target[0], current_token):
                        raise ValueError("不能在此操作中移除当前会话")
                    connection.execute("DELETE FROM web_sessions WHERE id = ? AND user_id = ?", (session_id, user_id))
                    write_platform_audit(connection, user_id, "session_revoked", "web_session", session_id)
                self.send_json(200, {"ok": True})
            elif self.path == "/api/auth/verify-contact":
                user_id = session_user(self)
                destination, code = str(payload.get("destination") or "").strip().lower(), str(payload.get("code") or "")
                registration = bool(payload.get("registration"))
                if not user_id and not registration:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                with database() as connection:
                    verification = consume_verification(connection, destination, "contact_verify", code)
                    if not verification or (user_id and verification["user_id"] != user_id) or (registration and verification["user_id"] is not None):
                        raise ValueError("验证码无效或已过期")
                    updated = connection.execute(
                        "UPDATE users SET phone_verified_at = CASE WHEN phone = ? THEN CURRENT_TIMESTAMP ELSE phone_verified_at END, email_verified_at = CASE WHEN lower(email) = ? THEN CURRENT_TIMESTAMP ELSE email_verified_at END, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (destination, destination, user_id),
                    ).rowcount
                    if user_id and not updated:
                        raise ValueError("联系方式不属于当前账号")
                self.send_json(200, {"ok": True})
            elif self.path == "/api/auth/register":
                # A timestamp can collide when a browser retries a request in
                # the same millisecond. Registration IDs must be independent
                # of request timing.
                user_id = f"user-{secrets.token_urlsafe(12)}"
                name = (payload.get("name") or "").strip()
                phone = (payload.get("phone") or "").strip() or None
                email = (payload.get("email") or "").strip().lower() or None
                contact = phone or email
                contact_subject = (
                    f"registration:{hashlib.sha256(contact.encode('utf-8')).hexdigest()[:24]}"
                    if contact
                    else None
                )
                if not self.enforce_rate_limit(
                    "registration", contact_subject, per_ip=12, per_user=3, window_seconds=3600
                ):
                    return
                password = payload.get("password") or ""
                confirm_password = payload.get("confirmPassword") or ""
                phone_verification_code = str(payload.get("phoneVerificationCode") or "").strip()
                role = payload.get("role") if payload.get("role") in ("buyer", "seller") else "buyer"
                if not name or not password:
                    raise ValueError("请填写昵称、密码和至少一种登录账号")
                if role == "seller" and not phone:
                    raise ValueError("店主注册请填写手机号")
                if role != "seller" and not (phone or email):
                    raise ValueError("请填写至少一种登录账号")
                if phone and (len(phone) != 11 or not phone.startswith("1") or not phone.isdigit()):
                    raise ValueError("请输入正确的 11 位手机号")
                if len(password) < 8:
                    raise ValueError("密码至少需要 8 位")
                if password != confirm_password:
                    raise ValueError("两次输入的密码不一致")
                if role == "seller":
                    if not phone_verification_code:
                        raise ValueError("请先完成手机号验证")
                with database() as connection:
                    # Check before consuming a seller verification code. A retry
                    # with an existing contact should guide the user to login,
                    # rather than spending a valid one-time code and returning a
                    # database-level error in English.
                    if phone and connection.execute("SELECT 1 FROM users WHERE phone = ?", (phone,)).fetchone():
                        raise ValueError("该手机号已注册，请直接登录或更换手机号")
                    if email and connection.execute("SELECT 1 FROM users WHERE lower(email) = ?", (email,)).fetchone():
                        raise ValueError("该邮箱已注册，请直接登录或更换邮箱")
                    if role == "seller":
                        verification = consume_verification(connection, phone, "contact_verify", phone_verification_code)
                        if not verification or verification["user_id"] is not None:
                            raise ValueError("手机号验证码无效或已过期")
                    connection.execute("INSERT INTO users (id, display_name, phone, email, password_hash) VALUES (?, ?, ?, ?, ?)", (user_id, name, phone, email, hash_password(password)))
                    connection.execute("INSERT INTO user_roles (user_id, role) VALUES (?, ?)", (user_id, role))
                    if role == "seller":
                        connection.execute("INSERT INTO seller_profiles (user_id, verification_status, contact_phone, payout_provider, payout_binding_status) VALUES (?, 'pending', ?, 'lianlian', 'unbound')", (user_id, phone))
                if role == "seller":
                    enqueue_tencent_sms_notification(phone, "seller_accepted")
                token, csrf_token = create_session(user_id, self)
                self.send_json(201, {"account": account_for_user(user_id)}, session_cookie(token), {"X-CSRF-Token": csrf_token})
            else:
                self.send_json(404, {"error": "Not found"})
        except StepUpRequiredError:
            self.send_json(403, {"error": "请先完成管理员二次验证"})
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})
        except sqlite3.IntegrityError as error:
            if self.path == "/api/auth/register":
                detail = str(error).lower()
                if "users.phone" in detail:
                    message = "该手机号已注册，请直接登录或更换手机号"
                elif "users.email" in detail:
                    message = "该邮箱已注册，请直接登录或更换邮箱"
                else:
                    print(f"Registration data conflict: {error}")
                    message = "注册信息保存冲突，请重新获取验证码后再试"
                self.send_json(409, {"error": message})
            else:
                self.send_json(409, {"error": "Data integrity error" if PRODUCTION_HTTPS else f"Data integrity error: {error}"})
        except Exception as error:
            print(f"Unhandled API error on {self.path}: {error}")
            self.send_json(500, {"error": "Internal server error" if PRODUCTION_HTTPS else str(error)})

    def do_PUT(self) -> None:
        if not self.enforce_state_change_protection():
            return
        request_length = self.request_body_length()
        if request_length is None:
            return
        if self.path.startswith("/api/admin/community/posts/"):
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            try:
                require_admin(user_id)
                length = request_length
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                post_id = self.path.removeprefix("/api/admin/community/posts/").rstrip("/")
                title = re.sub(r"\s+", " ", str(payload.get("title") or "").strip())
                content = str(payload.get("content") or "").strip()
                image_url = str(payload.get("imageUrl") or "").strip()
                if not post_id or not 2 <= len(title) <= 80 or not 2 <= len(content) <= 2000:
                    raise ValueError("帖子标题或正文长度无效")
                if image_url and not image_url.startswith(("/media/", "http://", "https://")):
                    raise ValueError("帖子图片地址无效")
                if next((word for word in SENSITIVE_CONTENT_WORDS if word in f"{title}\n{content}"), None):
                    raise ValueError("内容包含不允许发布的词语")
                with database() as connection:
                    updated = connection.execute(
                        "UPDATE community_posts SET title = ?, content = ?, attachment_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'published'",
                        (title, content, image_url, post_id),
                    ).rowcount
                    if not updated:
                        raise ValueError("帖子不存在或已处理")
                    connection.execute("DELETE FROM community_post_images WHERE post_id = ?", (post_id,))
                    if image_url:
                        connection.execute("INSERT INTO community_post_images (id, post_id, image_url, sort_order) VALUES (?, ?, ?, 0)", (f"community-post-image-{secrets.token_urlsafe(8)}", post_id, image_url))
                    if post_id.startswith("community-announcement-"):
                        announcement_id = post_id.removeprefix("community-announcement-")
                        connection.execute("UPDATE platform_announcements SET title = ?, content = ?, image_url = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (title, content, image_url, announcement_id))
                    write_platform_audit(connection, user_id, "community_post_edited", "community_post", post_id)
                COMMUNITY_LIVE_HUB.publish({"type": "community_post_updated", "postId": post_id})
                self.send_json(200, {"ok": True})
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json(400, {"error": str(error)})
            return
        if self.path.startswith("/api/admin/search-operations/"):
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            try:
                require_admin(user_id)
                require_admin_step_up(self, user_id)
                length = request_length
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                kind, rule_id = self.path.removeprefix("/api/admin/search-operations/").strip("/").split("/", 1)
                table = {"synonym": "search_synonyms", "correction": "search_corrections", "recommendation": "search_recommendations", "zero_result": "search_zero_result_rules"}.get(kind)
                if not table:
                    raise ValueError("搜索运营类型无效")
                enabled = 1 if bool(payload.get("enabled", True)) else 0
                with database() as connection:
                    if kind == "recommendation" and "weight" in payload:
                        weight = max(1, min(10000, int(payload["weight"])))
                        updated = connection.execute(f"UPDATE {table} SET enabled = ?, weight = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (enabled, weight, rule_id)).rowcount
                    else:
                        updated = connection.execute(f"UPDATE {table} SET enabled = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (enabled, rule_id)).rowcount
                    if not updated:
                        raise ValueError("搜索规则不存在")
                    write_platform_audit(connection, user_id, "search_operation_updated", "search", rule_id, {"kind": kind, "enabled": bool(enabled)})
                self.send_json(200, {"ok": True})
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                self.send_json(400, {"error": str(error)})
            return
        if self.path.startswith("/api/messages/quick-replies/"):
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            try:
                length = request_length
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                reply_id = self.path.removeprefix("/api/messages/quick-replies/").rstrip("/")
                content, category = str(payload.get("content") or "").strip(), str(payload.get("category") or "general").strip()[:30] or "general"
                if not 1 <= len(content) <= 500:
                    raise ValueError("快捷回复长度应为 1-500 个字符")
                with database() as connection:
                    if not is_seller(connection, user_id):
                        self.send_json(403, {"error": "Seller access required"})
                        return
                    if not connection.execute("UPDATE seller_quick_replies SET content = ?, category = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND seller_user_id = ?", (content, category, reply_id, user_id)).rowcount:
                        raise ValueError("快捷回复不存在")
                self.send_json(200, {"quickReply": {"id": reply_id, "content": content, "category": category}})
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json(400, {"error": str(error)})
            return
        if self.path.startswith("/api/seller/staff/"):
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            try:
                length = request_length
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                staff_id = self.path.removeprefix("/api/seller/staff/").rstrip("/")
                role, status = str(payload.get("role") or ""), str(payload.get("status") or "active")
                custom = [str(item) for item in payload.get("permissions") or [] if str(item) in SHOP_STAFF_CUSTOM_PERMISSIONS]
                if role not in SHOP_STAFF_ROLE_PERMISSIONS or status not in ("active", "disabled"):
                    raise ValueError("成员设置无效")
                with database() as connection:
                    row = connection.execute("SELECT shop_id FROM shop_staff WHERE id = ?", (staff_id,)).fetchone()
                    if not row:
                        raise ValueError("成员不存在")
                    require_shop_owner(connection, user_id, row[0])
                    connection.execute("UPDATE shop_staff SET role = ?, permissions_json = ?, status = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (role, json.dumps(custom, ensure_ascii=False), status, staff_id))
                    write_shop_staff_audit(connection, row[0], staff_id, user_id, "member_updated", {"role": role, "status": status, "permissions": custom})
                self.send_json(200, {"ok": True})
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json(400, {"error": str(error)})
            return
        if self.path == "/api/profile":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            try:
                length = request_length
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                name = str(payload.get("name") or "").strip()
                bio = str(payload.get("bio") or "").strip()
                phone = str(payload.get("phone") or "").strip() or None
                email = str(payload.get("email") or "").strip().lower() or None
                password = str(payload.get("currentPassword") or "")
                if not 1 <= len(name) <= 30:
                    raise ValueError("昵称长度应为 1-30 个字符")
                if len(bio) > 300:
                    raise ValueError("个人简介不能超过 300 个字符")
                if not phone and not email:
                    raise ValueError("请至少保留一种登录联系方式")
                if phone and not re.fullmatch(r"\d{6,20}", phone):
                    raise ValueError("请输入有效的手机号")
                if email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                    raise ValueError("请输入有效的邮箱")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    existing = connection.execute("SELECT display_name, phone, email, password_hash FROM users WHERE id = ? AND status = 'active'", (user_id,)).fetchone()
                    if not existing:
                        self.send_json(404, {"error": "Account not found"})
                        return
                    phone_changed, email_changed = phone != existing["phone"], email != existing["email"]
                    if (phone_changed or email_changed):
                        valid, _ = verify_password(password, existing["password_hash"])
                        if not valid:
                            raise ValueError("修改登录联系方式需要输入当前密码")
                    connection.execute(
                        """
                        UPDATE users
                        SET display_name = ?, phone = ?, email = ?,
                            phone_verified_at = CASE WHEN ? THEN NULL ELSE phone_verified_at END,
                            email_verified_at = CASE WHEN ? THEN NULL ELSE email_verified_at END,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ?
                        """,
                        (name, phone, email, int(phone_changed), int(email_changed), user_id),
                    )
                    connection.execute(
                        """
                        INSERT INTO user_profiles (user_id, bio) VALUES (?, ?)
                        ON CONFLICT(user_id) DO UPDATE SET bio = excluded.bio, updated_at = CURRENT_TIMESTAMP
                        """,
                        (user_id, bio),
                    )
                    write_platform_audit(connection, user_id, "profile_updated", "user", user_id, {"phoneChanged": phone_changed, "emailChanged": email_changed})
                    profile = profile_for_user(connection, user_id)
                self.send_json(200, {"profile": profile})
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json(400, {"error": str(error)})
            except sqlite3.IntegrityError:
                self.send_json(409, {"error": "手机号或邮箱已被使用"})
            return
        if self.path.startswith("/api/addresses/"):
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            address_id = self.path.rsplit("/", 1)[-1]
            try:
                length = request_length
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    existing = connection.execute("SELECT * FROM buyer_addresses WHERE id = ? AND buyer_user_id = ?", (address_id, user_id)).fetchone()
                    if not existing:
                        raise ValueError("收货地址不存在")
                    if payload.get("isDefault"):
                        connection.execute("UPDATE buyer_addresses SET is_default = 0 WHERE buyer_user_id = ?", (user_id,))
                    fields = {
                        "recipient_name": str(payload.get("recipient", existing["recipient_name"])).strip(),
                        "recipient_phone": str(payload.get("phone", existing["recipient_phone"])).strip(),
                        "province": str(payload.get("province", existing["province"])).strip(),
                        "city": str(payload.get("city", existing["city"])).strip(),
                        "district": str(payload.get("district", existing["district"])).strip(),
                        "detail": str(payload.get("detail", existing["detail"])).strip(),
                        "postal_code": str(payload.get("postalCode", existing["postal_code"] or "")).strip() or None,
                        "country_code": str(payload.get("countryCode", existing["country_code"] or "US")).strip().upper(),
                        "country_name": "",
                        "is_default": int(bool(payload.get("isDefault", existing["is_default"]))),
                    }
                    if fields["country_code"] not in SHIPPING_COUNTRIES:
                        raise ValueError("请选择平台当前支持配送的国家或地区")
                    fields["country_name"] = SHIPPING_COUNTRIES[fields["country_code"]]
                    if not all(fields[key] for key in ("recipient_name", "recipient_phone", "province", "city", "district", "detail")):
                        raise ValueError("请完整填写收货地址")
                    connection.execute("UPDATE buyer_addresses SET recipient_name = ?, recipient_phone = ?, province = ?, city = ?, district = ?, detail = ?, postal_code = ?, country_code = ?, country_name = ?, is_default = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (*fields.values(), address_id))
                    row = connection.execute("SELECT * FROM buyer_addresses WHERE id = ?", (address_id,)).fetchone()
                self.send_json(200, {"address": address_for_response(row)})
            except (ValueError, json.JSONDecodeError) as error:
                self.send_json(400, {"error": str(error)})
            return
        if not self.path.startswith("/api/states/"):
            self.send_json(404, {"error": "Not found"})
            return
        user_id = self.path.rsplit("/", 1)[-1]
        if session_user(self) != user_id:
            self.send_json(401, {"error": "Unauthorized"})
            return
        try:
            length = request_length
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            state = payload.get("state")
            if not isinstance(state, dict):
                raise ValueError("Invalid state")
            with database() as connection:
                connection.execute(
                    """
                    INSERT INTO application_states (user_id, state_json, updated_at) VALUES (?, ?, CURRENT_TIMESTAMP)
                    ON CONFLICT(user_id) DO UPDATE SET state_json = excluded.state_json, updated_at = CURRENT_TIMESTAMP
                    """,
                    (user_id, json.dumps(state, ensure_ascii=False)),
                )
            self.send_json(200, {"ok": True})
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})

    def do_DELETE(self) -> None:
        if not self.enforce_state_change_protection():
            return
        if self.path == "/api/seller/verification":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            try:
                with database() as connection:
                    if not is_seller(connection, user_id):
                        self.send_json(403, {"error": "Seller access required"})
                        return
                    application = connection.execute(
                        "SELECT id FROM seller_verification_applications WHERE seller_user_id = ? AND status = 'pending' ORDER BY created_at DESC LIMIT 1",
                        (user_id,),
                    ).fetchone()
                    if not application:
                        raise ValueError("没有可撤回的审核中认证申请")
                    # The original schema only permits pending/approved/rejected.
                    # Keep a distinct withdrawal marker in rejection_code so the
                    # request remains auditable without appearing as a failed review.
                    connection.execute(
                        "UPDATE seller_verification_applications SET status = 'rejected', rejection_code = 'seller_withdrew', review_note = '卖家已撤回，未进入平台审核', reviewed_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'pending'",
                        (application[0],),
                    )
                    connection.execute(
                        "UPDATE seller_profiles SET verification_status = 'pending', verification_expires_at = NULL, verification_expiry_notified_at = NULL WHERE user_id = ?",
                        (user_id,),
                    )
                    write_platform_audit(connection, user_id, "seller_verification_withdrawn", "seller_verification", application[0])
                self.send_json(200, {"ok": True})
            except ValueError as error:
                self.send_json(400, {"error": str(error)})
            return
        if self.path.startswith("/api/admin/community/posts/"):
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            try:
                require_admin(user_id)
                require_admin_step_up(self, user_id, force_fresh=True)
                post_id = self.path.removeprefix("/api/admin/community/posts/").rstrip("/")
                length = int(self.headers.get("Content-Length", "0"))
                payload = json.loads(self.rfile.read(length).decode("utf-8")) if length else {}
                reason = str(payload.get("reason") or "").strip()
                if not 2 <= len(reason) <= 500:
                    raise ValueError("请填写 2 到 500 个字的删除原因")
                with database() as connection:
                    deleted = connection.execute(
                        """
                        UPDATE community_posts
                        SET status = 'deleted', is_pinned = 0, pinned_at = NULL, pinned_by_user_id = NULL,
                            updated_at = CURRENT_TIMESTAMP
                        WHERE id = ? AND status = 'published'
                        """,
                        (post_id,),
                    ).rowcount
                    if not deleted:
                        raise ValueError("帖子不存在或已处理")
                    write_platform_audit(connection, user_id, "community_post_deleted", "community_post", post_id, {"reason": reason})
                COMMUNITY_LIVE_HUB.publish({"type": "community_post_updated", "postId": post_id})
                self.send_json(200, {"ok": True})
            except ValueError as error:
                self.send_json(400, {"error": str(error)})
            return
        if self.path.startswith("/api/admin/search-operations/"):
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            try:
                require_admin(user_id)
                require_admin_step_up(self, user_id)
                kind, rule_id = self.path.removeprefix("/api/admin/search-operations/").strip("/").split("/", 1)
                table = {"synonym": "search_synonyms", "correction": "search_corrections", "recommendation": "search_recommendations", "zero_result": "search_zero_result_rules"}.get(kind)
                if not table:
                    raise ValueError("搜索运营类型无效")
                with database() as connection:
                    if not connection.execute(f"DELETE FROM {table} WHERE id = ?", (rule_id,)).rowcount:
                        raise ValueError("搜索规则不存在")
                    write_platform_audit(connection, user_id, "search_operation_deleted", "search", rule_id, {"kind": kind})
                self.send_json(200, {"ok": True})
            except ValueError as error:
                self.send_json(400, {"error": str(error)})
            return
        if self.path.startswith("/api/seller/staff/"):
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            staff_id = self.path.removeprefix("/api/seller/staff/").rstrip("/")
            with database() as connection:
                row = connection.execute("SELECT shop_id FROM shop_staff WHERE id = ?", (staff_id,)).fetchone()
                if not row:
                    self.send_json(404, {"error": "Staff member not found"})
                    return
                try:
                    require_shop_owner(connection, user_id, row[0])
                except ValueError as error:
                    self.send_json(403, {"error": str(error)})
                    return
                connection.execute("DELETE FROM shop_staff WHERE id = ?", (staff_id,))
                write_shop_staff_audit(connection, row[0], staff_id, user_id, "member_removed")
            self.send_json(200, {"ok": True})
            return
        if self.path.startswith("/api/messages/quick-replies/"):
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            reply_id = self.path.removeprefix("/api/messages/quick-replies/").rstrip("/")
            with database() as connection:
                if not is_seller(connection, user_id):
                    self.send_json(403, {"error": "Seller access required"})
                    return
                if not connection.execute("DELETE FROM seller_quick_replies WHERE id = ? AND seller_user_id = ?", (reply_id, user_id)).rowcount:
                    self.send_json(404, {"error": "快捷回复不存在"})
                    return
            self.send_json(200, {"ok": True})
            return
        if self.path.startswith("/api/seller/products/"):
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            try:
                require_seller(user_id)
                product_id = self.path.removeprefix("/api/seller/products/").rstrip("/")
                if not product_id:
                    raise ValueError("作品不存在")
                with database() as connection:
                    shop_ids = seller_accessible_shop_ids(connection, user_id, "products")
                    deleted = connection.execute(
                        f"DELETE FROM products WHERE id = ? AND shop_id IN ({','.join('?' for _ in shop_ids)})",
                        (product_id, *shop_ids),
                    ).rowcount
                if not deleted:
                    raise ValueError("作品不存在或无权操作")
                self.send_json(200, {"ok": True})
            except ValueError as error:
                self.send_json(400, {"error": str(error)})
            return
        if not self.path.startswith("/api/addresses/"):
            self.send_json(404, {"error": "Not found"})
            return
        user_id = session_user(self)
        if not user_id:
            self.send_json(401, {"error": "Unauthorized"})
            return
        address_id = self.path.rsplit("/", 1)[-1]
        with database() as connection:
            deleted = connection.execute("DELETE FROM buyer_addresses WHERE id = ? AND buyer_user_id = ?", (address_id, user_id)).rowcount
            if not deleted:
                self.send_json(404, {"error": "收货地址不存在"})
                return
            fallback = connection.execute("SELECT id FROM buyer_addresses WHERE buyer_user_id = ? ORDER BY updated_at DESC LIMIT 1", (user_id,)).fetchone()
            if fallback:
                connection.execute("UPDATE buyer_addresses SET is_default = 1 WHERE id = ?", (fallback[0],))
        self.send_json(200, {"ok": True})


if __name__ == "__main__":
    validate_production_configuration()
    port = int(os.environ.get("HANDICRAFTS_PORT", "8787"))
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    expiry_stop_event = threading.Event()
    expiry_worker = OrderExpiryWorker(expiry_stop_event)
    expiry_worker.start()
    print(f"Migration API listening at http://127.0.0.1:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        expiry_stop_event.set()
        expiry_worker.join(timeout=ORDER_EXPIRY_SCAN_SECONDS + 1)
        server.server_close()
