#!/bin/bash
# Tactizen Deployment Script
# Usage: ./deploy.sh [--no-maintenance] [--skip-deps] [--skip-migrations]

set -e  # Exit on error

APP_DIR="/var/www/tactizen"
VENV_DIR="$APP_DIR/venv"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Parse arguments
MAINTENANCE=true
INSTALL_DEPS=true
RUN_MIGRATIONS=true

for arg in "$@"; do
    case $arg in
        --no-maintenance)
            MAINTENANCE=false
            ;;
        --skip-deps)
            INSTALL_DEPS=false
            ;;
        --skip-migrations)
            RUN_MIGRATIONS=false
            ;;
    esac
done

echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Tactizen Deployment Script${NC}"
echo -e "${GREEN}========================================${NC}"

cd $APP_DIR

# Enable maintenance mode
if [ "$MAINTENANCE" = true ]; then
    echo -e "${YELLOW}[1/6] Enabling maintenance mode...${NC}"
    touch MAINTENANCE_MODE
else
    echo -e "${YELLOW}[1/6] Skipping maintenance mode...${NC}"
fi

# Pull latest code
echo -e "${YELLOW}[2/6] Pulling latest code from GitHub...${NC}"
git pull origin master

# Activate virtual environment
echo -e "${YELLOW}[3/6] Activating virtual environment...${NC}"
source $VENV_DIR/bin/activate

# Install dependencies
if [ "$INSTALL_DEPS" = true ]; then
    echo -e "${YELLOW}[4/6] Installing/updating dependencies...${NC}"
    pip install -r requirements.txt --quiet
else
    echo -e "${YELLOW}[4/6] Skipping dependency installation...${NC}"
fi

# Run database migrations
if [ "$RUN_MIGRATIONS" = true ]; then
    echo -e "${YELLOW}[5/6] Running database migrations...${NC}"
    flask db upgrade
else
    echo -e "${YELLOW}[5/6] Skipping migrations...${NC}"
fi

# Restart application
echo -e "${YELLOW}[6/6] Restarting application...${NC}"
sudo systemctl restart tactizen

# Disable maintenance mode
if [ "$MAINTENANCE" = true ]; then
    rm -f MAINTENANCE_MODE
    echo -e "${GREEN}Maintenance mode disabled.${NC}"
fi

# Check status
echo ""
echo -e "${GREEN}========================================${NC}"
echo -e "${GREEN}  Deployment Complete!${NC}"
echo -e "${GREEN}========================================${NC}"
echo ""
sudo systemctl status tactizen --no-pager

echo ""
echo -e "${GREEN}Deployment finished at $(date)${NC}"
