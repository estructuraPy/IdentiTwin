"""
Configuration management module for the  monitoring system.

This module handles system-wide configuration including:
- Hardware setup and initialization
- Sampling rates and timing parameters
- Event detection thresholds
- Data storage paths and organization
- Sensor calibration parameters
- System operational modes

Key Features:
- Dynamic configuration based on available hardware
- Automatic directory structure creation
- LED indicator management
- ADC (ADS1115) configuration for LVDT sensors
- MPU6050 accelerometer setup
- Comprehensive parameter validation
"""

import os
import platform
from datetime import datetime
import time
import numpy as np

try:
    from gpiozero import LED
    import adafruit_ads1x15.ads1115 as ADS
    import board
    import busio
    from adafruit_ads1x15.analog_in import AnalogIn
    from mpu6050 import mpu6050
except (ImportError, NotImplementedError):
    LED = None
    ADS = None
    board = None
    busio = None
    AnalogIn = None
    mpu6050 = None

print(f"Platform: {platform.system()} {platform.release()}")


class SystemConfig:
    """Configuration class for the monitoring system."""

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
        Initializes the system configuration.

        Args:
            enable_lvdt: Enables LVDT measurements.
            enable_accel: Enables accelerometer measurements.
            output_dir: Base directory for output files.
            num_lvdts: Number of LVDT channels.
            num_accelerometers: Number of accelerometers.
            sampling_rate_acceleration: Sampling rate for accelerometers (Hz).
            sampling_rate_lvdt: Sampling rate for LVDTs (Hz).
            plot_refresh_rate: Refresh rate for plots (Hz).
            gpio_pins: List of GPIO pins for LEDs.
            trigger_acceleration_threshold: Acceleration threshold for event detection (m/s^2).
            detrigger_acceleration_threshold: Acceleration threshold for de-triggering (m/s^2).
            trigger_displacement_threshold: Displacement threshold for event detection (mm).
            detrigger_displacement_threshold: Displacement threshold for de-triggering (mm).
            pre_trigger_time: Time (s) before trigger to include in event.
            post_trigger_time: Time (s) after trigger to include in event.
            min_event_duration: Minimum duration (s) of an event.
        """

        # Set output directory and create necessary directories
        self.output_dir = output_dir
        if self.output_dir is None:
            today = datetime.now().strftime("%Y%m%d")
            self.output_dir = os.path.join("repository", today)

        os.makedirs(self.output_dir, exist_ok=True)

        self.events_dir = os.path.join(self.output_dir, "events")
        self.logs_dir = os.path.join(self.output_dir, "logs")
        self.reports_dir = os.path.join(self.output_dir, "reports")

        for directory in [self.events_dir, self.logs_dir, self.reports_dir]:
            os.makedirs(directory, exist_ok=True)

        self.acceleration_file = os.path.join(self.output_dir, "acceleration.csv")
        self.displacement_file = os.path.join(self.output_dir, "displacement.csv")
        self.general_file = os.path.join(self.output_dir, "general_measurements.csv")

        # Performance monitoring
        self.enable_performance_monitoring = True
        self.performance_log_file = os.path.join(self.logs_dir, "performance_log.csv")

        # Sensor configuration
        self.enable_lvdt = enable_lvdt
        self.enable_accel = enable_accel
        self.num_lvdts = num_lvdts
        self.num_accelerometers = num_accelerometers

        # Sampling rates
        self.sampling_rate_acceleration = sampling_rate_acceleration
        self.sampling_rate_lvdt = sampling_rate_lvdt
        self.plot_refresh_rate = plot_refresh_rate

        # Derived time values
        self.time_step_acceleration = 1.0 / self.sampling_rate_acceleration
        self.time_step_lvdt = 1.0 / self.sampling_rate_lvdt
        self.time_step_plot_refresh = 1.0 / self.plot_refresh_rate

        self.window_duration = 5  # seconds
        self.gravity = 9.81  # m/s^2

        # Jitter
        self.max_accel_jitter = 1.5  # 1.5ms maximum jitter
        self.max_lvdt_jitter = 5.0  # 5ms maximum jitter

        # Thresholds
        self.trigger_acceleration_threshold = (
            trigger_acceleration_threshold if trigger_acceleration_threshold is not None
            else 0.3 * self.gravity
        )
        self.trigger_displacement_threshold = (
            trigger_displacement_threshold if trigger_displacement_threshold is not None
            else 1.0
        )

        self.detrigger_acceleration_threshold = (
            detrigger_acceleration_threshold if detrigger_acceleration_threshold is not None
            else self.trigger_acceleration_threshold * 0.5
        )
        self.detrigger_displacement_threshold = (
            detrigger_displacement_threshold if detrigger_displacement_threshold is not None
            else self.trigger_displacement_threshold * 0.5
        )

        # Event detection parameters
        self.pre_trigger_time = pre_trigger_time
        self.post_trigger_time = post_trigger_time
        self.min_event_duration = min_event_duration

        # LVDT configuration
        self.lvdt_gain = 2.0 / 3.0  # ADC gain (+-6.144V)
        self.lvdt_scale_factor = 0.1875  # Constant for voltage conversion (mV)
        self.lvdt_slope = 19.86  # Default slope in mm/V
        self.lvdt_intercept = 0.0  # Default intercept

        # Accelerometer configuration
        self.accel_offsets = [
            {"x": 0.0, "y": 0.0, "z": 0.0},  # Offsets for accelerometer 1
            {"x": 0.0, "y": 0.0, "z": 0.0},  # Offsets for accelerometer 2
        ]

        # LED configuration
        self.gpio_pins = gpio_pins if gpio_pins is not None else [18, 17]

        # Warn on rate limits
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

    def initialize_thresholds(self):
        """
        Initializes the thresholds for event detection.

        Returns:
            A dictionary containing the threshold values for acceleration, displacement,
            pre-event time, post-event time, and minimum event duration.
        """
        thresholds = {
            "acceleration": self.trigger_acceleration_threshold if self.enable_accel else None,
            "displacement": self.trigger_displacement_threshold if self.enable_lvdt else None,
            "pre_event_time": self.pre_trigger_time,
            "post_event_time": self.post_trigger_time,
            "min_event_duration": self.min_event_duration,
        }
        return thresholds

    def initialize_leds(self):
        """
        Initializes LED indicators for Raspberry Pi hardware.

        Returns:
            A tuple containing the status LED and activity LED objects, or (None, None) if LED initialization fails.
        """
        if LED is None:
            return None, None
        try:
            status_led = LED(self.gpio_pins[0])
            activity_led = LED(self.gpio_pins[1])
            status_led.off()
            activity_led.off()
            return status_led, activity_led
        except Exception as e:
            print(f"Warning: Could not initialize LEDs: {e}")
            return None, None

    def create_ads1115(self):
        """
        Create and return an ADS1115 ADC object.

        Returns:
            An ADS1115 object if successful, otherwise None.
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
        Create LVDT channels using the provided ADS1115 object.

        Args:
            ads: The ADS1115 object.

        Returns:
            A list of AnalogIn objects representing the LVDT channels, or None if an error occurs.
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
        Create and return MPU6050 accelerometer objects.

        Returns:
            A list of MPU6050 objects, or None if an error occurs.
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


