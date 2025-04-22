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
# Check if we're running on a Raspberry Pi or similar platform
try:
    # Only import hardware-specific modules if we're on a compatible platform
    from gpiozero import LED
    import adafruit_ads1x15.ads1115 as ADS
    import board
    import busio
    from adafruit_ads1x15.analog_in import AnalogIn
    from mpu6050 import mpu6050
except (ImportError, NotImplementedError):
    # For simulation mode, just define variables to avoid errors
    LED = None
    ADS = None
    board = None
    busio = None
    AnalogIn = None
    mpu6050 = None

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
        pre_trigger_time=2.0,
        post_trigger_time=5.0,
        min_event_duration=1.0,
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
        self.pre_trigger_time = pre_trigger_time  # Changed
        self.post_trigger_time = post_trigger_time # Changed
        self.min_event_duration = min_event_duration

        # LVDT configuration - these default values can be overridden locally
        self.lvdt_gain = 2.0 / 3.0  # ADC gain (+-6.144V)
        self.lvdt_scale_factor = 0.1875  # Constant for voltage conversion (mV)
        self.lvdt_slope = 19.86  # Default slope in mm/V
        self.lvdt_intercept = 0.0  # Default intercept

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
            "pre_event_time": self.pre_trigger_time,
            "post_event_time": self.post_trigger_time,
            "min_event_duration": self.min_event_duration,
        }
        return thresholds

    def initialize_leds(self):
        """Initialize LED indicators for Raspberry Pi hardware."""
        if LED is None:
            return None, None
        try:
            # Initialize real LEDs using gpiozero
            status_led = LED(self.gpio_pins[0])
            activity_led = LED(self.gpio_pins[1])
            status_led.off()
            activity_led.off()
            return status_led, activity_led
        except Exception as e:
            print(f"Warning: Could not initialize LEDs: {e}")
            # Return None if LED initialization fails
            return None, None

    def create_ads1115(self):
        """Create and return an ADS1115 ADC object."""
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            ads = ADS.ADS1115(i2c)
            ads.gain = self.lvdt_gain  # Set gain as configured
            return ads
        except Exception as e:
            print(f"Error initializing ADS1115: {e}")
            return None

    def create_lvdt_channels(self, ads):
        """Create LVDT channels using the provided ADS1115 object."""
        try:
            channels = []
            # Ciclar entre los canales disponibles para soportar cualquier número de LVDTs
            channel_map = [ADS.P0, ADS.P1, ADS.P2, ADS.P3]
            for i in range(self.num_lvdts):
                ch = channel_map[i % len(channel_map)]
                channel = AnalogIn(ads, ch)
                channel.voltage = lambda: channel.voltage  # Ensure compatibility
                channels.append(channel)
            return channels
        except Exception as e:
            print(f"Error creating LVDT channels: {e}")
            return None

    def create_accelerometers(self):
        """Create and return MPU6050 accelerometer objects."""
        try:
            mpu_list = []
            for i in range(self.num_accelerometers):
                addr = 0x68 + i  # Assumes sensors on consecutive I2C addresses
                mpu_list.append(mpu6050(addr))
            return mpu_list
        except Exception as e:
            print(f"Error initializing accelerometers: {e}")
            return None


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
        ads.gain = 2.0 / 3.0  # Se puede ajustar el gain según sea necesario
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
