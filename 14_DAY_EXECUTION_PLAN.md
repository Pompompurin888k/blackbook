# Blackbook 14-Day Execution Plan

Generated: 2026-02-17  
Scope: `innbucks.org` launch stabilization, growth, and operator-grade scaling.

## 1) North Star For The Next 14 Days

By day 14, Blackbook should be:
- Operationally stable (no critical outages, backups/restores tested)
- Moderation-fast (new profiles reviewed quickly with clear admin workflows)
- Payment-reliable (providers can self-check payment status with confidence)
- Conversion-focused (trial users move to paid plans)
- Safe and compliant in daily operations (clear moderation SOP + incident response)

## 2) Hard Targets (Track Daily)

- `Uptime`: >= 99.9% for `web`, `bot`, `admin_bot`
- `P95 callback processing`: < 10 seconds from callback receipt to activation
- `Moderation SLA`: 90% of pending profiles reviewed within 30 minutes
- `Trial -> Paid conversion`: target initial 20%+, improve weekly
- `Payment support tickets`: reduce by 50% via status-check UX
- `Backup reliability`: 100% daily backup success, at least one tested restore

## 3) Guardrails (Do Not Skip)

- Keep `ENABLE_SEED_ENDPOINT=false` in production.
- Never expose `.env` or secrets in logs/screenshots.
- Rotate leaked tokens/keys as soon as operationally safe.
- Keep admin and client bot tokens separated.
- Require verified providers before callback-based activation.

## 4) Day-By-Day Plan

## Day 1: Baseline + Instrumentation Lock
- Validate production baseline:
  - `docker-compose ps` all services healthy
  - `/health` and `/health/live` green
  - `backup.sh` executes successfully
- Create simple daily ops checklist (`ops_daily.md`) with:
  - health checks
  - log checks
  - pending verification queue
  - payment failures
- Confirm all time displays and DB session timestamps are in `Africa/Nairobi`.
- Deliverable: baseline snapshot + checklist committed.

## Day 2: Client Bot UX Pass (Uncle Panda Style)
- Finalize persistent menu flow for client bot:
  - `The Collection`, `My Profile`, `Top up Balance`, `Safety Suite`, `Affiliate Program`, `Support`
- Ensure `/start`, `My Profile`, and post-action responses always return menu keyboard.
- Improve profile card formatting:
  - structured sections: identity, stats, services, rates, languages, verification, subscription status
  - readable markdown and spacing for mobile
- Fix duplicate message behavior in profile view if still present in any branch/path.
- Deliverable: improved interaction consistency and polished profile card UX.

## Day 3: Payment Reliability UX
- Add and surface `Check payment status` button after STK initiation.
- Add explicit statuses:
  - pending
  - success
  - failed
  - callback received but awaiting activation
- Add retry-safe guidance message:
  - what to do after 30s, 2m, 5m
  - support path if still pending
- Deliverable: reduced payment confusion and fewer manual support pings.

## Day 4: Callback + Payment Drill (No Real Charges)
- Run full callback simulation script for:
  - unverified provider (expect reject)
  - verified provider (expect activate)
  - duplicate callback (expect idempotent success/ignored)
  - bad signature (expect 403)
- Store sample commands in `PAYMENT_DRILL.md`.
- Deliverable: repeatable payment validation playbook.

## Day 5: Admin Moderation Queue Upgrade
- Improve admin queue views:
  - `new today`
  - `pending > 2h`
  - `missing fields`
- Add one-tap rejection reason templates:
  - photo quality
  - mismatch identity/profile
  - incomplete profile
  - policy breach
- Ensure rejected provider receives clear next-step message.
- Deliverable: faster moderation turnaround with consistent messaging.

## Day 6: Verification Notification Reliability
- Validate cross-bot media forwarding for admin review:
  - prevent wrong file identifier errors between client/admin bot tokens
  - fallback to direct photo URL if needed
- Add alerting on failed admin queue notifications to `ADMIN_CHAT_ID`.
- Deliverable: zero silent verification notification failures.

## Day 7: Trial Conversion Automation (Mid-Trial Value)
- Ensure trial sequence includes:
  - day-2 value reminder
  - day-5 reminder
  - final-day urgency
  - 24h post-expiry winback
