"""
Sensor Calibration Module for IdentiTwin.

Provides functions to perform calibration routines for LVDT and accelerometer
sensors. This typically involves determining zero-point offsets (intercepts) for
LVDTs and bias offsets and scaling factors for accelerometers. Calibration data
can be saved to a log file.

Key Features:
- LVDT zeroing based on current voltage reading and known slope.
- Accelerometer calibration by averaging readings over time to find biases
  relative to gravity and calculate a scaling factor.
- Support for calibrating multiple sensors of each type.
- Saving of calibration parameters (slopes, intercepts, offsets, scaling factors)
  to a persistent log file with timestamps.
"""

import time
import os
from datetime import datetime
import numpy as np


def initialize_lvdt(channels, slopes=None, config=None):
    """
    Initializes and calibrates multiple LVDT sensors by determining their zero intercept.

    Iterates through the provided LVDT channels, performs zeroing calibration
    using `zeroing_lvdt` for each, and optionally saves the results using the
    provided config object.

    Args:
        channels (list): A list of LVDT channel objects, each expected to have a
                         `.voltage` attribute or method returning the current voltage.
        slopes (list, optional): A list of calibration slopes (mm/V) corresponding
                                 to each channel. If None, a default slope (19.86)
                                 is used for all channels. Defaults to None.
        config (SystemConfig, optional): The system configuration object. If provided,
                                         calibration data will be saved via `_save_calibration_data`.
                                         Defaults to None.

    Returns:
        list: A list of dictionaries. Each dictionary contains the calibration
              parameters ('lvdt_slope', 'lvdt_intercept') for a corresponding LVDT.

    Raises:
        ValueError: If `channels` input is invalid (e.g., not a list).
        Exception: Propagates exceptions occurring during individual LVDT calibration.
    """
    if not channels or not isinstance(channels, list):
        raise ValueError("Invalid channels input.")

    lvdt_systems = []
    print("Calibrating LVDTs", flush=True)

    for i, channel in enumerate(channels):
        try:
            slope = slopes[i] if slopes else 19.86
            lvdt_system = zeroing_lvdt(channel, slope, label=f"LVDT-{i+1}")
            lvdt_systems.append(lvdt_system)
        except Exception as e:
            print(f"Error calibrating LVDT-{i+1}: {e}")
            raise

    if config:
        _save_calibration_data(config, lvdt_systems=lvdt_systems)

    return lvdt_systems


def zeroing_lvdt(channel, slope, label="LVDT"):
    """
    Performs zero-point calibration for a single LVDT sensor.

    Reads the current voltage from the channel and calculates the intercept required
    to make the current reading correspond to zero displacement, based on the provided slope.

    Args:
        channel: An LVDT channel object with a `.voltage` attribute/method.
        slope (float): The calibration slope of the LVDT sensor in mm/V.
        label (str): A descriptive label for the LVDT used in print messages.
                     Defaults to "LVDT".

    Returns:
        dict: A dictionary containing the calculated 'lvdt_slope' (passed-through)
              and 'lvdt_intercept' (calculated).

    Assumptions:
        - The LVDT is physically at its zero displacement position when this function is called.
    """
    voltage = channel.voltage
    intercept = -slope * voltage

    print(f" - {label} zeroing parameters: slope={slope:.4f}, intercept={intercept:.4f} at voltage={voltage:.4f}")

    return {
        'lvdt_slope': slope,
        'lvdt_intercept': intercept
    }


