#!/usr/bin/env bash
set -euo pipefail

# Verifies payment callback guard and activation flow:
# 1) Unverified provider callback is rejected (403)
# 2) Verified provider callback is accepted (200) and activated
#
# Usage:
#   ./verify_callback_flow.sh
#   ./verify_callback_flow.sh <telegram_id>

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT_DIR"

if command -v docker-compose >/dev/null 2>&1; then
  DC="docker-compose"
elif docker compose version >/dev/null 2>&1; then
  DC="docker compose"
else
  echo "FAIL: docker-compose or docker compose is required."
  exit 1
fi

if [[ ! -f .env ]]; then
  echo "FAIL: .env file not found in $ROOT_DIR"
  exit 1
fi

get_env() {
  local key="$1"
  local val
  val="$(grep -E "^${key}=" .env | tail -n1 | cut -d= -f2- || true)"
  echo "$val"
}

db_query() {
  local sql="$1"
  $DC exec -T db psql -U bb_operator -d blackbook_db -t -A -c "$sql"
}

db_exec() {
  local sql="$1"
  $DC exec -T db psql -U bb_operator -d blackbook_db -c "$sql" >/dev/null
}

CB_URL="$(get_env "MEGAPAY_CALLBACK_URL")"
if [[ -z "$CB_URL" ]]; then
  CB_URL="https://innbucks.org/payments/callback"
fi

CB_SECRET="$(get_env "MEGAPAY_CALLBACK_SECRET")"
if [[ -z "$CB_SECRET" ]]; then
  echo "FAIL: MEGAPAY_CALLBACK_SECRET is empty in .env"
  exit 1
fi

PACKAGE_DAYS=3
AMOUNT="$(get_env "PACKAGE_PRICE_3")"
if [[ -z "$AMOUNT" ]]; then
  AMOUNT=300
fi

TG_ID="${1:-}"
if [[ -z "$TG_ID" ]]; then
  TG_ID="$(db_query "SELECT telegram_id FROM providers ORDER BY created_at DESC LIMIT 1;")"
fi
TG_ID="$(echo "$TG_ID" | tr -d '[:space:]')"

if [[ -z "$TG_ID" ]]; then
  echo "FAIL: no provider found. Create at least one provider first."
  exit 1
fi

if ! [[ "$TG_ID" =~ ^[0-9]+$ ]]; then
  echo "FAIL: telegram_id must be numeric. Got: $TG_ID"
  exit 1
fi

exists="$(db_query "SELECT COUNT(*) FROM providers WHERE telegram_id='${TG_ID}';" | tr -d '[:space:]')"
if [[ "$exists" != "1" ]]; then
  echo "FAIL: provider not found for telegram_id=$TG_ID"
  exit 1
fi

send_callback() {
  local ref="$1"
  local amount="$2"
  local tmp_file
  tmp_file="$(mktemp)"

  local payload
  payload="$(printf '{"status":"success","reference":"%s","amount":%s,"account_reference":"%s"}' "$ref" "$amount" "$ref")"
  local sig
  sig="$(printf '%s' "$payload" | openssl dgst -sha256 -hmac "$CB_SECRET" -hex | awk '{print $2}')"

  local code
  code="$(curl -sS -o "$tmp_file" -w '%{http_code}' -X POST "$CB_URL" \
    -H "Content-Type: application/json" \
    -H "X-MegaPay-Signature: sha256=$sig" \
    -d "$payload")"
  local body
  body="$(cat "$tmp_file")"
  rm -f "$tmp_file"

  echo "$code|$body"
}

echo "Running callback verification for telegram_id=$TG_ID"
echo "Callback URL: $CB_URL"

echo "Step 1/4: force provider unverified"
db_exec "UPDATE providers SET is_verified=FALSE WHERE telegram_id='${TG_ID}';"

REF1="BB_${TG_ID}_${PACKAGE_DAYS}_SIMU$(date +%s)"
echo "Step 2/4: send callback while unverified (expect HTTP 403)"
R1="$(send_callback "$REF1" "$AMOUNT")"
CODE1="${R1%%|*}"
BODY1="${R1#*|}"

echo "Unverified callback response: HTTP $CODE1 $BODY1"
if [[ "$CODE1" != "403" ]]; then
  echo "FAIL: expected HTTP 403 for unverified provider."
  exit 1
fi
if ! echo "$BODY1" | grep -q "Provider not verified"; then
  echo "FAIL: expected 'Provider not verified' response body."
  exit 1
fi

PAY1="$(db_query "SELECT status FROM payments WHERE mpesa_reference='${REF1}' ORDER BY created_at DESC LIMIT 1;" | tr -d '[:space:]')"
if [[ "$PAY1" != "REJECTED_UNVERIFIED" ]]; then
  echo "FAIL: expected payment status REJECTED_UNVERIFIED, got '${PAY1:-<empty>}'"
  exit 1
fi

echo "Step 3/4: set provider verified and send callback again (expect HTTP 200)"
db_exec "UPDATE providers SET is_verified=TRUE WHERE telegram_id='${TG_ID}';"

REF2="BB_${TG_ID}_${PACKAGE_DAYS}_SIMS$(date +%s)"
R2="$(send_callback "$REF2" "$AMOUNT")"
CODE2="${R2%%|*}"
BODY2="${R2#*|}"

echo "Verified callback response: HTTP $CODE2 $BODY2"
if [[ "$CODE2" != "200" ]]; then
  echo "FAIL: expected HTTP 200 for verified provider."
  exit 1
fi
if ! echo "$BODY2" | grep -q "Subscription activated"; then
  echo "FAIL: expected 'Subscription activated' response body."
  exit 1
fi

PAY2="$(db_query "SELECT status FROM payments WHERE mpesa_reference='${REF2}' ORDER BY created_at DESC LIMIT 1;" | tr -d '[:space:]')"
if [[ "$PAY2" != "SUCCESS" ]]; then
  echo "FAIL: expected payment status SUCCESS, got '${PAY2:-<empty>}'"
  exit 1
fi

STATE="$(db_query "SELECT is_verified::text || '|' || is_active::text || '|' || COALESCE(subscription_tier,'') || '|' || COALESCE(expiry_date::text,'') FROM providers WHERE telegram_id='${TG_ID}' LIMIT 1;")"
STATE="$(echo "$STATE" | tr -d '\r')"
IFS='|' read -r is_verified is_active tier expiry <<< "$STATE"

is_truthy() {
  local v
  v="$(echo "${1:-}" | tr '[:upper:]' '[:lower:]')"
  [[ "$v" == "t" || "$v" == "true" || "$v" == "1" || "$v" == "yes" ]]
}

echo "Step 4/4: verify provider state"
echo "State: is_verified=$is_verified is_active=$is_active tier=$tier expiry=$expiry"

if ! is_truthy "$is_verified"; then
  echo "FAIL: provider is_verified should be true."
  exit 1
fi
if ! is_truthy "$is_active"; then
  echo "FAIL: provider is_active should be true."
  exit 1
fi
if [[ -z "$tier" || "$tier" == "none" ]]; then
  echo "FAIL: subscription tier was not set."
  exit 1
fi
if [[ -z "$expiry" ]]; then
  echo "FAIL: expiry_date was not set."
  exit 1
fi

echo "PASS: callback guard and activation flow verified for telegram_id=$TG_ID"
