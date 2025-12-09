# Tactizen Deployment Guide for Ubuntu 25 (OVH Server)

## Prerequisites

- Ubuntu 25 server with root/sudo access
- Domain name (tactizen.com) pointing to your server IP
- SSH access to your server

---

## 1. Initial Server Setup

### Connect to your server
```bash
ssh root@your-server-ip
```

### Update system
```bash
apt update && apt upgrade -y
```

### Create a non-root user (recommended)
```bash
adduser tactizen
usermod -aG sudo tactizen
su - tactizen
```

---

## 2. Install Required Packages

```bash
# Python and build tools
sudo apt install -y python3 python3-pip python3-venv python3-dev build-essential

# Nginx
sudo apt install -y nginx

# MySQL
sudo apt install -y mysql-server mysql-client libmysqlclient-dev

# Git
sudo apt install -y git

# Certbot for SSL
sudo apt install -y certbot python3-certbot-nginx

# Supervisor (alternative to systemd, optional)
# sudo apt install -y supervisor
```

---

## 3. Configure MySQL

```bash
# Secure MySQL installation
sudo mysql_secure_installation

# Login to MySQL
sudo mysql

# Create database and user
CREATE DATABASE tactizen CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'tactizen'@'localhost' IDENTIFIED BY 'YOUR_SECURE_PASSWORD_HERE';
GRANT ALL PRIVILEGES ON tactizen.* TO 'tactizen'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

---

## 4. Clone and Setup Application

### Create web directory
```bash
sudo mkdir -p /var/www/tactizen
sudo chown $USER:$USER /var/www/tactizen
```

### Clone repository
```bash
cd /var/www/tactizen
git clone https://github.com/NVladan/tactizen.git .
```

### Create virtual environment
```bash
python3 -m venv venv
source venv/bin/activate
```

### Install Python dependencies
```bash
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 5. Configure Environment Variables

### Create .env file
```bash
nano /var/www/tactizen/.env
```

### Add production settings:
```env
# Flask
FLASK_APP=app
FLASK_ENV=production
SECRET_KEY=your-very-long-random-secret-key-here

# Database
DATABASE_URL=mysql+pymysql://tactizen:YOUR_SECURE_PASSWORD_HERE@localhost/tactizen

# Blockchain (Horizen L3 Mainnet)
WEB3_PROVIDER_URL=https://rpc.horizen.io
CHAIN_ID=1708
ZEN_CONTRACT_ADDRESS=your_zen_contract_address
NFT_CONTRACT_ADDRESS=your_nft_contract_address
DEPLOYER_PRIVATE_KEY=your_deployer_private_key

# zkVerify (Mainnet)
ZKVERIFY_RPC_URL=wss://zkverify.io
ZKVERIFY_SEED_PHRASE=your_seed_phrase

# Security
ALLOWED_HOSTS=tactizen.com,www.tactizen.com
SESSION_COOKIE_SECURE=true
SESSION_COOKIE_HTTPONLY=true
SESSION_COOKIE_SAMESITE=Lax
```

### Secure the .env file
```bash
chmod 600 /var/www/tactizen/.env
```

---

## 6. Initialize Database

```bash
cd /var/www/tactizen
source venv/bin/activate

# Run migrations
flask db upgrade

# Seed initial data
python seed_countries.py
python seed_resources.py
python seed_achievements.py
python seed_missions.py
```

---

## 7. Setup Log Directories

```bash
sudo mkdir -p /var/log/tactizen
sudo chown www-data:www-data /var/log/tactizen

sudo mkdir -p /run/tactizen
sudo chown www-data:www-data /run/tactizen
```

---

## 8. Setup Uploads Directory

```bash
mkdir -p /var/www/tactizen/app/static/uploads/avatars
sudo chown -R www-data:www-data /var/www/tactizen/app/static/uploads
```

---

## 9. Configure Gunicorn

The `gunicorn.conf.py` is already in your repo. Verify paths:
```bash
# Edit if needed
nano /var/www/tactizen/gunicorn.conf.py
```

---

## 10. Setup Systemd Service

```bash
# Copy service file
sudo cp /var/www/tactizen/deploy/tactizen.service /etc/systemd/system/

# Reload systemd
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable tactizen

# Start service
sudo systemctl start tactizen

# Check status
sudo systemctl status tactizen
```

