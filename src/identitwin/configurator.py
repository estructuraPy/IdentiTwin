"""Configuration management and hardware setup module for IdentiTwin.

Provides the `SystemConfig` class to manage system parameters, operational
modes, and hardware initialization for Raspberry Pi. Attempts to import
necessary hardware libraries (`gpiozero`, `adafruit_ads1x15`, `mpu6050`, etc.)
and checks for I2C availability. If hardware access fails or if not running
on Linux, it defaults to a software-only mode where hardware interactions
are skipped or simulated.

Attributes:
    IS_RASPBERRY_PI (bool): True if the system detects it's running on Linux.
    I2C_AVAILABLE (bool): True if hardware libraries were imported and I2C bus
        communication check succeeded.
    LED (class or None): The `gpiozero.LED` class if available, otherwise None.
    ADS (module or None): The `adafruit_ads1x15.ads1115` module if available.
    board (module or None): The `board` module if available.
    busio (module or None): The `busio` module if available.
    AnalogIn (class or None): The `adafruit_ads1x15.analog_in.AnalogIn` class if available.
    mpu6050 (class or None): The `mpu6050.mpu6050` class if available.
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
warnings.filterwarnings("ignore", message=".*chip_id == None.*")

# Check if we're running on Linux (likely Raspberry Pi)
IS_RASPBERRY_PI = platform.system() == "Linux"
I2C_AVAILABLE = False  # Default to False until proven otherwise
LED = None # Define LED as None initially

# Only attempt to import hardware libraries if on Linux
if IS_RASPBERRY_PI: # Check if it's Linux first
    try:
        from gpiozero import LED # Now LED is the actual class if import succeeds
        import adafruit_ads1x15.ads1115 as ADS
        import board
        import busio
        from adafruit_ads1x15.analog_in import AnalogIn
        from mpu6050 import mpu6050
        # Check if I2C is actually working (optional but good)
        try:
            i2c_test = busio.I2C(board.SCL, board.SDA)
            i2c_test.deinit() # Release the bus
            I2C_AVAILABLE = True
            print("Hardware libraries successfully imported and I2C available.")
        except Exception as i2c_err:
             print(f"Hardware libraries imported, but I2C check failed: {i2c_err}. Assuming I2C unavailable.")
             I2C_AVAILABLE = False
             LED = None # Ensure LED is None if I2C fails

    except (ImportError, NotImplementedError, RuntimeError) as e: # Added RuntimeError
        print(f"Note: Hardware libraries not available or failed to import ({type(e).__name__}). Running in software simulation mode.")
        # Ensure all hardware variables are None if import fails
        LED = None
        ADS = None
        board = None
        busio = None
        AnalogIn = None
        mpu6050 = None
        I2C_AVAILABLE = False
else:
     print("Note: Not running on Linux. Hardware control disabled. Running in software simulation mode.")
     # Ensure all hardware variables are None on non-Linux
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
    """Configuration class for the IdentiTwin monitoring system.

    Manages all settings, including sensor enablement, sampling rates,
    thresholds, file paths, and hardware initialization parameters. Provides
    methods to initialize hardware components like LEDs, ADC (ADS1115),
    and accelerometers (MPU6050) if running on compatible hardware (Raspberry Pi)
    and libraries are available.

    Attributes:
        output_dir (str): Base directory for saving output files (logs, events, reports).
        events_dir (str): Subdirectory for event-specific data.
        logs_dir (str): Subdirectory for log files (performance, calibration).
        reports_dir (str): Subdirectory for generated reports.
        acceleration_file (str): Path for continuous acceleration CSV log.
        displacement_file (str): Path for continuous displacement CSV log.
        general_file (str): Path for combined sensor CSV log.
        enable_performance_monitoring (bool): Enable/disable performance logging.
        performance_log_file (str): Path for performance log CSV.
        enable_lvdt (bool): Enable/disable LVDT sensors.
        enable_accel (bool): Enable/disable accelerometer sensors.
        num_lvdts (int): Number of LVDT sensors to configure.
        lvdt_slopes (list or None): List of slopes (mm/V) for LVDT calibration.
        num_accelerometers (int): Number of accelerometer sensors to configure.
        sampling_rate_acceleration (float): Target sampling rate for accelerometers (Hz).
        sampling_rate_lvdt (float): Target sampling rate for LVDTs (Hz).
        plot_refresh_rate (float): Target refresh rate for dashboard plots (Hz).
        time_step_acceleration (float): Calculated time interval between accel samples (s).
        time_step_lvdt (float): Calculated time interval between LVDT samples (s).
        time_step_plot_refresh (float): Calculated time interval between plot updates (s).
        window_duration (int): Duration for plotting windows (seconds, currently unused).
        gravity (float): Standard gravity value (m/s²).
        max_accel_jitter (float): Max allowed jitter for accel timing (ms, unused).
        max_lvdt_jitter (float): Max allowed jitter for LVDT timing (ms, unused).
        trigger_acceleration_threshold (float): Threshold for event triggering (m/s²).
        trigger_displacement_threshold (float): Threshold for event triggering (mm).
        detrigger_acceleration_threshold (float): Threshold for event detriggering (m/s²).
        detrigger_displacement_threshold (float): Threshold for event detriggering (mm).
        pre_event_time (float): Duration of data to save before an event trigger (s).
        post_event_time (float): Duration of data to save after an event detrigger (s).
        min_event_duration (float): Minimum duration for a valid event (s).
        lvdt_gain (float): ADC gain setting for LVDTs.
        lvdt_scale_factor (float): ADC scale factor for voltage conversion (mV).
        gpio_pins (list): GPIO pin numbers [Status LED, Activity LED].
        enable_plots (bool): Enable/disable real-time plotting dashboard.
        enable_plot_displacement (bool): Enable/disable LVDT plot tab.
        enable_accel_plots (bool): Enable/disable Accelerometer plot tab.
        enable_fft_plots (bool): Enable/disable FFT plot tab.
        lvdt_calibration (list): Stores calibration data populated by calibration functions.
        accel_offsets (list): Stores calibration offsets populated by calibration functions.
    """

    def __init__(
        self,
        enable_lvdt=True,
        enable_accel=True,
        output_dir=None,
        num_lvdts=2,
        num_accelerometers=2,
        lvdt_slopes=None,  # Add the lvdt_slopes parameter here
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
        enable_plots=True,
        enable_plot_displacement=True,
        enable_accel_plots=True,
        enable_fft_plots=True,
    ):
        """Initializes the system configuration.

        Sets up file paths, sensor parameters, sampling rates, thresholds, and
        hardware settings based on provided arguments or defaults. Creates necessary
        output directories.

        Args:
            enable_lvdt (bool): Enable LVDT sensors.
            enable_accel (bool): Enable accelerometer sensors.
            output_dir (str, optional): Base directory for output. Defaults to
                'repository/<YYYYMMDD>'.
            num_lvdts (int): Number of LVDT sensors.
            num_accelerometers (int): Number of accelerometer sensors.
            lvdt_slopes (list, optional): List of slopes (mm/V) for LVDT calibration.
            sampling_rate_acceleration (float): Target accel sampling rate (Hz).
            sampling_rate_lvdt (float): Target LVDT sampling rate (Hz).
            plot_refresh_rate (float): Target plot refresh rate (Hz).
            gpio_pins (list, optional): GPIO pins for [Status, Activity] LEDs.
                Defaults to [18, 17].
            trigger_acceleration_threshold (float, optional): Event trigger threshold (m/s²).
            detrigger_acceleration_threshold (float, optional): Event detrigger threshold (m/s²).
            trigger_displacement_threshold (float, optional): Event trigger threshold (mm).
            detrigger_displacement_threshold (float, optional): Event detrigger threshold (mm).
            pre_event_time (float): Pre-event buffer duration (s).
            post_event_time (float): Post-event buffer duration (s).
            min_event_duration (float): Minimum valid event duration (s).
            enable_plots (bool): Enable plotting dashboard.
            enable_plot_displacement (bool): Enable LVDT plot tab.
            enable_accel_plots (bool): Enable Accelerometer plot tab.
            enable_fft_plots (bool): Enable FFT plot tab.
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
        self.lvdt_slopes = lvdt_slopes
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

        self.max_accel_jitter = 1.5
        self.max_lvdt_jitter = 5.0

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

        # Store visualization settings
        self.enable_plots = enable_plots
        self.enable_plot_displacement = enable_plot_displacement
        self.enable_accel_plots = enable_accel_plots
        self.enable_fft_plots = enable_fft_plots

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

        # Initialize calibration attributes
        self.lvdt_calibration = [None] * self.num_lvdts
        self.accel_offsets = [None] * self.num_accelerometers

    def _initialize_output_directory(self, custom_dir=None):
        """Initializes and returns the path to the session's output directory.

        Deprecated/Unused: Directory creation is now handled directly in `__init__`.

        Args:
            custom_dir (str, optional): A custom base directory. Defaults to None,
                in which case 'repository' is used.

        Returns:
            str: The path to the session-specific output directory (e.g., 'repository/YYYY-MM-DD').
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
        """Initializes and returns the dictionary of event detection thresholds.

        Based on the configuration settings (`trigger_*`, `detrigger_*`, `pre_event_time`, etc.).
        Sets thresholds to None for disabled sensor types.

        Returns:
            dict: A dictionary containing the configured thresholds.
        """
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
        """Initializes hardware LEDs using configured GPIO pins.

        Attempts to create `gpiozero.LED` objects for status and activity LEDs.
        Requires `gpiozero` library and running on compatible hardware (Raspberry Pi).
        Ensures LEDs start in the OFF state.

        Returns:
            tuple[gpiozero.LED or None, gpiozero.LED or None]: A tuple containing
            the initialized status LED and activity LED objects, or (None, None)
            if hardware/libraries are unavailable or initialization fails.
        """
        global LED # Reference the potentially imported LED class

        if not I2C_AVAILABLE or LED is None:
            print("Hardware LED control not available (I2C or gpiozero unavailable). Skipping LED initialization.")
            return None, None # Return None if hardware isn't available

        if not self.gpio_pins or len(self.gpio_pins) < 2:
            print("Warning: GPIO pins not configured correctly. Skipping LED initialization.")
            return None, None # Return None if config is wrong

        status_pin = self.gpio_pins[0]
        activity_pin = self.gpio_pins[1]

        try:
            # Attempt to initialize hardware LEDs using configured pins
            status_led = LED(status_pin)
            activity_led = LED(activity_pin)

            # Ensure LEDs start in the OFF state
            status_led.off()
            activity_led.off()

            print(f"Hardware LEDs initialized on GPIO pins: {status_pin} (Status), {activity_pin} (Activity)")
            return status_led, activity_led

        except Exception as e:
            # Catch any error during hardware initialization
            print(f"Error initializing hardware LEDs on pins {status_pin}, {activity_pin}: {e}")
            print("Skipping LED initialization due to error.")
            # Return None on error
            return None, None

    def create_ads1115(self):
        """Creates and configures an ADS1115 ADC object via I2C.

        Requires `adafruit_ads1x15`, `board`, `busio` libraries and working I2C.
        Sets the ADC gain based on `self.lvdt_gain`.

        Returns:
            ADS.ADS1115 or None: An initialized ADS1115 object, or None if
            hardware/libraries are unavailable or initialization fails.
        """
        if not I2C_AVAILABLE or busio is None or board is None or ADS is None:
            print("Error: Cannot create ADS1115, required hardware libraries not available or I2C failed.")
            return None
        try:
            # Initialize I2C bus
            i2c = busio.I2C(board.SCL, board.SDA)
            ads = ADS.ADS1115(i2c)
            ads.gain = self.lvdt_gain   # Gain of 2/3 (+-6.144V)
            print("ADS1115 initialized successfully.")
            return ads
        except Exception as e:
            print(f"Error initializing ADS1115: {e}")
            traceback.print_exc()
            return None

    def create_lvdt_channels(self, ads):
        """Creates analog input channels for LVDTs on the ADS1115.

        Initializes `AnalogIn` objects for the configured number of LVDTs,
        using default pins (P0, P1, ...). Performs an initial voltage read
        for each channel upon creation.

        Args:
            ads (ADS.ADS1115): An initialized ADS1115 object.

        Returns:
            list[AnalogIn] or None: A list of initialized `AnalogIn` channel
            objects, or None if `ads` is None, hardware/libraries are unavailable,
            or no channels could be initialized.
        """
        if ads is None or not I2C_AVAILABLE or AnalogIn is None:
            print("Error: Cannot create LVDT channels, ADS object is None or required hardware libraries not available.")
            return None

        try:
            channels = []
            pins = [ADS.P0, ADS.P1, ADS.P2, ADS.P3][:self.num_lvdts]  # Default pin configuration
            for i, pin in enumerate(pins):
                try:
                    # Initialize the channel and test voltage reading
                    channel = AnalogIn(ads, pin)
                    voltage = channel.voltage  # Read initial voltage
                    print(f"LVDT {i+1} initialized on pin {pin} with initial voltage: {voltage:.4f}V")
                    channels.append(channel)
                except Exception as ch_err:
                    print(f"Error initializing LVDT {i+1} on pin {pin}: {ch_err}")
                    # Continue initializing other channels even if one fails
            if not channels:
                print("No LVDT channels could be initialized.")
                return None
            return channels
        except Exception as e:
            print(f"Error creating LVDT channels: {e}")
            traceback.print_exc()
            return None

    def create_accelerometers(self):
        """Creates and initializes MPU6050 accelerometer objects via I2C.

        Attempts to instantiate `mpu6050.mpu6050` objects for the configured
        number of accelerometers, assuming consecutive I2C addresses starting
        from 0x68. Performs a basic communication check (reading temperature)
        for each sensor.

        Requires `mpu6050`, `board`, `busio` libraries and working I2C.

        Returns:
            list[mpu6050] or None: A list of initialized MPU6050 objects that
            responded successfully, or None if hardware/libraries are unavailable
            or no sensors could be initialized.
        """
        if not I2C_AVAILABLE or mpu6050 is None or board is None or busio is None:
            print("Error: Cannot create accelerometers, required hardware libraries not available or I2C failed.", file=sys.stderr)
            return None

        mpu_list = []
        print(f"\nInitialize {self.num_accelerometers} accelerometers...")
        for i in range(self.num_accelerometers):
            addr = 0x68 + i  # Assumes sensors on consecutive I2C addresses (0x68, 0x69, ...)
            try:
                # Instantiate mpu6050 directly with the address
                print(f"- Initialize MPU6050 at address {hex(addr)}...")
                mpu = mpu6050(addr)

                # Optional: Add a quick check to see if the sensor is responsive
                try:
                    temp = mpu.get_temp()  # Try reading temperature
                    mpu_list.append(mpu)
                except OSError as comm_err:
                    print(f"  Warning: Could not communicate with MPU6050 at address {hex(addr)}: {comm_err}. Skipping this sensor.", file=sys.stderr)
                    continue  # Skip this sensor
            except Exception as e:
                print(f"  Error initializing MPU6050 at address {hex(addr)}: {e}. Skipping this sensor.", file=sys.stderr)
                continue  # Continue trying other sensors even if one fails

        return mpu_list if mpu_list else None  # Return list or None if empty

# Utility functions

def thresholds(trigger_acceleration, trigger_displacement, pre_time, enable_accel, enable_lvdt):
    """Initializes a dictionary of event detection thresholds.

    Deprecated: Use `SystemConfig.initialize_thresholds()` or
    `SimulatorConfig.initialize_thresholds()` instead.

    Args:
        trigger_acceleration (float): Acceleration trigger threshold.
        trigger_displacement (float): Displacement trigger threshold.
        pre_time (float): Pre-event buffer time.
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
