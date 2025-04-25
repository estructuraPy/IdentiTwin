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
        slopes: List of slopes (mm/V) for each LVDT.
        config: System configuration object for saving calibration data.

    Returns:
        List of dictionaries, each containing 'lvdt_slope' and 'lvdt_intercept'.
    """
    if not channels or not isinstance(channels, list):
        raise ValueError("Invalid channels input.")
        
    print(f"\nInitializing {len(channels)} LVDT channels")
    
    # Validate that slopes are provided and match the number of channels
    if slopes is None:
        raise ValueError("LVDT slopes must be provided from initialization.py")
    
    if len(slopes) < len(channels):
        raise ValueError(f"Not enough slopes provided. Need {len(channels)} slopes, but only got {len(slopes)}.")
    
    # Only use the required number of slopes
    if len(slopes) > len(channels):
        slopes = slopes[:len(channels)]

    lvdt_systems = []
    print("\nCalibrating LVDTs...")
    for i, channel in enumerate(channels):
        try:
            # Read initial voltage 
            attempts = 0
            max_attempts = 3
            voltage = None
            
            while attempts < max_attempts:
                try:
                    voltage = channel.voltage
                    break
                except Exception as read_err:
                    attempts += 1
                    print(f"   Attempt {attempts} to read LVDT-{i+1} failed: {read_err}")
                    time.sleep(0.1)
            
            if voltage is None:
                print(f" - ERROR: Failed to read voltage from LVDT-{i+1} after {max_attempts} attempts")
                lvdt_systems.append(None)
                continue
            
            slope = slopes[i]
            intercept = -slope * voltage
            print(f" - LVDT-{i+1} zeroing parameters: slope={slope:.4f}, intercept={intercept:.4f} at voltage={voltage:.4f}")
            
            # Create dictionary with calibration parameters
            lvdt_system = {
                'slope': slope,
                'intercept': intercept,
                # Add these alternative names for compatibility with different code paths
                'lvdt_slope': slope,
                'lvdt_intercept': intercept
            }
            lvdt_systems.append(lvdt_system)
            
            # Test if the calibration produces reasonable values
            test_displacement = slope * voltage + intercept
            print(f" - LVDT-{i+1} test reading: {test_displacement:.4f}mm (should be near zero)")
            
            if config:
                if not hasattr(config, 'lvdt_calibration'):
                    config.lvdt_calibration = []
                while len(config.lvdt_calibration) <= i:
                    config.lvdt_calibration.append({})
                config.lvdt_calibration[i] = lvdt_system.copy()
        except Exception as e:
            print(f"Error calibrating LVDT-{i+1}: {e}")
            # Removing default values - each sensor must be properly calibrated
            print(f"LVDT-{i+1} calibration failed. This sensor must be calibrated before use.")
            lvdt_systems.append(None)

    
    if config:
        _save_calibration_data(config, lvdt_systems=lvdt_systems)
    return lvdt_systems

def zeroing_lvdt(channel, slope, label="LVDT"):
    """
    Calibrates an LVDT to adjust for zero displacement.

    Args:
        channel: Channel object representing the LVDT.
        slope: Slope of the LVDT (mm/V).
        label: Label for the LVDT.

    Returns:
        Dictionary containing 'lvdt_slope' and 'lvdt_intercept'.
    """
    voltage = channel.voltage
    intercept = -slope * voltage
    print(f" - {label} zeroing parameters: slope={slope:.4f}, intercept={intercept:.4f} at voltage={voltage:.4f}")

    channel.calibration_slope = slope
    channel.calibration_intercept = intercept

    return {'lvdt_slope': slope, 'lvdt_intercept': intercept}

def multiple_accelerometers(mpu_list, calibration_time=2.0, config=None):
    """
    Calibrates multiple accelerometers to determine bias offsets.

    Args:
        mpu_list: List of MPU objects with a 'get_accel_data()' method.
        calibration_time: Duration (seconds) to collect samples for calibration.
        config: System configuration object for saving calibration data.

    Returns:
        List of dictionaries with keys 'x', 'y', 'z'.
    """
    if not mpu_list:
        return None
    
    print("\nCalibrating accelerometers...", flush=True)
    offsets = []
    for i, mpu in enumerate(mpu_list):
        x_samples, y_samples, z_samples = [], [], []
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
            offset = {'x': -x_avg, 'y': -y_avg, 'z': -z_avg}
            offsets.append(offset)
            label = f"Accel-{i+1}"
            print(f" - {label} offsets: X={offset['x']:.3f}, Y={offset['y']:.3f}, Z={offset['z']:.3f} (should be near GRAVITY)")
        else:
            # Removing default values - each sensor must be properly calibrated
            print(f"Warning: Could not collect data for Accelerometer-{i+1}. Calibration failed.")
            # Instead of using defaults, we'll return None for this sensor
            offsets.append(None)
    if config:
        _save_calibration_data(config, accel_offsets=offsets)
    return offsets

def calibrate_accelerometer(data, offsets):
    """
    Calibrates accelerometer data using offsets only.
    
    Args:
        data: Dictionary with 'x', 'y', 'z' acceleration values.
        offsets: Dictionary with calibration parameters.

    Returns:
        Dictionary with calibrated 'x', 'y', 'z' values.
        
    Raises:
        ValueError: If required data components or calibration parameters are missing.
        TypeError: If offsets parameter is None (uncalibrated sensor).
    """
    if offsets is None:
        raise TypeError("Cannot calibrate with None offsets. Sensor must be properly calibrated first.")
    
    calibrated_data = data.copy()
    if not all(k in data for k in ['x', 'y', 'z']):
        raise ValueError("Missing acceleration components.")
    if not all(k in offsets for k in ['x', 'y', 'z']):
        raise ValueError("Missing calibration parameters.")
    
    calibrated_data["x"] = data["x"] + offsets["x"]
    calibrated_data["y"] = data["y"] + offsets["y"]
    calibrated_data["z"] = data["z"] + offsets["z"]
    return calibrated_data

def _save_calibration_data(config, lvdt_systems=None, accel_offsets=None):
    """
    Saves calibration data to a master calibration file by appending to the existing file.

    Args:
        config: Configuration object with 'logs_dir'.
        lvdt_systems: List of LVDT calibration dictionaries (optional).
        accel_offsets: List of accelerometer calibration dictionaries (optional).

    Returns:
        Path to the calibration file or None on error.
    """
    try:
        cal_file = os.path.join(config.logs_dir, "calibration_data.txt")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        new_calibration = f"Calibration Data - {timestamp}\n" + "-" * 50 + "\n\n"
        if accel_offsets:
            new_calibration += "Accelerometer Calibration:\n" + "------------------------\n"
            for i, offset in enumerate(accel_offsets):
                new_calibration += f"Accelerometer-{i+1}:\n"
                new_calibration += f"  X-offset: {offset['x']:.6f} m/s^2\n"
                new_calibration += f"  Y-offset: {offset['y']:.6f} m/s^2\n"
                new_calibration += f"  Z-offset: {offset['z']:.6f} m/s^2\n"
            new_calibration += "\n"
        if lvdt_systems:
            new_calibration += "LVDT Calibration:\n" + "-----------------\n"
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

def calibrate_lvdt_channels(channels, slopes):
    """Calibrate each LVDT channel independently."""
    for i, (channel, slope) in enumerate(zip(channels, slopes)):
        voltage = channel.voltage
        intercept = -slope * voltage
        print(f" - LVDT-{i+1} zeroing parameters: slope={slope:.4f}, intercept={intercept:.4f} at voltage={voltage:.4f}")
        channel.set_calibration(slope, intercept)  # Almacenar la calibración en el canal
    return channels