#!/bin/bash
# Cached runner for Antiyoy Python
# Copies source files to .run_cache/ and runs from there
# This allows source files to be modified without affecting the running instance

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

CACHE_DIR=".run_cache"

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Function to print colored messages
info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Rebuild cache
info "Rebuilding cache..."
mkdir -p "${CACHE_DIR}"

# Directories to copy (Python source modules)
dirs=("core" "ai" "campaign" "commands" "players" "save_load" "visibility" "web")

# Copy each directory
for dir in "${dirs[@]}"; do
    if [ -d "$dir" ]; then
        info "  Copying $dir/..."
        rm -rf "${CACHE_DIR}/${dir}"
        rsync -av --exclude='__pycache__' --exclude='*.pyc' "$dir/" "${CACHE_DIR}/${dir}/"
    fi
done

info "Cache rebuilt successfully"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    error "Virtual environment not found. Run ./setup_dev_env.sh first"
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate

# Check if assets are set up (check original source, not cache)
if [ ! -L "web/static/assets/original_game_assets" ] && [ ! -d "web/static/assets/original_game_assets" ]; then
    warn "Assets not set up. Setting up assets..."
    python web/setup_assets.py
    # Copy updated web directory after asset setup
    rsync -av --exclude='__pycache__' --exclude='*.pyc' web/ "${CACHE_DIR}/web/"
fi

# Create a launcher script in cache that sets up environment correctly
cat > "${CACHE_DIR}/run_server.py" << 'EOF'
#!/usr/bin/env python3
"""Launcher script for Flask app from cache with debug disabled."""
import sys
import os
from pathlib import Path

# Get the cache directory (where this script is located)
CACHE_DIR = Path(__file__).parent.absolute()
# Original project root is one level up from cache (cache is .run_cache inside project)
ORIGINAL_PROJECT_ROOT = CACHE_DIR.parent

# Add cache to Python path for imports (modules are in cache)
if str(CACHE_DIR) not in sys.path:
    sys.path.insert(0, str(CACHE_DIR))

# Set environment variable for original project root (for assets)
os.environ['ANTIYOY_ORIGINAL_ROOT'] = str(ORIGINAL_PROJECT_ROOT)

# Import app (this will use CACHE_DIR as PROJECT_ROOT, which is fine for imports)
from web.app import app
from pathlib import Path

# Fix ASSETS_ROOT to point to original location
# ASSETS_ROOT should be: original_project_root/../antiyoy_hd/assets
# Which is: work/antiyoy_hd/assets
app.config['ASSETS_ROOT'] = ORIGINAL_PROJECT_ROOT.parent / "antiyoy_hd" / "assets"
# Also update the module-level variable if it exists
import web.app as app_module
app_module.ASSETS_ROOT = app.config['ASSETS_ROOT']

# Override debug mode
app.config['DEBUG'] = False
app.config['TEMPLATES_AUTO_RELOAD'] = False

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000, use_reloader=False)
EOF

chmod +x "${CACHE_DIR}/run_server.py"

# Change to cache directory for running
cd "$CACHE_DIR"

info "Starting Flask server from cache..."
info "Server will be available at: http://localhost:5000"
info "Source files can be modified without affecting the running server"
info "Press Ctrl+C to stop the server"
echo ""

# Run in foreground
python run_server.py
