"""Data processing and storage module for the IdentiTwin system.

Handles reading raw sensor data, applying calibration, managing CSV file
creation and writing for both continuous logging (if enabled) and event-specific
data storage. Also includes functions for extracting numerical data from
event buffers for analysis.

Key Features:
    - Initialization of CSV files with appropriate headers for different data types.
    - Reading LVDT voltage and applying calibration (slope/intercept).
    - Handling missing or incomplete LVDT calibration data.
    - Extracting time series data (timestamps, accel, LVDT) from event buffers
      into NumPy arrays for analysis.
    - Creating event-specific CSV files for LVDT and accelerometer data.
    - Time synchronization and formatting for CSV output.
"""

import csv
import os
import numpy as np
import logging
import time  # Added for sleep functionality
from datetime import datetime, timedelta

def initialize_general_csv(num_lvdts, num_accelerometers, filename='general_measurements.csv'):
    """Initializes a CSV file for storing combined LVDT and accelerometer data.

    Creates the file and writes the header row, including columns for timestamp,
    relative time, LVDT voltage/displacement, and accelerometer X/Y/Z/Magnitude
    for the specified number of sensors.

    Args:
        num_lvdts (int): The number of LVDT sensors.
        num_accelerometers (int): The number of accelerometer sensors.
        filename (str, optional): The path to the CSV file to be created.
            Defaults to 'general_measurements.csv'.

    Returns:
        str: The filename of the initialized CSV file.
    """
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Create header with both absolute and relative time
        header = ['Timestamp', 'Time']  # Changed from 'Expected_Time'
        
        # Add LVDT columns
        for i in range(num_lvdts):
            header.append(f'LVDT{i+1}_Voltage')
            header.append(f'LVDT{i+1}_Displacement')
            
        # Add accelerometer columns
        for i in range(num_accelerometers):
            header.extend([f'Accel{i+1}_X', f'Accel{i+1}_Y', f'Accel{i+1}_Z', f'Accel{i+1}_Magnitude'])
            
        writer.writerow(header)
    return filename

def initialize_displacement_csv(filename='displacements.csv', num_lvdts=2):
    """Initializes a CSV file specifically for LVDT displacement data.

    Creates the file and writes the header row, including columns for timestamp,
    relative time, and voltage/displacement for each LVDT.

    Args:
        filename (str, optional): The path to the CSV file to be created.
            Defaults to 'displacements.csv'.
        num_lvdts (int, optional): The number of LVDT sensors. Defaults to 2.

    Returns:
        str: The filename of the initialized CSV file.
    """
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Create header with both absolute and relative time
        header = ['Timestamp', 'Time']  # Changed from 'Expected_Time'
        for i in range(num_lvdts):
            header.extend([f'LVDT{i+1}_Voltage', f'LVDT{i+1}_Displacement'])
            
        writer.writerow(header)
    return filename

def initialize_acceleration_csv(filename='acceleration.csv', num_accelerometers=2):
    """Initializes a CSV file specifically for accelerometer data.

    Creates the file and writes the header row, including columns for timestamp,
    relative time, and X/Y/Z/Magnitude for each accelerometer.

    Args:
        filename (str, optional): The path to the CSV file to be created.
            Defaults to 'acceleration.csv'.
        num_accelerometers (int, optional): The number of accelerometer sensors.
            Defaults to 2.

    Returns:
        str: The filename of the initialized CSV file.
    """
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Create header with both absolute and relative time
        header = ['Timestamp', 'Time']  # Changed from 'Expected_Time'
        for i in range(num_accelerometers):
            header.extend([f'Accel{i+1}_X', f'Accel{i+1}_Y', f'Accel{i+1}_Z', f'Accel{i+1}_Magnitude'])
            
        writer.writerow(header)
    return filename

