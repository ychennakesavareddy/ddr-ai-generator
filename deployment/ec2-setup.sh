#!/bin/bash
# ============================================================================
# EC2 Setup Script for AI DDR Report Generator
# This script automates the deployment of the FastAPI backend on AWS EC2
# Ubuntu 22.04 LTS
# ============================================================================

set -e  # Exit on error
set -o pipefail  # Pipe failures cause script to exit

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# ============================================================================
# Configuration Variables
# ============================================================================

APP_DIR="/home/ubuntu/ddr-ai-generator"
BACKEND_DIR="${APP_DIR}/backend"
PYTHON_VERSION="python3.10"
VENV_DIR="${BACKEND_DIR}/venv"
PORT=8000
DOMAIN_OR_IP=$(curl -s http://169.254.169.254/latest/meta-data/public-ipv4 || echo "localhost")

# ============================================================================
# Helper Functions
# ============================================================================

print_message() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_success() {
    if [ $? -eq 0 ]; then
        print_success "$1"
    else
        print_error "$2"
        exit 1
    fi
}

# ============================================================================
# 1. System Update and Prerequisites
# ============================================================================

print_message "Starting EC2 setup for AI DDR Report Generator..."
print_message "==========================================="

# Update package lists
print_message "Updating package lists..."
sudo apt-get update -y
check_success "Package lists updated successfully" "Failed to update package lists"

# Upgrade all packages
print_message "Upgrading installed packages..."
sudo apt-get upgrade -y
check_success "Packages upgraded successfully" "Failed to upgrade packages"

# Install essential system packages
print_message "Installing essential system packages..."
sudo apt-get install -y \
    software-properties-common \
    curl \
    wget \
    git \
    build-essential \
    libssl-dev \
    libffi-dev \
    python3-dev \
    python3-pip \
    python3-venv \
    nginx \
    ufw \
    supervisor \
    htop \
    vim
check_success "System packages installed successfully" "Failed to install system packages"

# ============================================================================
# 2. Python Installation
# ============================================================================

print_message "Checking Python installation..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION_INSTALLED=$(python3 --version | cut -d ' ' -f 2 | cut -d '.' -f 1-2)
    print_message "Python ${PYTHON_VERSION_INSTALLED} is already installed"
else
    print_message "Installing Python ${PYTHON_VERSION}..."
    sudo apt-get install -y ${PYTHON_VERSION}
    check_success "Python installed successfully" "Failed to install Python"
fi

# Install pip if not present
print_message "Checking pip installation..."
if ! command -v pip3 &> /dev/null; then
    print_message "Installing pip..."
    sudo apt-get install -y python3-pip
    check_success "pip installed successfully" "Failed to install pip"
else
    print_message "pip is already installed"
fi

# Upgrade pip to latest
print_message "Upgrading pip to latest version..."
sudo pip3 install --upgrade pip
check_success "pip upgraded successfully" "Failed to upgrade pip"

# ============================================================================
# 3. Application Setup
# ============================================================================

print_message "Setting up application directory..."

# Create application directory
if [ ! -d "${APP_DIR}" ]; then
    mkdir -p "${APP_DIR}"
    print_message "Created application directory: ${APP_DIR}"
else
    print_message "Application directory already exists: ${APP_DIR}"
fi

# Copy application files (assuming script is run from deployment directory)
print_message "Copying application files..."
if [ -d "../backend" ]; then
    cp -r ../backend "${APP_DIR}/"
    print_message "Backend files copied successfully"
else
    print_warning "Backend directory not found. Please upload manually."
    print_warning "You can use: scp -r backend/ ubuntu@${DOMAIN_OR_IP}:${APP_DIR}/"
fi

# ============================================================================
# 4. Virtual Environment Setup
# ============================================================================

print_message "Setting up Python virtual environment..."

cd "${BACKEND_DIR}"

# Create virtual environment
if [ ! -d "${VENV_DIR}" ]; then
    python3 -m venv "${VENV_DIR}"
    check_success "Virtual environment created at ${VENV_DIR}" "Failed to create virtual environment"
else
    print_message "Virtual environment already exists at ${VENV_DIR}"
fi

# Activate virtual environment and install requirements
print_message "Activating virtual environment and installing requirements..."
source "${VENV_DIR}/bin/activate"

# Install requirements
if [ -f "requirements.txt" ]; then
    print_message "Installing Python dependencies from requirements.txt..."
    pip install --upgrade pip
    pip install -r requirements.txt
    check_success "Dependencies installed successfully" "Failed to install dependencies"
    
    # Install additional packages for production
    pip install gunicorn uvicorn[standard]
    check_success "Production packages installed" "Failed to install production packages"
else
    print_error "requirements.txt not found in ${BACKEND_DIR}"
    exit 1
fi

# Create required directories
print_message "Creating required directories..."
mkdir -p uploads/extracted_images
mkdir -p generated_reports
check_success "Directories created" "Failed to create directories"

# Create .env file if not exists
if [ ! -f ".env" ]; then
    print_message "Creating .env file template..."
    cat > .env << EOF
# Google Gemini API Configuration
GEMINI_API_KEY=your_gemini_api_key_here

# Application Settings
UPLOAD_DIR=uploads
GENERATED_REPORTS_DIR=generated_reports
MAX_FILE_SIZE=20971520
CORS_ORIGINS=http://${DOMAIN_OR_IP}:3000,http://localhost:3000

# Logging
LOG_LEVEL=INFO
EOF
    print_warning "Please update .env file with your Gemini API key"
    print_warning "Edit: ${BACKEND_DIR}/.env"
else
    print_message ".env file already exists"
fi

# ============================================================================
# 5. Firewall Configuration
# ============================================================================

print_message "Configuring firewall..."

# Enable UFW
sudo ufw --force enable
check_success "UFW enabled" "Failed to enable UFW"

# Allow SSH (port 22)
sudo ufw allow 22/tcp
print_message "SSH (22) allowed"

# Allow HTTP (port 80)
sudo ufw allow 80/tcp
print_message "HTTP (80) allowed"

# Allow HTTPS (port 443)
sudo ufw allow 443/tcp
print_message "HTTPS (443) allowed"

# Allow application port
sudo ufw allow ${PORT}/tcp
print_message "Application port ${PORT} allowed"

# Allow Nginx
sudo ufw allow 'Nginx Full'
print_message "Nginx Full allowed"

# Show firewall status
sudo ufw status verbose
check_success "Firewall configured" "Failed to configure firewall"

# ============================================================================
# 6. Nginx Configuration (Reverse Proxy)
# ============================================================================

print_message "Configuring Nginx reverse proxy..."

# Create Nginx configuration
sudo tee /etc/nginx/sites-available/ddr-api > /dev/null << EOF
server {
    listen 80;
    server_name ${DOMAIN_OR_IP} _;

    # Increase client max body size for file uploads
    client_max_body_size 25M;

    location / {
        proxy_pass http://127.0.0.1:${PORT};
        proxy_http_version 1.1;
        proxy_set_header Upgrade \$http_upgrade;
        proxy_set_header Connection 'upgrade';
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
        proxy_cache_bypass \$http_upgrade;
        proxy_read_timeout 300s;
        proxy_connect_timeout 75s;
    }

    # Serve static reports
    location /reports/ {
        alias /home/ubuntu/ddr-ai-generator/backend/generated_reports/;
    }

    # Health check endpoint
    location /health {
        proxy_pass http://127.0.0.1:${PORT}/;
        access_log off;
    }
}
EOF

# Enable the site
sudo ln -sf /etc/nginx/sites-available/ddr-api /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Test Nginx configuration
sudo nginx -t
check_success "Nginx configuration is valid" "Nginx configuration test failed"

# Reload Nginx
sudo systemctl reload nginx
check_success "Nginx reloaded" "Failed to reload Nginx"

# ============================================================================
# 7. Supervisor Configuration (Process Management)
# ============================================================================

print_message "Configuring Supervisor for process management..."

# Create Supervisor configuration
sudo tee /etc/supervisor/conf.d/ddr-api.conf > /dev/null << EOF
[program:ddr-api]
command=${VENV_DIR}/bin/uvicorn main:app --host 0.0.0.0 --port ${PORT}
directory=${BACKEND_DIR}
user=ubuntu
autostart=true
autorestart=true
stopasgroup=true
killasgroup=true
stderr_logfile=/var/log/ddr-api.err.log
stdout_logfile=/var/log/ddr-api.out.log
environment=PATH="${VENV_DIR}/bin",PYTHONPATH="${BACKEND_DIR}"
EOF

# Reload Supervisor
sudo supervisorctl reread
check_success "Supervisor reread configuration" "Failed to reread Supervisor configuration"

sudo supervisorctl update
check_success "Supervisor updated" "Failed to update Supervisor"

sudo supervisorctl start ddr-api
check_success "Application started" "Failed to start application"

# ============================================================================
# 8. Logging and Monitoring Setup
# ============================================================================

print_message "Setting up logging and monitoring..."

# Create log rotation configuration
sudo tee /etc/logrotate.d/ddr-api > /dev/null << EOF
/var/log/ddr-api.*.log {
    daily
    missingok
    rotate 7
    compress
    delaycompress
    notifempty
    create 0640 ubuntu ubuntu
    sharedscripts
    postrotate
        supervisorctl signal USR1 ddr-api
    endscript
}
EOF

# ============================================================================
# 9. Health Check and Verification
# ============================================================================

print_message "Performing health check..."

# Wait for application to start
sleep 5

# Test health endpoint
if curl -s -f "http://localhost:${PORT}/" > /dev/null; then
    print_success "Application is running and responding!"
else
    print_warning "Application may not be responding. Check logs:"
    print_warning "sudo supervisorctl tail ddr-api"
fi

# ============================================================================
# 10. Final Instructions
# ============================================================================

echo ""
echo "==========================================="
print_success "EC2 Setup Complete!"
echo "==========================================="
echo ""
echo "Application Information:"
echo "  - IP Address: ${DOMAIN_OR_IP}"
echo "  - Port: ${PORT}"
echo "  - API URL: http://${DOMAIN_OR_IP}:${PORT}"
echo "  - Reports URL: http://${DOMAIN_OR_IP}/reports/"
echo ""
echo "Management Commands:"
echo "  - Start app:   sudo supervisorctl start ddr-api"
echo "  - Stop app:    sudo supervisorctl stop ddr-api"
echo "  - Restart app: sudo supervisorctl restart ddr-api"
echo "  - Check status: sudo supervisorctl status ddr-api"
echo "  - View logs:   sudo supervisorctl tail -f ddr-api"
echo "  - Reload Nginx: sudo systemctl reload nginx"
echo ""
echo "Next Steps:"
echo "  1. Update Gemini API key in ${BACKEND_DIR}/.env"
echo "  2. Restart application: sudo supervisorctl restart ddr-api"
echo "  3. Configure SSL certificate (optional):"
echo "     sudo apt-get install certbot python3-certbot-nginx"
echo "     sudo certbot --nginx -d ${DOMAIN_OR_IP}"
echo ""
echo "Frontend Deployment:"
echo "  - Deploy React frontend to AWS Amplify"
echo "  - Update API URL in frontend environment variables"
echo ""
echo "Important Notes:"
echo "  - Default username: ubuntu"
echo "  - Default application directory: ${APP_DIR}"
echo "  - Virtual environment: ${VENV_DIR}"
echo "  - Uploads directory: ${BACKEND_DIR}/uploads"
echo "  - Generated reports: ${BACKEND_DIR}/generated_reports"
echo ""
echo "==========================================="
print_success "Setup completed successfully!"
echo "==========================================="

# ============================================================================
# 11. Optional: Install SSL Certificate (Commented)
# ============================================================================

# Uncomment below lines to automatically install SSL certificate
# print_message "Installing SSL certificate (optional)..."
# sudo apt-get install -y certbot python3-certbot-nginx
# sudo certbot --nginx -d ${DOMAIN_OR_IP} --non-interactive --agree-tos --email admin@${DOMAIN_OR_IP}

# ============================================================================
# End of Script
# ============================================================================