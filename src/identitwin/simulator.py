"""Simulation configuration module replacing hardware configurator with dummy implementations."""
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
class DummyLED:
    # Use colorama constants
    GREEN = colorama.Fore.GREEN
    BLUE = colorama.Fore.BLUE
    RESET = colorama.Style.RESET_ALL # Use Style.RESET_ALL

    def __init__(self, pin_number, verbose=True): # Default verbosity to True for simulation feedback
        self.pin_number = pin_number # Store the pin number
        self.verbose = verbose
        self.state = False # Track LED state: False = off, True = on
        # Determine color based on pin number (assuming pin 17=Status, 18=Activity)
        if self.pin_number == 17: # Status LED
            self.color = self.GREEN
            self.name = "Status"
        elif self.pin_number == 18: # Activity LED
            self.color = self.BLUE
            self.name = "Activity"
        else: # Default/Unknown LED
            self.color = "" # No specific color for unknown
            self.name = f"Unknown (Pin {self.pin_number})"
        # Add a print here to confirm verbose state during init
        if self.verbose:
            print(f"{self.color}SIMULATOR_INIT: {self.name} LED (Pin {self.pin_number}) initialized with verbose=True")
        else:
             print(f"SIMULATOR_INIT: {self.name} LED (Pin {self.pin_number}) initialized with verbose=False")


    @property
    def is_lit(self):
        """Return the current state of the LED (True if ON, False if OFF)."""
        return self.state

    def on(self):
        """Turn on the LED."""
        # Simplified print - only if verbose and state changes
        if self.verbose and not self.state:
            self.state = True
            print(f"{self.color}SIMULATOR: {self.name} LED (Pin {self.pin_number}) ON")
        elif not self.verbose and not self.state:
             self.state = True # Still change state even if not verbose

    def off(self):
        """Turn off the LED."""
        # Simplified print - only if verbose and state changes
        if self.verbose and self.state:
            self.state = False
            print(f"{self.color}SIMULATOR: {self.name} LED (Pin {self.pin_number}) OFF")
        elif not self.verbose and self.state:
             self.state = False # Still change state even if not verbose

    def toggle(self):
        """Toggle the LED state."""
        if self.state:
            self.off()
        else:
            self.on()
        # Removed redundant print from here as on/off handle it

    def blink(self, on_time=1, off_time=1, n=1, background=False):
        """
        Simulate LED blinking.
        """
        if self.verbose:
            print(f"{self.color}SIMULATOR: {self.name} LED (Pin {self.pin_number}) blink called (background={background})")
        # Blinking logic remains the same, on/off methods will print messages
        if not background:
            initial_state = self.state
            for _ in range(n):
                self.on()
                time.sleep(on_time)
                self.off()
                if _ < n - 1:
                    time.sleep(off_time)
            # Restore initial state if it was ON before blinking started
            if initial_state:
                 self.on()

class DummyADS:
    def __init__(self):
        self.gain = None

class DummyAnalogIn:
    def __init__(self, ads, pin):
        self.pin = pin
        self._start_time = time.time()
        self._amplitude = 0.5  # 0.5V amplitud
        self._frequency = 0.1  # 0.1 Hz = 1 ciclo cada 10 segundos
        self._noise_level = 0.01  # 10mV de ruido
        self.calibration_slope = None  # Será establecido durante la calibración
        self.calibration_intercept = None  # Será establecido durante la calibración

    def set_calibration(self, slope, intercept):
        """Almacena los parámetros de calibración."""
        self.calibration_slope = slope
        self.calibration_intercept = intercept

    @property
    def voltage(self):
        t = time.time() - self._start_time
        base_signal = self._amplitude * math.sin(2 * math.pi * self._frequency * t)
        noise = random.uniform(-self._noise_level, self._noise_level)
        return base_signal + noise

import time
import random
import math

