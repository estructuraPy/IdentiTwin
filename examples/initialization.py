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
import numpy as np
from datetime import datetime
import matplotlib
# Keep pyplot import if plotting might be enabled via CLI
import matplotlib.pyplot as plt
import traceback # Import traceback
# queue is not directly used here, consider removing if not needed by future logic in this file
# import queue

# Set a suitable interactive backend BEFORE importing pyplot or other matplotlib modules
# Try TkAgg first, fall back if needed. Avoid 'agg' here for live plots.
try:
    matplotlib.use('TkAgg')
except ImportError:
    print("Warning: TkAgg backend not found, trying QtAgg...")
    try:
        matplotlib.use('QtAgg')
    except ImportError:
        print("Warning: QtAgg backend not found. Plotting might not work interactively.")
# os.environ["QT_LOGGING_RULES"] = "qt.qpa.*=false" # Keep if using QtAgg
# plt.switch_backend('agg') # Remove this - contradicts interactive plotting
warnings.filterwarnings("ignore", message="FigureCanvasAgg is non-interactive, and thus cannot be shown") # Keep warning suppression

# Import from the identitwin library
from identitwin import configurator
from identitwin.system_monitoring import MonitoringSystem
# from identitwin.event_monitoring import EventMonitor # Unused import
from identitwin import calibration
# state is used indirectly by other modules, keep import
from identitwin import state
from identitwin import report_generator

# Define default values using uppercase constants - these can be overridden by CLI arguments
ACCEL_SAMPLING_RATE = 200.0  # Hz - Default value
LVDT_SAMPLING_RATE = 5.0     # Hz - Default value  
PLOT_REFRESH_RATE = 10.0     # Hz - Default value

NUM_LVDTS = 2
NUM_ACCELS = 2
LVDT_SLOPES = [19.86, 19.85]  # Global definition of LVDT slopes

ACCEL_TRIGGER_THRESHOLD = 0.981  # m/s2 (0.1g)
ACCEL_DETRIGGER_THRESHOLD = 0.589  # m/s2 (60% of trigger threshold)

DISPLACEMENT_TRIGGER_THRESHOLD = 10.0 # mm
DISPLACEMENT_DETRIGGER_THRESHOLD = 5.0  # mm

PRE_TRIGGER_TIME = 5.0  # seconds
POST_TRIGGER_TIME = 15.0  # seconds
MIN_EVENT_DURATION = 2.0  # seconds

# Define which sensors and features are active (user configuration)
# These serve as defaults if not overridden by CLI args
enable_lvdt = True       # Enable LVDT measurements
enable_accel = True      # Enable accelerometer measurements

# Define which plots are active (user configuration)
# These serve as defaults if not overridden by CLI args
enable_plots = True         # Enable plotting (master switch)
enable_plot_displacement = True  # Enable LVDT displacement plots
enable_accel_plots = False       # Enable acceleration plots
enable_fft_plots = False         # Enable FFT plots

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
    time.sleep(2)  # Pause for 2 seconds

# ===== START: Simulated sensor functions =====
def simulated_create_ads1115(self):
    class SimulatedADS1115:
        def __init__(self):
            self.gain = 2.0 / 3.0
    return SimulatedADS1115()

def simulated_create_lvdt_channels(self, ads):
    class SimulatedAnalogIn:
        def __init__(self, ads, channel, slope=19.86):  # Use default slope if not provided
            self.ads = ads
            self.channel = channel
            self.last_voltage = 0.0
            self.cycle_start_time = time.time()
            # Simple sine wave simulation for displacement
            self.amplitude = 5.0 # mm
            self.frequency = 0.1 # Hz
            self.slope = slope

        @property
        def voltage(self):
            current_time = time.time()
            elapsed_time = current_time - self.cycle_start_time
            
            # Calculate displacement based on a sine wave
            # Add some phase shift based on channel index for variety
            phase_shift = self.channel * (np.pi / self.num_lvdts)
            displacement = self.amplitude * math.sin(2 * np.pi * self.frequency * elapsed_time + phase_shift)

            # Add small random noise
            noise = np.random.normal(0, 0.1) # Gaussian noise with std dev 0.1mm
            displacement += noise

            # Convert displacement to voltage using the slope
            # Avoid division by zero if slope is zero
            voltage = displacement / self.slope if self.slope != 0 else 0.0
            self.last_voltage = voltage
            return voltage

        @property
        def raw_value(self):
            # Simulate raw value based on voltage (assuming some ADC scaling)
            # This is just an approximation
            return int(self.voltage * (32767 / 6.144)) # Example scaling for ADS1115

    # Ensure num_lvdts is available in the class instance
    SimulatedAnalogIn.num_lvdts = self.num_lvdts
    return [SimulatedAnalogIn(ads, i, LVDT_SLOPES[i] if i < len(LVDT_SLOPES) else 19.86) for i in range(self.num_lvdts)]

