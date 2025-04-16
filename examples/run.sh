#!/bin/bash

# Check if Python is installed
if ! command -v python &> /dev/null; then
    echo "Error: Python is not installed"
    exit 1
fi

# Set working directory to script location
cd "$(dirname "$0")"

# Activate virtual environment if exists
if [ -d "../venv" ]; then
    source ../venv/bin/activate
fi

# Run initialization script with all arguments
python initialization.py "$@"

# Check exit status
if [ $? -ne 0 ]; then
    echo "Error: Initialization failed"
    exit 1
fi

echo "Initialization completed successfully"
