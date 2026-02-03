#!/bin/bash

# Blackbook Server Setup Script
# Run this once on your fresh server

set -e

echo "🔧 Setting up Blackbook Server..."

# Update system
echo "📦 Updating system packages..."
apt update && apt upgrade -y

# Install required packages
echo "📥 Installing dependencies..."
apt install -y git curl nginx certbot python3-certbot-nginx ufw

# Install Docker
if ! command -v docker &> /dev/null; then
    echo "🐳 Installing Docker..."
    curl -fsSL https://get.docker.com -o get-docker.sh
    sh get-docker.sh
    rm get-docker.sh
else
    echo "✅ Docker already installed"
fi

# Install Docker Compose
if ! command -v docker-compose &> /dev/null; then
    echo "🐳 Installing Docker Compose..."
    curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
    chmod +x /usr/local/bin/docker-compose
else
    echo "✅ Docker Compose already installed"
fi

# Setup firewall
echo "🔥 Configuring firewall..."
ufw --force enable
ufw allow 22/tcp    # SSH
ufw allow 80/tcp    # HTTP
ufw allow 443/tcp   # HTTPS
ufw status

# Clone repository
echo "📂 Cloning repository..."
cd /root
if [ -d "blackbook" ]; then
    echo "⚠️  blackbook directory exists, pulling latest..."
    cd blackbook
    git pull origin main
else
    REPO_URL="https://github.com/Pompompurin888k/blackbook.git"
    git clone $REPO_URL blackbook
    cd blackbook
fi

# Create .env file
echo "📝 Creating .env file..."
if [ ! -f .env ]; then
    cp .env.example .env
    echo ""
    echo "⚠️  IMPORTANT: Edit /root/blackbook/.env with your actual values!"
    echo "   nano /root/blackbook/.env"
    echo ""
    read -p "Press enter to open .env file for editing..."
    nano .env
else
    echo "✅ .env file already exists"
fi

# Setup nginx
echo "🌐 Configuring nginx..."
cp nginx.conf /etc/nginx/sites-available/blackbook
ln -sf /etc/nginx/sites-available/blackbook /etc/nginx/sites-enabled/
rm -f /etc/nginx/sites-enabled/default
nginx -t

# Restart nginx
systemctl restart nginx
systemctl enable nginx

# Get SSL certificate
echo "🔒 Setting up SSL certificate..."
read -p "Enter your email for Let's Encrypt: " EMAIL
certbot --nginx -d innbucks.org -d www.innbucks.org --non-interactive --agree-tos -m $EMAIL

# Setup auto-renewal for SSL
echo "🔄 Setting up SSL auto-renewal..."
systemctl enable certbot.timer
systemctl start certbot.timer

# Build and start containers
echo "🚀 Building and starting Docker containers..."
docker-compose up -d --build

# Wait for containers to be ready
echo "⏳ Waiting for services to start..."
sleep 10

# Check status
echo ""
echo "📊 Container Status:"
docker ps

echo ""
echo "✅ Setup complete!"
echo ""
echo "🌐 Your site: https://innbucks.org"
echo "📋 Next steps:"
echo "   1. Test the website: https://innbucks.org"
echo "   2. Check logs: cd /root/blackbook && docker-compose logs -f"
echo "   3. To deploy updates: cd /root/blackbook && ./deploy.sh"
echo ""
