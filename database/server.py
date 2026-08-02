import base64
import binascii
import hashlib
import json
import re
import secrets
import threading
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import sqlite3
import os
from urllib.parse import parse_qs, urlparse
from sqlite_config import connect as sqlite_connect


ROOT = Path(__file__).resolve().parent
DB_PATH = Path(os.environ.get("HANDICRAFTS_DB_PATH", ROOT / "handicrafts.db"))
MEDIA_DIR = Path(os.environ.get("HANDICRAFTS_MEDIA_DIR", ROOT.parent / "src" / "images" / "uploads"))
LEGACY_MEDIA_DIR = ROOT / "media"
SESSION_SECRET = os.environ.get("HANDICRAFTS_SESSION_SECRET", "development-only-change-me")
PRODUCTION_HTTPS = os.environ.get("HANDICRAFTS_HTTPS", "0") == "1"
SENSITIVE_CONTENT_WORDS = ("赌博", "博彩", "色情", "成人", "毒品", "枪支", "仿真枪", "管制刀具", "盗版", "假货")
IMAGE_MIME_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}
VIDEO_MIME_TYPES = {"video/mp4": ".mp4", "video/webm": ".webm", "video/quicktime": ".mov"}
MAX_IMAGE_BYTES = 10 * 1024 * 1024
MAX_VIDEO_BYTES = 50 * 1024 * 1024
LOGIN_FAILURES: dict[str, list[datetime]] = {}
ORDER_EXPIRY_SCAN_SECONDS = max(5, int(os.environ.get("HANDICRAFTS_ORDER_EXPIRY_SCAN_SECONDS", "30")))
CUSTOMER_SERVICE_WEBHOOK_SECRET = os.environ.get("CUSTOMER_SERVICE_WEBHOOK_SECRET", "")
LIANLIAN_MODE = os.environ.get("HANDICRAFTS_LIANLIAN_MODE", "unconfigured").strip().lower()
SELLER_OPERATING_CATEGORIES = {
    "布艺缝纫", "黏土&塑形", "滴胶&树脂", "编织", "木质&木艺", "皮具", "首饰", "陶艺陶瓷",
    "刺绣", "花艺干花", "香薰蜡烛 & 香氛", "古风国风", "绘画肌理", "纸品文创", "宠物专属",
    "苔藓微景观", "羊毛毡", "皂类", "非遗",
}
SELLER_PAYOUT_METHODS = {"bank_card", "alipay", "wechat"}


class StepUpRequiredError(Exception):
    pass


def database() -> sqlite3.Connection:
    return sqlite_connect(DB_PATH)


def number(value: object) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"scrypt$16384$8$1${salt.hex()}${digest.hex()}"


def token_hash(token: str) -> str:
    return hashlib.sha256(f"{SESSION_SECRET}:{token}".encode("utf-8")).hexdigest()


def issue_verification(connection: sqlite3.Connection, user_id: str | None, destination: str, purpose: str) -> str:
    code = f"{secrets.randbelow(900000) + 100000}"
    connection.execute("UPDATE verification_tokens SET consumed_at = CURRENT_TIMESTAMP WHERE destination = ? AND purpose = ? AND consumed_at IS NULL", (destination, purpose))
    connection.execute("INSERT INTO verification_tokens (id, user_id, destination, purpose, token_hash, expires_at) VALUES (?, ?, ?, ?, ?, datetime('now', '+10 minutes'))", (f"verify-{secrets.token_urlsafe(10)}", user_id, destination, purpose, token_hash(code)))
    return code


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


def login_allowed(client_ip: str) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=10)
    failures = [item for item in LOGIN_FAILURES.get(client_ip, []) if item > cutoff]
    LOGIN_FAILURES[client_ip] = failures
    return len(failures) < 5


def session_cookie(token: str) -> str:
    secure = "; Secure" if PRODUCTION_HTTPS else ""
    return f"handicrafts_session={token}; Path=/; Max-Age=1209600; HttpOnly; SameSite=Lax{secure}"


def register_login_failure(client_ip: str) -> None:
    LOGIN_FAILURES.setdefault(client_ip, []).append(datetime.now(timezone.utc))


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
    return f"{title}{product.get('description') or ''}{product.get('material') or ''}{''.join(tags)}{variant_text}".lower()


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


def media_storage_key(url: object) -> str | None:
    value = str(url or "")
    marker = "/media/"
    if marker not in value:
        return None
    return Path(value.split(marker, 1)[1].split("?", 1)[0]).name or None


def link_media_assets(connection: sqlite3.Connection, urls: list[object], target_type: str, target_id: str) -> None:
    keys = [key for key in (media_storage_key(url) for url in urls) if key]
    if not keys:
        return
    placeholders = ",".join("?" for _ in keys)
    assets = connection.execute(
        f"SELECT id FROM media_assets WHERE storage_key IN ({placeholders}) AND status != 'deleted'", tuple(keys)
    ).fetchall()
    for asset in assets:
        connection.execute(
            "INSERT OR IGNORE INTO media_asset_links (id, asset_id, target_type, target_id) VALUES (?, ?, ?, ?)",
            (f"asset-link-{secrets.token_urlsafe(10)}", asset[0], target_type, target_id),
        )
        connection.execute("UPDATE media_assets SET status = 'active' WHERE id = ?", (asset[0],))


def cleanup_temporary_media(connection: sqlite3.Connection) -> int:
    rows = connection.execute(
        """
        SELECT media_assets.id, media_assets.storage_key FROM media_assets
        WHERE media_assets.status = 'temporary' AND media_assets.created_at <= datetime('now', '-24 hours')
          AND NOT EXISTS (SELECT 1 FROM media_asset_links WHERE media_asset_links.asset_id = media_assets.id)
        """
    ).fetchall()
    for asset_id, storage_key in rows:
        path = MEDIA_DIR / Path(storage_key).name
        if not path.is_file():
            path = LEGACY_MEDIA_DIR / Path(storage_key).name
        if path.is_file():
            path.unlink()
        connection.execute("UPDATE media_assets SET status = 'deleted', deleted_at = CURRENT_TIMESTAMP WHERE id = ?", (asset_id,))
    return len(rows)


def media_rows(product_id: str, product: dict) -> list[tuple]:
    images = product.get("images") or ([product["image"]] if product.get("image") else [])
    rows = [
        (f"{product_id}-image-{index}", product_id, "image", url, url, index, int(index == 0))
        for index, url in enumerate(images)
        if url
    ]
    if product.get("video"):
        rows.append(
            (f"{product_id}-video", product_id, "video", product["video"], product["video"], len(rows), 0)
        )
    return rows


