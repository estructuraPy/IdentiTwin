"""
Calibration module for sensors in the IdentiTwin monitoring system.

This module provides functionality for calibrating and initializing various sensors:
- LVDT (Linear Variable Differential Transformer) displacement sensors
- Accelerometers (MPU6050)

Key Features:
- Automatic zero-point detection for LVDTs
- Multiple sensor support with individual calibration parameters
- Calibration data logging with timestamps
- Error handling and validation
"""

import time
import os
from datetime import datetime
import numpy as np


def initialize_lvdt(channels, slopes=None, config=None):
    """
    Initializes LVDT systems with calibration parameters.

    Args:
        channels: List of LVDT channel objects with a 'voltage' attribute.
        slopes: List of slopes (mm/V) for each LVDT. Defaults to 19.86 mm/V if not provided.
        config: System configuration object for saving calibration data.

    Returns:
        List of dictionaries, each containing 'lvdt_slope' and 'lvdt_intercept'.

    Assumptions:
        - Each channel object in 'channels' has a 'voltage' attribute representing the current voltage reading.
        - LVDT slopes are provided in mm/V, and the intercept is calculated in mm.
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
            
            # Store calibration in config object
            if config:
                if not hasattr(config, 'lvdt_calibration'):
                    config.lvdt_calibration = []
                while len(config.lvdt_calibration) <= i:
                    config.lvdt_calibration.append({})
                config.lvdt_calibration[i] = lvdt_system.copy()
                
        except Exception as e:
            print(f"Error calibrating LVDT-{i+1}: {e}")
            raise

    if config:
        _save_calibration_data(config, lvdt_systems=lvdt_systems)

    return lvdt_systems


def zeroing_lvdt(channel, slope, label="LVDT"):
    """
    Calibrates an LVDT to adjust for zero displacement.

    Args:
        channel: Channel object representing the LVDT.
        slope: Slope of the LVDT (mm/V).
        label: Label for the LVDT (e.g., "LVDT-1").

    Returns:
        Dictionary containing 'lvdt_slope' and 'lvdt_intercept'.

    Assumptions:
        - The 'channel' object has a 'voltage' attribute.
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
    Calibrates multiple accelerometers to determine bias offsets and scaling factors.

    Args:
        mpu_list: List of MPU objects with a 'get_accel_data()' method.
        calibration_time: Duration (seconds) to collect samples for calibration. Defaults to 2.0 seconds.
        config: System configuration object for saving calibration data.

    Returns:
        List of dictionaries, each containing 'x', 'y', 'z' (bias offsets), and 'scaling_factor'.

    Assumptions:
        - Each MPU object in 'mpu_list' has a 'get_accel_data()' method returning a dictionary with 'x', 'y', 'z' values.
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


def calibrate_accelerometer(data, offsets):
    """
    Calibrate accelerometer data using offsets and scaling factor.
    
    Args:
        data: Dictionary containing x, y, z acceleration values.
        offsets: Dictionary containing x, y, z offset values and scaling_factor.
        
    Returns:
        Dictionary with calibrated x, y, z values.
    """
    try:
        # Make a copy of the input data to avoid modifying the original
        calibrated_data = data.copy()
        
        # Validate input data
        if not all(k in data for k in ['x', 'y', 'z']):
            raise ValueError("Missing acceleration components in input data")
            
        if not all(k in offsets for k in ['x', 'y', 'z', 'scaling_factor']):
            raise ValueError("Missing calibration parameters")
            
        # Apply calibration - using provided scaling factor
        scaling_factor = offsets["scaling_factor"]
        calibrated_data["x"] = (data["x"] + offsets["x"]) * scaling_factor
        calibrated_data["y"] = (data["y"] + offsets["y"]) * scaling_factor
        calibrated_data["z"] = (data["z"] + offsets["z"]) * scaling_factor
        
        return calibrated_data
        
    except Exception as e:
        print(f"Warning: Error in accelerometer calibration: {e}")
        # Return zero values on error to avoid crashes
        return {"x": 0.0, "y": 0.0, "z": 0.0}


def _save_calibration_data(config, lvdt_systems=None, accel_offsets=None):
    """
    Saves calibration data to a master calibration file, appending new data to the existing file.

    Args:
        config: System configuration object containing the 'logs_dir' attribute.
        lvdt_systems: List of LVDT calibration dictionaries (optional).
        accel_offsets: List of accelerometer calibration dictionaries (optional).

    Returns:
        The path to the calibration file, or None if an error occurred.

    Assumptions:
        - The 'config' object has a 'logs_dir' attribute specifying the directory to save the calibration file.
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