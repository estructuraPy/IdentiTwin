"""
Configuration management module for the  monitoring system.

This module handles all system-wide configuration including:
- Hardware setup and initialization
- Sampling rates and timing parameters
- Event detection thresholds
- Data storage paths and organization
- Sensor calibration parameters
- System operational modes

Key Features:
- Dynamic configuration based on available hardware
- Platform-specific adaptations (Raspberry Pi vs simulation)
- Automatic directory structure creation
- LED indicator management
- ADC (ADS1115) configuration for LVDT sensors
- MPU6050 accelerometer setup
- Comprehensive parameter validation

Classes:
    SystemConfig: Main configuration class with all system parameters
"""
import os
import platform
from datetime import datetime
import time
import numpy as np
import sys # Import sys for stderr
import traceback # Import traceback for detailed errors

# Check if we're running on a Raspberry Pi or similar platform
try:
    # Only import hardware-specific modules if we're on a compatible platform
    from gpiozero import LED
    import adafruit_ads1x15.ads1115 as ADS
    import board
    import busio
    from adafruit_ads1x15.analog_in import AnalogIn
    # Import the specific mpu6050 library used in the working example
    from mpu6050 import mpu6050
    I2C_AVAILABLE = True
except (ImportError, NotImplementedError) as e:
    # For simulation mode or if hardware libs fail
    print(f"Warning: Hardware libraries not found or failed to import ({e}). Hardware functions disabled.")
    LED = None
    ADS = None
    board = None
    busio = None
    AnalogIn = None
    mpu6050 = None
    I2C_AVAILABLE = False

# Print platform information
print(f"Platform: {platform.system()} {platform.release()}")
print("Hardware detection: Raspberry Pi/Hardware Mode")


