#!/usr/bin/env python3
"""
Identitwin Monitoring System - Initialization Script

This script serves as the entry point for the Identitwin monitoring system.
"""

import argparse
import sys
import time
import math
import warnings
import os
import traceback
import platform
from datetime import datetime
import numpy as np
import matplotlib
import importlib  # Add importlib to dynamically load modules
from collections import deque  # Add deque import

# Suppress warnings related to hardware detection
warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", message=".*chip_id.*")
warnings.filterwarnings("ignore", message=".*Adafruit-PlatformDetect.*")

# Check if we're on a Raspberry Pi
IS_RASPBERRY_PI = platform.system() == "Linux"

# Ensure TkAgg backend is used, falling back to QtAgg if necessary.
try:
    matplotlib.use('TkAgg')
except ImportError:
    print("Warning: TkAgg backend not found, trying QtAgg...")
    try:
        matplotlib.use('QtAgg')
    except ImportError:
        print("Warning: QtAgg backend not found. Plotting might not work interactively.")

warnings.filterwarnings("ignore", message="FigureCanvasAgg is non-interactive, and thus cannot be shown")

# Import from the identitwin library
from identitwin import configurator
from identitwin.system_monitoring import MonitoringSystem
from identitwin import calibration
from identitwin import report_generator
from identitwin.calibration import calibrate_lvdt_channels

# Default values for sampling rates and thresholds.
ACCEL_SAMPLING_RATE = 100.0  # Hz
LVDT_SAMPLING_RATE = 5.0  # Hz
PLOT_REFRESH_RATE = 10.0  # Hz

NUM_LVDTS = 2
NUM_ACCELS = 2
LVDT_SLOPES = [19.86, 21.86]

ACCEL_TRIGGER_THRESHOLD = 0.981  # m/sSetting up^2 (0.1g)
ACCEL_DETRIGGER_THRESHOLD = 0.589  # m/s^2 (60% of trigger threshold)

DISPLACEMENT_TRIGGER_THRESHOLD = 10.0  # mm
DISPLACEMENT_DETRIGGER_THRESHOLD = 5.0  # mm

PRE_EVENT_TIME = 5.0  # seconds (Time recorded before the trigger)
POST_EVENT_TIME = 15.0 # seconds (Time recorded after the event ends)
MIN_EVENT_DURATION = 2.0  # seconds

STATUS_PIN = 17
ACTIVITY_PIN = 18

# Define default sensor and plot settings.
enable_lvdt = True
enable_accel = True

enable_plots = False  # Forced to False: visualization module removed
enable_plot_displacement = False  # Forced to False: visualization module removed
enable_accel_plots = False  # Forced to False: visualization module removed
enable_fft_plots = False  # Forced to False: visualization module removed


def print_banner():
    """Print a welcome banner with program and author information."""
    banner = """
===============================================================================
                  IdentiTwin Structural Monitoring System
===============================================================================

Developed by:
    - Ing. Angel Navarro-Mora M.Sc, Escuela de Ingeniería en Construcción
    - Alvaro Perez-Mora, Escuela de Ingeniería Electrónica

Instituto Tecnologico de Costa Rica, 2025

"""
    print(banner)
    time.sleep(2)


def parse_arguments():
    """Parse command-line arguments to configure the monitoring system.

    Args:
        None

    Returns:
        argparse.Namespace: Parsed arguments.
    """
    parser = argparse.ArgumentParser(description="Identitwin - Structural Vibration Monitoring System")

    # Sensor configuration
    sensor_group = parser.add_argument_group('Sensor Configuration')
    sensor_group.add_argument('--lvdt', action='store_true', help='Enable LVDT measurements')
    sensor_group.add_argument('--no-lvdt', action='store_true', help='Disable LVDT measurements')
    sensor_group.add_argument('--accel', action='store_true', help='Enable accelerometer measurements')
    sensor_group.add_argument('--no-accel', action='store_true', help='Disable accelerometer measurements')

    # Visualization configuration (Arguments kept for potential future use, but functionality disabled)
    visual_group = parser.add_argument_group('Visualization Configuration (Currently Disabled)')
    visual_group.add_argument('--plot-displacement', action='store_true', help='Enable LVDT displacement plots (Disabled)')
    visual_group.add_argument('--no-plot-displacement', action='store_true', help='Disable LVDT displacement plots (Disabled)')
    visual_group.add_argument('--accel-plots', action='store_true', help='Enable acceleration plots (Disabled)')
    visual_group.add_argument('--no-accel-plots', action='store_true', help='Disable acceleration plots (Disabled)')
    visual_group.add_argument('--fft-plots', action='store_true', help='Enable FFT plots (Disabled)')
    visual_group.add_argument('--no-fft-plots', action='store_true', help='Disable FFT plots (Disabled)')

    # Sampling rate configuration
    rate_group = parser.add_argument_group('Sampling Rate Configuration')
    rate_group.add_argument('--accel-rate', type=float,
                            help=f'Accelerometer sampling rate in Hz (default: {ACCEL_SAMPLING_RATE} Hz)')
    rate_group.add_argument('--lvdt-rate', type=float,
                            help=f'LVDT sampling rate in Hz (default: {LVDT_SAMPLING_RATE} Hz)')
    rate_group.add_argument('--plot-rate', type=float,
                            help=f'Plot refresh rate in Hz (default: {PLOT_REFRESH_RATE} Hz, Disabled)')

    # System configuration
    system_group = parser.add_argument_group('System Configuration')
    system_group.add_argument('--output-dir', type=str, help='Custom output directory for data, logs, and reports')
    # config file argument removed as it's not currently used
    # system_group.add_argument('--config', type=str, help='Path to configuration file')

    # Add simulation mode
    parser.add_argument('--simulation', action='store_true', help='Run in simulation mode (simulated sensors), automatically enabled if not on Raspberry Pi')

    return parser.parse_args()


