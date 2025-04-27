#!/bin/bash

echo "Using Python virtual environment..."
source ../setup_env/venv/bin/activate

echo "Running Identitwin System in hardware mode..."
python initialization.py

# No need for pause in Linux, but you can add this if you want to keep the terminal open
read -p "Press Enter to continue..."
