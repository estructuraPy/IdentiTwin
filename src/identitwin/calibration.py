"""
Calibration module for sensors in the IdentiTwin monitoring system.

This module provides functionality for calibrating and initializing various sensors:
- LVDT (Linear Variable Differential Transformer) displacement sensors
- Accelerometers (MPU6050)

The module handles:
- Zero-point calibration for LVDTs
- Accelerometer bias and scale factor calibration
- Calibration data persistence and loading
- Multi-sensor calibration procedures

Key Features:
- Automatic zero-point detection for LVDTs
- Multiple sensor support with individual calibration parameters
- Calibration data logging with timestamps
- Error handling and validation
"""

import time
import os
import numpy as np
from datetime import datetime  # Add this import



def initialize_lvdt(channels, slopes=None, config=None):
    """
    Initializes LVDT systems with calibration parameters.
    Units: slope in mm/V, intercept in mm

    Args:
        channels: List of channel objects representing LVDTs. Each channel must have a 'voltage' attribute.
        slopes: List of slopes for each LVDT. If not provided, a default slope of 19.86 mm/V is used.

    Returns:
        List of dictionaries, each with slope and intercept.
    """
    if not channels or not isinstance(channels, list):
        raise ValueError("Invalid channels input.")

    lvdt_systems = []
    print("Calibrating LVDTs", flush=True)

    for i, channel in enumerate(channels):
        try:
            # Use the provided slope or default to 19.86 mm/V
            slope = slopes[i]
            lvdt_system = zeroing_lvdt(channel, slope, label=f"LVDT-{i+1}")
            lvdt_systems.append(lvdt_system)
        except Exception as e:
            print(f"Error calibrating LVDT-{i+1}: {e}")
            raise

    if config:
        _save_calibration_data(config, lvdt_systems=lvdt_systems)

    return lvdt_systems


def zeroing_lvdt(channel, slope, label="LVDT"):
    """Calibrate LVDT to adjust zero displacement."""
    
    # Read the initial voltage
    voltage = channel.voltage
    
    # Calculate intercept to zero displacement
    intercept = -slope * voltage
    print(f" - {label} zeroing parameters: slope={slope:.4f}, intercept={intercept:.4f} at voltage={voltage:.4f}")
    
    # Return calibrated system
    return {
        'lvdt_slope': slope,
        'lvdt_intercept': intercept
    }


def multiple_accelerometers(mpu_list, calibration_time=2.0, config=None):
    """
    Calibrates multiple accelerometers.
    Returns bias offsets and scaling factors so that each axis reads near zero at rest.

    Args:
        mpu_list: List of MPU objects with 'get_accel_data()' method.
        calibration_time: Duration in seconds to collect samples.

    Returns:
        List of dictionaries per MPU: {'x': ..., 'y': ..., 'z': ..., 'scaling_factor': ...}.
        Subsequent accelerometer readings should be modified by the scaling factor.
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
            # Calculate average values for each axis
            x_avg = np.mean(x_samples)
            y_avg = np.mean(y_samples)
            z_avg = np.mean(z_samples)

            # Calculate the magnitude of the average acceleration
            magnitude = np.sqrt(x_avg**2 + y_avg**2 + z_avg**2)

            # Calculate the scaling factor to adjust the magnitude to gravity
            scaling_factor = GRAVITY / magnitude

            # Use the measured averages as offsets and scale them
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
    """Save calibration data to a master calibration file."""
    try:
        cal_file = os.path.join(config.logs_dir, "calibration_data.txt")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Create new calibration content with timestamp header
        new_calibration = f"Calibration Data - {timestamp}\n"
        new_calibration += "-" * 50 + "\n\n"
        
        # Add accelerometer data first
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
        
        # Then add LVDT data
        if lvdt_systems:
            new_calibration += "LVDT Calibration:\n"
            new_calibration += "-----------------\n"
            for i, lvdt in enumerate(lvdt_systems):
                new_calibration += f"LVDT-{i+1}:\n"
                new_calibration += f"  Slope: {lvdt['lvdt_slope']:.6f} mm/V\n"
                new_calibration += f"  Intercept: {lvdt['lvdt_intercept']:.6f} mm\n"
            new_calibration += "\n"

        # Read and write calibration data
        existing_calibrations = ""
        if os.path.exists(cal_file):
            with open(cal_file, 'r') as f:
                existing_calibrations = f.read()

        with open(cal_file, 'w') as f:
            f.write(new_calibration)  # Write new calibration with timestamp
            if existing_calibrations:
                f.write("-" * 50 + "\n\n")  # Simple separator
                f.write(existing_calibrations)
                
        print(f"\nCalibration data saved to: {cal_file}\n")
        return cal_file
    except Exception as e:
        print(f"\nError saving calibration data: {e}\n")
        return None
