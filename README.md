# Blackbook

Private concierge network for verified providers.

## Tech Stack
- Bot: Python + python-telegram-bot
- Web: FastAPI + Jinja2
- Database: PostgreSQL
- Queue/Cache: Redis + ARQ
- Storage: Local uploads or Cloudflare R2

## Quick Start

```bash
git clone https://github.com/Pompompurin888k/blackbook.git
cd blackbook
cp .env.example .env
# edit .env
docker compose up -d --build
```

Web startup automatically applies SQL migrations from `web/migrations/`.

## One-Command Deploy

Run this on the server after you update code or `.env`:

```bash
bash ./deploy.sh
```

Useful options:

```bash
bash ./deploy.sh --skip-pull
bash ./deploy.sh --no-build
bash ./deploy.sh --migrate-r2         # dry-run migration after deploy
bash ./deploy.sh --migrate-r2-apply   # apply migration after deploy
```

What it does:
- Pulls latest code (`git pull --ff-only origin main`) unless skipped
- Rebuilds and starts containers
- Waits for `http://127.0.0.1:8080/health`
- Prints container status + migration-related logs

## Migrate Existing Local Photos to Cloudflare R2

New uploads already use R2 when enabled. This command migrates older `/static/uploads/...` DB references.

Dry run:

```bash
bash ./migrate_photos_to_r2.sh
```

Apply changes:

```bash
bash ./migrate_photos_to_r2.sh --apply
```

Target one provider:

```bash
bash ./migrate_photos_to_r2.sh --apply --provider-id 59
```

Requirements in `.env` before `--apply`:
- `ENABLE_CLOUDFLARE_R2_UPLOADS=true`
- `CF_R2_BUCKET`
- `CF_R2_ENDPOINT`
- `CF_R2_ACCESS_KEY_ID`
- `CF_R2_SECRET_ACCESS_KEY`
- `CF_R2_PUBLIC_BASE_URL`

## Server Ops (Frequent Commands)

```bash
# Pull + full rebuild
git pull origin main
docker compose up -d --build

# Fast restart only web
docker compose up -d --build web

# Check service status
docker compose ps

# Logs
docker compose logs -f web
docker compose logs -f worker
docker compose logs -f bot

# DB quick checks
docker compose exec db psql -U bb_operator -d blackbook_db -c "SELECT COUNT(*) FROM providers;"
docker compose exec db psql -U bb_operator -d blackbook_db -c "SELECT id, display_name, email, email_verified, account_state FROM providers WHERE COALESCE(auth_channel,'telegram')='portal' ORDER BY created_at DESC LIMIT 20;"
```

Notes:
- After `.env` changes, restart affected containers.
- For SMTP/auth or R2 config changes, restart at least `web` and `worker`.

## Email Deliverability Checklist (Brevo + Your Domain)

1. In DNS, publish and verify all Brevo records:
- SPF TXT includes Brevo sender (`include:spf.brevo.com`)
- DKIM TXT/CNAME records from Brevo (all selectors they provide)
- DMARC TXT (recommended start): `v=DMARC1; p=none; rua=mailto:postmaster@yourdomain.com`
2. In `.env`, ensure:
- `SMTP_HOST=smtp-relay.brevo.com`
- `SMTP_PORT=587`
- `SMTP_USERNAME`, `SMTP_PASSWORD`
- `SMTP_FROM_EMAIL` uses your verified sender/domain
3. Restart services:

```bash
docker compose up -d --build web worker
```

4. Watch delivery/failure logs:

```bash
docker compose logs -f web | grep -Ei "verification email sent|password-reset email sent|Failed sending|SMTP is not fully configured"
```

## Abuse Protection (Portal)

New protections:
- Register route rate limit (IP+email)
- Verify-email confirm rate limit (provider+IP)
- Verify-email regenerate rate limit (IP window + provider daily cap)
- Password reset confirm rate limit (IP+email)
- Optional Cloudflare Turnstile captcha for register, verify-email, and password-reset request

Enable captcha in `.env`:

```bash
PORTAL_CAPTCHA_ENABLED=true
PORTAL_TURNSTILE_SITE_KEY=...
PORTAL_TURNSTILE_SECRET_KEY=...
```

Tune rate limits in `.env` (defaults are already set in `.env.example`):
- `PORTAL_REGISTER_RATE_LIMIT_ATTEMPTS`, `PORTAL_REGISTER_RATE_WINDOW_SECONDS`
- `PORTAL_VERIFY_REGEN_RATE_LIMIT_ATTEMPTS`, `PORTAL_VERIFY_REGEN_RATE_WINDOW_SECONDS`
- `PORTAL_VERIFY_CONFIRM_RATE_LIMIT_ATTEMPTS`, `PORTAL_VERIFY_CONFIRM_RATE_WINDOW_SECONDS`
- `PORTAL_PASSWORD_RESET_CONFIRM_LIMIT`, `PORTAL_PASSWORD_RESET_CONFIRM_WINDOW_SECONDS`

## Features
- Provider registration/login with email verification
- Password reset flow
- Portal onboarding + dashboard
- Provider listing + recommendations
- Payments + trial activation
- Admin review and safety controls