### Useful commands:
```bash
sudo systemctl start tactizen    # Start
sudo systemctl stop tactizen     # Stop
sudo systemctl restart tactizen  # Restart
sudo systemctl status tactizen   # Check status
sudo journalctl -u tactizen -f   # View logs (live)
```

---

## 11. Configure Nginx

```bash
# Copy nginx config
sudo cp /var/www/tactizen/deploy/nginx-tactizen.conf /etc/nginx/sites-available/tactizen

# Remove default site
sudo rm /etc/nginx/sites-enabled/default

# Enable tactizen site
sudo ln -s /etc/nginx/sites-available/tactizen /etc/nginx/sites-enabled/

# Test configuration
sudo nginx -t

# Reload nginx
sudo systemctl reload nginx
```

---

## 12. Setup SSL Certificate (Let's Encrypt)

### First, temporarily comment out SSL lines in nginx config:
```bash
sudo nano /etc/nginx/sites-available/tactizen
# Comment out the entire HTTPS server block initially
```

### Reload nginx to apply HTTP-only config:
```bash
sudo systemctl reload nginx
```

### Get SSL certificate:
```bash
sudo certbot --nginx -d tactizen.com -d www.tactizen.com
```

### Certbot will automatically:
- Obtain certificates
- Update your nginx config
- Setup auto-renewal

### Verify auto-renewal:
```bash
sudo certbot renew --dry-run
```

---

## 13. Configure Firewall

```bash
# Allow SSH, HTTP, HTTPS
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'
sudo ufw enable
sudo ufw status
```

---

## 14. Final Checks

### Test the site:
```bash
curl -I https://tactizen.com
```

### Check all services:
```bash
sudo systemctl status tactizen
sudo systemctl status nginx
sudo systemctl status mysql
```

### View logs:
```bash
# Gunicorn logs
tail -f /var/log/tactizen/gunicorn-error.log
tail -f /var/log/tactizen/gunicorn-access.log

# Nginx logs
tail -f /var/log/nginx/tactizen-error.log
tail -f /var/log/nginx/tactizen-access.log

# Systemd logs
sudo journalctl -u tactizen -f
```

---

## Deployment Updates

### When you push new code:

```bash
# SSH into server
ssh tactizen@your-server-ip

# Go to app directory
cd /var/www/tactizen

# Enable maintenance mode (optional)
touch MAINTENANCE_MODE

# Pull latest code
git pull origin master

# Activate venv
source venv/bin/activate

# Install any new dependencies
pip install -r requirements.txt

# Run migrations (if any)
flask db upgrade

# Restart the app
sudo systemctl restart tactizen

# Disable maintenance mode
rm MAINTENANCE_MODE

# Check status
sudo systemctl status tactizen
```

### Quick deploy script (create as deploy.sh):
```bash
#!/bin/bash
cd /var/www/tactizen
touch MAINTENANCE_MODE
git pull origin master
source venv/bin/activate
pip install -r requirements.txt
flask db upgrade
sudo systemctl restart tactizen
rm MAINTENANCE_MODE
echo "Deployment complete!"
```

---

## Troubleshooting

### App won't start:
```bash
# Check logs
sudo journalctl -u tactizen -n 50
cat /var/log/tactizen/gunicorn-error.log

# Try running manually
cd /var/www/tactizen
source venv/bin/activate
gunicorn --config gunicorn.conf.py "app:create_app()"
```

### 502 Bad Gateway:
```bash
# Check if gunicorn is running
sudo systemctl status tactizen

# Check if port 5000 is in use
sudo netstat -tlnp | grep 5000
```

### Permission errors:
```bash
# Fix ownership
sudo chown -R www-data:www-data /var/www/tactizen
sudo chown -R www-data:www-data /var/log/tactizen
```

### Database connection errors:
```bash
# Test MySQL connection
mysql -u tactizen -p tactizen
```

---

## Security Checklist

- [ ] Change default SSH port (optional)
- [ ] Disable root SSH login
- [ ] Setup fail2ban
- [ ] Keep system updated
- [ ] Backup database regularly
- [ ] Monitor server resources
- [ ] Review logs periodically

```bash
# Install fail2ban
sudo apt install fail2ban
sudo systemctl enable fail2ban
```

---

## Backup Database

```bash
# Manual backup
mysqldump -u tactizen -p tactizen > backup_$(date +%Y%m%d).sql

# Automated daily backup (add to crontab)
crontab -e
# Add: 0 3 * * * mysqldump -u tactizen -p'password' tactizen > /var/backups/tactizen_$(date +\%Y\%m\%d).sql
```