- Improve copy with direct CTA to top-up and clear package options.
- Add anti-spam guard so each reminder is sent once.
- Deliverable: complete retention messaging cadence live.

## Day 8: Conversion and Listing Quality Optimization
- Improve provider completion prompts:
  - missing photos
  - missing rates
  - weak bio
  - low service detail
- Add profile completion score shown in `My Profile`.
- Encourage completion before paid upgrade pitch.
- Deliverable: better listing quality and higher paid conversion readiness.

## Day 9: Affiliate Program Foundation
- Implement `/invite` referral generation and tracking.
- Rule v1:
  - referrer earns reward only when referred provider completes payment
  - anti-self-referral checks
- Reward policy (initial):
  - +2 days executive boost (or agreed equivalent)
- Add admin audit command for referral actions.
- Deliverable: working referral loop with abuse controls.

## Day 10: Ops Hardening + Fire Drill
- Run full restore drill from latest backup on a staging or temporary DB.
- Document exact restore steps and timing.
- Validate cron backups and retention cleanup behavior.
- Deliverable: proven backup/restore confidence.

## Day 11: Security Sweep
- Rotate sensitive credentials (tokens, API keys, callback secret) if safe window available.
- Confirm web surface hardening:
  - no `.env` exposure
  - no debug endpoints
  - strict callback signature validation
- Add optional IP allowlist note for payment callback path (if provider supports fixed ranges).
- Deliverable: hardened production posture.

## Day 12: Observability + Alerting
- Add concise operator alerts to admin bot for:
  - callback signature failures spike
  - repeated payment failures
  - DB connection issues
  - health endpoint failures
- Add daily summary report message:
  - new profiles
  - approved/rejected counts
  - payments success/fail
  - active subscriptions
- Deliverable: at-a-glance operational visibility from Telegram.

## Day 13: Website Conversion Polishing
- Final mobile polish on listing and profile pages:
  - faster photo interaction
  - clear call-to-action hierarchy
  - verified indicators and trust copy
- Review home copy to match premium, verified-only positioning.
- Deliverable: conversion-optimized mobile experience aligned with brand.

## Day 14: Launch Readiness Review + SOP Freeze
- Perform full checklist sign-off:
  - reliability
  - moderation SLA
  - payment flow
  - trial flow
  - backups/restores
  - alerts
- Freeze v1 SOP docs:
  - moderation SOP
  - incident response SOP
  - payment escalation SOP
- Produce `LAUNCH_READINESS_REPORT.md` with pass/fail and remaining risks.
- Deliverable: documented operator-grade launch state.

## 5) SOPs To Finalize

## Moderation SOP
- Review queue every 30 minutes during active hours.
- Approve/reject with template reasons only.
- Escalate suspicious identity patterns immediately.

## Payment SOP
- If callback missing after user paid:
  - run payment status check
  - verify callback logs
  - manually reconcile once confirmed
- Never activate on unverifiable payment evidence.

## Incident SOP
- If service unhealthy:
  - check `docker-compose ps`
  - inspect `web/bot/admin_bot` logs
  - restart affected service
  - announce status in admin channel
- If data incident:
  - run containment steps
  - rotate credentials
  - restore from verified backup if needed

## 6) KPI Dashboard (Simple Daily Table)

Track these metrics each day:
- New provider signups
- Profiles approved
- Profiles rejected
- Trial active count
- Paid active count by tier
- Callback success count
- Callback fail count
- Avg moderation time
- Support tickets (payment)

## 7) Weekly Cadence (Operator Rhythm)

- Morning (10 min): health, queue, payment errors
- Midday (10 min): conversion + trial reminder status
- Evening (10 min): backup status + unresolved incidents
- End of day (5 min): KPI snapshot message

## 8) Explicit Out-Of-Scope For This 14-Day Window

- Full in-app client/provider chat system
- AI voice verification pipeline
- Major frontend framework migration
- Complex multi-region infra changes

These can move into v1.2 after stable paid adoption.

## 9) Definition Of Success At Day 14

Blackbook is considered successful for this phase if:
- System stays stable under real-user onboarding volume
- Moderation and payment flows are predictable and fast
- Trial users consistently convert to paid plans
- Daily operations run from documented SOPs, not guesswork
- You can operate end-to-end from Telegram + lightweight server checks