def read_lvdt_data(lvdt_channels, config):
    """Reads voltage from LVDT channels and applies calibration.

    Iterates through the provided LVDT channel objects, reads the voltage,
    retrieves the corresponding calibration slope and intercept from the
    `config.lvdt_calibration` list, and calculates the displacement. Handles
    missing or incomplete calibration data by printing a warning and using
    default values (slope=20, intercept=0). Includes a small delay before
    reading for stability.

    Args:
        lvdt_channels (list): A list of LVDT channel objects (e.g., `AnalogIn`
            instances) that have a readable `voltage` attribute.
        config (SystemConfig or SimulatorConfig): The system configuration object,
            which must have an `lvdt_calibration` attribute (a list of dicts
            containing 'slope' and 'intercept').

    Returns:
        list[dict]: A list of dictionaries, one for each channel. Each dictionary
            contains 'voltage' (float) and 'displacement' (float). If reading or
            calibration fails for a channel, default values (0.0) might be returned
            in its dictionary along with a printed error message.
    """
    lvdt_values = []
    for i, ch in enumerate(lvdt_channels):
        try:
            # Add small delay before reading to ensure stable readings
            time.sleep(0.001)  # 1ms delay for stability
            
            voltage = ch.voltage
            
            # Use individual calibration parameters - fail explicitly if missing
            if not hasattr(config, 'lvdt_calibration'):
                print(f"Warning: No LVDT calibration data available in configuration. Using slope=20, intercept=0.")
                slope = 20.0
                intercept = 0.0
            elif i >= len(config.lvdt_calibration) or config.lvdt_calibration[i] is None:
                print(f"Warning: Missing calibration data for LVDT {i+1}. Using slope=20, intercept=0.")
                slope = 20.0
                intercept = 0.0
            else:
                calib = config.lvdt_calibration[i]
                # Check for both possible key names
                slope = calib.get('slope', calib.get('lvdt_slope'))
                intercept = calib.get('intercept', calib.get('lvdt_intercept'))
                
                if slope is None or intercept is None:
                    print(f"Warning: Incomplete calibration parameters for LVDT {i+1}. Using slope=20, intercept=0.")
                    slope = 20.0
                    intercept = 0.0
            
            displacement = slope * voltage + intercept
            
            # Print debug info for first reading
            if i == 0 and len(lvdt_values) == 0:
                print(f"DEBUG: LVDT {i+1} reading - voltage: {voltage:.4f}V, slope: {slope:.4f}, "
                      f"intercept: {intercept:.4f}, displacement: {displacement:.4f}mm")
            
            lvdt_values.append({
                'voltage': voltage,
                'displacement': displacement
            })
        except Exception as e:
            print(f"Error reading LVDT {i+1}: {e}")
            # Return empty dict instead of raising, to allow system to continue
            lvdt_values.append({'voltage': 0.0, 'displacement': 0.0})
            
    return lvdt_values

