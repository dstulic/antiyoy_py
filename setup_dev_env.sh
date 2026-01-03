#!/bin/bash
# Setup script for Antiyoy Python development environment
# This script creates a virtual environment and installs all dependencies
# Run this script to set up a fresh development environment

set -e  # Exit on error

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${SCRIPT_DIR}/.venv"
REQUIREMENTS_FILE="${SCRIPT_DIR}/requirements.txt"

echo "Setting up Antiyoy Python development environment..."
echo "Script directory: ${SCRIPT_DIR}"
echo "Virtual environment: ${VENV_DIR}"

# Check if Python 3 is available
if ! command -v python3 &> /dev/null; then
    echo "Error: python3 is not installed or not in PATH"
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
echo "Using: ${PYTHON_VERSION}"

# Remove existing virtual environment if it exists
if [ -d "${VENV_DIR}" ]; then
    echo "Removing existing virtual environment..."
    rm -rf "${VENV_DIR}"
fi

# Create new virtual environment
echo "Creating virtual environment..."
python3 -m venv "${VENV_DIR}"

# Activate virtual environment
echo "Activating virtual environment..."
source "${VENV_DIR}/bin/activate"

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install dependencies
if [ -f "${REQUIREMENTS_FILE}" ]; then
    echo "Installing dependencies from ${REQUIREMENTS_FILE}..."
    pip install -r "${REQUIREMENTS_FILE}"
else
    echo "Warning: ${REQUIREMENTS_FILE} not found. Installing minimal dependencies..."
    pip install pytest ruff
fi

# Verify installation
echo ""
echo "Verifying installation..."
echo "Python: $(python --version)"
echo "Pip: $(pip --version)"
echo ""
echo "Installed packages:"
pip list

echo ""
echo "✓ Development environment setup complete!"
echo ""
echo "To activate the virtual environment, run:"
echo "  source ${VENV_DIR}/bin/activate"
echo ""
echo "Or use the virtual environment directly:"
echo "  ${VENV_DIR}/bin/python <script>"
echo "  ${VENV_DIR}/bin/pytest tests/ -v"