def simulated_create_accelerometers(self):
    class SimulatedMPU6050:
        def __init__(self, address, offsets):
            self.address = address
            self.offsets = offsets
            self._last_data = None
        def get_accel_data(self):
            t = time.time()
            self._last_data = {
                'x': 0.1 * math.sin(t * 100) + 0.15 * math.sin(t * 50),
                'y': 0.5 * math.cos(t * 200) + 0.1 * math.cos(t * 90),
                'z': 9.81 + 0.25 * math.sin(5 * t) + 0.5 * math.sin(t * 350)
            }
            return self._last_data
        @property
        def accel_data(self):
            return self.get_accel_data()
    return [
        SimulatedMPU6050(0x68 + i,
            self.accel_offsets[i] if i < len(self.accel_offsets)
            else {'x': 0.0, 'y': 0.0, 'z': 0.0})
        for i in range(self.num_accelerometers)
    ]
# ===== END: Simulated sensor functions =====

def parse_arguments():
    """Parse command-line arguments to configure the monitoring system."""
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
    """Apply command-line arguments to override the default configuration."""
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
    """Return a descriptive name for the current operation mode."""
    if enable_lvdt and enable_accel:
        return "Combined Mode (LVDT + Accelerometers)"
    elif enable_lvdt:
        return "LVDT-Only Mode"
    elif enable_accel:
        return "Accelerometer-Only Mode"
    else:
        return "No Sensors Mode (Invalid)"

def create_system_config():
    from identitwin.configurator import SystemConfig
    config = SystemConfig(
        enable_lvdt=enable_lvdt,
        enable_accel=enable_accel,
        sampling_rate_acceleration=ACCEL_SAMPLING_RATE,  # Pass custom value
        sampling_rate_lvdt=LVDT_SAMPLING_RATE,    # Pass custom value
        plot_refresh_rate=PLOT_REFRESH_RATE,     # Pass custom value
        output_dir=None,
        num_lvdts=NUM_LVDTS,
        num_accelerometers=NUM_ACCELS,
        gpio_pins=None,
        trigger_acceleration_threshold=ACCEL_TRIGGER_THRESHOLD,
        detrigger_acceleration_threshold=ACCEL_DETRIGGER_THRESHOLD,
        trigger_displacement_threshold=DISPLACEMENT_TRIGGER_THRESHOLD,
        detrigger_displacement_threshold=DISPLACEMENT_DETRIGGER_THRESHOLD,
        pre_trigger_time = PRE_TRIGGER_TIME,
        post_trigger_time = POST_TRIGGER_TIME,
        min_event_duration = MIN_EVENT_DURATION
    )
    return config

