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

# Add the project root to the Python path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

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
from identitwin import state # <--- IMPORT STATE MODULE

# Default values for sampling rates and thresholds.
ACCEL_SAMPLING_RATE = 100.0  # Hz
LVDT_SAMPLING_RATE = 20.0  # Hz
PLOT_REFRESH_RATE = 1.0  # Hz
WINDOW_DURATION = 15.0  # seconds for relative time window in plots

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

enable_plots = True
enable_plot_displacement = True
enable_accel_plots = True
enable_fft_plots = True


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

===============================================================================
"""
    print(banner)
    time.sleep(5)


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

    # Visualization configuration
    visual_group = parser.add_argument_group('Visualization Configuration')
    visual_group.add_argument('--plot-displacement', action='store_true', help='Enable LVDT displacement plots')
    visual_group.add_argument('--no-plot-displacement', action='store_true', help='Disable LVDT displacement plots')
    visual_group.add_argument('--accel-plots', action='store_true', help='Enable acceleration plots')
    visual_group.add_argument('--no-accel-plots', action='store_true', help='Disable acceleration plots')
    visual_group.add_argument('--fft-plots', action='store_true', help='Enable FFT plots')
    visual_group.add_argument('--no-fft-plots', action='store_true', help='Disable FFT plots')

    # Sampling rate configuration
    rate_group = parser.add_argument_group('Sampling Rate Configuration')
    rate_group.add_argument('--accel-rate', type=float,
                            help=f'Accelerometer sampling rate in Hz (default: {ACCEL_SAMPLING_RATE} Hz)')
    rate_group.add_argument('--lvdt-rate', type=float,
                            help=f'LVDT sampling rate in Hz (default: {LVDT_SAMPLING_RATE} Hz)')
    rate_group.add_argument('--plot-rate', type=float,
                            help=f'Plot refresh rate in Hz (default: {PLOT_REFRESH_RATE} Hz)')

    # System configuration
    system_group = parser.add_argument_group('System Configuration')
    system_group.add_argument('--output-dir', type=str, help='Custom output directory')
    system_group.add_argument('--config', type=str, help='Path to configuration file')

    # Add simulation mode
    parser.add_argument('--simulation', action='store_true', help='Run in simulation mode (simulated sensors)')

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

    # Override visualization settings
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

    # Ensure plot settings are consistent with sensor availability
    if not enable_lvdt:
        enable_plot_displacement = False
    if not enable_accel:
        enable_accel_plots = False
        enable_fft_plots = False

    # Override sampling rates with validation
    if args.accel_rate is not None:
        if args.accel_rate > 0:
            ACCEL_SAMPLING_RATE = args.accel_rate
        else:
            print(f"Warning: Invalid accelerometer sampling rate ({args.accel_rate}). Using default: {ACCEL_SAMPLING_RATE} Hz")

    if args.lvdt_rate is not None:
        if args.lvdt_rate > 0:
            LVDT_SAMPLING_RATE = args.lvdt_rate
        else:
            print(f"Warning: Invalid LVDT sampling rate ({args.lvdt_rate}). Using default: {LVDT_SAMPLING_RATE} Hz")

    if args.plot_rate is not None:
        if args.plot_rate > 0:
            PLOT_REFRESH_RATE = args.plot_rate
        else:
            print(f"Warning: Invalid plot refresh rate ({args.plot_rate}). Using default: {PLOT_REFRESH_RATE} Hz")


def get_operation_mode_name():
    """Return a descriptive name for the current operation mode.

    Args:
        None

    Returns:
        str: Operation mode name.
    """
    if enable_lvdt and enable_accel:
        return "Combined Mode (LVDT + Accelerometers)"
    elif enable_lvdt:
        return "LVDT-Only Mode"
    elif enable_accel:
        return "Accelerometer-Only Mode"
    else:
        return "No Sensors Mode (Invalid)"


def create_system_config():
    """Create a SystemConfig object with current settings.

    Args:
        None

    Returns:
        configurator.SystemConfig: System configuration object.
    """
    
    gpio_pins_list = [STATUS_PIN, ACTIVITY_PIN]

    from identitwin.configurator import SystemConfig
    config = SystemConfig(
        enable_lvdt=enable_lvdt,
        enable_accel=enable_accel,
        sampling_rate_acceleration=ACCEL_SAMPLING_RATE,
        sampling_rate_lvdt=LVDT_SAMPLING_RATE,
        plot_refresh_rate=PLOT_REFRESH_RATE,
        gpio_pins=gpio_pins_list,
        output_dir=None,
        num_lvdts=NUM_LVDTS,
        num_accelerometers=NUM_ACCELS,
        lvdt_slopes=LVDT_SLOPES,
        trigger_acceleration_threshold=ACCEL_TRIGGER_THRESHOLD,
        detrigger_acceleration_threshold=ACCEL_DETRIGGER_THRESHOLD,
        trigger_displacement_threshold=DISPLACEMENT_TRIGGER_THRESHOLD,
        detrigger_displacement_threshold=DISPLACEMENT_DETRIGGER_THRESHOLD,
        pre_event_time=PRE_EVENT_TIME,
        post_event_time=POST_EVENT_TIME,
        min_event_duration=MIN_EVENT_DURATION,
        )
    
    # Configure LVDT pins explicitly
    try:
        import adafruit_ads1x15.ads1115 as ADS

        config.lvdt_pin_config = [ADS.P0, ADS.P1]
        print(f"LVDT pins configured: {[0, 1]}")
    except ImportError:
        print("Warning: Could not import ADS1115 for pin configuration - using defaults")
    
    return config

def main():
    """Main function to initialize and run the monitoring system."""
    print_banner()

    args = parse_arguments()
    apply_cli_args(args)

    if not enable_lvdt and not enable_accel:
        print("At least one sensor type (LVDT or accelerometer) must be enabled.")
        sys.exit(1)

    # Auto-detect simulation mode if not on Raspberry Pi
    simulation_mode = args.simulation or not IS_RASPBERRY_PI
    if not IS_RASPBERRY_PI and not args.simulation:
        print("Non-Raspberry Pi platform detected. Automatically enabling simulation mode.")
    
    # Dynamically load the appropriate configuration module
    config_module_name = "identitwin.simulator" if simulation_mode else "identitwin.configurator"
    config_module = importlib.import_module(config_module_name)
    SystemConfig = config_module.SimulatorConfig if simulation_mode else config_module.SystemConfig

    print("\n======================== Identitwin Monitoring System =========================\n")
    print(f"Operation Mode: {'Simulation' if simulation_mode else 'Hardware'}")

    config = SystemConfig(
        enable_lvdt=enable_lvdt,
        enable_accel=enable_accel,
        sampling_rate_acceleration=ACCEL_SAMPLING_RATE,
        sampling_rate_lvdt=LVDT_SAMPLING_RATE,
        plot_refresh_rate=PLOT_REFRESH_RATE,
        output_dir=args.output_dir,
        num_lvdts=NUM_LVDTS,
        num_accelerometers=NUM_ACCELS,
        gpio_pins=None,
        trigger_acceleration_threshold=ACCEL_TRIGGER_THRESHOLD,
        detrigger_acceleration_threshold=ACCEL_DETRIGGER_THRESHOLD,
        trigger_displacement_threshold=DISPLACEMENT_TRIGGER_THRESHOLD,
        detrigger_displacement_threshold=DISPLACEMENT_DETRIGGER_THRESHOLD,
        pre_event_time=PRE_EVENT_TIME,
        post_event_time=POST_EVENT_TIME,
        min_event_duration=MIN_EVENT_DURATION,
        lvdt_slopes=LVDT_SLOPES,
        enable_plots=enable_plots,
        enable_plot_displacement=enable_plot_displacement,
        enable_accel_plots=enable_accel_plots,
        enable_fft_plots=enable_fft_plots
    )
    
    # Assign LVDT slopes as an attribute after creating the config object
    config.lvdt_slopes = LVDT_SLOPES
    print(f"LVDT slopes configured: {LVDT_SLOPES}")
    
    # keep originals for printouts
    config.expected_sampling_rate_acceleration = config.sampling_rate_acceleration
    config.expected_sampling_rate_lvdt        = config.sampling_rate_lvdt

    print(f"Operation: {get_operation_mode_name()}")
    print("\nSensor Configuration:")
    print(f"  - LVDT Enabled: {enable_lvdt}")
    print(f"  - Accelerometer Enabled: {enable_accel}")
    print("\nVisualization Configuration:")
    print(f"  - LVDT Displacement Plots: {enable_plot_displacement}")
    print(f"  - Acceleration Plots: {enable_accel_plots}")
    print(f"  - FFT Plots: {enable_fft_plots}")
    print("\nSampling Rates:")
    print(f"  - Accelerometer Rate: {ACCEL_SAMPLING_RATE} Hz")
    print(f"  - LVDT Rate: {LVDT_SAMPLING_RATE} Hz")
    print(f"  - Plot Refresh Rate: {PLOT_REFRESH_RATE} Hz, Plot Window: {WINDOW_DURATION} s")
    print("\nEvent Detection Parameters:")
    print(f"  - Acceleration Trigger Threshold: {ACCEL_TRIGGER_THRESHOLD} m/s2")
    print(f"  - Displacement Trigger Threshold: {DISPLACEMENT_TRIGGER_THRESHOLD} mm")
    print(f"  - Pre-Trigger Buffer: {PRE_EVENT_TIME} seconds")
    print(f"  - Post-Trigger Buffer: {POST_EVENT_TIME} seconds")
    print(f"  - Minimum Event Duration: {MIN_EVENT_DURATION} seconds")

    if args.output_dir:
        config.output_dir = args.output_dir
        config.events_dir = os.path.join(config.output_dir, "events")
        config.logs_dir = os.path.join(config.output_dir, "logs")
        config.reports_dir = os.path.join(config.output_dir, "reports")
        os.makedirs(config.events_dir, exist_ok=True)
        os.makedirs(config.logs_dir, exist_ok=True)
        os.makedirs(config.reports_dir, exist_ok=True)

    config.operational_mode = get_operation_mode_name()

    monitor_system = MonitoringSystem(config)
    monitor_system.plot_queue = None

    try:
        monitor_system.setup_sensors()

        # turn ON status LED continuously
        if monitor_system.status_led:
            monitor_system.status_led.on()

        # ensure activity LED is off initially
        if hasattr(monitor_system, "activity_led") and monitor_system.activity_led:
            monitor_system.activity_led.off()

        # Add visualization if enabled
        if config.enable_lvdt:
            from identitwin.visualization import run_dashboard
            dashboard_thread = run_dashboard(monitor_system)

        print("\n================== Init data processing =====================\n")
        config.window_duration = WINDOW_DURATION  # seconds of data visible
        monitor_system.initialize_processing()

        system_report_file = os.path.join(config.reports_dir, "system_report.txt")
        report_generator.generate_system_report(config, system_report_file)

        monitor_system.start_monitoring()

        # monitor loop: blink activity LED only during events
        last_event_state = False # Use a different variable name to avoid confusion
        while monitor_system.running:
            try:
                # --- CORRECTED STATE READING ---
                # Read the shared state variable updated by event_monitoring.py
                current_event_state = state.get_event_variable("is_event_recording", default=False)
                # -------------------------------

                # Check if the activity LED object exists and is usable
                activity_led_available = hasattr(monitor_system, "activity_led") and monitor_system.activity_led is not None

                # Start blinking activity LED when event begins
                if current_event_state and not last_event_state:
                    if activity_led_available:
                        print("DEBUG INIT: Event started, starting blink.") # Debug print
                        monitor_system.activity_led.blink(on_time=0.1, off_time=0.1, background=True)
                    else:
                        print("DEBUG INIT: Event started (LED missing/failed)") # Debug print

                # Stop blinking when event ends
                elif not current_event_state and last_event_state:
                    if activity_led_available:
                        print("DEBUG INIT: Event ended, stopping blink.") # Debug print
                        monitor_system.activity_led.off()
                    else:
                        print("DEBUG INIT: Event ended (LED missing/failed)") # Debug print

                last_event_state = current_event_state # Update state for next iteration

            except Exception as loop_err:
                print(f"Error in main monitoring loop: {loop_err}", file=sys.stderr)
                traceback.print_exc() # Print full traceback for loop errors
                # Optionally disable LED on repeated errors
                if 'monitor_system' in locals() and hasattr(monitor_system, "activity_led"):
                    monitor_system.activity_led = None


            # Check state more frequently to react faster to event end
            time.sleep(0.1) # Reduced sleep time

    except KeyboardInterrupt:
        print("\nProgram stopped by user")
        if 'monitor_system' in locals() and monitor_system.running:
            monitor_system.stop_monitoring()
    except Exception as e:
        print(f"\nError in monitoring system: {e}")
        traceback.print_exc()
    finally:
        print("\nCleaning up...")
        if 'monitor_system' in locals():
            monitor_system.cleanup()
        print("Done!")


if __name__ == "__main__":
    main()
