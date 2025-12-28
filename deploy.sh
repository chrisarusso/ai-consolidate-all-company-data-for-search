#!/bin/bash
# Deploy multi-source-knowledge-base to remote server
#
# Usage: ./deploy.sh

set -e

# Configuration
REMOTE_HOST="${REMOTE_HOST:-ubuntu@3.16.155.59}"
SSH_KEY="${SSH_KEY:-~/.ssh/AWS-created-nov-27-2025.pem}"
REMOTE_DIR="/home/ubuntu/knowledge-base"
SERVICE_NAME="knowledge-base"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo "=========================================="
echo "Knowledge Base - Deploy"
echo "=========================================="

# Check for uncommitted local changes
if ! git diff --quiet HEAD 2>/dev/null; then
    echo -e "${YELLOW}Warning: You have uncommitted local changes${NC}"
    git status --short
    echo ""
    echo "Commit and push first, then deploy."
    exit 1
fi

# Check if local is ahead of remote
LOCAL=$(git rev-parse HEAD)
REMOTE=$(git rev-parse origin/master 2>/dev/null || echo "unknown")

if [ "$LOCAL" != "$REMOTE" ]; then
    echo -e "${YELLOW}Local and origin/master differ${NC}"
    echo "Local:  $LOCAL"
    echo "Remote: $REMOTE"
    echo ""
    echo "Push your changes first: git push origin master"
    exit 1
fi

echo "Deploying commit: $(git rev-parse --short HEAD)"
echo ""

# Build frontend first
echo "[1/5] Building frontend..."
cd frontend
npm run build
cd ..

# SSH and deploy
echo "[2/5] Pulling latest code on server..."
ssh -i "$SSH_KEY" "$REMOTE_HOST" "cd $REMOTE_DIR && git fetch origin && git reset --hard origin/master"

echo "[3/5] Installing Python dependencies..."
ssh -i "$SSH_KEY" "$REMOTE_HOST" "cd $REMOTE_DIR && /home/ubuntu/.local/bin/uv sync --quiet"

echo "[4/5] Moving database from backup..."
ssh -i "$SSH_KEY" "$REMOTE_HOST" "mkdir -p $REMOTE_DIR/data && cp ~/backups/knowledge-base-raw-data.db $REMOTE_DIR/data/raw_data.db"

echo "[5/5] Restarting service..."
ssh -i "$SSH_KEY" "$REMOTE_HOST" "sudo systemctl restart $SERVICE_NAME"
sleep 2

STATUS=$(ssh -i "$SSH_KEY" "$REMOTE_HOST" "systemctl is-active $SERVICE_NAME" 2>/dev/null || echo "failed")

echo ""
if [ "$STATUS" = "active" ]; then
    echo -e "${GREEN}Deploy successful!${NC}"
    echo "  Commit: $(git rev-parse --short HEAD)"
    echo "  Status: $STATUS"
    echo "  URL: https://internal.savaslabs.com/knowledge-base/"
else
    echo -e "${RED}Deploy failed - service not running${NC}"
    echo "  Check logs: ssh -i $SSH_KEY $REMOTE_HOST 'journalctl -u $SERVICE_NAME -n 50'"
    exit 1
fi
