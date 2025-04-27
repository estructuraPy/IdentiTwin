#!/bin/bash

echo "Using Python virtual environment..."
source ../setup_env/venv/bin/activate

echo "Running Identitwin System in simulation mode..."
python initialization.py --simulation

read -p "Press Enter to continue..."
