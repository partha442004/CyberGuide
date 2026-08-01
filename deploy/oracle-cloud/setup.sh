#!/bin/bash
# ============================================
# CyberGuide - Oracle Cloud Free Tier Setup
# Always-Free ARM VM Deployment
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
    git clone https://github.com/partha442004/CyberGuide.git
fi
cd cybershield

# Configure environment
echo "⚙️  Configuring environment..."
SECRET=$(openssl rand -hex 32)
API_KEY=$(openssl rand -hex 16)

cat > .env << EOF
APP_NAME=CyberGuide
APP_VERSION=1.12.0
ENVIRONMENT=production
DEBUG=false
DATABASE_URL=postgresql+asyncpg://cyberguide:cyberguide_secret@postgres:5432/cyberguide
REDIS_URL=redis://redis:6379/0
ELASTICSEARCH_URL=http://elasticsearch:9200
SECRET_KEY=$SECRET
API_KEYS=$API_KEY
SCRAPE_INTERVAL_MINUTES=30
MAX_CONCURRENT_SCRAPERS=5
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
DISCORD_WEBHOOK_URL=
SLACK_WEBHOOK_URL=
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=
SMTP_PASSWORD=
EOF

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

# Verify services
echo ""
echo "📊 Verifying services..."
sleep 10
docker-compose ps

# Test health endpoint
echo ""
echo "🏥 Testing health endpoint..."
sleep 5
HEALTH=$(curl -s http://localhost:8000/health 2>/dev/null || echo "Not ready yet")
echo "Health: $HEALTH"

echo ""
echo "✅ CyberGuide is running!"
echo ""
echo "🌐 Access URLs:"
echo "   - API:       http://YOUR-PUBLIC-IP:8000"
echo "   - Dashboard: http://YOUR-PUBLIC-IP:8501"
echo "   - API Docs:  http://YOUR-PUBLIC-IP:8000/api/docs"
echo ""
echo "🔑 Your API Key: $API_KEY"
echo "   (Saved in .env file)"
echo ""
echo "📋 Useful commands:"
echo "   docker-compose logs -f          # View logs"
echo "   docker-compose ps               # Check status"
echo "   docker-compose restart          # Restart all"
echo "   docker-compose down             # Stop all"
echo ""