def apply_cli_args(args):
    """Apply command-line arguments to override the default configuration.

    Args:
        args: Parsed command-line arguments.

    Returns:
        None
    """
    global enable_lvdt, enable_accel, enable_plot_displacement, enable_accel_plots, enable_fft_plots
    global ACCEL_SAMPLING_RATE, LVDT_SAMPLING_RATE, PLOT_REFRESH_RATE

    # Override sensor settings
    if args.lvdt:
        enable_lvdt = True
    if args.no_lvdt:
        enable_lvdt = False
    if args.accel:
        enable_accel = True
    if args.no_accel:
        enable_accel = False

    # Override visualization settings (currently disabled, but keep logic)
    if args.plot_displacement:
        enable_plot_displacement = True
    if args.no_plot_displacement:
        enable_plot_displacement = False
    if args.accel_plots:
        enable_accel_plots = True
    if args.no_accel_plots:
        enable_accel_plots = False
    if args.fft_plots:
        enable_fft_plots = True
    if args.no_fft_plots:
        enable_fft_plots = False

    # Ensure plot settings are consistent with sensor availability (even if disabled)
    if not enable_lvdt:
        enable_plot_displacement = False
    if not enable_accel:
        enable_accel_plots = False
        enable_fft_plots = False # FFT depends on accel data

    # Override sampling rates with validation
    if args.accel_rate is not None:
        if args.accel_rate > 0:
            ACCEL_SAMPLING_RATE = args.accel_rate
        else:
            print("Warning: Invalid accelerometer rate provided. Using default.")
    if args.lvdt_rate is not None:
        if args.lvdt_rate > 0:
            LVDT_SAMPLING_RATE = args.lvdt_rate
        else:
            print("Warning: Invalid LVDT rate provided. Using default.")
    if args.plot_rate is not None:
        if args.plot_rate > 0:
            PLOT_REFRESH_RATE = args.plot_rate
        else:
            print("Warning: Invalid plot rate provided. Using default.")


def get_operation_mode_name():
    """Return a descriptive name for the current operation mode."""
    if enable_lvdt and enable_accel:
        return "LVDT + Accelerometer"
    elif enable_lvdt:
        return "LVDT Only"
    elif enable_accel:
        return "Accelerometer Only"
    else:
        return "No Sensors Enabled"


def create_system_config(args):
    """Create the system configuration object based on mode and arguments."""
    global enable_lvdt, enable_accel, enable_plots, enable_plot_displacement, enable_accel_plots, enable_fft_plots
    global SimulatorConfig # Make sure SimulatorConfig is accessible if imported

    # Determine if running in simulation mode
    simulation_mode = args.simulation or not IS_RASPBERRY_PI

    # Choose the correct configuration class
    # Ensure SimulatorConfig is loaded if needed (handled in main)
    if simulation_mode and SimulatorConfig is None:
         # This case should ideally not happen if main logic is correct, but added as safeguard
         raise RuntimeError("SimulatorConfig not loaded despite simulation mode being active.")
    ConfigClass = SimulatorConfig if simulation_mode else configurator.SystemConfig

    # Prepare GPIO pins list
    gpio_pins_list = [STATUS_PIN, ACTIVITY_PIN]

    # Create the configuration object using global constants and CLI args
    config = ConfigClass(
        enable_lvdt=enable_lvdt,
        enable_accel=enable_accel,
        output_dir=args.output_dir, # Use output_dir from args
        num_lvdts=NUM_LVDTS,
        num_accelerometers=NUM_ACCELS,
        lvdt_slopes=LVDT_SLOPES, # Ensure LVDT_SLOPES is passed here
        sampling_rate_acceleration=ACCEL_SAMPLING_RATE,
        sampling_rate_lvdt=LVDT_SAMPLING_RATE,
        plot_refresh_rate=PLOT_REFRESH_RATE, # Plot rate kept for consistency
        gpio_pins=gpio_pins_list,
        trigger_acceleration_threshold=ACCEL_TRIGGER_THRESHOLD,
        detrigger_acceleration_threshold=ACCEL_DETRIGGER_THRESHOLD,
        trigger_displacement_threshold=DISPLACEMENT_TRIGGER_THRESHOLD,
        detrigger_displacement_threshold=DISPLACEMENT_DETRIGGER_THRESHOLD,
        pre_event_time=PRE_EVENT_TIME,
        post_event_time=POST_EVENT_TIME,
        min_event_duration=MIN_EVENT_DURATION,
        verbose=simulation_mode # Enable verbosity in simulation mode by default
    )

    # Store operational mode and plot settings in config
    config.operational_mode = get_operation_mode_name()
    config.enable_plots = False # Force False
    config.enable_plot_displacement = False # Force False
    config.enable_accel_plots = False # Force False
    config.enable_fft_plots = False # Force False

    # Store expected rates for reporting
    config.expected_sampling_rate_acceleration = ACCEL_SAMPLING_RATE
    config.expected_sampling_rate_lvdt = LVDT_SAMPLING_RATE

    return config


