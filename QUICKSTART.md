# 🚀 Quick Start - Deploy to innbucks.org

## Prerequisites
✅ Domain pointing to 185.194.217.100 (DONE)
✅ Code pushed to GitHub (DONE)
⬜ SSH access to server

---

## Deploy in 3 Commands

### 1️⃣ SSH into your server
```bash
ssh root@185.194.217.100
```

### 2️⃣ Download and run setup script
```bash
curl -O https://raw.githubusercontent.com/Pompompurin888k/blackbook/main/server-setup.sh
chmod +x server-setup.sh
./server-setup.sh
```

The script will ask you:
- Your GitHub repository URL
- Your email (for SSL certificate)
- Then open .env file for you to configure

### 3️⃣ Fill in .env file when prompted

**Required values:**
```env
TELEGRAM_TOKEN=123456:ABC-DEF...     # From @BotFather on Telegram
ADMIN_CHAT_ID=123456789              # Your Telegram user ID
DB_PASSWORD=create_strong_password    # Make it secure!
```

**Optional (can add later):**
```env
PARTNER_TELEGRAM_ID=                 # Leave blank for now
MEGAPAY_API_KEY=                     # Leave blank for now
MEGAPAY_EMAIL=                       # Leave blank for now
```

Save and exit: `Ctrl + X`, then `Y`, then `Enter`

---

## That's It! 🎉

Your site will be live at: **https://innbucks.org**

The setup script automatically:
- Installs Docker & Nginx
- Configures SSL certificate
- Starts your application
- Sets up firewall

---

## After First Setup - Deploy Updates

When you push changes to GitHub, just run:

```bash
ssh root@185.194.217.100
cd /root/blackbook
./deploy.sh
```

---

## Check if Everything is Working

```bash
# See running containers
docker ps

# View logs
docker-compose logs -f web

# Check SSL certificate
certbot certificates

# Test site
curl -I https://innbucks.org
```

---

## Get Your Telegram Bot Token

If you don't have it yet:

1. Open Telegram
2. Search for `@BotFather`
3. Type `/newbot`
4. Follow instructions
5. Copy the token (looks like: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)
6. Add to .env file

---

## Get Your Telegram User ID

1. Open Telegram
2. Search for `@userinfobot`
3. Type `/start`
4. Bot will reply with your user ID
5. Add to .env as `ADMIN_CHAT_ID`

---

## Troubleshooting

**Site not loading?**
```bash
docker-compose logs -f web
systemctl status nginx
```

**SSL issues?**
```bash
certbot renew
systemctl restart nginx
```

**Database issues?**
```bash
docker-compose logs -f db
```

---

## Need Help?

Check full documentation: [DEPLOYMENT.md](./DEPLOYMENT.md)

---

**Ready? Let's deploy! 🚀**
