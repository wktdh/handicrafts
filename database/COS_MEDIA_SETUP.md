# COS public product-media setup

The backend uploads public seller catalogue media to COS only when all of these
server-side environment variables are set:

```text
HANDICRAFTS_COS_SECRET_ID=...
HANDICRAFTS_COS_SECRET_KEY=...
HANDICRAFTS_COS_BUCKET=handicraft-platform-cn-1330129678-1330129678
HANDICRAFTS_COS_REGION=ap-guangzhou
HANDICRAFTS_COS_CDN_BASE_URL=https://cdn.shouzuohub.com
HANDICRAFTS_COS_PUBLIC_PREFIX=products
HANDICRAFTS_COS_QUARANTINE_PREFIX=quarantine
```

Use a dedicated CAM sub-account. It needs only object write, read, and delete
permission for the `products/*` and `quarantine/*` prefixes of this one bucket. Do not use the root
account credentials and never place these values in browser code or a Vite
environment variable.

With the variables present, the browser first uploads seller product media to a
private `quarantine/*` key. The backend reads it back, validates its true type
and size, removes image EXIF by decoding and re-encoding it, records the media
review decision, then permits the asset to be referenced by ID.
Only on listing publication is that verified object copied to `products/*` and
made available through the CDN. The quarantine prefix must never be attached to
a CDN distribution or a public bucket policy. Configure a COS lifecycle rule as
a secondary safeguard for stale quarantine objects.

The bucket CORS policy may permit browser `PUT` only for the signed quarantine
upload URLs; do not grant the browser credentials or public write access to
either prefix.

After publication, seller product and catalogue media return
URLs such as:

```text
https://cdn.shouzuohub.com/products/2026/08/image-....webp
```

Other generic uploads, including seller verification documents, keep using the
local private-media flow. This is intentional: do not place identity documents
or other private material in the public-read COS bucket.

Without the variables, local development falls back to `/media/...` as before.