def main():
    """Main function to initialize and run the monitoring system."""
    print_banner()
    args = parse_arguments()
    apply_cli_args(args) # Apply CLI args to modify global constants

    # --- Simulation Mode Handling ---
    simulation_mode = args.simulation or not IS_RASPBERRY_PI
    global SimulatorConfig # Needed to assign the class
    SimulatorConfig = None # Initialize to None
    if simulation_mode:
        if not IS_RASPBERRY_PI and not args.simulation:
             print("Non-Raspberry Pi platform detected. Automatically enabling simulation mode.")
        try:
            simulator_module = importlib.import_module('identitwin.simulator')
            SimulatorConfig = simulator_module.SimulatorConfig
            print("Simulator configuration module loaded.")
        except ImportError as e:
            print(f"FATAL: Error importing simulator module: {e}")
            sys.exit(1) # Exit if simulator cannot be loaded when needed
    else:
         print("Hardware mode enabled (Raspberry Pi detected or --simulation not used).")


    # --- Configuration ---
    if not enable_lvdt and not enable_accel:
        print("ERROR: At least one sensor type (LVDT or accelerometer) must be enabled.")
        sys.exit(1)

    # Create the single, definitive config object
    config = create_system_config(args)

    print("\n======================== Identitwin Monitoring System =========================\n")
    print(f"Operation Mode: {'Simulation' if simulation_mode else 'Hardware'}")
    print(f"Sensor Mode: {config.operational_mode}")
    print("\nConfiguration Summary:")
    print(f"  LVDT Enabled: {config.enable_lvdt} ({config.num_lvdts} channels)")
    print(f"  Accelerometer Enabled: {config.enable_accel} ({config.num_accelerometers} channels)")
    print(f"  LVDT Rate (Expected): {config.expected_sampling_rate_lvdt} Hz")
    print(f"  Accel Rate (Expected): {config.expected_sampling_rate_acceleration} Hz")
    print(f"  Output Directory: {config.output_dir}")
    # Add other relevant config details if needed

    # --- System Initialization ---
    monitor_system = MonitoringSystem(config)

    try:
        # Generate initial system report before setup
        system_report_file = os.path.join(config.reports_dir, f"system_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        report_generator.generate_system_report(config, system_report_file)

        # Setup sensors (includes calibration) and processing
        monitor_system.setup_sensors()
        monitor_system.initialize_processing()

        # --- Monitoring ---
        print("\n======================== Starting Monitoring ========================\n")
        monitor_system.start_monitoring()
        monitor_system.wait_for_completion() # Blocks until stopped (e.g., by Ctrl+C)

    except KeyboardInterrupt:
        print("\nProgram stopped by user (KeyboardInterrupt).")
        # stop_monitoring is called within wait_for_completion's exception handler

    except Exception as e:
        print(f"\nFATAL ERROR during monitoring: {e}")
        traceback.print_exc()
        # Attempt graceful shutdown if possible
        if 'monitor_system' in locals() and monitor_system.running:
            try:
                monitor_system.stop_monitoring()
            except Exception as stop_err:
                 print(f"Error during forced stop: {stop_err}")

    finally:
        # --- Cleanup and Final Report ---
        print("\n======================== Shutting Down ========================\n")
        if 'monitor_system' in locals():
            # Generate final summary report
            print("Generating final summary report...")
            summary_report_file = os.path.join(config.reports_dir, f"summary_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
            # Ensure performance stats are updated before generating the report
            if hasattr(monitor_system, '_update_performance_stats'):
                 try:
                     # Pass the deques required by the method
                     monitor_system._update_performance_stats(
                         monitor_system.performance_stats.get('accel_periods', deque()),
                         monitor_system.performance_stats.get('lvdt_periods', deque())
                     )
                 except Exception as perf_update_err:
                      print(f"Warning: Could not update performance stats for final report: {perf_update_err}")

            report_generator.generate_summary_report(monitor_system, summary_report_file)

            # Cleanup resources
            monitor_system.cleanup()
        print("\nIdentitwin monitoring system shut down.")


if __name__ == "__main__":
    main() # Call the refactored main function