class DummyMPU6050:
    def __init__(self, addr):
        self.addr = addr
        self._cycle_start_time = time.time()
        self._current_interval = self._generate_random_interval()
        self.state = "noise"  # Initial state: only noise
        self.transition_progress = 0  # Progress of the transition (0 to 1)

    def _generate_random_interval(self):
        """Generates a random interval between 30 and 35 seconds."""
        return random.uniform(30, 35)

    def _update_state(self, t):
        """Updates the state and resets the cycle if the interval is exceeded."""
        if t >= self._current_interval:
            self._cycle_start_time = time.time()
            self._current_interval = self._generate_random_interval()
            self.state = "periodic" if self.state == "noise" else "noise"
            self.transition_progress = 0  # Reset the transition

    def _apply_smooth_transition(self, value):
        """Applies a smooth transition using a sigmoid curve."""
        # Sigmoid function for a smoother transition
        sigmoid_progress = 1 / (1 + math.exp(-10 * (self.transition_progress - 0.5)))
        return value * sigmoid_progress

    def get_accel_data(self):
        """Simulates accelerometer data with constant noise and periodic signals."""
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
            periodic_signal_x = 7.5 * math.sin(t * 2 * math.pi * 2) + 1.5 * math.sin(t * 2 * math.pi * 3.7)
            periodic_signal_y = 5.5 * math.cos(t * 2 * math.pi * 2.5) + 1.5 * math.cos(t * 2 * math.pi * 3.75)
            periodic_signal_z = 7.5 * math.sin(t * 2 * math.pi * 2.1) + 1.5 * math.sin(t * 2 * math.pi * 3.8)

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
    """Configuration class for simulation mode."""
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
    ):
        self.verbose = verbose  # Store verbosity setting
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
        """Initialize the thresholds for event detection."""
        return {
            "acceleration": self.trigger_acceleration_threshold if self.enable_accel else None,
            "displacement": self.trigger_displacement_threshold if self.enable_lvdt else None,
            "pre_event_time": self.pre_event_time, # Corrected
            "post_event_time": self.post_event_time, # Corrected
            "min_event_duration": self.min_event_duration,
        }

    def initialize_leds(self):
        """Return dummy LED objects with pin numbers."""
        print(f"DEBUG: SimulatorConfig.initialize_leds called with self.verbose={self.verbose}") # Add this check
        # Use default pins if not provided, assuming 17=Status, 18=Activity
        status_pin = self.gpio_pins[0] if self.gpio_pins and len(self.gpio_pins) > 0 and self.gpio_pins[0] is not None else 17
        activity_pin = self.gpio_pins[1] if self.gpio_pins and len(self.gpio_pins) > 1 and self.gpio_pins[1] is not None else 18
        # Pass self.verbose explicitly
        status_led = DummyLED(pin_number=status_pin, verbose=self.verbose)
        activity_led = DummyLED(pin_number=activity_pin, verbose=self.verbose)
        status_led.off() # Ensure they start off
        activity_led.off() # Ensure they start off
        return status_led, activity_led

    def create_ads1115(self):
        """Return a dummy ADS instance."""
        dummy = DummyADS()
        dummy.gain = self.lvdt_gain
        return dummy

    def create_lvdt_channels(self, ads):
        """Create simulated LVDT channels."""
        channels = []
        for i in range(self.num_lvdts):
            channel = DummyAnalogIn(ads, i)
            channels.append(channel)
        return channels

    def create_accelerometers(self):
        """Return dummy MPU6050 accelerometer objects."""
        mpu_list = []
        for i in range(self.num_accelerometers):
            mpu_list.append(DummyMPU6050(0x68 + i))
        return mpu_list

    def process_lvdt_data(self, lvdt_data, lvdt_index=None):
        """Process LVDT data without any logging."""
        return lvdt_data  # Return data directly without any logging


# Simulated utilities (similar to configurator, but dummy)
# Removed leds() function

# Removed ads1115() function

def thresholds(trigger_acceleration, trigger_displacement, pre_time, enable_accel, enable_lvdt):
    return {
        "acceleration": trigger_acceleration if enable_accel else None,
        "displacement": trigger_displacement if enable_lvdt else None,
        "pre_event_time": pre_time,
        "post_event_time": pre_time,
    }
