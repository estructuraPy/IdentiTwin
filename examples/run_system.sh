#!/bin/bash

echo "Using Conda environment..."
source ~/miniconda3/etc/profile.d/conda.sh
conda activate identitwin

echo "Running Identitwin System in simulation mode..."
python initialization.py --simulation

# No need for pause in Linux, but you can add this if you want to keep the terminal open
read -p "Press Enter to continue..."