def extract_data_from_event(event_data, start_time, config):
    """Extracts numerical time series data from a buffered event into NumPy arrays.

    Processes a list of dictionaries (representing sensor readings over time)
    collected during an event. Extracts timestamps, accelerometer data (X, Y, Z, Mag),
    and LVDT data (displacement) for each sensor. Converts these into NumPy arrays,
    calculating relative timestamps based on the earliest timestamp in the event.

    Args:
        event_data (list[dict]): A list where each dictionary represents a
            sensor reading packet, typically containing 'timestamp' and
            'sensor_data' (which in turn contains 'accel_data' and/or 'lvdt_data').
        start_time (datetime): The nominal start time of the event (used for context,
            but relative time is calculated from the first timestamp in `event_data`).
        config (SystemConfig or SimulatorConfig): The system configuration object, used
            to determine the number of expected sensors (`num_accelerometers`, `num_lvdts`)
            and which sensor types are enabled (`enable_accel`, `enable_lvdt`).

    Returns:
        dict: A dictionary where keys are strings identifying the data
            (e.g., 'timestamps', 'accel1_x', 'lvdt1_displacement', 'lvdt1_time')
            and values are NumPy arrays containing the corresponding numerical data.
            Returns an empty dictionary if no valid timestamps are found.
    """
    np_data = {}
    
    # Extract timestamps
    timestamps = []
    for data in event_data:
        if "timestamp" in data and isinstance(data["timestamp"], datetime):
             timestamps.append(data["timestamp"])
        else:
             logging.warning(f"Missing or invalid timestamp in event data entry: {data}")
             continue
    
    if not timestamps:
        logging.error("No valid timestamps found in event data.")
        return {}

    first_ts = min(timestamps)
    last_ts = max(timestamps)
    actual_duration = (last_ts - first_ts).total_seconds()

    if config.enable_accel:
        # Store main timestamps array (used primarily for accelerometer data)
        np_data['timestamps'] = np.array([(ts - first_ts).total_seconds() for ts in timestamps])
        np_data['absolute_timestamps'] = np.array([ts.timestamp() for ts in timestamps])
        
        for accel_idx in range(config.num_accelerometers):
            accel_x, accel_y, accel_z, accel_mag = [], [], [], []
            
            for data in event_data:
                 if "timestamp" not in data or not isinstance(data["timestamp"], datetime):
                     continue
                 
                 sensor_dict = data.get("sensor_data", {})
                 accel_list = sensor_dict.get("accel_data", [])
                 
                 if accel_idx < len(accel_list):
                    accel = accel_list[accel_idx]
                    if all(k in accel for k in ['x', 'y', 'z']):
                        accel_x.append(accel['x'])
                        accel_y.append(accel['y'])
                        accel_z.append(accel['z'])
                        mag = np.sqrt(accel['x']**2 + accel['y']**2 + accel['z']**2)
                        accel_mag.append(mag)
                    else:
                        accel_x.append(np.nan)
                        accel_y.append(np.nan)
                        accel_z.append(np.nan)
                        accel_mag.append(np.nan)
                 else:
                     accel_x.append(np.nan)
                     accel_y.append(np.nan)
                     accel_z.append(np.nan)
                     accel_mag.append(np.nan)

            if accel_x:
                np_data[f'accel{accel_idx+1}_x'] = np.array(accel_x)
                np_data[f'accel{accel_idx+1}_y'] = np.array(accel_y)
                np_data[f'accel{accel_idx+1}_z'] = np.array(accel_z)
                np_data[f'accel{accel_idx+1}_mag'] = np.array(accel_mag)

    # Extract LVDT data
    if config.enable_lvdt:
        for lvdt_idx in range(config.num_lvdts):
            lvdt_times = []
            lvdt_displacements = []
            
            for data in event_data:
                if "timestamp" not in data or not isinstance(data["timestamp"], datetime):
                    continue

                sensor_dict = data.get("sensor_data", {})
                lvdt_list = sensor_dict.get("lvdt_data", [])

                if lvdt_idx < len(lvdt_list):
                    lvdt = lvdt_list[lvdt_idx]
                    disp = lvdt.get('displacement')
                    
                    if disp is not None and not np.isnan(disp):
                        rel_time = (data["timestamp"] - first_ts).total_seconds()
                        lvdt_times.append(rel_time)
                        lvdt_displacements.append(disp)

            if lvdt_times:
                key_time = f'lvdt{lvdt_idx+1}_time'
                key_disp = f'lvdt{lvdt_idx+1}_displacement'
                np_data[key_time] = np.array(lvdt_times)
                np_data[key_disp] = np.array(lvdt_displacements)

    return np_data