def main():
    """Main function to initialize and run the monitoring system."""
    # First, make sure we clean up any lingering GPIO resources from previous runs
    try:
        from gpiozero import Device
        print("Performing GPIO cleanup from possible previous runs...")
        Device.close_all()
        print("GPIO resources released.")
    except ImportError:
        pass  # gpiozero not available, likely running in simulation mode
    except Exception as e:
        print(f"Warning: Could not clean up GPIO resources: {e}")
    
    # Correct indentation for the start of the function
    print_banner()
    args = parse_arguments()
    apply_cli_args(args) # Apply CLI args to override defaults

    # Validate configuration after applying CLI args
    if not enable_lvdt and not enable_accel:
        print("Error: At least one sensor type (LVDT or accelerometer) must be enabled.")
        sys.exit(1)

    # Plotting is now controlled by apply_cli_args based on defaults and CLI flags.
    # Remove the forced disabling:
    # global enable_plots, enable_plot_displacement, enable_accel_plots, enable_fft_plots
    # enable_plots = False
    # enable_plot_displacement = False
    # enable_accel_plots = False
    # enable_fft_plots = False

    print("\n======================== Identitwin Monitoring System =========================\n")

    # Apply simulation mode overrides if specified
    if args.simulation:
        print("Simulation mode enabled: Overriding hardware creation methods...")
        # Store original methods before patching
        original_create_ads1115 = configurator.SystemConfig.create_ads1115
        original_create_lvdt_channels = configurator.SystemConfig.create_lvdt_channels
        original_create_accelerometers = configurator.SystemConfig.create_accelerometers

        # Patch methods with simulated versions
        configurator.SystemConfig.create_ads1115 = simulated_create_ads1115
        configurator.SystemConfig.create_lvdt_channels = simulated_create_lvdt_channels
        configurator.SystemConfig.create_accelerometers = simulated_create_accelerometers
        print("Using simulated sensors.")
    else:
        print("Real hardware mode enabled.")
        # Add early I2C check for hardware mode
        print("\nPerforming initial hardware checks...")
        try:
            # FIRST: Check if hardware modules were loaded successfully in configurator.py
            if not configurator._HARDWARE_AVAILABLE:
                 # Display the specific error message from configurator
                 error_details = configurator._HARDWARE_ERROR_MESSAGE or "Unknown hardware import error"
                 print(f"  ERROR: Hardware interface modules failed to load.")
                 print(f"  Details: {error_details}") # Show the specific error
                 print("  Cannot proceed in hardware mode. Check installations and system compatibility.")
                 print("  Common issues:")
                 print("    - Missing libraries (run pip install -r requirements.txt or install manually)")
                 print("    - Running on an incompatible OS (e.g., Windows without Blinka)")
                 print("    - Incorrect Python environment")
                 print("  Consider running in --simulation mode if hardware is unavailable.")
                 sys.exit(1) # Exit if essential hardware modules are missing

            # If modules loaded, proceed with I2C check
            import board # Already imported in configurator, but good practice here too
            import busio
            print("  Attempting to initialize I2C bus...")
            # ... (rest of the I2C check logic remains the same) ...
            i2c = busio.I2C(board.SCL, board.SDA)
            print("  I2C bus initialized successfully.")
            while not i2c.try_lock():
                pass # Wait for lock
            try:
                print("  Scanning I2C devices...")
                addresses = i2c.scan()
                if addresses:
                    print(f"  Found I2C devices at: {[hex(addr) for addr in addresses]}")
                else:
                    print("  WARNING: No I2C devices found. Check wiring and power.")
            finally:
                i2c.unlock()
        except Exception as i2c_err:
            # This block now only catches errors during the I2C check itself
            print(f"  ERROR during I2C check: {i2c_err}")
            print("  Please ensure I2C is enabled (raspi-config) and hardware is connected correctly.")
            # Exit if initial I2C check fails critically in hardware mode
            # Consider making this conditional or adding a '--force' flag if needed
            print("Exiting due to I2C initialization failure.")
            sys.exit(1)

    # Print configuration summary
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
    print(f"  - Plot Refresh Rate: {PLOT_REFRESH_RATE} Hz")
    print("\nEvent Detection Parameters:")
    print(f"  - Acceleration Trigger Threshold: {ACCEL_TRIGGER_THRESHOLD} m/s2")
    print(f"  - Displacement Trigger Threshold: {DISPLACEMENT_TRIGGER_THRESHOLD} mm")
    print(f"  - Pre-Trigger Buffer: {PRE_TRIGGER_TIME} seconds")
    print(f"  - Post-Trigger Buffer: {POST_TRIGGER_TIME} seconds")
    print(f"  - Minimum Event Duration: {MIN_EVENT_DURATION} seconds")

    # Create the system configuration
    config = create_system_config()
    # Apply custom output directory from CLI args if provided
    if args.output_dir:
        config.output_dir = args.output_dir
        # Recreate subdirectories based on the new output_dir
        config.events_dir = os.path.join(config.output_dir, "events")
        config.logs_dir = os.path.join(config.output_dir, "logs")
        config.reports_dir = os.path.join(config.output_dir, "reports")
        os.makedirs(config.events_dir, exist_ok=True)
        os.makedirs(config.logs_dir, exist_ok=True)
        os.makedirs(config.reports_dir, exist_ok=True)

    # Add operational mode and final plot status to config
    config.operational_mode = get_operation_mode_name()
    # Ensure config reflects the actual plot status after CLI args
    config.enable_plots = enable_plots
    config.enable_plot_displacement = enable_plot_displacement
    config.enable_accel_plots = enable_accel_plots
    config.enable_fft_plots = enable_fft_plots

    # Initialize the monitoring system
    print("\nInitializing Monitoring System...")
    monitor_system = MonitoringSystem(config)

    # Initialize plot queue only if plots are enabled
    if config.enable_plots:
         # Assuming plot queue might be needed by visualization module (if reintroduced)
         # For now, keep it None as visualization is not fully integrated/used
         monitor_system.plot_queue = None # Placeholder
         print("Plotting enabled (Note: Visualization module integration may be needed).")
    else:
         monitor_system.plot_queue = None
         print("Plotting disabled.")

    # Initialize LEDs safely
    print("Initializing LEDs...")
    try:
        monitor_system.status_led, monitor_system.activity_led = config.initialize_leds()
    except Exception as e:
        print(f"Could not initialize LEDs: {e}")
        monitor_system.status_led = None
        monitor_system.activity_led = None

    print(f"\n=========================== Sensor Setup & Calibration ===========================\n")

    try:
        # Setup sensors (this calls the create_* methods in config)
        print("Setting up sensors...")
        monitor_system.setup_sensors() # This now calls the potentially overridden create_* methods
        print("Sensor setup process completed.")

        # Check if sensors were actually created before attempting calibration
        # Use hasattr for safer checks
        sensors_ok = True
        if config.enable_lvdt and (not hasattr(monitor_system, 'lvdt_channels') or not monitor_system.lvdt_channels):
            print("Error: LVDT enabled but channels failed to initialize.")
            sensors_ok = False
        if config.enable_accel and (not hasattr(monitor_system, 'accelerometers') or not monitor_system.accelerometers):
            print("Error: Accelerometers enabled but failed to initialize.")
            sensors_ok = False

        if not sensors_ok:
             print("\nSkipping calibration due to sensor initialization errors.")
             # Ensure calibration params are None if sensors failed
             config.lvdt_calibration_params = None
             # Keep existing accel_offsets or defaults if accel failed
        else:
            print("\nKeep the devices completely still during calibration...")
            time.sleep(1) # Short pause before calibration

            # Calibrate LVDTs if enabled and initialized
            if config.enable_lvdt and monitor_system.lvdt_channels:
                print("\nCalibrating LVDTs...")
                try:
                    lvdt_cal_params = calibration.initialize_lvdt(
                        channels=monitor_system.lvdt_channels,
                        slopes=LVDT_SLOPES, # Pass the globally defined slopes
                        config=config # Pass config to save calibration data
                    )
                    # Store calibration results in config for use during acquisition
                    if lvdt_cal_params and len(lvdt_cal_params) == len(monitor_system.lvdt_channels):
                        config.lvdt_calibration_params = lvdt_cal_params # Store the list
                        print("LVDT calibration successful.")
                        # Optional: Print the calibration results for verification
                        for i, params in enumerate(lvdt_cal_params):
                            print(f"  LVDT {i+1} Calibrated: Slope={params['lvdt_slope']:.4f}, Intercept={params['lvdt_intercept']:.4f}")
                    else:
                         print("Warning: LVDT calibration did not return expected parameters.")
                         config.lvdt_calibration_params = None # Ensure it's None if calibration failed
                except Exception as cal_e:
                    print(f"Error during LVDT calibration: {cal_e}")
                    traceback.print_exc()
                    config.lvdt_calibration_params = None # Ensure it's None on error
            else:
                print("\nLVDT calibration skipped (disabled or channels not available).")
                config.lvdt_calibration_params = None # Ensure it's None if skipped

            # Calibrate accelerometers if enabled and initialized
            if config.enable_accel and monitor_system.accelerometers:
                print("\nCalibrating accelerometers...")
                try:
                    accel_offsets = calibration.multiple_accelerometers(
                        mpu_list=monitor_system.accelerometers,
                        calibration_time=2.0, # Duration for calibration
                        config=config # Pass config to save calibration data
                    )
                    if accel_offsets:
                        config.accel_offsets = accel_offsets # Overwrite default/previous offsets
                        print("Accelerometer calibration complete.")
                    else:
                        print("Warning: Accelerometer calibration failed or returned no offsets.")
                        # Keep existing/default offsets if calibration fails
                except Exception as cal_e:
                    print(f"Error during accelerometer calibration: {cal_e}")
                    traceback.print_exc()
                    # Keep existing/default offsets on error
            else:
                 print("\nAccelerometer calibration skipped (disabled or sensors not available).")

        # Initialize data processing (CSV files)
        print("\n================== Initializing Data Processing =====================\n")
        # Set window duration before initializing processing (if used by processing)
        # config.window_duration = 10.0 # Example if needed
        monitor_system.initialize_processing()

        # Generate system report (after potential calibration updates)
        print("Generating system report...")
        system_report_file = os.path.join(config.reports_dir, "system_report.txt")
        report_generator.generate_system_report(config, system_report_file)

        # Start monitoring threads only if sensors initialized correctly OR in simulation mode
        if sensors_ok or args.simulation:
            print("\nStarting monitoring threads...")
            monitor_system.start_monitoring()

            # Main loop
            print("\nMonitoring active. Press Ctrl+C to exit.")
            while monitor_system.running:
                # Status LED blink
                if monitor_system.status_led:
                    try:
                        # Blink briefly without blocking background tasks
                        monitor_system.status_led.blink(on_time=0.05, off_time=0.95, n=1, background=True)
                    except Exception as led_err:
                        # Avoid crashing the main loop if LED fails
                        print(f"Warning: Status LED blink failed: {led_err}", file=sys.stderr)
                        monitor_system.status_led = None # Prevent further attempts
                time.sleep(1.0) # Main loop sleep, status prints handled by monitor thread

            # Wait for threads to finish after loop exits
            print("\nWaiting for threads to complete...")
            if hasattr(monitor_system, "acquisition_thread") and monitor_system.acquisition_thread.is_alive():
                monitor_system.acquisition_thread.join(timeout=2.0)
            if hasattr(monitor_system, "event_thread") and monitor_system.event_thread.is_alive():
                monitor_system.event_thread.join(timeout=2.0)

            # Generate final summary report
            print("Generating summary report...")
            summary_report_file = os.path.join(config.reports_dir, "summary_report.txt")
            report_generator.generate_summary_report(monitor_system, summary_report_file)
        else:
            print("\nMonitoring cannot start due to sensor initialization errors.")

    except KeyboardInterrupt:
        print("\nProgram stopped by user")
        if 'monitor_system' in locals() and monitor_system.running:
            monitor_system.stop_monitoring()
    except RuntimeError as e: # Catch runtime errors from sensor init
         print(f"\nFATAL RUNTIME ERROR during initialization: {e}")
         traceback.print_exc()
         print("System cannot start.")
    except Exception as e:
        print(f"\nUNEXPECTED ERROR in main execution: {e}")
        traceback.print_exc()
    finally:
        # Clean up
        print("\nCleaning up resources...")
        if 'monitor_system' in locals():
            monitor_system.cleanup() # cleanup calls stop_monitoring internally

        # Restore original hardware methods if they were patched for simulation
        if args.simulation:
             print("Restoring original hardware methods...")
             configurator.SystemConfig.create_ads1115 = original_create_ads1115
             configurator.SystemConfig.create_lvdt_channels = original_create_lvdt_channels
             configurator.SystemConfig.create_accelerometers = original_create_accelerometers

        print("Done!")

if __name__ == "__main__":
    main()
