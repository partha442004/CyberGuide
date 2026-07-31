#!/bin/bash
# ============================================
# CyberGuide - Oracle Cloud Free Tier Setup
# Always-Free ARM VM Deployment
# ============================================
# Run this script on a fresh Oracle Linux 8/9 ARM VM
# ssh -i your-key.pem opc@your-ip
# ============================================

set -e

echo "🛡️  CyberGuide - Oracle Cloud Free Tier Setup"
echo "=============================================="
echo ""

# Update system
echo "📦 Updating system packages..."
sudo dnf update -y
sudo dnf install -y git curl wget nano unzip

# Install Docker
echo "🐳 Installing Docker..."
sudo dnf config-manager --add-repo https://download.docker.com/linux/centos/docker-ce.repo
sudo dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
sudo systemctl enable --now docker
sudo usermod -aG docker opc
echo "Docker installed: $(docker --version)"

# Install Docker Compose (standalone)
echo "🐳 Installing Docker Compose..."
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose
echo "Docker Compose installed: $(docker-compose --version)"

# Clone CyberGuide repo
echo "📥 Cloning CyberGuide..."
cd /home/opc
if [ ! -d "cybershield" ]; then
    git clone https://github.com/partha442004/cybershield.git
fi
cd cybershield

# Configure environment
echo "⚙️  Configuring environment..."
cat > .env << 'EOF'
# CyberGuide Configuration
APP_NAME=CyberGuide
APP_VERSION=1.0.0
ENVIRONMENT=production
DEBUG=false

# Database (Docker PostgreSQL)
DATABASE_URL=postgresql+asyncpg://cyberguide:cyberguide_secret@postgres:5432/cyberguide

# Redis
REDIS_URL=redis://redis:6379/0

# Elasticsearch
ELASTICSEARCH_URL=http://elasticsearch:9200

# Security
SECRET_KEY=$(openssl rand -hex 32)
API_KEYS=$(openssl rand -hex 16)

# Scraper Settings
SCRAPE_INTERVAL_MINUTES=30
MAX_CONCURRENT_SCRAPERS=5

# Notifications (optional - leave empty to disable)
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
DISCORD_WEBHOOK_URL=
SLACK_WEBHOOK_URL=
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
EOF

# Generate a random secret key
SECRET=$(openssl rand -hex 32)
sed -i "s/SECRET_KEY=.*/SECRET_KEY=$SECRET/" .env

echo "Environment configured!"

# Set up firewall
echo "🔥 Configuring firewall..."
sudo firewall-cmd --permanent --add-port=80/tcp
sudo firewall-cmd --permanent --add-port=443/tcp
sudo firewall-cmd --permanent --add-port=8000/tcp
sudo firewall-cmd --permanent --add-port=8501/tcp
sudo firewall-cmd --reload
echo "Firewall configured!"

# Start services
echo "🚀 Starting CyberGuide services..."
docker-compose up -d

echo ""
echo "✅ CyberGuide is starting up!"
echo ""
echo "📊 Services:"
echo "   - API:        http://localhost:8000"
echo "   - Dashboard:  http://localhost:8501"
echo "   - API Docs:   http://localhost:8000/api/docs"
echo "   - Health:     http://localhost:8000/health"
echo ""
echo "🔑 Your API Key is in .env file (API_KEYS)"
echo ""
echo "📋 Useful commands:"
echo "   docker-compose logs -f          # View logs"
echo "   docker-compose ps               # Check status"
echo "   docker-compose restart          # Restart all"
echo "   docker-compose down             # Stop all"
echo ""
echo "🌐 To access from your browser:"
echo "   1. Go to Oracle Cloud Console"
echo "   2. Networking > Virtual Cloud Networks > Your VCN"
echo "   3. Security Lists > Add Ingress Rule"
echo "   4. Add rules for ports 8000 and 8501"
echo "   5. Access: http://YOUR-PUBLIC-IP:8000"
echo ""
