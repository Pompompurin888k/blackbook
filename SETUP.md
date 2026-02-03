# Blackbook Setup Guide

## Prerequisites
- Docker Desktop installed and running
- Telegram account
- (Optional) MegaPay account for M-Pesa payments

---

## Quick Start (5 minutes)

### 1. Get Your Telegram Bot Token

1. Open Telegram and search for `@BotFather`
2. Send `/newbot`
3. Choose a name: `Blackbook Concierge` (or any name)
4. Choose a username: `blackbook_concierge_bot` (must end in `bot`)
5. Copy the token you receive (looks like: `1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`)

### 2. Get Your Telegram User ID

1. Search for `@userinfobot` on Telegram
2. Send `/start`
3. Copy your user ID (a number like `123456789`)

### 3. Configure Environment Variables

Edit `.env` file and fill in:

```bash
# Paste your bot token from BotFather
TELEGRAM_TOKEN=1234567890:ABCdefGHIjklMNOpqrsTUVwxyz

# Paste your user ID from @userinfobot (you'll be the admin)
ADMIN_CHAT_ID=123456789
PARTNER_TELEGRAM_ID=123456789

# Change this to a secure password
DB_PASSWORD=YourSecurePassword123!
```

**Note:** MegaPay config is optional for now - the bot works without payments for testing.

### 4. Start the Project

Open terminal in the project directory and run:

```bash
docker-compose up -d --build
```

This will:
- Build the bot and web containers
- Start PostgreSQL database
- Initialize all tables automatically

### 5. Check Status

```bash
# View running containers
docker ps

# View bot logs (to see if it's connected)
docker logs blackbook_bot -f

# View web logs
docker logs blackbook_web -f
```

### 6. Test Your Bot

1. Open Telegram
2. Search for your bot username (e.g., `@blackbook_concierge_bot`)
3. Send `/start`
4. You should see the welcome message!

### 7. Access the Website

Open browser to: **http://localhost:8080**

---

## Common Issues

### Bot not responding?
```bash
# Check bot logs
docker logs blackbook_bot

# Restart bot
docker-compose restart bot
```

### Database connection error?
```bash
# Check if database is running
docker ps | grep postgres

# Restart everything
docker-compose down
docker-compose up -d
```

### Port 8080 already in use?
Edit `docker-compose.yml` and change:
```yaml
ports:
  - "8081:8080"  # Use 8081 instead
```

---

## Next Steps

1. **Register as Provider:** Send `/start` to your bot and complete registration
2. **Verify Yourself:** As admin, you'll see verification requests
3. **Test Payments:** MegaPay setup required (see Payment Setup below)
4. **Go Live:** Deploy to a server with domain

---

## Payment Setup (Optional)

### Get MegaPay Credentials

1. Sign up at https://megapay.co.ke
2. Get your API key from dashboard
3. Update `.env`:
   ```
   MEGAPAY_API_KEY=your_actual_api_key
   MEGAPAY_EMAIL=your@email.com
   MEGAPAY_CALLBACK_URL=https://yourdomain.com/payments/callback
   ```

4. Restart services:
   ```bash
   docker-compose restart bot web
   ```

---

## Production Deployment

For production on a VPS:

1. Get a domain (e.g., innbucks.org)
2. Point DNS A record to your VPS IP
3. SSH to your server
4. Clone the repo: `git clone <repo-url>`
5. Configure `.env` with production values
6. Run: `bash deploy.sh`
7. Setup HTTPS with nginx/Caddy

---

## Useful Commands

```bash
# Stop everything
docker-compose down

# Start everything
docker-compose up -d

# Rebuild after code changes
docker-compose up -d --build

# View logs
docker logs blackbook_bot -f
docker logs blackbook_web -f

# Access database directly
docker exec -it blackbook_db psql -U bb_operator -d blackbook_db

# Backup database
docker exec blackbook_db pg_dump -U bb_operator blackbook_db > backup.sql
```

---

## Troubleshooting

### Reset everything (DANGER: deletes data)
```bash
docker-compose down -v
rm -rf db_data/*
docker-compose up -d --build
```

### Check if bot can reach Telegram
```bash
docker exec blackbook_bot python -c "import httpx; print(httpx.get('https://api.telegram.org').status_code)"
```

---

Need help? Check logs first: `docker logs blackbook_bot -f`
