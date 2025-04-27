# Refactored Code:

import time
import os
from datetime import datetime
import numpy as np
from typing import List, Dict, Optional

# Potential Improvement: Consider using Python's logging module instead of print
# for better control over output levels and destinations.

"""Calibration module for IdentiTwin sensors (LVDT and Accelerometer).

Provides functions to:
    - Initialize LVDT sensors by determining zero-point intercepts based on
      initial voltage readings and provided slopes.
    - Calibrate multiple accelerometers (MPU6050) by calculating bias offsets
      while assuming they are stationary.
    - Apply calculated offsets to raw accelerometer data.
    - Save calibration results (LVDT intercepts, accelerometer offsets) to a
      log file.
"""


def initialize_lvdt(channels: list[object], slopes: list[float] = None, config: object = None) -> List[Optional[Dict]]:
    """Initializes LVDT sensors and determines zero-point intercepts.

    Reads the initial voltage from each LVDT channel and calculates the
    intercept required to make this reading correspond to zero displacement,
    given the provided sensitivity slope. Stores the calibration parameters
    (slope and intercept) in the `config` object if provided, and saves them
    to a log file.

    Args:
        channels (list[object]): A list of LVDT channel objects (e.g., `AnalogIn`).
            Each object must have a readable `voltage` attribute.
        slopes (list[float], optional): A list of sensitivity slopes (e.g., mm/V)
            corresponding to each LVDT channel. Must be provided if `config` is None
            or doesn't contain slopes. Defaults to None.
        config (object, optional): The system configuration object. If provided,
            calibration data (`slope`, `intercept`) is stored in its
            `lvdt_calibration` attribute and saved via `_save_calibration_data`.
            Defaults to None.

    Returns:
        List[Optional[Dict]]: A list where each element is a dictionary
        containing the 'slope' and 'intercept' for a successfully calibrated
        LVDT, or None if calibration failed for that channel.

    Raises:
        ValueError: If `channels` is invalid, or if `slopes` are required but
                    not provided or have insufficient length.
    """
    if not channels or not isinstance(channels, list):
        raise ValueError("Invalid channels input: Must be a non-empty list.")

    print(f"\nInitializing {len(channels)} LVDT channels")

    if slopes is None:
        raise ValueError("LVDT slopes must be provided.")

    if len(slopes) < len(channels):
        raise ValueError(f"Insufficient slopes provided. Need {len(channels)}, got {len(slopes)}.")

    # Use only the required number of slopes if more are provided
    cal_slopes = slopes[:len(channels)]

    lvdt_systems = []
    print("\nCalibrating LVDTs...")
    for i, channel in enumerate(channels):
        lvdt_label = f"LVDT-{i+1}"
        try:
            attempts = 0
            max_attempts = 3
            voltage = None

            while attempts < max_attempts:
                try:
                    voltage = channel.voltage
                    break
                except Exception as read_err:
                    attempts += 1
                    print(f"   Attempt {attempts} to read {lvdt_label} failed: {read_err}")
                    time.sleep(0.1)

            if voltage is None:
                print(f" - ERROR: Failed to read voltage from {lvdt_label} after {max_attempts} attempts.")
                lvdt_systems.append(None)
                continue

            slope = cal_slopes[i]
            # Calculate intercept to zero the sensor at the current voltage
            intercept = -slope * voltage
            print(f" - {lvdt_label} zeroing parameters: slope={slope:.4f}, intercept={intercept:.4f} at voltage={voltage:.4f}")

            # Store calibration parameters
            # Includes alternative names for backward compatibility or different use cases.
            lvdt_system = {
                'slope': slope,
                'intercept': intercept,
                'lvdt_slope': slope,
                'lvdt_intercept': intercept
            }
            lvdt_systems.append(lvdt_system)

            test_displacement = slope * voltage + intercept
            print(f" - {lvdt_label} test reading: {test_displacement:.4f} mm (should be near zero)")

            if config:
                if not hasattr(config, 'lvdt_calibration'):
                    config.lvdt_calibration = []
                # Ensure the list is long enough
                while len(config.lvdt_calibration) <= i:
                    config.lvdt_calibration.append({})
                config.lvdt_calibration[i] = lvdt_system.copy()

        except Exception as e:
            print(f"Error calibrating {lvdt_label}: {e}")
            # Each sensor must be properly calibrated; None indicates failure.
            print(f"{lvdt_label} calibration failed. This sensor must be calibrated before use.")
            lvdt_systems.append(None)
            if config and hasattr(config, 'lvdt_calibration') and len(config.lvdt_calibration) > i:
                 config.lvdt_calibration[i] = None # Mark as failed in config too

    if config:
        _save_calibration_data(config, lvdt_systems=lvdt_systems)

    return lvdt_systems


