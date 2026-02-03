# Blackbook Deployment Guide

## Server Information
- **Domain**: innbucks.org
- **Server IP**: 185.194.217.100
- **OS**: Ubuntu 20.04+ recommended

## Quick Deployment (3 Steps)

### Step 1: SSH into Your Server
```bash
ssh root@185.194.217.100
```

### Step 2: Run Initial Setup (First Time Only)
```bash
# Download and run the setup script
curl -fsSL https://raw.githubusercontent.com/Pompompurin888k/blackbook/main/server-setup.sh -o setup.sh
chmod +x setup.sh
./setup.sh
```

This will:
- Install Docker, Docker Compose, Nginx
- Configure firewall (UFW)
- Clone your repository
- Setup SSL certificate (Let's Encrypt)
- Create .env file
- Start the application

### Step 3: Test Your Site
Open your browser: **https://innbucks.org**

---

## Manual Deployment (If You Prefer)

### 1. Prepare Server

```bash
# SSH into server
ssh root@185.194.217.100

# Update system
apt update && apt upgrade -y

# Install Docker
curl -fsSL https://get.docker.com | sh

# Install Docker Compose
curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose

# Install nginx and certbot
apt install -y nginx certbot python3-certbot-nginx git ufw

# Setup firewall
ufw allow 22/tcp
ufw allow 80/tcp
ufw allow 443/tcp
ufw --force enable
```

### 2. Clone Repository

```bash
cd /root
git clone https://github.com/Pompompurin888k/blackbook.git blackbook
cd blackbook
```

### 3. Configure Environment

```bash
# Copy example env file
cp .env.example .env

# Edit with your values
nano .env
```

**Fill in these required values**:
```env
TELEGRAM_TOKEN=123456:ABC-DEF1234...           # Get from @BotFather
ADMIN_CHAT_ID=123456789                        # Your Telegram user ID
PARTNER_TELEGRAM_ID=987654321                  # Partner's Telegram ID
DB_PASSWORD=your_strong_password_here          # Create a strong password
MEGAPAY_API_KEY=your_megapay_key              # Optional for now
MEGAPAY_EMAIL=your@email.com                   # Optional for now
```

### 4. Setup Nginx

```bash
# Copy nginx config
cp nginx.conf /etc/nginx/sites-available/blackbook

# Enable site
ln -sf /etc/nginx/sites-available/blackbook /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default

# Test config
nginx -t

# Restart nginx
systemctl restart nginx
systemctl enable nginx
```

### 5. Get SSL Certificate

```bash
certbot --nginx -d innbucks.org -d www.innbucks.org --agree-tos -m your@email.com

# Enable auto-renewal
systemctl enable certbot.timer
systemctl start certbot.timer
```

### 6. Deploy Application

```bash
cd /root/blackbook

# Make scripts executable
chmod +x deploy.sh server-setup.sh

# Start the application
docker-compose up -d --build
```

---

## Future Deployments

After initial setup, just push to GitHub and run:

```bash
ssh root@185.194.217.100
cd /root/blackbook
./deploy.sh
```

That's it! The script handles everything.

---

## Useful Commands

### View Logs
```bash
cd /root/blackbook

# All logs
docker-compose logs -f

# Just web logs
docker-compose logs -f web

# Just bot logs
docker-compose logs -f bot

# Database logs
docker-compose logs -f db
```

### Restart Services
```bash
cd /root/blackbook

# Restart all
docker-compose restart

# Restart just web
docker-compose restart web

# Rebuild and restart
docker-compose up -d --build
```

### Check Status
```bash
# Container status
docker ps

# Resource usage
docker stats

# Nginx status
systemctl status nginx

# SSL certificate info
certbot certificates
```

### Database Access
```bash
# Connect to PostgreSQL
docker exec -it blackbook_db psql -U bb_operator -d blackbook_db

# Backup database
docker exec blackbook_db pg_dump -U bb_operator blackbook_db > backup_$(date +%Y%m%d).sql

# Restore database
cat backup.sql | docker exec -i blackbook_db psql -U bb_operator -d blackbook_db
```

---

## Troubleshooting

### Site Not Loading?

1. **Check containers are running:**
   ```bash
   docker ps
   ```

2. **Check web logs:**
   ```bash
   docker-compose logs web
   ```

3. **Check nginx:**
   ```bash
   systemctl status nginx
   nginx -t
   ```

4. **Check firewall:**
   ```bash
   ufw status
   ```

### SSL Issues?

```bash
# Renew certificate manually
certbot renew --force-renewal

# Restart nginx
systemctl restart nginx
```

### Database Connection Issues?

```bash
# Check database is running
docker exec blackbook_db psql -U bb_operator -d blackbook_db -c "SELECT 1"

# Check environment variables
docker exec blackbook_web env | grep DB_
```

### Can't Connect via SSH?

```bash
# From your local machine
ssh -v root@185.194.217.100

# Add your SSH key
ssh-copy-id root@185.194.217.100
```

---

## Security Checklist

- [x] Firewall configured (UFW)
- [x] SSL/HTTPS enabled
- [x] Strong database password set
- [ ] Change default SSH port (optional)
- [ ] Setup fail2ban (optional)
- [ ] Regular backups scheduled
- [ ] Keep system updated (`apt update && apt upgrade`)

---

## Production Optimizations (Later)

### 1. Remove --reload flag
In `docker-compose.yml`:
```yaml
web:
  command: uvicorn main:app --host 0.0.0.0 --port 8080 --workers 4
```

### 2. Setup Redis for caching
```yaml
redis:
  image: redis:7-alpine
  container_name: blackbook_redis
```

### 3. Setup automated backups
```bash
# Add to crontab
0 2 * * * /root/blackbook/backup.sh
```

---

## Support

If you encounter issues:
1. Check logs: `docker-compose logs -f`
2. Verify .env file is configured correctly
3. Ensure domain DNS is pointing to 185.194.217.100
4. Check firewall allows ports 80 and 443

---

**Your site will be live at: https://innbucks.org** 🚀
