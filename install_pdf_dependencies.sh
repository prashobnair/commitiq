#!/bin/bash

# CommitIQ - PDF Report Generation Dependencies Installer
# This script installs dependencies required for PDF report generation

echo "===================================="
echo "CommitIQ PDF Dependencies Installer"
echo "===================================="

# Function to detect OS
detect_os() {
    if [[ "$OSTYPE" == "linux-gnu"* ]]; then
        OS="Linux"
    elif [[ "$OSTYPE" == "darwin"* ]]; then
        OS="macOS"
    else
        OS="Unsupported"
    fi
    echo "Detected OS: $OS"
}

# Python package installation
install_python_packages() {
    echo "Installing Python packages..."
    pip install pdfkit jinja2
    if [ $? -eq 0 ]; then
        echo "✅ Python packages installed successfully!"
    else
        echo "❌ Failed to install Python packages. Please install them manually:"
        echo "pip install pdfkit jinja2"
    fi
}

# Install wkhtmltopdf on Linux
install_wkhtmltopdf_linux() {
    echo "Installing wkhtmltopdf on Linux..."
    
    # Checking if apt is available (Debian/Ubuntu)
    if command -v apt &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y wkhtmltopdf
    # Checking if yum is available (CentOS/RHEL/Fedora)
    elif command -v yum &> /dev/null; then
        sudo yum install -y wkhtmltopdf
    # Checking if dnf is available (newer Fedora)
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y wkhtmltopdf
    else
        echo "❌ Could not determine package manager. Please install wkhtmltopdf manually."
        echo "Visit: https://wkhtmltopdf.org/downloads.html"
    fi
    
    # Verify installation
    if command -v wkhtmltopdf &> /dev/null; then
        echo "✅ wkhtmltopdf installed successfully!"
    else
        echo "❌ Failed to install wkhtmltopdf. Please install it manually:"
        echo "Visit: https://wkhtmltopdf.org/downloads.html"
    fi
}

# Install wkhtmltopdf on macOS
install_wkhtmltopdf_mac() {
    echo "Installing wkhtmltopdf on macOS..."
    
    # Check if Homebrew is installed
    if command -v brew &> /dev/null; then
        brew install wkhtmltopdf
    else
        echo "❌ Homebrew not found. Please install it first:"
        echo "Visit: https://brew.sh"
        return 1
    fi
    
    # Verify installation
    if command -v wkhtmltopdf &> /dev/null; then
        echo "✅ wkhtmltopdf installed successfully!"
    else
        echo "❌ Failed to install wkhtmltopdf. Please install it manually:"
        echo "brew install wkhtmltopdf"
    fi
}

# Update requirements.txt
update_requirements() {
    echo "Updating requirements.txt..."
    
    if [ -f "requirements.txt" ]; then
        if ! grep -q "pdfkit" requirements.txt; then
            echo "pdfkit==1.0.0" >> requirements.txt
        fi
        if ! grep -q "jinja2" requirements.txt; then
            echo "Jinja2==3.1.2" >> requirements.txt
        fi
        echo "✅ requirements.txt updated successfully!"
    else
        echo "⚠️ requirements.txt not found, creating new one..."
        echo "pdfkit==1.0.0" > requirements.txt
        echo "Jinja2==3.1.2" >> requirements.txt
        echo "✅ requirements.txt created successfully!"
    fi
}

# Main installation process
install() {
    detect_os
    
    # Install OS-specific dependencies
    if [[ "$OS" == "Linux" ]]; then
        install_wkhtmltopdf_linux
    elif [[ "$OS" == "macOS" ]]; then
        install_wkhtmltopdf_mac
    else
        echo "❌ Unsupported OS. Please install wkhtmltopdf manually:"
        echo "Visit: https://wkhtmltopdf.org/downloads.html"
    fi
    
    # Install Python packages
    install_python_packages
    
    # Update requirements.txt
    update_requirements
    
    echo ""
    echo "===================================="
    echo "Installation Complete!"
    echo "===================================="
    echo ""
    echo "If you encountered any errors, please install the missing dependencies manually."
    echo "For more information, visit: https://github.com/JazzCore/python-pdfkit"
}

# Execute the installation
install 