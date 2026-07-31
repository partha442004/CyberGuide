#!/bin/bash

# InternTrack Setup Script
# This script automates the project setup process

set -e  # Exit on error

echo "=================================="
echo "   InternTrack Setup Script"
echo "=================================="
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check Python version
check_python() {
    echo -e "${YELLOW}Checking Python version...${NC}"
    if command -v python3 &> /dev/null; then
        PYTHON=python3
    elif command -v python &> /dev/null; then
        PYTHON=python
    else
        echo -e "${RED}Python not found. Please install Python 3.11+${NC}"
        exit 1
    fi

    VERSION=$($PYTHON --version 2>&1 | awk '{print $2}')
    echo -e "${GREEN}Python version: $VERSION${NC}"
}

# Create virtual environment
create_venv() {
    echo ""
    echo -e "${YELLOW}Creating virtual environment...${NC}"

    if [ ! -d "venv" ]; then
        $PYTHON -m venv venv
        echo -e "${GREEN}Virtual environment created${NC}"
    else
        echo -e "${GREEN}Virtual environment already exists${NC}"
    fi

    # Activate virtual environment
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        source venv/Scripts/activate
    else
        source venv/bin/activate
    fi
    echo -e "${GREEN}Virtual environment activated${NC}"
}

# Install dependencies
install_deps() {
    echo ""
    echo -e "${YELLOW}Installing dependencies...${NC}"

    pip install --upgrade pip
    pip install -r requirements.txt
    pip install -r requirements-dev.txt

    echo -e "${GREEN}Dependencies installed${NC}"
}

# Setup environment
setup_env() {
    echo ""
    echo -e "${YELLOW}Setting up environment...${NC}"

    if [ ! -f ".env" ]; then
        cp .env.example .env
        echo -e "${GREEN}Created .env file from .env.example${NC}"
        echo -e "${YELLOW}Please edit .env with your configuration${NC}"
    else
        echo -e "${GREEN}.env file already exists${NC}"
    fi
}

# Create directories
create_dirs() {
    echo ""
    echo -e "${YELLOW}Creating directories...${NC}"

    mkdir -p data
    mkdir -p logs
    mkdir -p backups

    echo -e "${GREEN}Directories created${NC}"
}

# Initialize database
init_db() {
    echo ""
    echo -e "${YELLOW}Initializing database...${NC}"

    # Try to run migrations if alembic is configured
    if command -v alembic &> /dev/null; then
        alembic upgrade head
        echo -e "${GREEN}Database migrations applied${NC}"
    else
        echo -e "${YELLOW}Alembic not found, skipping migrations${NC}"
    fi
}

# Verify installation
verify_install() {
    echo ""
    echo -e "${YELLOW}Verifying installation...${NC}"

    python -c "import interntrack; print('Import successful')"

    echo -e "${GREEN}Installation verified${NC}"
}

# Print summary
print_summary() {
    echo ""
    echo "=================================="
    echo -e "${GREEN}Setup Complete!${NC}"
    echo "=================================="
    echo ""
    echo "To start the application:"
    echo ""
    echo "  1. Activate virtual environment:"
    if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
        echo "     venv\\Scripts\\activate"
    else
        echo "     source venv/bin/activate"
    fi
    echo ""
    echo "  2. Start the API server:"
    echo "     uvicorn interntrack.main:app --reload"
    echo ""
    echo "  3. Open browser:"
    echo "     http://localhost:8000/docs"
    echo ""
    echo "  4. (Optional) Start dashboard:"
    echo "     streamlit run dashboard/app.py"
    echo ""
    echo "=================================="
}

# Main execution
main() {
    check_python
    create_venv
    install_deps
    setup_env
    create_dirs
    init_db
    verify_install
    print_summary
}

# Run main function
main
