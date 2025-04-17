"""
Configuration Management Module for IdentiTwin.

Handles the setup and storage of all system-wide configuration parameters.
Detects the platform (Raspberry Pi vs. other) to conditionally import hardware
libraries and provides methods for initializing hardware components like LEDs,
ADC (ADS1115), and accelerometers (MPU6050).

Key Features:
- Centralized configuration management via the `SystemConfig` class.
- Platform detection for hardware-specific initialization.
- Dynamic creation of output directory structures based on date.
- Configuration of sensor enablement, sampling rates, event thresholds, and timing.
- Initialization methods for hardware components (LEDs, ADC, Accelerometers).
- Default values and validation for key parameters.

Classes:
    SystemConfig: Holds all configuration parameters and provides initialization methods.
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
    """
    Configuration class holding all parameters for the IdentiTwin monitoring system.

    Manages settings related to sensor enablement, sampling rates, data storage,
    event detection, hardware interfaces (GPIO, I2C), and calibration. Provides
    methods to initialize hardware components based on the configuration.

    Attributes:
        output_dir (str): Base directory for all output files (logs, events, reports).
        events_dir (str): Subdirectory for storing individual event data.
        logs_dir (str): Subdirectory for log files (performance, calibration).
        reports_dir (str): Subdirectory for summary reports.
        acceleration_file (str): Path for the main acceleration CSV log.
        displacement_file (str): Path for the main displacement CSV log.
        general_file (str): Path for the main combined measurements CSV log.
        enable_performance_monitoring (bool): Flag to enable performance logging.
        performance_log_file (str): Path for the performance log CSV.
        enable_lvdt (bool): Flag to enable LVDT sensor processing.
        enable_accel (bool): Flag to enable accelerometer sensor processing.
        num_lvdts (int): Number of LVDT sensors configured.
        num_accelerometers (int): Number of accelerometer sensors configured.
        sampling_rate_acceleration (float): Target sampling rate for accelerometers (Hz).
        sampling_rate_lvdt (float): Target sampling rate for LVDTs (Hz).
        plot_refresh_rate (float): Target refresh rate for live plotting (if used, Hz).
        time_step_acceleration (float): Calculated time interval between accelerometer samples (s).
        time_step_lvdt (float): Calculated time interval between LVDT samples (s).
        time_step_plot_refresh (float): Calculated time interval for plot updates (s).
        window_duration (int): Duration for analysis windows (e.g., moving averages) in seconds.
        gravity (float): Standard gravity value (m/s^2).
        max_accel_jitter (float): Maximum allowable jitter for accelerometer timing (ms).
        max_lvdt_jitter (float): Maximum allowable jitter for LVDT timing (ms).
        trigger_acceleration_threshold (float): Threshold for acceleration magnitude to trigger an event (m/s^2).
        trigger_displacement_threshold (float): Threshold for absolute displacement to trigger an event (mm).
        detrigger_acceleration_threshold (float): Threshold below which acceleration must fall to potentially end an event.
        detrigger_displacement_threshold (float): Threshold below which displacement must fall to potentially end an event.
        pre_trigger_time (float): Duration of data to save before an event trigger (s).
        post_trigger_time (float): Duration to continue recording after the last trigger condition (s).
        min_event_duration (float): Minimum total duration for a recording to be saved as an event (s).
        lvdt_gain (float): Gain setting for the ADS1115 ADC when reading LVDTs.
        lvdt_scale_factor (float): Voltage conversion factor for LVDT ADC readings (mV/bit).
        lvdt_slope (float): Default LVDT calibration slope (mm/V).
        lvdt_intercept (float): Default LVDT calibration intercept (mm).
        accel_offsets (list): List of dictionaries containing calibration offsets ('x', 'y', 'z')
                              and 'scaling_factor' for each accelerometer.
        gpio_pins (list): List of GPIO pin numbers used for status and activity LEDs.
        operational_mode (str): Description of the operational mode (e.g., "Hardware Mode").
    """

    def __init__(
        self,
        enable_lvdt=True,
        enable_accel=True,
        output_dir=None,
        num_lvdts=2,
        num_accelerometers=2,
        sampling_rate_acceleration=200.0,
        sampling_rate_lvdt=5.0,
        plot_refresh_rate=10.0,
        gpio_pins=None,
        trigger_acceleration_threshold=None,
        detrigger_acceleration_threshold=None,
        trigger_displacement_threshold=None,
        detrigger_displacement_threshold=None,
        pre_trigger_time=2.0,
        post_trigger_time=5.0,
        min_event_duration=1.0,
    ):
        """
        Initializes the SystemConfig object with provided or default parameters.

        Sets up data storage paths, sensor configurations, sampling rates,
        event detection parameters, and default hardware settings.

        Args:
            enable_lvdt (bool): Enable LVDT usage. Defaults to True.
            enable_accel (bool): Enable accelerometer usage. Defaults to True.
            output_dir (str, optional): Base directory for output. If None, defaults
                                        to 'repository/YYYYMMDD'. Defaults to None.
            num_lvdts (int): Number of LVDT sensors. Defaults to 2.
            num_accelerometers (int): Number of accelerometer sensors. Defaults to 2.
            sampling_rate_acceleration (float): Target accelerometer sampling rate (Hz). Defaults to 200.0.
            sampling_rate_lvdt (float): Target LVDT sampling rate (Hz). Defaults to 5.0.
            plot_refresh_rate (float): Target plot refresh rate (Hz). Defaults to 10.0.
            gpio_pins (list, optional): GPIO pins for LEDs [status, activity]. If None,
                                        defaults to [18, 17]. Defaults to None.
            trigger_acceleration_threshold (float, optional): Event trigger threshold for acceleration (m/s^2).
                                                              If None, defaults based on gravity. Defaults to None.
            detrigger_acceleration_threshold (float, optional): Event detrigger threshold for acceleration (m/s^2).
                                                                If None, defaults based on trigger threshold. Defaults to None.
            trigger_displacement_threshold (float, optional): Event trigger threshold for displacement (mm).
                                                              If None, defaults to 1.0. Defaults to None.
            detrigger_displacement_threshold (float, optional): Event detrigger threshold for displacement (mm).
                                                                If None, defaults based on trigger threshold. Defaults to None.
            pre_trigger_time (float): Duration of pre-event buffer (s). Defaults to 2.0.
            post_trigger_time (float): Duration to record after last trigger (s). Defaults to 5.0.
            min_event_duration (float): Minimum duration for a valid event (s). Defaults to 1.0.

        Returns:
            None
        """
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
        # Add operational mode attribute
        self.operational_mode = "Hardware Mode" if LED is not None else "Simulation Mode"

    def _initialize_output_directory(self, custom_dir=None):
        """
        DEPRECATED/Internal: Initializes and creates the output directory structure.

        Note: This logic is now primarily handled within __init__. This method
        might be redundant or used for specific cases.

        Creates the base directory and a session-specific subdirectory based on the current date.

        Args:
            custom_dir (str, optional): A custom base directory path. If None, uses 'repository'.
                                        Defaults to None.

        Returns:
            str: The path to the created session-specific directory (e.g., 'repository/YYYY-MM-DD').

        Side Effects:
            - Creates directories on the filesystem if they don't exist.
        """
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
        """
        Creates a dictionary containing the configured event detection thresholds and timings.

        Returns:
            dict: A dictionary with keys 'acceleration', 'displacement', 'pre_event_time',
                  'post_event_time', 'min_event_duration', populated with values from
                  the config object. Thresholds are set to None if the corresponding sensor
                  is disabled.
        """
        # Include detrigger thresholds
        thresholds = {
            "acceleration": self.trigger_acceleration_threshold if self.enable_accel else None,
            "displacement": self.trigger_displacement_threshold if self.enable_lvdt else None,
            "detrigger_acceleration": self.detrigger_acceleration_threshold if self.enable_accel else None,
            "detrigger_displacement": self.detrigger_displacement_threshold if self.enable_lvdt else None,
            "pre_event_time": self.pre_trigger_time,
            "post_event_time": self.post_trigger_time,
            "min_event_duration": self.min_event_duration,
        }
        return thresholds

    def initialize_leds(self):
        """
        Initializes GPIO LEDs for status and activity indication (Raspberry Pi only).

        Uses the `gpiozero` library to create LED objects based on the configured
        `gpio_pins`. Handles potential exceptions during initialization.

        Returns:
            tuple: A tuple containing (status_led, activity_led). Each element is
                   a `gpiozero.LED` object if successful, or None if running in
                   simulation mode or if initialization fails.

        Side Effects:
            - Initializes GPIO pins for LED output.
            - Turns off LEDs initially.
            - Prints a warning message if initialization fails.
        """
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
        """
        Initializes and returns an ADS1115 ADC object via I2C (Raspberry Pi only).

        Uses the `adafruit_ads1x15` library to communicate with the ADC chip.
        Sets the ADC gain based on `self.lvdt_gain`. Handles potential I2C
        communication errors.

        Returns:
            ADS.ADS1115 or None: An initialized ADS1115 object if successful,
                                 otherwise None.

        Side Effects:
            - Initializes I2C communication.
            - Prints an error message if initialization fails.
        """
        try:
            i2c = busio.I2C(board.SCL, board.SDA)
            ads = ADS.ADS1115(i2c)
            ads.gain = self.lvdt_gain  # Set gain as configured
            return ads
        except Exception as e:
            print(f"Error initializing ADS1115: {e}")
            return None

    def create_lvdt_channels(self, ads):
        """
        Creates AnalogIn channel objects for LVDTs using a provided ADS1115 object.

        Maps the configured number of LVDTs (`self.num_lvdts`) to the physical
        channels (P0, P1, P2, P3) of the ADS1115 ADC.

        Args:
            ads: An initialized `ADS.ADS1115` object returned by `create_ads1115`.

        Returns:
            list or None: A list of `AnalogIn` objects, one for each configured LVDT,
                          or None if creation fails or `ads` is None.

        Side Effects:
            - Prints an error message if channel creation fails.
        """
        try:
            channels = []
            channel_map = [ADS.P0, ADS.P1, ADS.P2, ADS.P3]  # ADS1115 has 4 channels
            for i in range(self.num_lvdts):
                if i < len(channel_map):
                    channels.append(AnalogIn(ads, channel_map[i]))
                else:
                    channels.append(AnalogIn(ads, channel_map[-1]))
            return channels
        except Exception as e:
            print(f"Error creating LVDT channels: {e}")
            return None

    def create_accelerometers(self):
        """
        Initializes and returns MPU6050 accelerometer objects via I2C (Raspberry Pi only).

        Uses the `mpu6050-raspberrypi` library. Assumes accelerometers are connected
        at consecutive I2C addresses starting from 0x68.

        Returns:
            list or None: A list of initialized `mpu6050` objects, one for each
                          configured accelerometer (`self.num_accelerometers`),
                          or None if initialization fails.

        Side Effects:
            - Initializes I2C communication for each sensor.
            - Prints an error message if initialization fails.
        """
        try:
            mpu_list = []
            for i in range(self.num_accelerometers):
                addr = 0x68 + i  # Assumes sensors on consecutive I2C addresses
                mpu_list.append(mpu6050(addr))
            return mpu_list
        except Exception as e:
            print(f"Error initializing accelerometers: {e}")
            return None


# Utility functions (Consider integrating these into the class or removing if redundant)

def leds(gpio_pins):
    """
    Standalone utility function to initialize LEDs.

    Args:
        gpio_pins (list): List of two GPIO pin numbers [status, activity].

    Returns:
        tuple: (status_led, activity_led) objects or (None, None) on failure.
    """
    try:
        return LED(gpio_pins[0]), LED(gpio_pins[1])
    except Exception as e:
        print(f"Warning: Could not initialize LEDs: {e}")
        return None, None


def ads1115():
    """
    Standalone utility function to initialize the ADS1115 ADC.

    Returns:
        ADS.ADS1115 object or None on failure.
    """
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS.ADS1115(i2c)
        ads.gain = 2.0 / 3.0  # Se puede ajustar el gain según sea necesario
        return ads
    except Exception as e:
        print(f"Error initializing ADS1115: {e}")
        return None


def thresholds(trigger_acceleration, trigger_displacement, pre_time, enable_accel, enable_lvdt):
    """
    Standalone utility function to create a threshold dictionary.

    Args:
        trigger_acceleration (float): Acceleration trigger threshold.
        trigger_displacement (float): Displacement trigger threshold.
        pre_time (float): Pre-trigger time.
        enable_accel (bool): Whether accelerometers are enabled.
        enable_lvdt (bool): Whether LVDTs are enabled.

    Returns:
        dict: Dictionary containing threshold values.
    """
    return {
        "acceleration": trigger_acceleration if enable_accel else None,
        "displacement": trigger_displacement if enable_lvdt else None,
        "pre_event_time": pre_time,
        "post_event_time": pre_time,
    }