# Utility functions (moved outside class for clarity)
def leds(gpio_pins):
    """
    Initializes LEDs connected to the specified GPIO pins.

    Args:
        gpio_pins: A list containing the GPIO pins for the LEDs.

    Returns:
        A tuple containing the LED objects for the status and activity LEDs, or (None, None) if an error occurs.
    """
    try:
        return LED(gpio_pins[0]), LED(gpio_pins[1])
    except Exception as e:
        print(f"Warning: Could not initialize LEDs: {e}")
        return None, None


def ads1115():
    """
    Initializes the ADS1115 ADC.

    Returns:
        An ADS1115 object if successful, otherwise None.
    """
    try:
        i2c = busio.I2C(board.SCL, board.SDA)
        ads = ADS.ADS1115(i2c)
        ads.gain = 2.0 / 3.0  # Adjust gain as needed
        return ads
    except Exception as e:
        print(f"Error initializing ADS1115: {e}")
        return None


def thresholds(trigger_acceleration, trigger_displacement, pre_time, enable_accel, enable_lvdt):
    """
    Initializes thresholds for event detection.

    Args:
        trigger_acceleration: The acceleration trigger threshold.
        trigger_displacement: The displacement trigger threshold.
        pre_time: The pre-trigger time.
        enable_accel: Whether acceleration measurements are enabled.
        enable_lvdt: Whether LVDT measurements are enabled.

    Returns:
        A dictionary containing the threshold values.
    """
    return {
        "acceleration": trigger_acceleration if enable_accel else None,
        "displacement": trigger_displacement if enable_lvdt else None,
        "pre_event_time": pre_time,
        "post_event_time": pre_time,
    }