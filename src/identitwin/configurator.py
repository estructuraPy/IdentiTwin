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
import warnings # Import warnings to suppress hardware-related warnings

# Suppress warnings related to hardware detection
warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", message=".*chip_id.*")
warnings.filterwarnings("ignore", message=".*Adafruit-PlatformDetect.*")

# Check if we're running on Linux (likely Raspberry Pi)
IS_RASPBERRY_PI = platform.system() == "Linux"
I2C_AVAILABLE = False  # Default to False until proven otherwise

# Only attempt to import hardware libraries if on Linux
if IS_RASPBERRY_PI:
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
        print("Hardware libraries successfully imported.")
    except (ImportError, NotImplementedError) as e:
        print(f"Note: Hardware libraries not available. Using software simulation mode.")
        LED = None
        ADS = None
        board = None
        busio = None
        AnalogIn = None
        mpu6050 = None
        I2C_AVAILABLE = False
else:
    # On non-Linux systems, don't even try to import hardware libraries
    print("Non-Linux platform detected. Using software simulation mode.")
    LED = None
    ADS = None
    board = None
    busio = None
    AnalogIn = None
    mpu6050 = None
    I2C_AVAILABLE = False

# Print platform information
print(f"Platform: {platform.system()} {platform.release()}")
print(f"Hardware mode: {'Raspberry Pi/Hardware' if I2C_AVAILABLE else 'Software Simulation'}")


class SystemConfig:
    """Configuration class for the monitoring system."""

    def __init__(
        self,
        enable_lvdt=True,
        enable_accel=True,
        output_dir=None,
        num_lvdts=2,
        num_accelerometers=2,
        sampling_rate_acceleration=100.0,
        sampling_rate_lvdt=5.0,         
        plot_refresh_rate=10.0,         
        gpio_pins=None,
        trigger_acceleration_threshold=None,
        detrigger_acceleration_threshold=None,
        trigger_displacement_threshold=None,
        detrigger_displacement_threshold=None,
        pre_event_time=5.0, 
        post_event_time=15.0,
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

        # LVDT configuration - ADC settings only, individual calibration handled separately
        self.lvdt_gain = 2.0 / 3.0  # ADC gain (+-6.144V)
        self.lvdt_scale_factor = 0.1875  # Constant for voltage conversion (mV)

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
            print("Error: Cannot create ADS1115, required hardware libraries not available.", file=sys.stderr)
            return None
        try:
            # Initialize I2C bus with higher clock speed
            i2c = busio.I2C(board.SCL, board.SDA, frequency=400000)  # 400 kHz
            print("I2C bus initialized successfully for ADS1115.")
            
            ads = ADS.ADS1115(i2c)
            ads.mode = 0 # Continuous conversion mode
            ads.data_rate = 860 # Highest data rate
            ads.gain = self.lvdt_gain
            print("ADS1115 object created and configured successfully.")
            return ads
        except Exception as e:
            print(f"Error initializing ADS1115: {e}", file=sys.stderr)
            traceback.print_exc()
            return None

    def create_lvdt_channels(self, ads):
        """Create LVDT channels using the provided ADS1115 object."""
        if ads is None or not I2C_AVAILABLE or AnalogIn is None:
            print("Error: Cannot create LVDT channels.", file=sys.stderr)
            return None
        try:
            channels = []
            # Use custom pin config if provided, otherwise use defaults
            if hasattr(self, 'lvdt_pin_config') and len(self.lvdt_pin_config) >= self.num_lvdts:
                pins = self.lvdt_pin_config
                print(f"Using custom LVDT pin configuration")
            else:
                pins = [ADS.P0, ADS.P1, ADS.P2, ADS.P3][:self.num_lvdts]
                print(f"Using default LVDT pin configuration: A0, A1")
            
            # Try to configure ADS1115 for higher reliability
            try:
                # Set higher data rate for better readings
                ads.data_rate = 860  # Maximum data rate in SPS
                # Set continuous conversion mode
                ads.mode = 0  # 0 = Continuous conversion mode
                print(f"Configured ADS1115: data_rate={ads.data_rate}, mode={ads.mode}, gain={ads.gain}")
            except Exception as config_err:
                print(f"Warning: Could not configure ADS1115 settings: {config_err}")
            
            for i in range(self.num_lvdts):
                try:
                    print(f"Initializing LVDT {i+1} on pin {i}")
                    channel = AnalogIn(ads, pins[i])
                    # Test reading
                    voltage = channel.voltage
                    print(f"  - LVDT {i+1} initial voltage reading: {voltage:.4f}V")
                    channels.append(channel)
                except Exception as ch_err:
                    print(f"Error initializing LVDT {i+1}: {ch_err}")
                    continue
                    
            if not channels:
                print("No LVDT channels could be initialized")
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
