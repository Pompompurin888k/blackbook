# Blackbook

Private Concierge Network - Premium directory for verified professionals.

## Tech Stack
- **Bot**: Python + python-telegram-bot
- **Web**: FastAPI + Jinja2 templates
- **Database**: PostgreSQL
- **Payments**: MegaPay (M-Pesa STK Push)

## Quick Start

```bash
# Clone
git clone https://github.com/Pompompurin888k/blackbook.git
cd blackbook

# Configure
cp .env.example .env
# Edit .env with your credentials

# Deploy
docker-compose up -d
```

## Environment Variables

```env
TELEGRAM_TOKEN=your_bot_token
ADMIN_CHAT_ID=your_admin_id
PARTNER_TELEGRAM_ID=partner_id
DB_HOST=db
DB_NAME=blackbook_db
DB_USER=bb_operator
DB_PASSWORD=your_password
DB_PORT=5432
MEGAPAY_API_KEY=your_megapay_key
MEGAPAY_EMAIL=your_megapay_account_email
MEGAPAY_CALLBACK_URL=https://yourdomain.com/payments/callback
MEGAPAY_STK_ENDPOINT=https://megapay.co.ke/backend/v1/initiatestk
MEGAPAY_CALLBACK_SECRET=your_shared_callback_secret
BOOST_DURATION_HOURS=12
BOOST_PRICE=100
PACKAGE_PRICE_3=300
PACKAGE_PRICE_7=600
PACKAGE_PRICE_30=1500
PACKAGE_PRICE_90=4000
MAX_PHOTO_CACHE_ITEMS=2000
ENABLE_SEED_ENDPOINT=false
```

## Features

- ✅ Provider registration & verification
- ✅ Blue Tick verification system
- ✅ M-Pesa payment integration
- ✅ Safety suite (Blacklist, Session Timer)
- ✅ Live status toggle
- ✅ Premium website directory