class SystemConfig:
    """Configuration class for the monitoring system."""

    def __init__(
        self,
        enable_lvdt=True,
        enable_accel=True,
        output_dir=None,
        num_lvdts=2,
        num_accelerometers=2,
        sampling_rate_acceleration=200.0,  # Accept any provided value
        sampling_rate_lvdt=5.0,           # Accept any provided value
        plot_refresh_rate=10.0,           # Accept any provided value
        gpio_pins=None,
        trigger_acceleration_threshold=None,
        detrigger_acceleration_threshold=None,
        trigger_displacement_threshold=None,
        detrigger_displacement_threshold=None,
        pre_event_time=5.0,   # Renamed from pre_trigger_time
        post_event_time=15.0, # Renamed from post_trigger_time
        min_event_duration=2.0,
    ):
        """Initialize system configuration."""
        # Set output directory first to avoid the AttributeError
        self.output_dir = output_dir
        if self.output_dir is None:
            today = datetime.now().strftime("%Y%m%d")
            self.output_dir = os.path.join("repository", today)

        # Create all required subdirectories
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Create standard subdirectories
        self.events_dir = os.path.join(self.output_dir, "events")
        self.logs_dir = os.path.join(self.output_dir, "logs")
        self.reports_dir = os.path.join(self.output_dir, "reports")
        
        # Create all subdirectories
        for directory in [self.events_dir, self.logs_dir, self.reports_dir]:
            os.makedirs(directory, exist_ok=True)
            
        # Set default file paths
        self.acceleration_file = os.path.join(self.output_dir, "acceleration.csv")
        self.displacement_file = os.path.join(self.output_dir, "displacement.csv")
        self.general_file = os.path.join(self.output_dir, "general_measurements.csv")
        
        # Performance monitoring settings
        self.enable_performance_monitoring = True
        self.performance_log_file = os.path.join(self.logs_dir, "performance_log.csv")

        # Sensor configuration
        self.enable_lvdt = enable_lvdt
        self.enable_accel = enable_accel
        self.num_lvdts = num_lvdts
        self.num_accelerometers = num_accelerometers

        # Sampling rates - use provided values directly
        self.sampling_rate_acceleration = sampling_rate_acceleration
        self.sampling_rate_lvdt = sampling_rate_lvdt
        self.plot_refresh_rate = plot_refresh_rate

        # Calculate derived time values
        self.time_step_acceleration = 1.0 / self.sampling_rate_acceleration
        self.time_step_lvdt = 1.0 / self.sampling_rate_lvdt
        self.time_step_plot_refresh = 1.0 / self.plot_refresh_rate

        self.window_duration = 5  # seconds
        self.gravity = 9.81  # m/s^2

        # Maximum allowable jitter (ms) - more realistic values
        self.max_accel_jitter = 1.5  # 1.5ms maximum jitter for accelerometers (1.5% at 100Hz)
        self.max_lvdt_jitter = 5.0  # 5ms maximum jitter for LVDT (2.5% at 5Hz)

        # Set thresholds - use more reasonable values to prevent too many events
        self.trigger_acceleration_threshold = (
            trigger_acceleration_threshold if trigger_acceleration_threshold is not None
            else 0.3 * self.gravity
        )
        self.trigger_displacement_threshold = (
            trigger_displacement_threshold if trigger_displacement_threshold is not None
            else 1.0
        )
        # New: assign detrigger thresholds
        self.detrigger_acceleration_threshold = (
            detrigger_acceleration_threshold if detrigger_acceleration_threshold is not None
            else self.trigger_acceleration_threshold * 0.5
        )
        self.detrigger_displacement_threshold = (
            detrigger_displacement_threshold if detrigger_displacement_threshold is not None
            else self.trigger_displacement_threshold * 0.5
        )

        # Event detection parameters - renamed for consistency
        self.pre_event_time = pre_event_time    # Renamed
        self.post_event_time = post_event_time  # Renamed
        self.min_event_duration = min_event_duration

        # LVDT configuration - these default values can be overridden locally
        self.lvdt_gain = 2.0 / 3.0  # ADC gain (+-6.144V)
        self.lvdt_scale_factor = 0.1875  # Constant for voltage conversion (mV)
        self.lvdt_slope = 19.86  # Default slope in mm/V
        self.lvdt_intercept = 0.0  # Default intercept
        self.lvdt_calibration = []  # Lista para calibraciones individuales
        self.lvdt_pin_config = []   # Lista para configuración de pines

        # Accelerometer configuration (from initialization.py)
        self.accel_offsets = [
            {"x": 0.0, "y": 0.0, "z": 0.0},  # Offsets for accelerometer 1
            {"x": 0.0, "y": 0.0, "z": 0.0},  # Offsets for accelerometer 2
        ]

        # LED configuration - default GPIO pins; can be modified from initialization or simulation
        self.gpio_pins = gpio_pins if gpio_pins is not None else [18, 17]

        # Validate rates and print warnings if needed
        if self.sampling_rate_acceleration != sampling_rate_acceleration:
            print(
                f"Warning: Accelerometer rate limited to {self.sampling_rate_acceleration} Hz (requested: {sampling_rate_acceleration} Hz)"
            )
        if self.sampling_rate_lvdt != sampling_rate_lvdt:
            print(f"Warning: LVDT rate limited to {self.sampling_rate_lvdt} Hz (requested: {sampling_rate_lvdt} Hz)")
        if self.plot_refresh_rate != 10.0:
            print(
                f"Warning: Plot refresh rate limited to {self.plot_refresh_rate} Hz (requested: {plot_refresh_rate} Hz)"
            )

    def _initialize_output_directory(self, custom_dir=None):
        """Initialize the output directory for saving data."""
        if custom_dir:
            base_folder = custom_dir
        else:
            base_folder = "repository"

        if not os.path.exists(base_folder):
            os.makedirs(base_folder)

        # Create a subfolder for this monitoring session with date only
        today = datetime.now().strftime("%Y-%m-%d")
        session_path = os.path.join(base_folder, today)

        # Create the session directory if it doesn't exist
        if not os.path.exists(session_path):
            os.makedirs(session_path)

        return session_path

    def initialize_thresholds(self):
        """Initialize the thresholds for event detection."""
        thresholds = {
            "acceleration": self.trigger_acceleration_threshold if self.enable_accel else None,
            "displacement": self.trigger_displacement_threshold if self.enable_lvdt else None,
            "detrigger_acceleration": self.detrigger_acceleration_threshold, # Added
            "detrigger_displacement": self.detrigger_displacement_threshold, # Added
            "pre_event_time": self.pre_event_time,      # Renamed
            "post_event_time": self.post_event_time,    # Renamed
            "min_event_duration": self.min_event_duration,
        }
        return thresholds

    def initialize_leds(self):
        """Initialize LED indicators for Raspberry Pi hardware."""
        # Check specifically if the LED class from gpiozero was imported successfully
        if LED is None:
            print("Warning: Cannot initialize LEDs, 'gpiozero' library not available or failed to import.")
            return None, None
        # Check if GPIO pins are configured
        if not self.gpio_pins or len(self.gpio_pins) < 2:
             print("Warning: Cannot initialize LEDs, GPIO pins not configured correctly.")
             return None, None

        try:
            # Initialize real LEDs using gpiozero
            print(f"Attempting to initialize LEDs on GPIO pins: {self.gpio_pins[0]}, {self.gpio_pins[1]}")
            status_led = LED(self.gpio_pins[0])
            activity_led = LED(self.gpio_pins[1])
            status_led.off()
            activity_led.off()
            print("LEDs initialized successfully.")
            return status_led, activity_led
        except Exception as e:
            # Catch potential errors during LED object creation (e.g., invalid pin)
            print(f"Warning: Could not initialize LEDs on specified pins: {e}", file=sys.stderr)
            # Return None if LED initialization fails
            return None, None

    def create_ads1115(self):
        """Create and return an ADS1115 ADC object."""
        if not I2C_AVAILABLE or busio is None or board is None or ADS is None:
            print("Error: Cannot create ADS1115, required hardware libraries (busio, board, ADS) not available.", file=sys.stderr)
            return None
        try:
            # Initialize I2C bus directly here
            i2c = busio.I2C(board.SCL, board.SDA)
            print("I2C bus initialized successfully for ADS1115.")
            # Create ADS object using the initialized bus
            ads = ADS.ADS1115(i2c)
            ads.gain = self.lvdt_gain  # Set gain as configured
            print("ADS1115 object created successfully.")
            return ads
        except ValueError as e:
            # Specific error for I2C initialization failure (e.g., no device found)
            print(f"Error initializing I2C bus for ADS1115: {e}. Check connections/config.", file=sys.stderr)
            return None
        except RuntimeError as e:
            # Specific error often related to permissions or kernel modules
            print(f"Error initializing I2C bus for ADS1115: {e}. Ensure I2C is enabled and permissions are correct.", file=sys.stderr)
            return None
        except NameError as e:
             # Error if libraries weren't imported correctly
             print(f"Error: Missing hardware library component ({e}). Cannot create ADS1115.", file=sys.stderr)
             return None
        except Exception as e:
            # Catch other potential errors (like OSError if device address is wrong/busy)
            print(f"Unexpected error initializing ADS1115: {e}", file=sys.stderr)
            traceback.print_exc()
            return None

    def create_lvdt_channels(self, ads):
        """Create LVDT channels using the provided ADS1115 object."""
        if ads is None or not I2C_AVAILABLE or AnalogIn is None:
            print("Error: Cannot create LVDT channels, ADS1115 object is invalid or AnalogIn library not available.", file=sys.stderr)
            return None
        try:
            channels = []
            # Map ADS pins and use pin_config if available
            channel_map = [ADS.P0, ADS.P1, ADS.P2, ADS.P3]
            pin_config = self.lvdt_pin_config if self.lvdt_pin_config else channel_map[:2]
            
            print(f"Attempting to create {self.num_lvdts} LVDT channels...")
            for i in range(min(self.num_lvdts, len(pin_config))):
                ch_pin = pin_config[i]
                print(f"  Creating LVDT channel {i+1} on pin {ch_pin}")
                try:
                    channel = AnalogIn(ads, ch_pin)
                    test_voltage = channel.voltage
                    print(f"  LVDT {i+1} initial voltage reading: {test_voltage:.6f}V")
                    channels.append(channel)
                except Exception as e:
                    print(f"Error creating LVDT channel {i+1}: {e}", file=sys.stderr)
                    return None

            print(f"Successfully created {len(channels)} LVDT channels")
            return channels

        except Exception as e:
            print(f"Error creating LVDT channels: {e}", file=sys.stderr)
            traceback.print_exc()
            return None

    def create_accelerometers(self):
        """Create and return MPU6050 accelerometer objects."""
        if not I2C_AVAILABLE or mpu6050 is None or board is None or busio is None:
            print("Error: Cannot create accelerometers, required hardware libraries (mpu6050, busio, board) not available.", file=sys.stderr)
            return None

        mpu_list = []
        print(f"Attempting to initialize {self.num_accelerometers} accelerometers...")
        # Note: The mpu6050 library used in the example initializes I2C implicitly when
        # the object is created with just the address. We don't need to create busio.I2C here.
        for i in range(self.num_accelerometers):
            addr = 0x68 + i  # Assumes sensors on consecutive I2C addresses (0x68, 0x69, ...)
            try:
                # Instantiate mpu6050 directly with the address, like the example
                print(f"  Attempting to initialize MPU6050 at address {hex(addr)}...")
                mpu = mpu6050(addr)

                # Optional: Add a quick check to see if the sensor is responsive
                try:
                    temp = mpu.get_temp() # Try reading temperature
                    print(f"  MPU6050 at {hex(addr)} initialized successfully (Temp: {temp:.1f}C).")
                    mpu_list.append(mpu)
                except OSError as comm_err:
                    # This error often means the device is not present or responding at this address
                    print(f"  Warning: Could not communicate with MPU6050 at address {hex(addr)} after initialization: {comm_err}. Skipping this sensor.", file=sys.stderr)
                    continue # Skip this sensor

            except NameError as e:
                 # Error if mpu6050 wasn't imported correctly
                 print(f"Error: Missing mpu6050 library component ({e}). Cannot create accelerometer.", file=sys.stderr)
                 # Stop trying if the library itself is missing
                 return None
            except Exception as e:
                # Catch potential errors during initialization (e.g., OSError if device not found)
                print(f"  Error initializing MPU6050 at address {hex(addr)}: {e}. Skipping this sensor.", file=sys.stderr)
                # Continue trying other sensors even if one fails

        print(f"Successfully created {len(mpu_list)} MPU6050 objects.")
        return mpu_list if mpu_list else None # Return list or None if empty

# Utility functions
def leds(gpio_pins):
    """Initialize LEDs connected to the specified GPIO pins."""
    try:
        return LED(gpio_pins[0]), LED(gpio_pins[1])
    except Exception as e:
        print(f"Warning: Could not initialize LEDs: {e}")
        return None, None


def ads1115():
    """Initialize the ADS1115 ADC."""
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS.ADS1115(i2c)
        ads.gain = 2.0 / 3.0  # Gain can be adjusted as needed
        return ads
    except Exception as e:
        print(f"Error initializing ADS1115: {e}")
        return None


def thresholds(trigger_acceleration, trigger_displacement, pre_time, enable_accel, enable_lvdt):
    """Initialize thresholds for event detection."""
    return {
        "acceleration": trigger_acceleration if enable_accel else None,
        "displacement": trigger_displacement if enable_lvdt else None,
        "pre_event_time": pre_time,
        "post_event_time": pre_time,
    }