def zeroing_lvdt(channel: object, slope: float, label: str = "LVDT") -> Dict:
    """Calculates LVDT intercept to zero displacement at the current reading.

    Reads the current voltage and calculates the intercept needed to achieve
    zero displacement output. Optionally updates the channel object directly.

    Args:
        channel (object): The LVDT channel object (must have `.voltage` attribute).
        slope (float): The sensitivity slope of the LVDT (e.g., mm/V).
        label (str, optional): A descriptive label for logging. Defaults to "LVDT".

    Returns:
        Dict: A dictionary containing {'lvdt_slope': slope, 'lvdt_intercept': intercept}.

    Note:
        Directly setting `calibration_slope` and `calibration_intercept` on the
        `channel` object depends on the object's implementation.
    """
    voltage = channel.voltage
    intercept = -slope * voltage
    print(f" - {label} zeroing parameters: slope={slope:.4f}, intercept={intercept:.4f} at voltage={voltage:.4f}")

    # Update channel object directly (if supported by the object's design)
    # Potential Improvement: This direct attribute setting might violate
    # encapsulation. Consider returning values and letting the caller update.
    channel.calibration_slope = slope
    channel.calibration_intercept = intercept

    return {'lvdt_slope': slope, 'lvdt_intercept': intercept}


def multiple_accelerometers(mpu_list: list[object], calibration_time: float = 2.0, config: object = None) -> List[Optional[Dict]]:
    """Calibrates multiple accelerometers by calculating bias offsets.

    Assumes sensors are stationary. Collects data for `calibration_time`,
    averages readings for each axis (X, Y, Z), and calculates the offset
    required to zero the output (or center around gravity). Stores offsets
    in the `config` object if provided and saves them to a log file.

    Args:
        mpu_list (list[object]): A list of MPU (accelerometer) objects. Each must
            have a `get_accel_data()` method returning {'x', 'y', 'z'}.
        calibration_time (float, optional): Duration (seconds) to collect data
            for averaging. Defaults to 2.0.
        config (object, optional): The system configuration object. If provided,
            offsets are stored in its `accel_offsets` attribute and saved via
            `_save_calibration_data`. Defaults to None.

    Returns:
        List[Optional[Dict]]: A list where each element is a dictionary
        containing the offsets {'x', 'y', 'z'} for a successfully calibrated
        accelerometer, or None if calibration failed for that sensor.
    """
    if not mpu_list:
        print("Warning: No MPU objects provided for accelerometer calibration.")
        return []

    print(f"\nCalibrating {len(mpu_list)} accelerometers...", flush=True)
    offsets = []
    for i, mpu in enumerate(mpu_list):
        accel_label = f"Accel-{i+1}"
        x_samples, y_samples, z_samples = [], [], []
        end_time = time.time() + calibration_time
        sample_count = 0
        fail_count = 0
        max_fail_streak = 10 # Allow some intermittent read failures

        print(f" - Collecting data for {accel_label} for {calibration_time:.1f} seconds...")
        while time.time() < end_time:
            try:
                data = mpu.get_accel_data()
                if data and 'x' in data and 'y' in data and 'z' in data:
                    x_samples.append(data['x'])
                    y_samples.append(data['y'])
                    z_samples.append(data['z'])
                    sample_count += 1
                    fail_count = 0 # Reset fail count on success
                else:
                     fail_count += 1
                     print(f"   Warning: Invalid data received from {accel_label}")
                # Prevent busy-waiting and allow sensor time
                time.sleep(0.01)
            except Exception as read_err:
                fail_count += 1
                # Log only occasional errors to avoid flooding console
                if fail_count % 5 == 0:
                     print(f"   Warning: Read error from {accel_label}: {read_err}")
                if fail_count > max_fail_streak:
                    print(f" - ERROR: Too many consecutive read errors for {accel_label}. Aborting calibration for this sensor.")
                    break # Exit inner while loop for this sensor
                time.sleep(0.02) # Longer sleep after error

        if sample_count > 0 and fail_count <= max_fail_streak : # Check if loop exited normally and got data
            x_avg = np.mean(x_samples)
            y_avg = np.mean(y_samples)
            z_avg = np.mean(z_samples)
            # Offset is the negative of the average reading during stationary period
            offset = {'x': -x_avg, 'y': -y_avg, 'z': -z_avg}
            offsets.append(offset)
            print(f" - {accel_label} collected {sample_count} samples.")
            print(f" - {accel_label} average readings: X={x_avg:.3f}, Y={y_avg:.3f}, Z={z_avg:.3f}")
            print(f" - {accel_label} calculated offsets: X={offset['x']:.3f}, Y={offset['y']:.3f}, Z={offset['z']:.3f}")
        else:
            # Each sensor must be properly calibrated; None indicates failure.
            print(f"Warning: Could not collect sufficient data for {accel_label}. Calibration failed.")
            offsets.append(None)
            if config and hasattr(config, 'accel_offsets') and len(config.accel_offsets) > i:
                 config.accel_offsets[i] = None # Mark as failed in config

    if config:
        # Ensure the attribute exists and is the correct length before saving
        if not hasattr(config, 'accel_offsets'):
            config.accel_offsets = [None] * len(mpu_list)
        elif len(config.accel_offsets) < len(mpu_list):
             config.accel_offsets.extend([None] * (len(mpu_list) - len(config.accel_offsets)))

        for i, offset_data in enumerate(offsets):
             if i < len(config.accel_offsets):
                 config.accel_offsets[i] = offset_data

        _save_calibration_data(config, accel_offsets=offsets) # Save the results

    return offsets


