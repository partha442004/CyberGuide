# 🛡️ CyberGuide - Oracle Cloud Free Tier Deployment Guide

## Always-Free Resources
Oracle Cloud Always Free Tier provides **forever free** resources:
- **2 AMD VMs**: 1/8 OCPU, 1 GB RAM each
- **Up to 4 ARM VMs**: 4 OCPUs total, 24 GB RAM total
- **200 GB block storage**
- **10 GB object storage**
- **10 GB/month outbound data transfer**

## Recommended ARM VM Configuration
- **Shape**: VM.Standard.A1.Flex
- **OCPU**: 4 (all 4 available)
- **RAM**: 24 GB
- **Boot Volume**: 50 GB

This provides more than enough resources for CyberGuide with all services.

---

## Step-by-Step Deployment Guide

### Step 1: Create Oracle Cloud Account
1. Go to [cloud.oracle.com](https://cloud.oracle.com)
2. Sign up for a free account
3. Add a credit card (required for verification, won't be charged for Always Free)

### Step 2: Create an ARM VM
1. Go to **Compute > Instances > Create Instance**
2. Select **Image**: Oracle Linux 8 or 9 (latest)
3. Select **Shape**: VM.Standard.A1.Flex
4. Configure:
   - **OCPU**: 4
   - **RAM**: 24 GB
5. Create SSH keys:
   ```bash
   # On your local machine
   ssh-keygen -t rsa -b 4096 -f cybershield-key
   ```
6. Paste the **public key** in the SSH Keys section
7. Create the instance

### Step 3: Configure Network Security
1. Go to **Networking > Virtual Cloud Networks > Your VCN**
2. Click on **Default Security List**
3. **Add Ingress Rules** (one at a time):

| Port | Protocol | Source | Description |
|------|----------|--------|-------------|
| 22 | TCP | Your IP/32 | SSH Access |
| 8000 | TCP | 0.0.0.0/0 | CyberGuide API |
| 8501 | TCP | 0.0.0.0/0 | CyberGuide Dashboard |

### Step 4: Connect to Your VM
```bash
# On your local machine
chmod 400 cybershield-key
ssh -i cybershield-key opc@YOUR-PUBLIC-IP
```

### Step 5: Deploy CyberGuide
```bash
# Download and run the setup script
curl -sSL https://raw.githubusercontent.com/partha442004/CyberGuide/main/deploy/oracle-cloud/setup.sh | bash
```

**Or manually:**
```bash
# Clone the repo
git clone https://github.com/partha442004/CyberGuide.git
cd CyberGuide

# Run setup
chmod +x deploy/oracle-cloud/setup.sh
./deploy/oracle-cloud/setup.sh
```

### Step 6: Access CyberGuide
- **API**: http://YOUR-PUBLIC-IP:8000
- **Dashboard**: http://YOUR-PUBLIC-IP:8501
- **API Docs**: http://YOUR-PUBLIC-IP:8000/api/docs

---

## Post-Deployment Checklist

### 1. Verify All Services Are Running
```bash
cd /home/opc/cybershield
docker-compose ps
```

Expected output:
```
NAME                STATUS          PORTS
cybershield-api     Up              0.0.0.0:8000->8000/tcp
cybershield-postgres Up             5432/tcp
cybershield-redis   Up              6379/tcp
cybershield-scheduler Up
```

### 2. Check Health Endpoint
```bash
curl http://localhost:8000/health
```

Expected output:
```json
{"status":"healthy","version":"1.15.0","debug":false}
```

### 3. View Logs
```bash
# All services
docker-compose logs -f

# API only
docker-compose logs -f api

# Scheduler only
docker-compose logs -f scheduler
```

---

## Troubleshooting

### Service Won't Start
```bash
# Check logs
docker-compose logs api

# Restart specific service
docker-compose restart api
```

### Port Already in Use
```bash
# Find what's using port 8000
sudo lsof -i :8000

# Kill the process
sudo kill -9 <PID>
```

### Out of Memory
The ARM VM has 24GB RAM. If you encounter OOM:
1. Reduce Elasticsearch memory:
   Edit `docker-compose.yml`:
   ```yaml
   elasticsearch:
     environment:
       - "ES_JAVA_OPTS=-Xms256m -Xmx512m"
   ```
2. Restart services: `docker-compose down && docker-compose up -d`

---

## Automatic Updates (Optional)

### Enable Docker Auto-Restart
Docker services are configured with `restart: unless-stopped`, so they auto-start on VM reboot.

### Add Swap Space (Optional)
If you need more memory headroom:
```bash
sudo fallocate -l 4G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab
```

---

## Cost Summary
| Item | Cost |
|------|------|
| ARM VM (4 OCPU, 24GB) | **$0.00/month** (Always Free) |
| Block Storage (50GB) | **$0.00/month** (within 200GB free) |
| Data Transfer (10GB) | **$0.00/month** (within 10GB free) |
| **Total** | **$0.00/month forever** |
