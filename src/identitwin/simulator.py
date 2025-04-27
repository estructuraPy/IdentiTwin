"""Simulation configuration and dummy hardware implementations.

Provides a `SimulatorConfig` class that mirrors `SystemConfig` but replaces
hardware initialization calls with dummy objects (`DummyADS`, `DummyAnalogIn`,
`DummyMPU6050`). Allows running the IdentiTwin system without actual hardware,
generating simulated sensor data for testing and development.

Suppresses hardware-related warnings when running in simulation mode.
"""
import os
import platform
from datetime import datetime
import time
import math
import numpy as np
import random  # Add this import
import warnings  # For suppressing warnings
import colorama # Import colorama

# Initialize colorama
colorama.init(autoreset=True) # autoreset=True automatically adds Fore.RESET after each print

# Suppress any hardware-related warnings in simulation mode
warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", message=".*chip_id.*")
warnings.filterwarnings("ignore", message=".*Adafruit-PlatformDetect.*")

# Dummy classes to simulate hardware

class DummyADS:
    """Dummy class simulating the ADS1115 ADC."""
    def __init__(self):
        """Initializes the dummy ADS."""
        self.gain = None

class DummyAnalogIn:
    """Dummy class simulating an analog input channel on the ADS1115.

    Generates a simulated LVDT signal consisting of a low-frequency sine wave
    with added noise. Stores calibration parameters set via `set_calibration`.

    Attributes:
        pin (int): The simulated pin number.
        _start_time (float): Time when the instance was created.
        _amplitude (float): Amplitude of the simulated sine wave voltage.
        _frequency (float): Frequency of the simulated sine wave voltage.
        _noise_level (float): Amplitude of the random noise added to the signal.
        calibration_slope (float or None): LVDT calibration slope (mm/V).
        calibration_intercept (float or None): LVDT calibration intercept (mm).
    """
    def __init__(self, ads, pin):
        """Initializes the dummy analog input channel.

        Args:
            ads (DummyADS): The dummy ADS instance.
            pin (int): The simulated pin number associated with this channel.
        """
        self.pin = pin
        self._start_time = time.time()
        self._amplitude = 0.5  # 0.5V amplitud
        self._frequency = 0.1  # 0.1 Hz = 1 ciclo cada 10 segundos
        self._noise_level = 0.01  # 10mV de ruido
        self.calibration_slope = None  # Será establecido durante la calibración
        self.calibration_intercept = None  # Será establecido durante la calibración

    def set_calibration(self, slope, intercept):
        """Stores LVDT calibration parameters.

        Args:
            slope (float): The calibration slope (e.g., mm/V).
            intercept (float): The calibration intercept (e.g., mm).
        """
        self.calibration_slope = slope
        self.calibration_intercept = intercept

    @property
    def voltage(self):
        """Simulates reading the voltage from the LVDT channel.

        Generates a voltage value based on a sine wave plus random noise.

        Returns:
            float: The simulated voltage reading.
        """
        t = time.time() - self._start_time
        base_signal = self._amplitude * math.sin(2 * math.pi * self._frequency * t) / 2
        noise = random.uniform(-self._noise_level, self._noise_level)
        return base_signal + noise

import time
import random
import math