def calibrate_accelerometer(data: dict, offsets: Optional[Dict]) -> dict:
    """Applies pre-calculated bias offsets to raw accelerometer data.

    Args:
        data (dict): Raw acceleration readings {'x': float, 'y': float, 'z': float}.
        offsets (Optional[Dict]): Bias offsets {'x': float, 'y': float, 'z': float}
            obtained from `multiple_accelerometers`. If None, calibration failed.

    Returns:
        dict: Calibrated acceleration values {'x': float, 'y': float, 'z': float}.

    Raises:
        ValueError: If `data` or `offsets` dictionaries are missing required keys.
        TypeError: If `offsets` is None, indicating prior calibration failure.
    """
    if offsets is None:
        raise TypeError("Cannot calibrate with None offsets. Sensor calibration may have failed.")

    if not isinstance(data, dict) or not all(k in data for k in ['x', 'y', 'z']):
        raise ValueError("Invalid input data: Must be a dict with 'x', 'y', 'z' keys.")
    if not isinstance(offsets, dict) or not all(k in offsets for k in ['x', 'y', 'z']):
        raise ValueError("Invalid offsets: Must be a dict with 'x', 'y', 'z' keys.")

    calibrated_data = data.copy()
    calibrated_data["x"] = data["x"] + offsets["x"]
    calibrated_data["y"] = data["y"] + offsets["y"]
    calibrated_data["z"] = data["z"] + offsets["z"]
    return calibrated_data


