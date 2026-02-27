#!/bin/bash

# Deployment script for Raspberry Pi with GitHub integration

# Load environment variables from .env file
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
else
    echo -e "\033[0;31mError: .env file not found${NC}"
    echo "Please create a .env file with the following variables:"
    echo "  PI_HOST, PI_USER, PI_PASS, DEST_DIR, GITHUB_TOKEN, GITHUB_REPO"
    exit 1
fi

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Show usage
usage() {
    echo -e "${BLUE}Usage: $0 {init|update}${NC}"
    echo ""
    echo "  init   - Clone repository for the first time"
    echo "  update - Pull latest changes from repository"
    exit 1
}

# Check argument
if [ $# -eq 0 ]; then
    usage
fi

MODE=$1

if [[ "$MODE" != "init" && "$MODE" != "update" ]]; then
    echo -e "${RED}Error: Invalid mode '$MODE'${NC}"
    usage
fi

echo -e "${YELLOW}Starting deployment to Raspberry Pi (Mode: $MODE)...${NC}"

# Check if sshpass is installed
if ! command -v sshpass &> /dev/null; then
    echo -e "${RED}Error: sshpass is not installed${NC}"
    echo "Install it using:"
    echo "  macOS: brew install sshpass"
    echo "  Linux: sudo apt-get install sshpass"
    exit 1
fi

# Construct git URL with token
GIT_URL="https://${GITHUB_TOKEN}@github.com/thitanatinno/easymoney-dashboard.git"

if [ "$MODE" == "init" ]; then
    echo -e "${YELLOW}Initializing - Cloning repository...${NC}"
    
    # Check if directory already exists on Pi
    DIR_EXISTS=$(sshpass -p "$PI_PASS" ssh "${PI_USER}@${PI_HOST}" "[ -d ${DEST_DIR} ] && echo 'yes' || echo 'no'")
    
    if [ "$DIR_EXISTS" == "yes" ]; then
        echo -e "${RED}Error: Directory ${DEST_DIR} already exists on Pi${NC}"
        echo -e "${YELLOW}Use 'update' mode to pull latest changes or manually remove the directory${NC}"
        exit 1
    fi
    
    # Clone repository on Pi
    echo "Cloning from GitHub to ${DEST_DIR}..."
    sshpass -p "$PI_PASS" ssh "${PI_USER}@${PI_HOST}" "sudo git clone ${GIT_URL} ${DEST_DIR}"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Repository cloned successfully${NC}"
    else
        echo -e "${RED}✗ Failed to clone repository${NC}"
        exit 1
    fi
    
    # Set ownership
    echo -e "${YELLOW}Setting ownership...${NC}"
    sshpass -p "$PI_PASS" ssh "${PI_USER}@${PI_HOST}" "sudo chown -R ${PI_USER}:${PI_USER} ${DEST_DIR}"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Ownership set successfully${NC}"
    else
        echo -e "${RED}✗ Failed to set ownership${NC}"
        exit 1
    fi

    # Run autostart setup (init only)
    echo -e "${YELLOW}Setting up autostart...${NC}"
    sshpass -p "$PI_PASS" ssh "${PI_USER}@${PI_HOST}" "bash ${DEST_DIR}/setup_autostart.sh"

    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Autostart configured successfully${NC}"
        echo -e "${YELLOW}⚠ Remember to edit ~/.config/autostart env file on the Pi with your credentials${NC}"
    else
        echo -e "${RED}✗ Failed to configure autostart${NC}"
        exit 1
    fi

elif [ "$MODE" == "update" ]; then
    echo -e "${YELLOW}Updating - Pulling latest changes...${NC}"
    
    # Check if directory exists on Pi
    DIR_EXISTS=$(sshpass -p "$PI_PASS" ssh "${PI_USER}@${PI_HOST}" "[ -d ${DEST_DIR} ] && echo 'yes' || echo 'no'")
    
    if [ "$DIR_EXISTS" == "no" ]; then
        echo -e "${RED}Error: Directory ${DEST_DIR} does not exist on Pi${NC}"
        echo -e "${YELLOW}Use 'init' mode to clone the repository first${NC}"
        exit 1
    fi
    
    # Pull latest changes
    echo "Pulling latest changes from GitHub..."
    sshpass -p "$PI_PASS" ssh "${PI_USER}@${PI_HOST}" "cd ${DEST_DIR} && sudo git pull ${GIT_URL}"
    
    if [ $? -eq 0 ]; then
        echo -e "${GREEN}✓ Repository updated successfully${NC}"
    else
        echo -e "${RED}✗ Failed to update repository${NC}"
        exit 1
    fi
fi

# Upload .env file to Pi
echo -e "${YELLOW}Uploading .env to Pi...${NC}"
sshpass -p "$PI_PASS" scp .env "${PI_USER}@${PI_HOST}:${DEST_DIR}/.env"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ .env uploaded successfully${NC}"
else
    echo -e "${RED}✗ Failed to upload .env${NC}"
    exit 1
fi

# Set executable permissions for shell scripts
echo -e "${YELLOW}Setting executable permissions...${NC}"
sshpass -p "$PI_PASS" ssh "${PI_USER}@${PI_HOST}" "sudo chmod +x ${DEST_DIR}/*.sh 2>/dev/null || true"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Permissions set successfully${NC}"
else
    echo -e "${YELLOW}⚠ Warning: Could not set permissions (may not be critical)${NC}"
fi

# Verify deployment
echo -e "${YELLOW}Verifying deployment...${NC}"
sshpass -p "$PI_PASS" ssh "${PI_USER}@${PI_HOST}" "ls -lh ${DEST_DIR}/ | head -20"

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✓ Deployment completed successfully!${NC}"
else
    echo -e "${RED}✗ Verification failed${NC}"
    exit 1
fi