def create_displacement_csv(event_data, event_folder, config):
    """Creates a CSV file containing LVDT data for a specific event.

    Writes the timestamp, calculated relative time (based on sample count and
    configured LVDT sampling rate), voltage, and displacement for each LVDT
    sensor during the event to a CSV file within the specified event folder.

    Args:
        event_data (list[dict]): The buffered data collected for the event.
        event_folder (str): The path to the directory where the event's files
            are stored.
        config (SystemConfig or SimulatorConfig): The system configuration object,
            used for `num_lvdts` and `sampling_rate_lvdt`.

    Returns:
        str or None: The full path to the created CSV file, or None if an error occurred.
    """
    displacement_file = os.path.join(event_folder, 'displacements.csv')
    
    try:
        with open(displacement_file, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Create header
            header = ['Timestamp', 'Time']  # Changed from 'Expected_Time'
            for i in range(config.num_lvdts):
                header.extend([f'LVDT{i+1}_Voltage', f'LVDT{i+1}_Displacement'])
            writer.writerow(header)
            
            # Correct start time to cover pre-event period.
            if not event_data:
                logging.warning("No event data provided for displacement CSV creation.")
                return displacement_file # Return empty file path
                
            # Use counter instead of measured time
            valid_counter = 0
            time_counter = 0
            
            rows_to_write = []
            # Collect data rows: use elapsed seconds from corrected start_time
            for data in event_data:
                # Check if 'sensor_data' and 'lvdt_data' exist and are not empty
                if "sensor_data" in data and "lvdt_data" in data["sensor_data"] and data["sensor_data"]["lvdt_data"]:
                    timestamp = data["timestamp"].strftime('%Y-%m-%d %H:%M:%S.%f')
                    # Expected time from counter and expected LVDT rate
                    time_value = time_counter * (1.0 / config.sampling_rate_lvdt)
                    row = [timestamp, f"{time_value:.6f}"]
                    for lvdt in data["sensor_data"]["lvdt_data"]:
                        # Ensure lvdt dictionary has the required keys
                        voltage = lvdt.get('voltage', float('nan')) # Use NaN as default if key missing
                        displacement = lvdt.get('displacement', float('nan'))
                        row.extend([f"{voltage:.6f}", f"{displacement:.6f}"])
                    rows_to_write.append(row)
                    valid_counter += 1
                    time_counter += 1
                else:
                    # Optionally log missing data or handle differently
                    logging.debug(f"Skipping data point due to missing LVDT data: {data.get('timestamp')}")

            # Write all collected rows at once
            if rows_to_write:
                writer.writerows(rows_to_write)
            else:
                logging.warning(f"No valid LVDT data found to write to {displacement_file}")

        return displacement_file
    except Exception as e:
        logging.error(f"Error creating displacement CSV: {e}", exc_info=True) # Log traceback
        return None

def create_acceleration_csv(event_data, event_folder, config):
    """Creates a CSV file containing accelerometer data for a specific event.

    Writes the timestamp, calculated relative time (based on sample count and
    configured accelerometer sampling rate), X, Y, Z, and Magnitude for each
    accelerometer sensor during the event to a CSV file within the specified
    event folder.

    Args:
        event_data (list[dict]): The buffered data collected for the event.
        event_folder (str): The path to the directory where the event's files
            are stored.
        config (SystemConfig or SimulatorConfig): The system configuration object,
            used for `num_accelerometers` and `sampling_rate_acceleration`.

    Returns:
        str or None: The full path to the created CSV file, or None if an error occurred.
    """
    acceleration_file = os.path.join(event_folder, 'acceleration.csv')
    
    try:
        with open(acceleration_file, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Create header
            header = ['Timestamp', 'Time']  # Changed from 'Expected_Time'
            for i in range(config.num_accelerometers):
                header.extend([f'Accel{i+1}_X', f'Accel{i+1}_Y', f'Accel{i+1}_Z', f'Accel{i+1}_Magnitude'])
            writer.writerow(header)
            
            # Correct start time to cover pre-event period.
            if not event_data:
                logging.warning("No event data provided for acceleration CSV creation.")
                return acceleration_file # Return empty file path

            # Use counter instead of measured time
            valid_counter = 0
            time_counter = 0
            
            rows_to_write = []
            # Collect data rows: compute expected_time as elapsed seconds from corrected start_time
            for data in event_data:
                 # Check if 'sensor_data' and 'accel_data' exist and are not empty
                if "sensor_data" in data and "accel_data" in data["sensor_data"] and data["sensor_data"]["accel_data"]:
                    timestamp = data["timestamp"].strftime('%Y-%m-%d %H:%M:%S.%f')
                    # Expected time from counter and expected accelerometer rate
                    time_value = time_counter * (1.0 / config.sampling_rate_acceleration)
                    row = [timestamp, f"{time_value:.6f}"]
                    for accel in data["sensor_data"]["accel_data"]:
                        # Ensure accel dictionary has the required keys
                        x = accel.get('x', float('nan')) # Use NaN as default
                        y = accel.get('y', float('nan'))
                        z = accel.get('z', float('nan'))
                        # Calculate magnitude safely, handling potential NaNs
                        if not (np.isnan(x) or np.isnan(y) or np.isnan(z)):
                            magnitude = np.sqrt(x**2 + y**2 + z**2)
                        else:
                            magnitude = float('nan')
                            
                        row.extend([
                            f"{x:.6f}", 
                            f"{y:.6f}", 
                            f"{z:.6f}",
                            f"{magnitude:.6f}"
                        ])
                    rows_to_write.append(row)
                    valid_counter += 1
                    time_counter += 1
                else:
                     # Optionally log missing data or handle differently
                    logging.debug(f"Skipping data point due to missing Accelerometer data: {data.get('timestamp')}")

            # Write all collected rows at once
            if rows_to_write:
                writer.writerows(rows_to_write)
            else:
                 logging.warning(f"No valid Accelerometer data found to write to {acceleration_file}")

        return acceleration_file
    except Exception as e:
        logging.error(f"Error creating acceleration CSV: {e}", exc_info=True) # Log traceback
        return None