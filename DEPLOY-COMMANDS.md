# 🚀 Deployment Commands - Run One by One

## Step 1: SSH into Server
```bash
ssh root@185.194.217.100
```

---

## Step 2: Update System & Install Docker
```bash
apt update && apt upgrade -y
```

```bash
curl -fsSL https://get.docker.com | sh
```

```bash
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
```

---

## Step 3: Install Nginx & Certbot
```bash
apt install -y nginx certbot python3-certbot-nginx git
```

---

## Step 4: Setup Firewall
```bash
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
```

---

## Step 5: Clone Your Repository
```bash
cd /root
git clone https://github.com/Pompompurin888k/blackbook.git blackbook
cd blackbook
```

---

## Step 6: Create .env File
```bash
cp .env.example .env
nano .env
```

**Fill in these values:**
```env
TELEGRAM_TOKEN=your_bot_token_from_botfather
ADMIN_CHAT_ID=your_telegram_user_id
PARTNER_TELEGRAM_ID=partner_id_or_leave_blank
DB_PASSWORD=create_strong_password_here
MEGAPAY_API_KEY=leave_blank_for_now
MEGAPAY_EMAIL=leave_blank_for_now
```

Press `Ctrl+X`, then `Y`, then `Enter` to save.

---

## Step 7: Setup Nginx
```bash
cp nginx.conf /etc/nginx/sites-available/blackbook
```

```bash
ln -sf /etc/nginx/sites-available/blackbook /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
```

```bash
nginx -t
```

```bash
systemctl restart nginx
systemctl enable nginx
```

---

## Step 8: Get SSL Certificate
**Replace `your@email.com` with your actual email:**
```bash
certbot --nginx -d innbucks.org -d www.innbucks.org --non-interactive --agree-tos -m your@email.com
```

```bash
systemctl enable certbot.timer
systemctl start certbot.timer
```

---

## Step 9: Start Application
```bash
cd /root/blackbook
docker-compose up -d --build
```

---

## Step 10: Check Status
```bash
docker ps
```

```bash
docker-compose logs -f web
```

Press `Ctrl+C` to exit logs.

---

## ✅ Done! 

Your site is live at: **https://innbucks.org**

---

## Future Updates

When you push changes to GitHub:

```bash
ssh root@185.194.217.100
cd /root/blackbook
git pull origin main
docker-compose up -d --build
```

---

## Useful Commands

**View logs:**
```bash
docker-compose logs -f web
docker-compose logs -f bot
docker-compose logs -f db
```

**Restart services:**
```bash
docker-compose restart
```

**Stop services:**
```bash
docker-compose down
```

**Backup database:**
```bash
docker exec blackbook_db pg_dump -U bb_operator blackbook_db > backup.sql
```

**Check SSL:**
```bash
certbot certificates
```

**Firewall status:**
```bash
ufw status
```