class DummyMPU6050:
    """Dummy class simulating the MPU6050 accelerometer/gyroscope.

    Generates simulated accelerometer data that transitions between periods of
    constant noise and periods with added periodic signals. Includes smooth
    transitions between states.

    Attributes:
        addr (int): The simulated I2C address.
        _cycle_start_time (float): Timestamp when the current noise/periodic cycle began.
        _current_interval (float): Duration of the current cycle (randomly generated).
        state (str): Current simulation state ('noise' or 'periodic').
        transition_progress (float): Progress (0 to 1) of the smooth transition
            between states.
    """
    def __init__(self, addr):
        """Initializes the dummy MPU6050 sensor.

        Args:
            addr (int): The simulated I2C address for this sensor.
        """
        self.addr = addr
        self._cycle_start_time = time.time()
        self._current_interval = self._generate_random_interval()
        self.state = "noise"  # Initial state: only noise
        self.transition_progress = 0  # Progress of the transition (0 to 1)

    def _generate_random_interval(self):
        """Generates a random duration for the noise/periodic cycle.

        Returns:
            float: A random duration between 30 and 35 seconds.
        """
        return random.uniform(30, 35)

    def _update_state(self, t):
        """Updates the simulation state (noise/periodic) based on elapsed time.

        If the elapsed time `t` exceeds the `_current_interval`, it toggles
        the state, resets the cycle timer and transition progress, and generates
        a new random interval.

        Args:
            t (float): Time elapsed since the start of the current cycle.
        """
        if t >= self._current_interval:
            self._cycle_start_time = time.time()
            self._current_interval = self._generate_random_interval()
            self.state = "periodic" if self.state == "noise" else "noise"
            self.transition_progress = 0  # Reset the transition

    def _apply_smooth_transition(self, value):
        """Applies a smooth sigmoid transition to a signal value.

        Used to smoothly fade the periodic signals in or out when the state changes.

        Args:
            value (float): The original signal value.

        Returns:
            float: The signal value scaled by the sigmoid transition factor.
        """
        # Sigmoid function for a smoother transition
        sigmoid_progress = 1 / (1 + math.exp(-10 * (self.transition_progress - 0.5)))
        return value * sigmoid_progress

    def get_accel_data(self):
        """Simulates reading accelerometer data.

        Generates data based on the current state ('noise' or 'periodic').
        Applies constant noise and, if in 'periodic' state, adds simulated
        periodic signals with smooth transitions. Assumes gravity acts along Z.

        Returns:
            dict: A dictionary containing simulated acceleration values for
                  'x', 'y', and 'z' axes in m/s².
        """
        t = time.time() - self._cycle_start_time

        # Update the state if needed
        self._update_state(t)

        # Increment the progress of the transition
        self.transition_progress = min(self.transition_progress + 0.01, 1)  # Progress in each call

        # Constant noise
        noise_x = 0.0005 * math.sin(t * 2 * math.pi * 50) + 0.0003 * math.sin(t * 2 * math.pi * 80)
        noise_y = 0.0006 * math.cos(t * 2 * math.pi * 60) + 0.0004 * math.cos(t * 2 * math.pi * 100)
        noise_z = 0.0007 * math.sin(t * 2 * math.pi * 70) + 0.0005 * math.cos(t * 2 * math.pi * 90)

        if self.state == "periodic":
            # Periodic signals
            periodic_signal_x = 7.5 * math.sin(t * 2 * math.pi * 20) + 1.5 * math.sin(t * 2 * math.pi * 35)
            periodic_signal_y = 5.5 * math.cos(t * 2 * math.pi * 22) + 1.5 * math.cos(t * 2 * math.pi * 37)
            periodic_signal_z = 7.5 * math.sin(t * 2 * math.pi * 20) + 1.5 * math.sin(t * 2 * math.pi * 35)

            # Apply the smooth transition to periodic signals
            periodic_signal_x = self._apply_smooth_transition(periodic_signal_x)
            periodic_signal_y = self._apply_smooth_transition(periodic_signal_y)
            periodic_signal_z = self._apply_smooth_transition(periodic_signal_z)

            return {
                'x': noise_x + periodic_signal_x,
                'y': noise_y + periodic_signal_y,
                'z': 9.81 + noise_z + periodic_signal_z  # Gravity + noise + periodic signals
            }
        else:
            # Only noise
            return {
                'x': noise_x,
                'y': noise_y,
                'z': 9.81 + noise_z  # Gravity + noise
            }

        
