#!/bin/bash

# Blackbook Deployment Script
# Domain: innbucks.org
# Port: 8080 (web), 5432 (postgres internal)

set -e

echo "🚀 Deploying Blackbook..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "   Copy .env.example to .env and configure it first"
    exit 1
fi

# Stop any existing containers
cd /root/blackbook
echo "🛑 Stopping existing containers..."
docker-compose down 2>/dev/null || true

# Pull latest code
echo "📥 Pulling latest code from GitHub..."
git pull origin main

# Build and start
echo "🏗️  Building and starting containers..."
docker-compose up -d --build

# Wait for services
echo "⏳ Waiting for services to be ready..."
sleep 5

# Check status
echo ""
echo "📊 Container Status:"
docker ps --filter "name=blackbook"

echo ""
echo "✅ Deployment complete!"
echo "🌐 Website: https://innbucks.org"
echo ""
echo "📋 Useful commands:"
echo "   View logs: docker-compose logs -f"
echo "   View web logs: docker-compose logs -f web"
echo "   Restart: docker-compose restart"
echo "   Stop: docker-compose down"
echo ""