def multiple_accelerometers(mpu_list, calibration_time=2.0, config=None):
    """
    Calibrates multiple MPU6050 accelerometers to determine bias offsets and scaling factors.

    For each accelerometer, collects data for a specified duration, calculates the
    average readings for X, Y, and Z axes. Assumes the sensor is stationary and
    calculates bias offsets (negated averages) and a scaling factor to make the
    magnitude of the average readings equal to standard gravity (GRAVITY).

    Args:
        mpu_list (list): A list of MPU6050 sensor objects, each expected to have a
                         `get_accel_data()` method returning {'x': ..., 'y': ..., 'z': ...}.
        calibration_time (float): The duration in seconds to collect data for averaging.
                                  Defaults to 2.0.
        config (SystemConfig, optional): The system configuration object. If provided,
                                         calibration data will be saved. Defaults to None.

    Returns:
        list or None: A list of dictionaries, each containing the calibration offsets
                      ('x', 'y', 'z') and 'scaling_factor' for a corresponding
                      accelerometer. Returns None if `mpu_list` is empty. Returns default
                      offsets/scaling (0.0/1.0) for sensors where reading fails.

    Assumptions:
        - Each accelerometer is stationary and oriented such that the gravity vector
          is measurable during the calibration period.
    """
    if not mpu_list:
        return None

    offsets = []
    GRAVITY = 9.80665  # Standard gravity in m/s^2

    for i, mpu in enumerate(mpu_list):
        x_samples = []
        y_samples = []
        z_samples = []

        end_time = time.time() + calibration_time
        while time.time() < end_time:
            try:
                data = mpu.get_accel_data()
                x_samples.append(data['x'])
                y_samples.append(data['y'])
                z_samples.append(data['z'])
                time.sleep(0.01)
            except Exception:
                continue

        if x_samples:
            x_avg = np.mean(x_samples)
            y_avg = np.mean(y_samples)
            z_avg = np.mean(z_samples)

            magnitude = np.sqrt(x_avg**2 + y_avg**2 + z_avg**2)
            scaling_factor = GRAVITY / magnitude

            offset = {
                'x': -x_avg,
                'y': -y_avg,
                'z': -z_avg,
                'scaling_factor': scaling_factor
            }
            offsets.append(offset)
            label = f"Accelerometer-{i+1}"
            print(f" - {label} scaling factor: {scaling_factor:.3f}")
            print(f" - {label} zeroing calibrated offsets: X={offset['x']:.3f}, Y={offset['y']:.3f}, Z={offset['z']:.3f}")
        else:
            offsets.append({'x': 0.0, 'y': 0.0, 'z': 0.0, 'scaling_factor': 1.0})

    if config:
        _save_calibration_data(config, accel_offsets=offsets)

    return offsets


def _save_calibration_data(config, lvdt_systems=None, accel_offsets=None):
    """
    Saves LVDT and/or accelerometer calibration data to a log file.

    Appends the new calibration parameters (slopes, intercepts, offsets, scaling factors)
    with a timestamp to the beginning of the master calibration file specified in the config.
    Existing content in the file is preserved below the new entry.

    Args:
        config: The system configuration object, expected to have a `logs_dir` attribute.
        lvdt_systems (list, optional): A list of LVDT calibration dictionaries
                                       (output from `initialize_lvdt`). Defaults to None.
        accel_offsets (list, optional): A list of accelerometer calibration dictionaries
                                        (output from `multiple_accelerometers`). Defaults to None.

    Returns:
        str or None: The path to the calibration file if saving was successful,
                     otherwise None.

    Side Effects:
        - Creates or modifies the 'calibration_data.txt' file in the `config.logs_dir`.
        - Prints success or error messages to the console.
    """
    try:
        cal_file = os.path.join(config.logs_dir, "calibration_data.txt")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        new_calibration = f"Calibration Data - {timestamp}\n"
        new_calibration += "-" * 50 + "\n\n"

        if accel_offsets:
            new_calibration += "Accelerometer Calibration:\n"
            new_calibration += "------------------------\n"
            for i, offset in enumerate(accel_offsets):
                new_calibration += f"Accelerometer-{i+1}:\n"
                new_calibration += f"  X-offset: {offset['x']:.6f} m/s^2\n"
                new_calibration += f"  Y-offset: {offset['y']:.6f} m/s^2\n"
                new_calibration += f"  Z-offset: {offset['z']:.6f} m/s^2\n"
                new_calibration += f"  Scaling factor: {offset['scaling_factor']:.6f}\n"
            new_calibration += "\n"

        if lvdt_systems:
            new_calibration += "LVDT Calibration:\n"
            new_calibration += "-----------------\n"
            for i, lvdt in enumerate(lvdt_systems):
                new_calibration += f"LVDT-{i+1}:\n"
                new_calibration += f"  Slope: {lvdt['lvdt_slope']:.6f} mm/V\n"
                new_calibration += f"  Intercept: {lvdt['lvdt_intercept']:.6f} mm\n"
            new_calibration += "\n"

        existing_calibrations = ""
        if os.path.exists(cal_file):
            with open(cal_file, 'r') as f:
                existing_calibrations = f.read()

        with open(cal_file, 'w') as f:
            f.write(new_calibration)
            if existing_calibrations:
                f.write("-" * 50 + "\n\n")
                f.write(existing_calibrations)

        print(f"\nCalibration data saved to: {cal_file}\n")
        return cal_file
    except Exception as e:
        print(f"\nError saving calibration data: {e}\n")
        return None