def upsert_product(connection: sqlite3.Connection, product_id: str, shop_id: str, product: dict, status: str) -> None:
    connection.row_factory = sqlite3.Row
    title = str(product.get("title") or "未命名作品").strip()
    media_urls = product.get("images") or ([product.get("image")] if product.get("image") else [])
    tags = seo_tags(product)
    if len(title) > 30:
        raise ValueError("作品名称最多 30 个字")
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
    moderation_status = "pending" if matched_rule and matched_rule["action"] == "manual_review" else "approved"
    moderation_reason = f"命中审核规则“{matched_rule['name']}”，等待人工审核" if moderation_status == "pending" else None
    effective_status = "draft" if moderation_status == "pending" and status == "published" else status
    if status == "published":
        validate_product_media(product)
    price = int(round(number(product.get("price")) * 100))
    stock = max(0, int(number(product.get("stock"))))
    low_stock_threshold = max(0, int(number(product.get("lowStockThreshold", 3))))
    connection.execute(
        """
        INSERT INTO products (id, shop_id, category, title, description, material, price_cents, stock, low_stock_threshold, status, published_at, moderation_status, moderation_reason, moderated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, CASE WHEN ? = 'published' THEN CURRENT_TIMESTAMP END, ?, ?, CURRENT_TIMESTAMP)
        ON CONFLICT(id) DO UPDATE SET
          category = excluded.category,
          title = excluded.title,
          description = excluded.description,
          material = excluded.material,
          price_cents = excluded.price_cents,
          stock = excluded.stock,
          low_stock_threshold = excluded.low_stock_threshold,
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
            product.get("category", "陶艺"),
            title,
            product.get("description") or "",
            product.get("material") or "手工制作",
            price,
            stock,
            low_stock_threshold,
            effective_status,
            effective_status,
            moderation_status,
            moderation_reason,
        ),
    )
    if matched_rule:
        record_governance_rule_hit(connection, matched_rule, product_id, content)
    if moderation_status == "approved":
        write_moderation_log(connection, product_id, content, "approved", None)
    connection.execute("DELETE FROM product_media WHERE product_id = ?", (product_id,))
    connection.execute("DELETE FROM product_options WHERE product_id = ?", (product_id,))
    connection.execute("DELETE FROM product_skus WHERE product_id = ?", (product_id,))
    connection.execute("DELETE FROM product_seo_tags WHERE product_id = ?", (product_id,))
    connection.executemany(
        "INSERT INTO product_seo_tags (product_id, tag, weight, sort_order) VALUES (?, ?, ?, ?)",
        [(product_id, tag, 1, index) for index, tag in enumerate(tags)],
    )
    connection.executemany(
        "INSERT INTO product_media (id, product_id, media_type, storage_key, public_url, sort_order, is_cover) VALUES (?, ?, ?, ?, ?, ?, ?)",
        media_rows(product_id, product),
    )
    link_media_assets(connection, [*media_urls, product.get("video")], "product", product_id)
    option_value_ids: dict[tuple[str, str], str] = {}
    for option_index, variant in enumerate(product.get("variants") or []):
        option_id = f"{product_id}-option-{option_index}"
        connection.execute(
            "INSERT INTO product_options (id, product_id, name, sort_order) VALUES (?, ?, ?, ?)",
            (option_id, product_id, variant.get("name") or "规格", option_index),
        )
        images = variant.get("valueImages") or {}
        for value_index, value in enumerate(variant.get("values") or []):
            value_id = f"{option_id}-value-{value_index}"
            connection.execute(
                "INSERT INTO product_option_values (id, option_id, value, image_url, sort_order) VALUES (?, ?, ?, ?, ?)",
                (value_id, option_id, value, images.get(value), value_index),
            )
            option_value_ids[(variant.get("name") or "规格", value)] = value_id
    skus = product.get("skus") or []
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
                    str(sku.get("code") or "").strip() or None,
                    int(round(number(sku.get("price", price / 100)) * 100)),
                    max(0, int(number(sku.get("stock")))),
                    option_value_ids_json,
                    "disabled" if sku.get("status") == "disabled" else "active",
                ),
            )
    else:
        connection.execute(
            "INSERT INTO product_skus (id, product_id, price_cents, stock) VALUES (?, ?, ?, ?)",
            (f"{product_id}-default-sku", product_id, price, stock),
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
        connection.execute(
            "UPDATE shops SET settings_json = ? WHERE id = ?",
            (json.dumps({"featuredProductIds": shop.get("featuredProductIds") or []}, ensure_ascii=False), shop_id),
        )
    return {"products": len(products), "drafts": len(drafts)}


def catalog(shop_ids: tuple[str, ...] | None = None, statuses: tuple[str, ...] = ("published",)) -> list[dict]:
    with database() as connection:
        connection.row_factory = sqlite3.Row
        shop_filter = ""
        params: tuple[object, ...] = tuple(statuses)
        if shop_ids:
            shop_filter = f" AND products.shop_id IN ({','.join('?' for _ in shop_ids)})"
            params += tuple(shop_ids)
        products = connection.execute(
            f"""
            SELECT products.*, shops.name AS shop_name
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
                "SELECT media_type, public_url FROM product_media WHERE product_id = ? ORDER BY sort_order",
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
                    "SELECT id, value, image_url FROM product_option_values WHERE option_id = ? ORDER BY sort_order",
                    (option["id"],),
                ).fetchall()
                variants.append(
                    {
                        "name": option["name"],
                        "values": [value["value"] for value in values],
                        "valueImages": {value["value"]: value["image_url"] for value in values if value["image_url"]},
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
            result.append(
                {
                    "id": legacy_id,
                    "catalogId": product["id"],
                    "title": product["title"],
                    "category": product["category"],
                    "price": product["price_cents"] / 100,
                    "image": images[0] if images else "",
                    "images": images or None,
                    "video": video,
                    "shopId": 99,
                    "analyticsShopId": product["shop_id"],
                    "shop": product["shop_name"],
                    "rating": round(float(review_summary["average_rating"] or 5), 1),
                    "reviews": review_summary["review_count"],
                    "stock": product["stock"],
                    "lowStockThreshold": product["low_stock_threshold"],
                    "tags": ["原创手作"],
                    "seoTags": seo_tags,
                    "publishStatus": product["status"],
                    "listed": product["status"] == "published",
                    "reviewStatus": product["moderation_status"],
                    "moderationReason": product["moderation_reason"],
                    "custom": True,
                    "description": product["description"],
                    "material": product["material"],
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


def create_session(user_id: str, handler: BaseHTTPRequestHandler | None = None) -> str:
    token = secrets.token_urlsafe(32)
    expires = (datetime.now(timezone.utc) + timedelta(days=14)).strftime("%Y-%m-%d %H:%M:%S")
    user_agent = handler.headers.get("User-Agent", "")[:300] if handler else ""
    ip_address = handler.client_address[0] if handler else ""
    with database() as connection:
        connection.execute(
            "INSERT INTO web_sessions (token, id, user_id, expires_at, last_seen_at, user_agent, ip_address) VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP, ?, ?)",
            (token, f"session-{secrets.token_urlsafe(10)}", user_id, expires, user_agent, ip_address),
        )
    return token


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


def seller_analytics(user_id: str, days: int) -> dict:
    days = max(1, min(days, 365))
    with database() as connection:
        connection.row_factory = sqlite3.Row
        shop_ids = seller_accessible_shop_ids(connection, user_id, "settings")
        if not shop_ids:
            return {"days": days, "revenue": 0, "orders": 0, "visitors": 0, "conversionRate": 0, "pendingFulfillment": 0, "refundRate": 0, "lowStock": 0, "hotProducts": []}
        marks = ",".join("?" for _ in shop_ids)
        scope = tuple(shop_ids)
        order_stats = connection.execute(f"SELECT COUNT(*) AS orders, COALESCE(SUM(paid_amount_cents), 0) AS revenue, SUM(CASE WHEN status = 'refunded' THEN 1 ELSE 0 END) AS refunded, SUM(CASE WHEN status = 'pending_fulfillment' THEN 1 ELSE 0 END) AS pending FROM orders WHERE shop_id IN ({marks}) AND placed_at >= datetime('now', ?)", (*scope, f"-{days} days")).fetchone()
        visitors = connection.execute(f"SELECT COUNT(DISTINCT visitor_key) FROM shop_visit_events WHERE shop_id IN ({marks}) AND visited_on >= date('now', ?)", (*scope, f"-{days} days")).fetchone()[0]
        low_stock = connection.execute(f"SELECT COUNT(*) FROM products WHERE shop_id IN ({marks}) AND status = 'published' AND stock BETWEEN 1 AND low_stock_threshold", scope).fetchone()[0]
        hot = connection.execute(f"SELECT products.id, products.title, SUM(order_items.quantity) AS sales FROM order_items JOIN orders ON orders.id = order_items.order_id JOIN products ON products.id = order_items.product_id WHERE orders.shop_id IN ({marks}) AND orders.status NOT IN ('cancelled', 'refunded') AND orders.placed_at >= datetime('now', ?) GROUP BY products.id ORDER BY sales DESC LIMIT 5", (*scope, f"-{days} days")).fetchall()
        count = int(order_stats["orders"] or 0)
        return {"days": days, "revenue": order_stats["revenue"] / 100, "orders": count, "visitors": visitors, "conversionRate": round(count / visitors * 100, 2) if visitors else 0, "pendingFulfillment": int(order_stats["pending"] or 0), "refundRate": round(int(order_stats["refunded"] or 0) / count * 100, 2) if count else 0, "lowStock": low_stock, "hotProducts": [{"id": row["id"], "title": row["title"], "sales": row["sales"]} for row in hot]}


def platform_analytics(days: int) -> dict:
    days = max(1, min(days, 365))
    with database() as connection:
        connection.row_factory = sqlite3.Row
        orders = connection.execute("SELECT COALESCE(SUM(paid_amount_cents), 0) AS revenue, COUNT(*) AS total FROM orders WHERE paid_at >= datetime('now', ?) AND status NOT IN ('cancelled', 'refunded', 'pending_payment')", (f"-{days} days",)).fetchone()
        statuses = {row["status"]: row["count"] for row in connection.execute("SELECT status, COUNT(*) AS count FROM orders WHERE placed_at >= datetime('now', ?) GROUP BY status", (f"-{days} days",))}
        active_shops = connection.execute("SELECT COUNT(DISTINCT shop_id) FROM orders WHERE paid_at >= datetime('now', ?) AND status NOT IN ('cancelled', 'refunded', 'pending_payment')", (f"-{days} days",)).fetchone()[0]
        pending_reports = connection.execute("SELECT COUNT(*) FROM content_reports WHERE status = 'pending'").fetchone()[0]
        pending_appeals = connection.execute("SELECT COUNT(*) FROM governance_appeals WHERE status = 'pending'").fetchone()[0]
        timing = connection.execute("SELECT AVG((julianday(handled_at) - julianday(created_at)) * 24) FROM governance_appeals WHERE status IN ('approved', 'rejected') AND handled_at IS NOT NULL AND created_at >= datetime('now', ?)", (f"-{days} days",)).fetchone()[0]
        daily_rows = connection.execute("SELECT date(paid_at) AS day, COALESCE(SUM(paid_amount_cents), 0) AS revenue, COUNT(*) AS orders FROM orders WHERE paid_at >= datetime('now', ?) AND status NOT IN ('cancelled', 'refunded', 'pending_payment') GROUP BY date(paid_at)", (f"-{days - 1} days",)).fetchall()
        daily_lookup = {row["day"]: {"revenue": row["revenue"] / 100, "orders": row["orders"]} for row in daily_rows}
        daily = []
        for offset in range(days - 1, -1, -1):
            day = (datetime.now().date() - timedelta(days=offset)).isoformat()
            daily.append({"date": day, **daily_lookup.get(day, {"revenue": 0, "orders": 0})})
        categories = connection.execute("SELECT products.category, COUNT(order_items.id) AS sales, COALESCE(SUM(order_items.subtotal_cents), 0) AS revenue FROM order_items JOIN orders ON orders.id = order_items.order_id JOIN products ON products.id = order_items.product_id WHERE orders.paid_at >= datetime('now', ?) AND orders.status NOT IN ('cancelled', 'refunded', 'pending_payment') GROUP BY products.category ORDER BY revenue DESC LIMIT 6", (f"-{days} days",)).fetchall()
        shops = connection.execute("SELECT shops.name, COUNT(orders.id) AS orders, COALESCE(SUM(orders.paid_amount_cents), 0) AS revenue FROM orders JOIN shops ON shops.id = orders.shop_id WHERE orders.paid_at >= datetime('now', ?) AND orders.status NOT IN ('cancelled', 'refunded', 'pending_payment') GROUP BY shops.id ORDER BY revenue DESC LIMIT 5", (f"-{days} days",)).fetchall()
        active_campaigns = connection.execute("SELECT COUNT(*) FROM platform_campaigns WHERE status = 'active' AND (starts_at IS NULL OR starts_at <= CURRENT_TIMESTAMP) AND (ends_at IS NULL OR ends_at > CURRENT_TIMESTAMP)").fetchone()[0]
        event_scope = (f"-{days} days",)
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
        products = connection.execute("SELECT products.id, products.title, COALESCE(SUM(CASE WHEN orders.id IS NOT NULL THEN order_items.quantity ELSE 0 END), 0) AS sales, COALESCE(SUM(CASE WHEN orders.id IS NOT NULL THEN order_items.subtotal_cents ELSE 0 END), 0) AS revenue FROM products LEFT JOIN order_items ON order_items.product_id = products.id LEFT JOIN orders ON orders.id = order_items.order_id AND orders.paid_at >= datetime('now', ?) AND orders.status NOT IN ('cancelled', 'refunded', 'pending_payment') GROUP BY products.id ORDER BY revenue DESC LIMIT 6", event_scope).fetchall()
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


def record_analytics_event(connection: sqlite3.Connection, event_type: str, visitor_key: str | None = None, user_id: str | None = None, shop_id: str | None = None, product_id: str | None = None, campaign_id: str | None = None, channel: object = "direct") -> None:
    connection.execute("INSERT INTO analytics_events (id, event_type, visitor_key, user_id, shop_id, product_id, campaign_id, channel) VALUES (?, ?, ?, ?, ?, ?, ?, ?)", (f"analytics-{secrets.token_urlsafe(10)}", event_type, visitor_key or None, user_id, shop_id, product_id, campaign_id, analytics_channel(channel)))


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


def catalog_product_number(product_id: str) -> int:
    try:
        return int(product_id.rsplit("-", 1)[-1])
    except ValueError:
        return int(hashlib.sha256(product_id.encode("utf-8")).hexdigest()[:8], 16)


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


def require_shop_permission(connection: sqlite3.Connection, user_id: str, shop_id: str, permission: str) -> None:
    if permission not in seller_shop_permissions(connection, user_id).get(shop_id, set()):
        raise ValueError("无权操作该店铺")


def require_shop_owner(connection: sqlite3.Connection, user_id: str, shop_id: str) -> None:
    if not connection.execute("SELECT 1 FROM shops WHERE id = ? AND owner_user_id IN (?, ?)", (shop_id, user_id, f"legacy-seller-{user_id}")).fetchone():
        raise ValueError("仅店主可管理成员")


def finance_fee_bps(connection: sqlite3.Connection) -> int:
    row = connection.execute("SELECT service_fee_bps FROM platform_finance_settings WHERE id = 1").fetchone()
    return max(0, min(3000, int(row[0] if row else 500)))


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
    order = connection.execute("SELECT id, shop_id, paid_amount_cents, status, paid_at FROM orders WHERE id = ?", (order_id,)).fetchone()
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
          (id, shop_id, order_id, gross_cents, platform_fee_cents, net_cents, fee_rate_bps)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (settlement_id, order["shop_id"], order_id, gross, fee, net, fee_bps),
    ).rowcount
    if not inserted:
        return False
    ensure_shop_wallet(connection, order["shop_id"])
    connection.execute("UPDATE shop_wallets SET pending_cents = pending_cents + ?, updated_at = CURRENT_TIMESTAMP WHERE shop_id = ?", (net, order["shop_id"]))
    write_wallet_ledger(connection, order["shop_id"], "order_pending", settlement_id=settlement_id, pending=net, note=f"订单 {order_id} 待结算")
    return True


def release_order_settlement(connection: sqlite3.Connection, order_id: str) -> bool:
    """Release a completed order from pending settlement to withdrawable balance."""
    connection.row_factory = sqlite3.Row
    settlement = connection.execute("SELECT * FROM shop_settlements WHERE order_id = ?", (order_id,)).fetchone()
    if not settlement or settlement["status"] != "pending":
        return False
    changed = connection.execute("UPDATE shop_settlements SET status = 'available', available_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = 'pending'", (settlement["id"],)).rowcount
    if not changed:
        return False
    ensure_shop_wallet(connection, settlement["shop_id"])
    connection.execute("UPDATE shop_wallets SET pending_cents = pending_cents - ?, available_cents = available_cents + ?, updated_at = CURRENT_TIMESTAMP WHERE shop_id = ?", (settlement["net_cents"], settlement["net_cents"], settlement["shop_id"]))
    write_wallet_ledger(connection, settlement["shop_id"], "order_available", settlement_id=settlement["id"], available=settlement["net_cents"], pending=-settlement["net_cents"], note=f"订单 {order_id} 结算完成")
    return True


def reverse_order_settlement(connection: sqlite3.Connection, order_id: str) -> bool:
    """Reverse an order settlement once when its order is refunded."""
    connection.row_factory = sqlite3.Row
    settlement = connection.execute("SELECT * FROM shop_settlements WHERE order_id = ?", (order_id,)).fetchone()
    if not settlement or settlement["status"] == "reversed":
        return False
    previous_status = settlement["status"]
    changed = connection.execute("UPDATE shop_settlements SET status = 'reversed', reversed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ? AND status = ?", (settlement["id"], previous_status)).rowcount
    if not changed:
        return False
    ensure_shop_wallet(connection, settlement["shop_id"])
    pending_delta = -settlement["net_cents"] if previous_status == "pending" else 0
    available_delta = -settlement["net_cents"] if previous_status == "available" else 0
    connection.execute("UPDATE shop_wallets SET pending_cents = pending_cents + ?, available_cents = available_cents + ?, updated_at = CURRENT_TIMESTAMP WHERE shop_id = ?", (pending_delta, available_delta, settlement["shop_id"]))
    write_wallet_ledger(connection, settlement["shop_id"], "refund_reversal", settlement_id=settlement["id"], pending=pending_delta, available=available_delta, note=f"订单 {order_id} 退款冲回")
    return True


def ensure_finance_for_paid_orders(connection: sqlite3.Connection, shop_ids: list[str] | None = None) -> None:
    where, params = "paid_at IS NOT NULL AND status NOT IN ('pending_payment', 'cancelled', 'refunded')", []
    if shop_ids:
        where += f" AND shop_id IN ({','.join('?' for _ in shop_ids)})"
        params.extend(shop_ids)
    for row in connection.execute(f"SELECT id, status FROM orders WHERE {where}", tuple(params)).fetchall():
        create_order_settlement(connection, row[0])
        if row[1] == "completed":
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
    totals = {key: sum(int(row[key] or 0) for row in wallets) for key in ("available_cents", "pending_cents", "withdrawing_cents", "withdrawn_cents")}
    return {
        "feeRateBps": finance_fee_bps(connection), "wallet": {"available": totals["available_cents"] / 100, "pending": totals["pending_cents"] / 100, "withdrawing": totals["withdrawing_cents"] / 100, "withdrawn": totals["withdrawn_cents"] / 100},
        "shops": [{"id": row["shop_id"], "name": row["shop_name"], "available": row["available_cents"] / 100, "pending": row["pending_cents"] / 100, "withdrawing": row["withdrawing_cents"] / 100, "withdrawn": row["withdrawn_cents"] / 100} for row in wallets],
        "settlements": [{"id": row["id"], "orderNo": row["order_no"], "shopId": row["shop_id"], "gross": row["gross_cents"] / 100, "fee": row["platform_fee_cents"] / 100, "net": row["net_cents"] / 100, "status": row["status"], "createdAt": row["created_at"], "availableAt": row["available_at"]} for row in settlements],
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
    wallet = connection.execute("SELECT COALESCE(SUM(available_cents), 0), COALESCE(SUM(pending_cents), 0), COALESCE(SUM(withdrawing_cents), 0), COALESCE(SUM(withdrawn_cents), 0) FROM shop_wallets").fetchone()
    fees = connection.execute("SELECT COALESCE(SUM(platform_fee_cents), 0) FROM shop_settlements WHERE status != 'reversed'").fetchone()[0]
    rows = connection.execute("SELECT shop_withdrawal_requests.*, shops.name AS shop_name, users.display_name AS applicant FROM shop_withdrawal_requests JOIN shops ON shops.id = shop_withdrawal_requests.shop_id JOIN users ON users.id = shop_withdrawal_requests.applicant_user_id ORDER BY CASE status WHEN 'pending' THEN 0 WHEN 'approved' THEN 1 ELSE 2 END, created_at DESC LIMIT 200").fetchall()
    return {"feeRateBps": finance_fee_bps(connection), "summary": {"available": wallet[0] / 100, "pending": wallet[1] / 100, "withdrawing": wallet[2] / 100, "withdrawn": wallet[3] / 100, "platformFees": fees / 100}, "withdrawals": [{"id": row["id"], "shop": row["shop_name"], "applicant": row["applicant"], "amount": row["amount_cents"] / 100, "recipientType": row["recipient_type"], "recipient": row["recipient_snapshot"], "status": row["status"], "note": row["reviewer_note"], "createdAt": row["created_at"]} for row in rows]}


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
    destination = str(row[0] or row[1] or "").strip().lower()
    if not destination:
        raise ValueError("管理员账号未设置邮箱或手机号")
    return destination


def require_admin_step_up(handler: BaseHTTPRequestHandler, user_id: str) -> None:
    ticket = str(handler.headers.get("X-Admin-Step-Up") or "").strip()
    if not ticket:
        raise StepUpRequiredError()
    with database() as connection:
        updated = connection.execute(
            """
            UPDATE admin_step_up_tickets
            SET consumed_at = CURRENT_TIMESTAMP
            WHERE user_id = ? AND ticket_hash = ? AND consumed_at IS NULL
              AND expires_at > CURRENT_TIMESTAMP
            """,
            (user_id, token_hash(ticket)),
        ).rowcount
    if not updated:
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
        ("product_moderation", "products", "moderation_status = 'pending'"),
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
                (shop_id, user_id, f"{user['display_name']}的手作店"),
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
        try:
            coupons = json.loads(shop["coupons_json"] or "[]")
        except json.JSONDecodeError:
            coupons = []
        try:
            settings = json.loads(shop["settings_json"] or "{}")
        except json.JSONDecodeError:
            settings = {}
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
            "coupons": coupons if isinstance(coupons, list) else [],
            "featuredProductIds": settings.get("featuredProductIds") if isinstance(settings.get("featuredProductIds"), list) else [],
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
            "lowStockThreshold": str(product["lowStockThreshold"]),
            "description": product["description"],
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
                json.dumps(shipping if isinstance(shipping, dict) else json.loads(current["shipping_template_json"] or "{}"), ensure_ascii=False),
                json.dumps(coupons if isinstance(coupons, list) else json.loads(current["coupons_json"] or "[]"), ensure_ascii=False),
                json.dumps({"featuredProductIds": featured if isinstance(featured, list) else json.loads(current["settings_json"] or "{}").get("featuredProductIds", [])}, ensure_ascii=False),
                shop_id,
            ),
        )
    return seller_workspace(user_id)["shop"]


def order_items_for_response(connection: sqlite3.Connection, order_id: str) -> list[dict]:
    rows = connection.execute(
        """
        SELECT order_items.product_id, order_items.title_snapshot, order_items.image_url_snapshot,
               order_items.unit_price_cents, order_items.quantity, order_items.specifications_snapshot,
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
        where, params = ["products.status = 'published'"], []
        if category and category != "全部":
            where.append("products.category = ?")
            params.append(category)
        search_terms = semantic_expanded_terms(list(dict.fromkeys(normalize_search_term(term) for term in (terms or [keyword]) if normalize_search_term(term)))[:12])
        rows = connection.execute(
            f"""
            SELECT products.id, products.title, products.description, products.material, products.category,
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
        title, description, material, product_category, shop, tags = (str(row[key] or "").lower() for key in ("title", "description", "material", "category", "shop_name", "tags"))
        value = min(int(row["sales"] or 0), 100) * 0.18
        for term in search_terms:
            if title == term:
                value += 150
            elif title.startswith(term):
                value += 92
            elif term in title:
                value += 56
            if term in tags:
                value += 38
            if term in product_category or term in material:
                value += 27
            if term in description:
                value += 14
            if term in shop:
                value += 9
        semantic_text = " ".join((title, description, material, product_category, shop, tags))
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
        records = [row for row in records if any(term in " ".join(str(row[key] or "").lower() for key in ("title", "description", "material", "category", "shop_name", "tags")) for term in search_terms)]
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
        for row in connection.execute("SELECT title FROM products WHERE status = 'published' AND lower(title) LIKE ? ORDER BY published_at DESC LIMIT 5", (f"%{term}%",)):
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
    days = 7 if days == 7 else 30
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


def shop_charge(connection: sqlite3.Connection, shop_id: str, buyer_user_id: str, item_amount: int, quantity: int, provisional_usage: dict[str, tuple[int, int]] | None = None) -> tuple[int, int, dict | None]:
    shop = connection.execute(
        "SELECT shipping_template_json, coupons_json FROM shops WHERE id = ?", (shop_id,)
    ).fetchone()
    shipping = json.loads(shop["shipping_template_json"] or "{}") if shop else {}
    first_fee = max(0, int(round(number(shipping.get("firstFee")) * 100)))
    additional_fee = max(0, int(round(number(shipping.get("additionalFee")) * 100)))
    free_threshold = number(shipping.get("freeShippingThreshold"))
    shipping_amount = 0 if free_threshold and item_amount >= int(round(free_threshold * 100)) else first_fee + max(0, quantity - 1) * additional_fee
    coupons = json.loads(shop["coupons_json"] or "[]") if shop else []
    eligible = [coupon for coupon in coupons if item_amount >= int(round(number(coupon.get("threshold")) * 100))]
    discount = max((int(round(number(coupon.get("discount")) * 100)) for coupon in eligible), default=0)
    campaign = platform_campaign_for_charge(connection, buyer_user_id, item_amount, provisional_usage)
    discount += campaign["discount"] if campaign else 0
    return shipping_amount, min(discount, item_amount + shipping_amount), campaign


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
            self.stop_event.wait(self.interval_seconds)


def message_row_for_response(row: sqlite3.Row) -> dict:
    message_type = row["message_type"] or "text"
    order = None
    if row["order_id"]:
        order = {
            "id": row["order_id"],
            "orderNo": row["order_no"],
            "status": ORDER_STATUS_LABELS.get(row["order_status"], row["order_status"]),
            "amount": number(row["order_amount"]) / 100,
            "title": row["order_title"] or "订单作品",
            "image": row["order_image"],
        }
    return {
        "id": row["id"], "cursor": row["message_cursor"], "shopId": row["shop_id"], "shop": row["shop_name"],
        "buyerUserId": row["buyer_user_id"], "buyer": row["buyer_name"],
        "sender": row["sender_role"], "senderUserId": row["sender_user_id"], "type": message_type, "content": row["content"],
        "attachmentUrl": row["attachment_url"], "order": order,
        "read": bool(row["read_at"]), "createdAt": row["created_at"],
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
               (SELECT image_url_snapshot FROM order_items WHERE order_items.order_id = orders.id ORDER BY rowid LIMIT 1) AS order_image
        FROM shop_messages
        JOIN shops ON shops.id = shop_messages.shop_id
        JOIN users ON users.id = shop_messages.buyer_user_id
        LEFT JOIN orders ON orders.id = shop_messages.order_id
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
            conversations[key] = {"shopId": message["shopId"], "shop": message["shop"], "buyerUserId": message["buyerUserId"], "buyer": message["buyer"], "preview": conversation_preview(message), "lastMessageAt": message["createdAt"], "unread": 0}
        if message["sender"] == "buyer" and not message["read"]:
            conversations[key]["unread"] += 1
    messages: list[dict] = []
    if shop_id or buyer_id:
        if not shop_id or not buyer_id or shop_id not in shop_ids or (shop_id, buyer_id) not in conversations:
            raise ValueError("会话不存在")
        connection.execute("UPDATE shop_messages SET read_at = CURRENT_TIMESTAMP WHERE shop_id = ? AND buyer_user_id = ? AND sender_role = 'buyer' AND read_at IS NULL", (shop_id, buyer_id))
        messages = [message_row_for_response(row) for row in message_rows(connection, "shop_messages.shop_id = ? AND shop_messages.buyer_user_id = ?", (shop_id, buyer_id))]
    return {"conversations": list(conversations.values()), "messages": messages}


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
        rows = connection.execute("SELECT * FROM support_tickets WHERE buyer_user_id = ? ORDER BY updated_at DESC", (user_id,)).fetchall()
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
            "SELECT payment_method, status, provider_reference, paid_at, initiated_at, failure_reason FROM payment_transactions WHERE order_id = ?",
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
                "discountAmount": order["discount_amount_cents"] / 100,
                "platformCampaign": ({"id": campaign["id"], "name": campaign["name"], "discountAmount": campaign["discount_amount_cents"] / 100, "status": campaign["status"]} if campaign else None),
                "resourceEvents": resource_events,
                "amount": order["paid_amount_cents"] / 100,
                "payment": (
                    {
                        "method": payment["payment_method"],
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
        payment_method = str(payload.get("paymentMethod") or "alipay")
        channel = analytics_channel(payload.get("channel"))
        if payment_method not in ("alipay", "card"):
            raise ValueError("不支持的支付方式")

        created_ids: list[str] = []
        for shop_id, items in grouped.items():
            order_id = f"order-{secrets.token_urlsafe(12)}"
            order_no = f"SZ{datetime.now().strftime('%y%m%d%H%M%S')}{secrets.randbelow(900) + 100}"
            item_amount = sum(item[1]["price_cents"] * item[2] for item in items)
            shipping_amount, discount_amount, campaign = shop_charge(
                connection, shop_id, user_id, item_amount, sum(item[2] for item in items)
            )
            amount = item_amount + shipping_amount - discount_amount
            connection.execute(
                """
                INSERT INTO orders (id, order_no, buyer_user_id, shop_id, address_snapshot, item_amount_cents, shipping_amount_cents, discount_amount_cents, paid_amount_cents, attribution_channel, status, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending_payment', datetime('now', '+30 minutes'))
                """,
                (order_id, order_no, user_id, shop_id, json.dumps(address_for_response(address), ensure_ascii=False), item_amount, shipping_amount, discount_amount, amount, channel),
            )
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
                "INSERT INTO payment_transactions (id, order_id, payment_method, amount_cents, payment_token) VALUES (?, ?, ?, ?, ?)",
                (f"payment-{secrets.token_urlsafe(10)}", order_id, payment_method, amount, f"pay-{secrets.token_urlsafe(18)}"),
            )
            for product, sku, quantity, variants, activity_id in items:
                order_item_id = f"item-{secrets.token_urlsafe(10)}"
                cover = connection.execute(
                    "SELECT public_url FROM product_media WHERE product_id = ? ORDER BY is_cover DESC, sort_order LIMIT 1",
                    (product["id"],),
                ).fetchone()
                connection.execute(
                    """
                    INSERT INTO order_items (id, order_id, product_id, sku_id, title_snapshot, image_url_snapshot, specifications_snapshot, unit_price_cents, quantity, subtotal_cents)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        order_item_id, order_id, product["id"], sku["id"], product["title"],
                        cover[0] if cover else None, json.dumps(variants, ensure_ascii=False), sku["price_cents"], quantity,
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
        if not connection.execute("SELECT 1 FROM buyer_addresses WHERE id = ? AND buyer_user_id = ?", (address_id, user_id)).fetchone():
            raise ValueError("请选择收货地址")
        groups = checkout_groups(connection, raw_items)
        record_analytics_event(connection, "checkout_started", user_id=user_id, channel=payload.get("channel"))
        shops = []
        provisional_usage: dict[str, tuple[int, int]] = {}
        provisional_activity_usage: dict[str, int] = {}
        item_total = shipping_total = discount_total = 0
        for shop_id, items in groups.items():
            amount = sum(item[1]["price_cents"] * item[2] for item in items)
            shipping, discount, campaign = shop_charge(connection, shop_id, user_id, amount, sum(item[2] for item in items), provisional_usage)
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
            shops.append({"shopId": shop_id, "shop": shop_name, "itemAmount": amount / 100, "shippingAmount": shipping / 100, "discountAmount": discount / 100, "amount": (amount + shipping - discount) / 100, "platformCampaign": campaign["name"] if campaign else None, "activities": activity_items})
            item_total += amount
            shipping_total += shipping
            discount_total += discount
        return {"shops": shops, "itemAmount": item_total / 100, "shippingAmount": shipping_total / 100, "discountAmount": discount_total / 100, "amount": (item_total + shipping_total - discount_total) / 100}


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
        SELECT after_sale_requests.*, orders.order_no, shops.location AS return_address
        FROM after_sale_requests
        JOIN orders ON orders.id = after_sale_requests.order_id
        JOIN shops ON shops.id = orders.shop_id
        WHERE {where} ORDER BY after_sale_requests.created_at DESC
        """,
        params,
    ).fetchall()
    def status_label(row: sqlite3.Row) -> str:
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

    return [
        {
            "id": row["id"],
            "orderId": row["order_no"],
            "type": "退款" if row["request_type"] == "refund" else "退货退款",
            "reason": row["reason"],
            "status": status_label(row),
            "amount": row["requested_amount_cents"] / 100,
            "sellerResponse": row["seller_response"],
            "evidence": [item[0] for item in connection.execute("SELECT image_url FROM after_sale_evidence WHERE after_sale_id = ? ORDER BY sort_order", (row["id"],))],
            "returnAddress": row["return_address"],
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
    def cors_origin(self) -> str:
        origin = self.headers.get("Origin", "")
        if origin.startswith("http://127.0.0.1:") or origin.startswith("http://localhost:"):
            return origin
        return "http://127.0.0.1:5174"

    def send_json(self, status: int, payload: dict, cookie: str | None = None) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Access-Control-Allow-Origin", self.cors_origin())
        self.send_header("Access-Control-Allow-Credentials", "true")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

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

    def do_OPTIONS(self) -> None:
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", self.cors_origin())
        self.send_header("Access-Control-Allow-Methods", "GET, POST, PUT, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-Admin-Step-Up")
        self.send_header("Access-Control-Allow-Credentials", "true")
        self.end_headers()

    def do_GET(self) -> None:
        if self.path == "/health":
            self.send_json(200, {"ok": True})
        elif self.path.startswith("/media/"):
            self.send_media(self.path.removeprefix("/media/"))
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
                profile = connection.execute("SELECT verification_status, legal_name, identity_number, contact_phone, verification_expires_at, verification_expiry_notified_at FROM seller_profiles WHERE user_id = ?", (user_id,)).fetchone()
                application = connection.execute("SELECT * FROM seller_verification_applications WHERE seller_user_id = ? ORDER BY created_at DESC LIMIT 1", (user_id,)).fetchone()
                expired = bool(profile and profile["verification_status"] == "approved" and profile["verification_expires_at"] and profile["verification_expires_at"] <= datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"))
                if expired and not profile["verification_expiry_notified_at"]:
                    connection.execute("UPDATE seller_profiles SET verification_expiry_notified_at = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,))
                    notify_governance(connection, user_id, "seller_verification_expired", "卖家认证已到期", "请提交新的认证资料后继续经营", "seller_verification", application["id"] if application else user_id)
                verification = {"status": "expired" if expired else (profile["verification_status"] if profile else "pending"), "legalName": profile["legal_name"] if profile else "", "identityNumber": profile["identity_number"] if profile else "", "contactPhone": profile["contact_phone"] if profile else "", "expiresAt": profile["verification_expires_at"] if profile else None, "application": None if not application else verification_application_response(connection, application)}
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
                    ORDER BY CASE products.moderation_status WHEN 'pending' THEN 0 WHEN 'rejected' THEN 1 ELSE 2 END,
                             products.updated_at DESC
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
                    "SELECT id, title, content, audience, published_at FROM platform_announcements WHERE status = 'published' ORDER BY published_at DESC LIMIT 10"
                ).fetchall()
                roles = {row[0] for row in connection.execute("SELECT role FROM user_roles WHERE user_id = ?", (user_id,))} if user_id else set()
            audiences = {"all"}
            if "buyer" in roles:
                audiences.add("buyer")
            if "seller" in roles:
                audiences.add("seller")
            self.send_json(200, {"announcements": [{"id": row["id"], "title": row["title"], "content": row["content"], "audience": row["audience"], "publishedAt": row["published_at"]} for row in rows if row["audience"] in audiences]})
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
            self.send_json(200, {"announcements": [{"id": row["id"], "title": row["title"], "content": row["content"], "audience": row["audience"], "status": row["status"], "publishedAt": row["published_at"]} for row in announcements], "campaigns": campaigns})
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
            self.send_json(200, {"account": account})
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
        elif urlparse(self.path).path == "/api/analytics/seller":
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            with database() as connection:
                if not is_seller(connection, user_id):
                    self.send_json(403, {"error": "Seller access required"})
                    return
            days = int(parse_qs(urlparse(self.path).query).get("days", ["30"])[0])
            self.send_json(200, {"analytics": seller_analytics(user_id, days)})
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
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode("utf-8"))
            if self.path == "/api/integrations/customer-service/webhooks":
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
            elif self.path == "/api/campaign-codes/redeem":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                code = re.sub(r"\s+", "", str(payload.get("code") or "").upper())
                with database() as connection:
                    connection.row_factory = sqlite3.Row
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
                event_type = str(payload.get("type") or "")
                product_id = str(payload.get("productId") or "") or None
                if event_type != "product_view" or not product_id:
                    raise ValueError("Invalid analytics event")
                with database() as connection:
                    product = connection.execute("SELECT shop_id FROM products WHERE id = ? AND status = 'published'", (product_id,)).fetchone()
                    if not product:
                        raise ValueError("Product not found")
                    record_analytics_event(connection, "product_view", visitor_key=str(payload.get("visitorKey") or "")[:100], user_id=session_user(self), shop_id=product[0], product_id=product_id, channel=payload.get("channel"))
                self.send_json(201, {"ok": True})
            elif self.path == "/api/media":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                media_type = str(payload.get("mediaType") or "")
                if media_type not in ("image", "video"):
                    raise ValueError("媒体类型无效")
                mime_type, binary = decode_media_data_url(payload.get("data"), media_type)
                MEDIA_DIR.mkdir(parents=True, exist_ok=True)
                filename = f"{media_type}-{secrets.token_urlsafe(16)}{(IMAGE_MIME_TYPES if media_type == 'image' else VIDEO_MIME_TYPES)[mime_type]}"
                (MEDIA_DIR / filename).write_bytes(binary)
                asset_id = f"asset-{secrets.token_urlsafe(12)}"
                with database() as connection:
                    connection.execute(
                        "INSERT INTO media_assets (id, uploader_user_id, media_type, mime_type, storage_key, public_url, byte_size) VALUES (?, ?, ?, ?, ?, ?, ?)",
                        (asset_id, user_id, media_type, mime_type, filename, f"/media/{filename}", len(binary)),
                    )
                self.send_json(201, {"id": asset_id, "url": f"/media/{filename}", "mediaType": media_type, "size": len(binary)})
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
                require_admin_step_up(self, user_id)
                announcement_id = str(payload.get("id") or f"announcement-{secrets.token_urlsafe(10)}")
                title, content = str(payload.get("title") or "").strip(), str(payload.get("content") or "").strip()
                audience, status = str(payload.get("audience") or "all"), str(payload.get("status") or "draft")
                if not title or not content or len(title) > 80 or len(content) > 500 or audience not in ("all", "buyer", "seller") or status not in ("draft", "published", "archived"):
                    raise ValueError("公告内容或状态无效")
                with database() as connection:
                    connection.execute(
                        """
                        INSERT INTO platform_announcements (id, title, content, audience, status, published_at, created_by_user_id)
                        VALUES (?, ?, ?, ?, ?, CASE WHEN ? = 'published' THEN CURRENT_TIMESTAMP END, ?)
                        ON CONFLICT(id) DO UPDATE SET title = excluded.title, content = excluded.content, audience = excluded.audience,
                          status = excluded.status, published_at = CASE WHEN excluded.status = 'published' THEN COALESCE(platform_announcements.published_at, CURRENT_TIMESTAMP) ELSE platform_announcements.published_at END,
                          updated_at = CURRENT_TIMESTAMP
                        """,
                        (announcement_id, title, content, audience, status, status, user_id),
                    )
                    write_platform_audit(connection, user_id, f"announcement_{status}", "announcement", announcement_id, {"audience": audience})
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
                require_admin_step_up(self, user_id)
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
                require_admin_step_up(self, user_id)
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
                require_admin_step_up(self, user_id)
                product_ids = list(dict.fromkeys(str(item) for item in payload.get("productIds") or [] if str(item)))[:100]
                decision, reason = str(payload.get("decision") or ""), str(payload.get("reason") or "").strip()
                if not product_ids or decision not in ("approved", "rejected") or (decision == "rejected" and not reason):
                    raise ValueError("批量审核参数无效")
                with database() as connection:
                    placeholders = ",".join("?" for _ in product_ids)
                    found = {row[0] for row in connection.execute(f"SELECT id FROM products WHERE id IN ({placeholders})", tuple(product_ids))}
                    if len(found) != len(product_ids):
                        raise ValueError("包含不存在的作品")
                    for product_id in product_ids:
                        connection.execute("UPDATE products SET moderation_status = ?, moderation_reason = ?, moderated_at = CURRENT_TIMESTAMP, status = CASE WHEN ? = 'rejected' THEN 'unlisted' ELSE status END, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (decision, reason or None, decision, product_id))
                        write_moderation_log(connection, product_id, f"bulk:{decision}:{reason}", decision, reason or None)
                        complete_governance_task(connection, "product_moderation", product_id, user_id)
                    write_platform_audit(connection, user_id, f"products_bulk_{decision}", "product", ",".join(product_ids), {"count": len(product_ids), "reason": reason})
                self.send_json(200, {"ok": True, "count": len(product_ids)})
            elif self.path.startswith("/api/admin/enforcement/templates/") and self.path.endswith("/apply"):
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                require_admin(user_id)
                require_admin_step_up(self, user_id)
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
                require_admin_step_up(self, user_id)
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
                require_admin_step_up(self, user_id)
                product_id = self.path.removeprefix("/api/admin/moderation/products/").rstrip("/")
                decision = str(payload.get("decision") or "")
                reason = str(payload.get("reason") or "").strip()
                if decision not in ("approved", "rejected"):
                    raise ValueError("审核决定无效")
                if decision == "rejected" and not reason:
                    raise ValueError("请填写驳回原因")
                with database() as connection:
                    product = connection.execute("SELECT id FROM products WHERE id = ?", (product_id,)).fetchone()
                    if not product:
                        raise ValueError("作品不存在")
                    connection.execute(
                        "UPDATE products SET moderation_status = ?, moderation_reason = ?, moderated_at = CURRENT_TIMESTAMP, status = CASE WHEN ? = 'rejected' THEN 'unlisted' ELSE status END, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (decision, reason or None, decision, product_id),
                    )
                    write_moderation_log(connection, product_id, f"manual:{decision}:{reason}", decision, reason or None)
                    complete_governance_task(connection, "product_moderation", product_id, user_id)
                    write_platform_audit(connection, user_id, f"product_{decision}", "product", product_id, {"reason": reason})
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
                    if existing: connection.execute(f"DELETE FROM {table} WHERE buyer_user_id = ? AND {field} = ?", (user_id, target))
                    else: connection.execute(f"INSERT INTO {table} (buyer_user_id, {field}) VALUES (?, ?)", (user_id, target))
                    self.send_json(200, buyer_state(connection, user_id))
            elif self.path == "/api/messages/buyer":
                user_id = session_user(self)
                shop_id, content = str(payload.get("shopId") or ""), str(payload.get("content") or "").strip()
                message_type = str(payload.get("type") or "text")
                attachment_url = str(payload.get("attachmentUrl") or "").strip() or None
                order_id = str(payload.get("orderId") or "").strip() or None
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                if not shop_id or message_type not in ("text", "image", "order"):
                    raise ValueError("消息参数无效")
                if message_type == "text" and not content:
                    raise ValueError("请输入消息内容")
                if message_type == "image" and not attachment_url:
                    raise ValueError("请上传图片")
                if message_type == "order" and not order_id:
                    raise ValueError("请选择订单")
                if len(content) > 500:
                    raise ValueError("消息不能超过 500 个字符")
                with database() as connection:
                    if not connection.execute("SELECT 1 FROM shops WHERE id = ?", (shop_id,)).fetchone():
                        raise ValueError("店铺不存在")
                    if order_id and not connection.execute("SELECT 1 FROM orders WHERE id = ? AND buyer_user_id = ? AND shop_id = ?", (order_id, user_id, shop_id)).fetchone():
                        raise ValueError("只能发送当前店铺的订单卡片")
                    message_id = f"message-{secrets.token_urlsafe(10)}"
                    connection.execute("INSERT INTO shop_messages (id, shop_id, buyer_user_id, sender_role, sender_user_id, content, message_type, attachment_url, order_id) VALUES (?, ?, ?, 'buyer', ?, ?, ?, ?, ?)", (message_id, shop_id, user_id, user_id, content, message_type, attachment_url, order_id))
                    if attachment_url:
                        link_media_assets(connection, [attachment_url], "message", message_id)
                    owner = connection.execute("SELECT owner_user_id FROM shops WHERE id = ?", (shop_id,)).fetchone()
                    if owner: notify_governance(connection, owner[0], "buyer_message", "收到买家消息", content[:80], "shop", shop_id)
                self.send_json(201, {"ok": True})
            elif self.path == "/api/messages/seller":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                shop_id, buyer_id, content = str(payload.get("shopId") or ""), str(payload.get("buyerUserId") or ""), str(payload.get("content") or "").strip()
                message_type = str(payload.get("type") or "text")
                attachment_url = str(payload.get("attachmentUrl") or "").strip() or None
                order_id = str(payload.get("orderId") or "").strip() or None
                if not shop_id or not buyer_id or message_type not in ("text", "image", "order"):
                    raise ValueError("消息参数无效")
                if message_type == "text" and not content:
                    raise ValueError("请输入回复内容")
                if message_type == "image" and not attachment_url:
                    raise ValueError("请上传图片")
                if message_type == "order" and not order_id:
                    raise ValueError("请选择订单")
                if len(content) > 500:
                    raise ValueError("消息不能超过 500 个字符")
                with database() as connection:
                    require_shop_permission(connection, user_id, shop_id, "messages")
                    if order_id and not connection.execute("SELECT 1 FROM orders WHERE id = ? AND buyer_user_id = ? AND shop_id = ?", (order_id, buyer_id, shop_id)).fetchone():
                        raise ValueError("只能发送当前会话买家的订单卡片")
                    message_id = f"message-{secrets.token_urlsafe(10)}"
                    connection.execute("INSERT INTO shop_messages (id, shop_id, buyer_user_id, sender_role, sender_user_id, content, message_type, attachment_url, order_id) VALUES (?, ?, ?, 'seller', ?, ?, ?, ?, ?)", (message_id, shop_id, buyer_id, user_id, content, message_type, attachment_url, order_id))
                    if attachment_url:
                        link_media_assets(connection, [attachment_url], "message", message_id)
                    notify_governance(connection, buyer_id, "seller_message", "收到店铺回复", content[:80], "shop", shop_id)
                    audit_delegated_shop_operation(connection, user_id, shop_id, "buyer_message_sent", {"messageType": message_type, "buyerUserId": buyer_id})
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
                documents = [item for item in payload.get("documents") or [] if isinstance(item, dict) and str(item.get("url") or "").startswith(("/media/", "http://", "https://"))][:8]
                if not 2 <= len(legal_name) <= 80 or not 6 <= len(identity_number) <= 32 or not re.fullmatch(r"\d{6,20}", contact_phone) or business_type not in ("individual", "enterprise") or (business_type == "enterprise" and (not representative or not license_no or not address)):
                    raise ValueError("请完整填写认证信息")
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    if not is_seller(connection, user_id):
                        self.send_json(403, {"error": "Seller access required"})
                        return
                    pending = connection.execute("SELECT id FROM seller_verification_applications WHERE seller_user_id = ? AND status = 'pending'", (user_id,)).fetchone()
                    if pending:
                        raise ValueError("已有认证申请正在审核，请等待审核结果")
                    application_id = f"verification-{secrets.token_urlsafe(10)}"
                    prior = connection.execute("SELECT id, review_round FROM seller_verification_applications WHERE seller_user_id = ? AND status = 'rejected' ORDER BY reviewed_at DESC LIMIT 1", (user_id,)).fetchone()
                    review_round = int(prior["review_round"] or 1) + 1 if prior else 1
                    connection.execute("INSERT INTO seller_verification_applications (id, seller_user_id, legal_name, identity_number, contact_phone, evidence_json, business_type, legal_representative, business_license_no, business_address, resubmission_of, review_round) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", (application_id, user_id, legal_name, identity_number, contact_phone, json.dumps(evidence, ensure_ascii=False), business_type, representative or None, license_no or None, address or None, prior["id"] if prior else None, review_round))
                    for document in documents:
                        document_type = str(document.get("type") or "other")
                        connection.execute("INSERT INTO seller_verification_documents (id, application_id, document_type, file_url) VALUES (?, ?, ?, ?)", (f"verification-document-{secrets.token_urlsafe(8)}", application_id, document_type if document_type in ("identity_front", "identity_back", "business_license", "authorization", "other") else "other", str(document["url"])))
                    connection.execute("INSERT INTO seller_profiles (user_id, verification_status, legal_name, identity_number, contact_phone) VALUES (?, 'pending', ?, ?, ?) ON CONFLICT(user_id) DO UPDATE SET verification_status = 'pending', legal_name = excluded.legal_name, identity_number = excluded.identity_number, contact_phone = excluded.contact_phone", (user_id, legal_name, identity_number, contact_phone))
                    link_media_assets(connection, evidence, "seller_verification", application_id)
                    write_platform_audit(connection, user_id, "seller_verification_submitted", "seller_verification", application_id)
                self.send_json(201, {"id": application_id, "status": "pending"})
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
                        INSERT INTO buyer_addresses (id, buyer_user_id, recipient_name, recipient_phone, province, city, district, detail, postal_code, is_default)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (address_id, user_id, recipient, phone, province, city, district, detail, str(payload.get("postalCode") or "").strip() or None, int(make_default)),
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
                    connection.execute("UPDATE orders SET status = 'shipped', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (order["id"],))
                    connection.execute("INSERT INTO shipments (id, order_id, carrier, tracking_no, status) VALUES (?, ?, ?, ?, 'in_transit')", (shipment_id, order["id"], carrier, tracking_no))
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
                    if order["status"] not in ("shipped", "delivered"):
                        raise ValueError("该订单尚未发货")
                    connection.execute("UPDATE orders SET status = 'completed', completed_at = CURRENT_TIMESTAMP, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (order["id"],))
                    connection.execute("UPDATE shipments SET status = 'delivered', delivered_at = CURRENT_TIMESTAMP WHERE order_id = ?", (order["id"],))
                    release_order_settlement(connection, order["id"])
                    owner = connection.execute("SELECT owner_user_id FROM shops WHERE id = ?", (order["shop_id"],)).fetchone()
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
                        INSERT INTO after_sale_requests (id, order_id, order_item_id, buyer_user_id, request_type, reason, requested_amount_cents, order_status_before)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (request_id, order["id"], item["id"] if item else None, user_id, request_type, str(payload.get("reason") or "七天无理由退款"), amount, order["status"]),
                    )
                    connection.executemany("INSERT INTO after_sale_evidence (id, after_sale_id, image_url, sort_order) VALUES (?, ?, ?, ?)", [(f"evidence-{secrets.token_urlsafe(8)}", request_id, image, index) for index, image in enumerate(evidence)])
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
                    restore_order_inventory(connection, request["order_id"], status="reversed")
                    connection.execute("UPDATE orders SET status = 'refunded', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (request["order_id"],))
                    reverse_order_settlement(connection, request["order_id"])
                    set_campaign_redemption_status(connection, request["order_id"], "reversed")
                    set_activity_allocation_status(connection, request["order_id"], "reversed")
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
                        restore_order_inventory(connection, request["order_id"], status="reversed")
                        connection.execute("UPDATE orders SET status = 'refunded', updated_at = CURRENT_TIMESTAMP WHERE id = ?", (request["order_id"],))
                        reverse_order_settlement(connection, request["order_id"])
                        set_campaign_redemption_status(connection, request["order_id"], "reversed")
                        set_activity_allocation_status(connection, request["order_id"], "reversed")
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
                if confirmation != "注销账号":
                    raise ValueError("请输入“注销账号”确认操作")
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
                client_ip = self.client_address[0]
                if not login_allowed(client_ip):
                    self.send_json(429, {"error": "登录失败次数过多，请 10 分钟后再试"})
                    return
                with database() as connection:
                    connection.row_factory = sqlite3.Row
                    user = connection.execute("SELECT * FROM users WHERE status = 'active' AND (phone = ? OR lower(email) = ?)", (identifier, identifier)).fetchone()
                valid, legacy = verify_password(password, user["password_hash"]) if user else (False, False)
                if not user or not valid:
                    register_login_failure(client_ip)
                    with database() as connection:
                        write_login_audit(connection, identifier, False, self, user["id"] if user else None, "invalid_credentials")
                    self.send_json(401, {"error": "账号或密码不正确"})
                    return
                LOGIN_FAILURES.pop(client_ip, None)
                if legacy:
                    with database() as connection:
                        connection.execute("UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (hash_password(password), user["id"]))
                with database() as connection:
                    connection.execute("UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?", (user["id"],))
                    write_login_audit(connection, identifier, True, self, user["id"])
                token = create_session(user["id"], self)
                self.send_json(200, {"account": account_for_user(user["id"])}, session_cookie(token))
            elif self.path == "/api/auth/request-verification":
                destination = str(payload.get("destination") or "").strip().lower()
                purpose = str(payload.get("purpose") or "")
                registration = bool(payload.get("registration"))
                if purpose not in ("contact_verify", "password_reset") or not destination:
                    raise ValueError("验证请求无效")
                authenticated_user_id = session_user(self)
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
                self.send_json(200, {"ok": True, **({"developmentCode": code} if not PRODUCTION_HTTPS else {})})
            elif self.path == "/api/auth/request-admin-step-up":
                user_id = session_user(self)
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
                with database() as connection:
                    if not is_admin(connection, user_id):
                        self.send_json(403, {"error": "Administrator access required"})
                        return
                    destination = admin_verification_destination(connection, user_id)
                    code = issue_verification(connection, user_id, destination, "admin_step_up")
                self.send_json(200, {"ok": True, **({"developmentCode": code} if not PRODUCTION_HTTPS else {})})
            elif self.path == "/api/auth/confirm-admin-step-up":
                user_id = session_user(self)
                code = str(payload.get("code") or "").strip()
                if not user_id:
                    self.send_json(401, {"error": "Unauthorized"})
                    return
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
                        "INSERT INTO admin_step_up_tickets (id, user_id, ticket_hash, expires_at) VALUES (?, ?, ?, datetime('now', '+10 minutes'))",
                        (f"step-up-{secrets.token_urlsafe(10)}", user_id, token_hash(ticket)),
                    )
                self.send_json(200, {"ticket": ticket, "expiresIn": 600})
            elif self.path == "/api/auth/reset-password":
                destination = str(payload.get("destination") or "").strip().lower()
                code, password = str(payload.get("code") or ""), str(payload.get("password") or "")
                if len(password) < 8:
                    raise ValueError("密码至少需要 8 位")
                with database() as connection:
                    verification = consume_verification(connection, destination, "password_reset", code)
                    if not verification or not verification["user_id"]:
                        raise ValueError("验证码无效或已过期")
                    connection.execute("UPDATE users SET password_hash = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (hash_password(password), verification["user_id"]))
                    connection.execute("DELETE FROM web_sessions WHERE user_id = ?", (verification["user_id"],))
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
                user_id = f"user-{int(datetime.now().timestamp() * 1000)}"
                name = (payload.get("name") or "").strip()
                phone = (payload.get("phone") or "").strip() or None
                email = (payload.get("email") or "").strip().lower() or None
                password = payload.get("password") or ""
                confirm_password = payload.get("confirmPassword") or ""
                phone_verification_code = str(payload.get("phoneVerificationCode") or "").strip()
                role = payload.get("role") if payload.get("role") in ("buyer", "seller") else "buyer"
                seller_profile = payload.get("sellerProfile") if isinstance(payload.get("sellerProfile"), dict) else {}
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
                real_name = str(seller_profile.get("realName") or "").strip()
                identity_number = str(seller_profile.get("identityNumber") or "").strip()
                business_address = str(seller_profile.get("address") or "").strip()
                payout_provider = str(seller_profile.get("payoutProvider") or "lianlian")
                categories = []
                for category in seller_profile.get("operatingCategories") or []:
                    value = str(category).strip()
                    if value and value not in categories:
                        categories.append(value)
                if role == "seller":
                    if not phone_verification_code:
                        raise ValueError("请先完成手机号验证")
                    if not 2 <= len(real_name) <= 80 or not 6 <= len(identity_number) <= 32 or not 5 <= len(business_address) <= 300:
                        raise ValueError("请完整填写真实姓名、身份证号和经营地址")
                    if payout_provider != "lianlian":
                        raise ValueError("目前仅支持绑定连连收款账户")
                    if not categories or len(categories) > 10 or any(category not in SELLER_OPERATING_CATEGORIES for category in categories):
                        raise ValueError("请至少选择一个有效的经营类目")
                with database() as connection:
                    if role == "seller":
                        verification = consume_verification(connection, phone, "contact_verify", phone_verification_code)
                        if not verification or verification["user_id"] is not None:
                            raise ValueError("手机号验证码无效或已过期")
                    connection.execute("INSERT INTO users (id, display_name, phone, email, password_hash) VALUES (?, ?, ?, ?, ?)", (user_id, name, phone, email, hash_password(password)))
                    connection.execute("INSERT INTO user_roles (user_id, role) VALUES (?, ?)", (user_id, role))
                    if role == "seller":
                        application_id = f"verification-{secrets.token_urlsafe(10)}"
                        connection.execute(
                            "INSERT INTO seller_profiles (user_id, verification_status, legal_name, identity_number, contact_phone, business_address, payout_method, payout_account, operating_categories_json, payout_provider, payout_binding_status) VALUES (?, 'pending', ?, ?, ?, ?, NULL, NULL, ?, 'lianlian', 'unbound')",
                            (user_id, real_name, identity_number, phone, business_address, json.dumps(categories, ensure_ascii=False)),
                        )
                        connection.execute(
                            "INSERT INTO seller_verification_applications (id, seller_user_id, legal_name, identity_number, contact_phone, evidence_json, business_type, business_address) VALUES (?, ?, ?, ?, ?, '[]', 'individual', ?)",
                            (application_id, user_id, real_name, identity_number, phone, business_address),
                        )
                        write_platform_audit(connection, user_id, "seller_verification_submitted", "seller_verification", application_id, {"source": "registration"})
                token = create_session(user_id, self)
                self.send_json(201, {"account": account_for_user(user_id)}, session_cookie(token))
            else:
                self.send_json(404, {"error": "Not found"})
        except StepUpRequiredError:
            self.send_json(403, {"error": "请先完成管理员二次验证"})
        except (ValueError, json.JSONDecodeError) as error:
            self.send_json(400, {"error": str(error)})
        except sqlite3.IntegrityError:
            self.send_json(409, {"error": "Phone number or email is already registered"})
        except Exception as error:
            self.send_json(500, {"error": str(error)})

    def do_PUT(self) -> None:
        if self.path.startswith("/api/admin/search-operations/"):
            user_id = session_user(self)
            if not user_id:
                self.send_json(401, {"error": "Unauthorized"})
                return
            try:
                require_admin(user_id)
                require_admin_step_up(self, user_id)
                length = int(self.headers.get("Content-Length", "0"))
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
                length = int(self.headers.get("Content-Length", "0"))
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
                length = int(self.headers.get("Content-Length", "0"))
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
                length = int(self.headers.get("Content-Length", "0"))
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
                length = int(self.headers.get("Content-Length", "0"))
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
                        "is_default": int(bool(payload.get("isDefault", existing["is_default"]))),
                    }
                    if not all(fields[key] for key in ("recipient_name", "recipient_phone", "province", "city", "district", "detail")):
                        raise ValueError("请完整填写收货地址")
                    connection.execute("UPDATE buyer_addresses SET recipient_name = ?, recipient_phone = ?, province = ?, city = ?, district = ?, detail = ?, postal_code = ?, is_default = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (*fields.values(), address_id))
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
            length = int(self.headers.get("Content-Length", "0"))
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
