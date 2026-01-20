#!/bin/bash

# Blackbook Deployment Script
# Domain: innbucks.org
# Port: 8080 (web), 5432 (postgres internal)

set -e

echo "🚀 Deploying Blackbook..."

# Stop any existing containers
cd /root/blackbook
docker-compose down 2>/dev/null || true

# Pull latest code
git pull origin main

# Build and start
docker-compose up -d --build

# Check status
echo "📊 Container Status:"
docker ps | grep blackbook

echo "✅ Deployment complete!"
echo "🌐 Website: https://innbucks.org"
