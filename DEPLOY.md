# Deploying to Vercel → whatsapp.prodaxis.in

This guide deploys the FastAPI app to Vercel and exposes a trimmed Swagger UI
at `https://whatsapp.prodaxis.in/docs` that your client can use to test the
two approved templates (`prodaxis_welcome`, `prodaxis_appointment_generic`)
without ever seeing the admin API key or any Meta credentials.

## What changed for the Vercel build

| Concern | How it's handled |
|---|---|
| Celery workers | Removed from the request path. `/campaigns/{id}/start` returns 409 until you bring a worker back online. |
| Webhook processing | Inlined in `POST /api/v1/webhooks/whatsapp`. Meta retries on 5xx, so a transient failure is safe. |
| File-based logs | Skipped when `VERCEL=1` (set automatically by `vercel.json`). Stdout still goes to Vercel logs. |
| Client auth | New `api_keys` table — keys are SHA-256 hashed, scoped per-template, revocable, expirable. |
| Swagger surface | Tenants / campaigns / admin / webhooks are hidden. Client `/docs` shows only messages + read-only templates. |

## 0. One-time: run the migration on Supabase

The new `api_keys` table needs to exist before any client key can be minted.
Run from your local machine (the `.venv` already has alembic):

```powershell
.\.venv\Scripts\alembic.exe upgrade head
```

This applies `alembic/versions/20260523_0002_api_keys.py` against the
`DATABASE_URL` in your `.env`.

## 1. Install the Vercel CLI and link the project

```powershell
npm i -g vercel
vercel login
vercel link
```

When `vercel link` asks for a directory, accept the project root.
It creates a `.vercel/` folder (already ignored by `.gitignore`).

## 2. Set environment variables in Vercel

Copy each line from your local `.env` into Vercel project settings
(Settings → Environment Variables → Production). Or pipe them via CLI:

```powershell
vercel env add APP_NAME production
vercel env add APP_ENV production       # value: production
vercel env add SECRET_KEY production
vercel env add API_KEY production       # this becomes the ADMIN key
vercel env add DATABASE_URL production
vercel env add REDIS_URL production
vercel env add META_APP_ID production
vercel env add META_APP_SECRET production
vercel env add META_WABA_ID production
vercel env add META_PHONE_NUMBER_ID production
vercel env add META_ACCESS_TOKEN production
vercel env add META_WEBHOOK_VERIFY_TOKEN production
vercel env add ENCRYPTION_KEY production
vercel env add SENTRY_DSN production
vercel env add CORS_ALLOWED_ORIGINS production   # value: https://whatsapp.prodaxis.in,https://prodaxis.in
```

Do **not** set `LOG_FILE_PATH` — file logging is skipped on Vercel automatically.
Do **not** set `CELERY_BROKER_URL` / `CELERY_RESULT_BACKEND` — no workers in this deployment.

## 3. Deploy

```powershell
vercel --prod
```

First deploy gives you a `https://<project>-<hash>.vercel.app` URL.
Open `/docs` on it — you should see exactly the messages + templates list endpoints.

## 4. Map whatsapp.prodaxis.in

In Vercel: **Project → Settings → Domains → Add** → `whatsapp.prodaxis.in`.

Vercel will show the DNS record it wants. At your DNS provider (wherever
`prodaxis.in` is registered):

```
Type:  CNAME
Name:  whatsapp
Value: cname.vercel-dns.com
TTL:   3600 (or default)
```

Wait 1–5 minutes for DNS to propagate, then Vercel issues a TLS cert
automatically. Confirm `curl -I https://whatsapp.prodaxis.in/api/v1/health/live`
returns `200`.

## 5. Update Meta webhook URL

Meta App dashboard → **WhatsApp → Configuration → Webhook**:

- Callback URL: `https://whatsapp.prodaxis.in/api/v1/webhooks/whatsapp`
- Verify token: same as `META_WEBHOOK_VERIFY_TOKEN` in your Vercel env.

Click **Verify and save** — Meta hits the GET endpoint with the handshake.

## 6. Mint a client API key

Once the deploy is live, create a scoped key for the client using your
**admin** key (the value of `API_KEY` you set in step 2).

```bash
curl -X POST https://whatsapp.prodaxis.in/api/v1/admin/api-keys \
  -H "X-API-Key: <YOUR_ADMIN_API_KEY>" \
  -H "Content-Type: application/json" \
  -d '{
    "label": "Client - test access",
    "allowed_templates": ["prodaxis_welcome", "prodaxis_appointment_generic"],
    "allowed_scopes": ["send_template", "read_messages", "read_templates"],
    "rate_limit_per_hour": 30,
    "expires_in_days": 30
  }'
```

The response includes `plaintext_key` **exactly once**. Save it; you cannot
retrieve it again. Hand this key to the client.

## 7. What the client sees

Send the client this:

> **Test interface:** https://whatsapp.prodaxis.in/docs
>
> **Your API key (header `X-API-Key`):** `pdx_…`
>
> You can send these two templates:
> - `prodaxis_welcome` — 1 variable (recipient name)
> - `prodaxis_appointment_generic` — 5 variables (name, doctor, date, time, contact)
>
> Use the **Try it out** button on `POST /api/v1/messages/send/template`.
> The key works only for these templates — any other `template_name` returns 403.

Nothing in `/docs`, the OpenAPI spec, or any HTTP response leaks the admin
key, the Meta access token, the database URL, or any other secret.

## 8. Revoking a key

```bash
curl -X POST https://whatsapp.prodaxis.in/api/v1/admin/api-keys/<KEY_ID>/revoke \
  -H "X-API-Key: <YOUR_ADMIN_API_KEY>"
```

Or set `is_active = false` directly in Supabase.

## Known limitations of this deployment

- **No bulk campaigns.** `/api/v1/campaigns/{id}/start` raises 409. Run the
  worker stack (docker-compose) or migrate to Railway/Render when you need it.
- **60-second request timeout.** A single send completes in ~1s, so headroom
  is generous, but template sync over a slow Meta link could near the limit.
- **No Celery beat / scheduled jobs.** If you need cron-style work, add
  Vercel Cron entries pointing at HTTP endpoints (none required today).
- **Cold starts** of ~1–2s on the first request after idle. Subsequent
  requests in the same container are fast.

## Local dev still works the same way

`uvicorn src.main:app --port 8000` continues to run with file logging and
all the existing endpoints. The `VERCEL` env var is the only thing that
toggles serverless behavior.