def _save_calibration_data(config: object, lvdt_systems: Optional[List[Optional[Dict]]] = None, accel_offsets: Optional[List[Optional[Dict]]] = None) -> Optional[str]:
    """Saves LVDT and/or accelerometer calibration data to a log file.

    Appends the results of the current calibration session (timestamped) to the
    beginning of the `calibration_log.txt` file located in the `config.logs_dir`.

    Args:
        config (object): Configuration object with a `logs_dir` attribute.
        lvdt_systems (Optional[List[Optional[Dict]]]): List of LVDT calibration
            results (dicts with 'slope'/'intercept' or None). Defaults to None.
        accel_offsets (Optional[List[Optional[Dict]]]): List of accelerometer offset
            results (dicts with 'x'/'y'/'z' or None). Defaults to None.

    Returns:
        Optional[str]: The full path to the saved calibration log file, or None
                       if an error occurred or `config.logs_dir` is missing.
    """
    if not hasattr(config, 'logs_dir') or not config.logs_dir:
         print("\nError: config object missing 'logs_dir'. Cannot save calibration data.")
         return None

    try:
        # Ensure logs directory exists
        os.makedirs(config.logs_dir, exist_ok=True)
        cal_file = os.path.join(config.logs_dir, "calibration_log.txt")
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        new_calibration_entry = f"Calibration Session: {timestamp}\n"
        new_calibration_entry += "=" * 50 + "\n"

        has_data = False
        if accel_offsets:
            new_calibration_entry += "\nAccelerometer Calibration Offsets:\n"
            new_calibration_entry += "--------------------------------\n"
            for i, offset in enumerate(accel_offsets):
                label = f"Accelerometer-{i+1}"
                if offset and all(k in offset for k in ['x', 'y', 'z']):
                    new_calibration_entry += f"  {label}:\n"
                    new_calibration_entry += f"    X-offset: {offset['x']:.6f} m/s^2\n"
                    new_calibration_entry += f"    Y-offset: {offset['y']:.6f} m/s^2\n"
                    new_calibration_entry += f"    Z-offset: {offset['z']:.6f} m/s^2\n"
                    has_data = True
                else:
                    new_calibration_entry += f"  {label}: Calibration FAILED\n"
            new_calibration_entry += "\n"

        if lvdt_systems:
            new_calibration_entry += "LVDT Calibration Parameters:\n"
            new_calibration_entry += "----------------------------\n"
            for i, lvdt in enumerate(lvdt_systems):
                label = f"LVDT-{i+1}"
                # Check for both naming conventions for robustness
                slope_key = 'lvdt_slope' if 'lvdt_slope' in (lvdt or {}) else 'slope'
                intercept_key = 'lvdt_intercept' if 'lvdt_intercept' in (lvdt or {}) else 'intercept'

                if lvdt and slope_key in lvdt and intercept_key in lvdt:
                    new_calibration_entry += f"  {label}:\n"
                    new_calibration_entry += f"    Slope:     {lvdt[slope_key]:.6f} mm/V\n"
                    new_calibration_entry += f"    Intercept: {lvdt[intercept_key]:.6f} mm\n"
                    has_data = True
                else:
                    new_calibration_entry += f"  {label}: Calibration FAILED\n"
            new_calibration_entry += "\n"

        if not has_data:
            print("\nNo successful calibration data to save.")
            return cal_file # Return path even if empty this session

        new_calibration_entry += "-" * 50 + "\n\n"

        # Read existing content if file exists
        existing_content = ""
        if os.path.exists(cal_file):
            try:
                with open(cal_file, 'r', encoding='utf-8') as f:
                    existing_content = f.read()
            except Exception as read_err:
                print(f"\nWarning: Could not read existing calibration file '{cal_file}': {read_err}")
                existing_content = f"ERROR READING PREVIOUS CONTENT: {read_err}\n\n"


        # Write new entry followed by existing content
        with open(cal_file, 'w', encoding='utf-8') as f:
            f.write(new_calibration_entry)
            f.write(existing_content)

        print(f"\nCalibration data updated in: {cal_file}\n")
        return cal_file

    except Exception as e:
        print(f"\nError saving calibration data to '{config.logs_dir}': {e}\n")
        return None