# Simulated configuration class
class SimulatorConfig:
    """Configuration class for simulation mode. Mirrors `SystemConfig`.

    Provides the same configuration attributes as `SystemConfig` but includes
    methods to create dummy hardware objects instead of real ones. Used to run
    the system without requiring physical hardware connections.

    Attributes:
        verbose (bool): Flag for enabling verbose output (currently unused).
        enable_plots (bool): Enable/disable real-time plotting dashboard.
        enable_plot_displacement (bool): Enable/disable LVDT plot tab.
        enable_accel_plots (bool): Enable/disable Accelerometer plot tab.
        enable_fft_plots (bool): Enable/disable FFT plot tab.
        output_dir (str): Base directory for saving output files (logs, events, reports).
        events_dir (str): Subdirectory for event-specific data.
        logs_dir (str): Subdirectory for log files (performance, calibration).
        reports_dir (str): Subdirectory for generated reports.
        acceleration_file (str): Path for continuous acceleration CSV log (unused in sim).
        displacement_file (str): Path for continuous displacement CSV log (unused in sim).
        general_file (str): Path for combined sensor CSV log (unused in sim).
        enable_performance_monitoring (bool): Enable/disable performance logging.
        performance_log_file (str): Path for performance log CSV.
        enable_lvdt (bool): Enable/disable LVDT simulation.
        enable_accel (bool): Enable/disable accelerometer simulation.
        num_lvdts (int): Number of simulated LVDTs.
        num_accelerometers (int): Number of simulated accelerometers.
        lvdt_slopes (list or None): List of slopes (mm/V) for LVDT calibration.
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
        lvdt_gain (float): Simulated ADC gain setting.
        lvdt_scale_factor (float): Simulated ADC scale factor (mV).
        lvdt_slope (float): Default LVDT slope if not provided (mm/V).
        lvdt_intercept (float): Default LVDT intercept (mm).
        accel_offsets (list): List of dummy accelerometer offsets.
        gpio_pins (list or None): Simulated GPIO pin numbers for LEDs.
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
        verbose=False,  # Add verbosity flag
        enable_plots=True,
        enable_plot_displacement=True,
        enable_accel_plots=True,
        enable_fft_plots=True,
    ):
        """Initializes the simulation configuration.

        Args:
            enable_lvdt (bool): Enable LVDT simulation.
            enable_accel (bool): Enable accelerometer simulation.
            output_dir (str, optional): Base directory for output. Defaults to
                'repository/<YYYYMMDD>'.
            num_lvdts (int): Number of simulated LVDTs.
            num_accelerometers (int): Number of simulated accelerometers.
            lvdt_slopes (list, optional): List of slopes (mm/V) for LVDT calibration.
            sampling_rate_acceleration (float): Target accel sampling rate (Hz).
            sampling_rate_lvdt (float): Target LVDT sampling rate (Hz).
            plot_refresh_rate (float): Target plot refresh rate (Hz).
            gpio_pins (list, optional): Simulated GPIO pins for LEDs. Defaults to None.
            trigger_acceleration_threshold (float, optional): Event trigger threshold (m/s²).
            detrigger_acceleration_threshold (float, optional): Event detrigger threshold (m/s²).
            trigger_displacement_threshold (float, optional): Event trigger threshold (mm).
            detrigger_displacement_threshold (float, optional): Event detrigger threshold (mm).
            pre_event_time (float): Pre-event buffer duration (s).
            post_event_time (float): Post-event buffer duration (s).
            min_event_duration (float): Minimum valid event duration (s).
            verbose (bool): Enable verbose output (currently unused).
            enable_plots (bool): Enable plotting dashboard.
            enable_plot_displacement (bool): Enable LVDT plot tab.
            enable_accel_plots (bool): Enable Accelerometer plot tab.
            enable_fft_plots (bool): Enable FFT plot tab.
        """
        self.verbose = verbose  # Store verbosity setting
        self.enable_plots = enable_plots
        self.enable_plot_displacement = enable_plot_displacement
        self.enable_accel_plots = enable_accel_plots
        self.enable_fft_plots = enable_fft_plots
        # Directory and file configuration
        self.output_dir = output_dir or os.path.join("repository", datetime.now().strftime("%Y%m%d"))
        os.makedirs(self.output_dir, exist_ok=True)
        self.events_dir = os.path.join(self.output_dir, "events")
        self.logs_dir = os.path.join(self.output_dir, "logs")
        self.reports_dir = os.path.join(self.output_dir, "reports")
        for directory in [self.events_dir, self.logs_dir, self.reports_dir]:
            os.makedirs(directory, exist_ok=True)
        self.acceleration_file = os.path.join(self.output_dir, "acceleration.csv")
        self.displacement_file = os.path.join(self.output_dir, "displacement.csv")
        self.general_file = os.path.join(self.output_dir, "general_measurements.csv")
        self.enable_performance_monitoring = True
        self.performance_log_file = os.path.join(self.logs_dir, "performance_log.csv")
        
        # Sensor configuration
        self.enable_lvdt = enable_lvdt
        self.enable_accel = enable_accel
        self.num_lvdts = num_lvdts
        self.num_accelerometers = num_accelerometers
        self.lvdt_slopes = lvdt_slopes # Store the lvdt_slopes

        self.sampling_rate_acceleration = sampling_rate_acceleration
        self.sampling_rate_lvdt = sampling_rate_lvdt
        self.plot_refresh_rate = plot_refresh_rate
        self.time_step_acceleration = 1.0 / self.sampling_rate_acceleration
        self.time_step_lvdt = 1.0 / self.sampling_rate_lvdt
        self.time_step_plot_refresh = 1.0 / self.plot_refresh_rate
        
        self.window_duration = 5
        self.gravity = 9.81
        self.max_accel_jitter = 1.5
        self.max_lvdt_jitter = 5.0
        
        self.trigger_acceleration_threshold = trigger_acceleration_threshold or (0.3 * self.gravity)
        self.trigger_displacement_threshold = trigger_displacement_threshold or 1.0
        self.detrigger_acceleration_threshold = detrigger_acceleration_threshold or (self.trigger_acceleration_threshold * 0.5)
        self.detrigger_displacement_threshold = detrigger_displacement_threshold or (self.trigger_displacement_threshold * 0.5)
        
        self.pre_event_time = pre_event_time # Corrected
        self.post_event_time = post_event_time # Corrected
        self.min_event_duration = min_event_duration
        
        # Simulation parameters for LVDT
        self.lvdt_gain = 2.0 / 3.0
        self.lvdt_scale_factor = 0.1875
        self.lvdt_slope = 19.86
        self.lvdt_intercept = 0.0
        
        # Accelerometer configuration (dummy values)
        self.accel_offsets = [{"x": 0.0, "y": 0.0, "z": 0.0} for _ in range(self.num_accelerometers)]
        
        # In simulation, no real GPIO pins are used
        self.gpio_pins = gpio_pins or [None, None]
        
        # Print platform information in simulation mode
        print(f"Platform: {platform.system()} {platform.release()}")
        print("Running in Simulation Mode")

    def initialize_thresholds(self):
        """Initializes the dictionary of event detection thresholds.

        Returns:
            dict: A dictionary containing the configured thresholds for
                  acceleration, displacement, pre/post event times, and minimum duration.
                  Thresholds for disabled sensors are set to None.
        """
        return {
            "acceleration": self.trigger_acceleration_threshold if self.enable_accel else None,
            "displacement": self.trigger_displacement_threshold if self.enable_lvdt else None,
            "pre_event_time": self.pre_event_time,
            "post_event_time": self.post_event_time,
            "min_event_duration": self.min_event_duration,
        }

    def initialize_leds(self):
        """Simulates LED initialization (returns None).

        In simulation mode, no hardware LEDs are used.

        Returns:
            tuple[None, None]: Always returns (None, None).
        """
        print("SIMULATOR: Skipping hardware LED initialization.")
        # Return None, None as hardware is not used in simulation
        return None, None

    def create_ads1115(self):
        """Creates and returns a dummy ADS1115 ADC object.

        Returns:
            DummyADS: An instance of the dummy ADC simulator.
        """
        dummy = DummyADS()
        dummy.gain = self.lvdt_gain
        return dummy

    def create_lvdt_channels(self, ads):
        """Creates simulated LVDT analog input channels.

        Args:
            ads (DummyADS): The dummy ADS instance.

        Returns:
            list[DummyAnalogIn]: A list of dummy analog input channel objects.
        """
        channels = []
        for i in range(self.num_lvdts):
            channel = DummyAnalogIn(ads, i)
            channels.append(channel)
        return channels

    def create_accelerometers(self):
        """Creates dummy MPU6050 accelerometer objects.

        Returns:
            list[DummyMPU6050]: A list of dummy accelerometer objects, one for
                                each `num_accelerometers` configured.
        """
        mpu_list = []
        for i in range(self.num_accelerometers):
            mpu_list.append(DummyMPU6050(0x68 + i))
        return mpu_list

    def process_lvdt_data(self, lvdt_data, lvdt_index=None):
        """Processes simulated LVDT data (identity function in simulation).

        Args:
            lvdt_data (any): The input LVDT data.
            lvdt_index (int, optional): Index of the LVDT (unused).

        Returns:
            any: The original `lvdt_data` unchanged.
        """
        return lvdt_data  # Return data directly without any logging


# Simulated utilities (similar to configurator, but dummy)
# Removed leds() function

# Removed ads1115() function

def thresholds(trigger_acceleration, trigger_displacement, pre_time, enable_accel, enable_lvdt):
    """Initializes a dictionary of event detection thresholds.

    Deprecated: Use `SimulatorConfig.initialize_thresholds()` or
    `SystemConfig.initialize_thresholds()` instead.

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
