#!/bin/bash
echo "Setting up Identitwin environment..."

# Get script directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Check for requirements.txt in common locations
if [ -f "$PROJECT_ROOT/requirements.txt" ]; then
    REQ_FILE="$PROJECT_ROOT/requirements.txt"
elif [ -f "$SCRIPT_DIR/requirements.txt" ]; then
    REQ_FILE="$SCRIPT_DIR/requirements.txt"
else
    echo "Error: requirements.txt not found"
    echo "Looked in:"
    echo "- $PROJECT_ROOT/requirements.txt"
    echo "- $SCRIPT_DIR/requirements.txt"
    exit 1
fi

# Remove existing virtual environment if it exists
if [ -d "venv" ]; then
    echo "Removing existing virtual environment..."
    rm -rf venv
fi

# Create and activate virtual environment
echo "Creating virtual environment..."
python3 -m venv venv
source venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r "$REQ_FILE"

echo "Environment setup complete! You can now run run_pi.sh to start the application."
