#!/bin/bash
# Script to run the simulation of the Identitwin Monitoring System on a Raspberry Pi.
# Ensure Python3 is installed and available in the system PATH.
# Set the output directory for simulation data.
OUTPUT_DIR="/home/pi/identitwin_sim_output"

# Run the initialization script in simulation mode.
python initialization.py --simulation "$@"
