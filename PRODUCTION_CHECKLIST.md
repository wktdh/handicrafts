# Production checklist

## Required API environment

Set these values in the backend service environment before enabling `HANDICRAFTS_HTTPS=1`:

```text
HANDICRAFTS_HTTPS=1
HANDICRAFTS_SESSION_SECRET=<random secret, at least 32 characters>
HANDICRAFTS_ALLOWED_ORIGINS=https://shouzuohub.com,https://www.shouzuohub.com
HANDICRAFTS_REGISTRATION_TEST_MODE=0
HANDICRAFTS_AUTO_APPROVE_SELLER_VERIFICATION=0
HANDICRAFTS_LOGISTICS_WEBHOOK_SECRET=<random webhook secret>
```

The server refuses to start in production when the session secret, allowed origins,
or test-mode settings are unsafe.

Keep payment-provider production keys unset until the company account, merchant
agreement, KYC review, and callback domains have all been approved.

## Seller message automation

The message worker persists off-hours acknowledgements and escalation jobs. Set
these values to enable email delivery; without them, in-site and browser-push
notifications continue to work but email jobs are recorded as failed.

```text
HANDICRAFTS_SMTP_HOST=smtp.example.com
HANDICRAFTS_SMTP_PORT=587
HANDICRAFTS_SMTP_USERNAME=notifications@example.com
HANDICRAFTS_SMTP_PASSWORD=<smtp-password>
HANDICRAFTS_SMTP_FROM=notifications@example.com
HANDICRAFTS_SMTP_STARTTLS=1
HANDICRAFTS_MESSAGE_AUTOMATION_SCAN_SECONDS=30
```

Urgent SMS is opt-in per shop. Configure the Tencent SMS template ID as
`TENCENT_SMS_TEMPLATE_SELLER_MESSAGE_URGENT` before enabling that setting.

## Logistics callback contract

`POST /api/integrations/logistics/webhooks`

Headers:

```text
Content-Type: application/json
X-Logistics-Signature: sha256=<hex HMAC-SHA256 of the raw request body>
```

The HMAC key is `HANDICRAFTS_LOGISTICS_WEBHOOK_SECRET`. Retries are safe when
`provider` and `eventId` are unchanged.

```json
{
  "provider": "sf",
  "eventId": "provider-event-unique-id",
  "trackingNo": "SF123456789",
  "status": "delivered",
  "occurredAt": "2026-08-17 12:00:00",
  "label": "Delivered",
  "detail": "Handed to recipient"
}
```

Supported statuses: `label_created`, `in_transit`, `exception`, `returned`, and
`delivered`. Only a valid signed `delivered` callback can automatically complete
an order; seller-entered logistics notes cannot do so.

## Nginx

Terminate TLS at Nginx, proxy `/api`, `/media`, and `/ws` to `127.0.0.1:8787`,
and add security headers for static files, especially a restrictive
`Content-Security-Policy`, `X-Content-Type-Options: nosniff`, and HSTS. Apply
rate limits to authentication, checkout, media upload, and webhook routes. In
the Nginx `http` block, define for example:

```nginx
limit_req_zone $binary_remote_addr zone=api_limit:10m rate=20r/s;
limit_req_zone $binary_remote_addr zone=auth_limit:10m rate=5r/m;
```

Then apply `limit_req zone=api_limit burst=50 nodelay;` to `/api/` and the
stricter `auth_limit` zone to `/api/auth/`.

Run a database backup and a restore rehearsal before every production release.
