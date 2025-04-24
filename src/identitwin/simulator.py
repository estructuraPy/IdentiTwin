"""Simulation configuration module replacing hardware configurator with dummy implementations."""
import os
import platform
from datetime import datetime
import time
import math
import numpy as np
import random  # Add this import
import warnings  # For suppressing warnings

# Suppress any hardware-related warnings in simulation mode
warnings.filterwarnings("ignore", category=RuntimeWarning)
warnings.filterwarnings("ignore", message=".*chip_id.*")
warnings.filterwarnings("ignore", message=".*Adafruit-PlatformDetect.*")

# Dummy classes to simulate hardware
class DummyLED:
    def __init__(self, verbose=False):  # Default verbosity to False
        self.verbose = verbose  # Control whether messages are printed
        self.state = False  # Track LED state: False = off, True = on

    def on(self):
        """Turn on the LED."""
        self.state = True
        if self.verbose:
            print("DummyLED on")
    
    def off(self):
        """Turn off the LED."""
        self.state = False
        if self.verbose:
            print("DummyLED off")

    def toggle(self):
        """Toggle the LED state."""
        self.state = not self.state
        if self.verbose:
            print(f"DummyLED toggled to {'on' if self.state else 'off'}")

    def blink(self, on_time=1, off_time=1, n=1, background=False):
        """
        Simulate LED blinking.
        
        Args:
            on_time: Time in seconds the LED is on for each blink
            off_time: Time in seconds the LED is off for each blink
            n: Number of blinks
            background: Whether to blink in the background
        """
        if self.verbose:
            print(f"DummyLED blink: on_time={on_time}, off_time={off_time}, n={n}, background={background}")
        
        # For background blinking, just return immediately
        if not background:
            # Only for non-background blinking: toggle the LED state n times
            for _ in range(n):
                self.on()
                time.sleep(on_time)
                self.off()
                if _ < n - 1:  # Don't sleep after the last blink
                    time.sleep(off_time)

class DummyADS:
    def __init__(self):
        self.gain = None

class DummyAnalogIn:
    def __init__(self, ads, channel, slope=19.86, intercept=0.0):
        self.ads = ads
        self.channel = channel
        self._raw_value = 0  # Internal state for raw value
        self.last_voltage = 0.0
        self.cycle_start_time = time.time()
        self.amplitude = 5.0  # mm
        self.frequency = 0.1  # Hz
        
        # These parameters are only used internally for simulation
        # They should NOT be used for calibration - that comes from config.lvdt_calibration
        self._sim_slope = 19.86  # Internal parameter for simulation only

    def _calculate_displacement(self):
        """Calculates the simulated displacement."""
        current_time = time.time()
        elapsed_time = current_time - self.cycle_start_time
        phase_shift = self.channel * (math.pi / 4)  # Adjust phase shift for each channel
        displacement = self.amplitude * math.sin(2 * math.pi * self.frequency * elapsed_time + phase_shift)
        noise = np.random.normal(0, 0.1)  # Gaussian noise with std dev 0.1mm
        displacement += noise
        return displacement

    def _update_raw_value(self):
        """Updates the internal raw value based on simulated displacement."""
        displacement = self._calculate_displacement()
        # Convert displacement to voltage using internal sim parameter
        voltage = displacement / self._sim_slope if self._sim_slope != 0 else 0.0
        simulated_raw = int((voltage * 1000.0) / 0.1875)
        self._raw_value = max(-32768, min(simulated_raw, 32767))

    @property
    def voltage(self):
        """Calculates voltage from the simulated raw value."""
        self._update_raw_value()  # Ensure raw value is current
        voltage = (self._raw_value * 0.1875) / 1000.0
        self.last_voltage = voltage
        return voltage

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
        """Return dummy LED objects."""
        return DummyLED(), DummyLED()

    def create_ads1115(self):
        """Return a dummy ADS instance."""
        dummy = DummyADS()
        dummy.gain = self.lvdt_gain
        return dummy

    def create_lvdt_channels(self, ads):
        """Create dummy LVDT channels using a cyclic mapping (simulation)."""
        channels = []
        # Use 4 dummy channels to simulate ADS1115
        dummy_channel_list = [0, 1, 2, 3]
        for i in range(self.num_lvdts):
            ch = dummy_channel_list[i % len(dummy_channel_list)]
            channels.append(DummyAnalogIn(ads, ch))
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
def leds(gpio_pins):
    return DummyLED(), DummyLED()

def ads1115():
    dummy = DummyADS()
    dummy.gain = 2.0 / 3.0
    return dummy

def thresholds(trigger_acceleration, trigger_displacement, pre_time, enable_accel, enable_lvdt):
    return {
        "acceleration": trigger_acceleration if enable_accel else None,
        "displacement": trigger_displacement if enable_lvdt else None,
        "pre_event_time": pre_time,
        "post_event_time": pre_time,
    }
