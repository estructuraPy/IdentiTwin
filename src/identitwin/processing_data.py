"""
Data Processing and Storage Module for IdentiTwin.

Handles initialization of CSV files for data logging, reading sensor data,
and extracting/formatting data, particularly for event analysis and storage.

Key Features:
- Initialization of CSV files with appropriate headers for general measurements,
  LVDT displacements, and accelerometer readings.
- Functions to read and process data from multiple LVDT sensors.
- Extraction and conversion of raw event data buffers into NumPy arrays suitable
  for analysis.
- Creation of specific CSV files for individual recorded events.
"""

import csv
import os
import numpy as np

def initialize_general_csv(num_lvdts, num_accelerometers, filename='general_measurements.csv'):
    """
    Initializes the main CSV file for logging combined sensor data.

    Creates a CSV file with a header row including timestamp, expected time,
    and columns for voltage/displacement for each LVDT, and X/Y/Z/Magnitude
    for each accelerometer, based on the numbers provided.

    Args:
        num_lvdts (int): The number of LVDT sensors enabled.
        num_accelerometers (int): The number of accelerometer sensors enabled.
        filename (str): The path to the CSV file to be created. Defaults to
                        'general_measurements.csv'.

    Returns:
        str: The filename of the created CSV file.

    Side Effects:
        - Creates or overwrites the specified CSV file.
        - Writes the header row to the CSV file.
    """
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Create header with both absolute and relative time
        header = ['Timestamp', 'Expected_Time']
        
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
    """
    Initializes a CSV file specifically for LVDT displacement data.

    Creates a CSV file with a header row including timestamp, expected time,
    and columns for voltage and displacement for each LVDT.

    Args:
        filename (str): The path to the CSV file to be created. Defaults to
                        'displacements.csv'.
        num_lvdts (int): The number of LVDT sensors. Defaults to 2.

    Returns:
        str: The filename of the created CSV file.

    Side Effects:
        - Creates or overwrites the specified CSV file.
        - Writes the header row to the CSV file.
    """
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Create header with both absolute and relative time
        header = ['Timestamp', 'Expected_Time']
        for i in range(num_lvdts):
            header.extend([f'LVDT{i+1}_Voltage', f'LVDT{i+1}_Displacement'])
            
        writer.writerow(header)
    return filename

def initialize_acceleration_csv(filename='acceleration.csv', num_accelerometers=2):
    """
    Initializes a CSV file specifically for accelerometer data.

    Creates a CSV file with a header row including timestamp, expected time,
    and columns for X, Y, Z, and Magnitude for each accelerometer.

    Args:
        filename (str): The path to the CSV file to be created. Defaults to
                        'acceleration.csv'.
        num_accelerometers (int): The number of accelerometer sensors. Defaults to 2.

    Returns:
        str: The filename of the created CSV file.

    Side Effects:
        - Creates or overwrites the specified CSV file.
        - Writes the header row to the CSV file.
    """
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Create header with both absolute and relative time
        header = ['Timestamp', 'Expected_Time']
        for i in range(num_accelerometers):
            header.extend([f'Accel{i+1}_X', f'Accel{i+1}_Y', f'Accel{i+1}_Z', f'Accel{i+1}_Magnitude'])
            
        writer.writerow(header)
    return filename

def multiple_lvdt(channels, lvdt_systems):
    """
    Reads voltage from multiple LVDT channels and calculates displacement.

    Iterates through corresponding LVDT channels and their calibration parameters
    (slope and intercept) to compute displacement from the measured voltage.

    Args:
        channels: A list of LVDT channel objects, each having a 'voltage' attribute.
        lvdt_systems: A list of dictionaries, where each dictionary contains
                      'lvdt_slope' and 'lvdt_intercept' for the corresponding channel.

    Returns:
        list: A list of dictionaries, each containing the 'voltage' and calculated
              'displacement' for an LVDT sensor.
    """
    results = []
    for i, (channel, system) in enumerate(zip(channels, lvdt_systems)):
        voltage = channel.voltage
        displacement = system.lvdt_slope * voltage + system.lvdt_intercept
        results.append({
            'voltage': voltage,
            'displacement': displacement
        })
    return results

def read_lvdt_data(lvdt_channels, config):
    """
    Reads voltage from LVDT channels and calculates displacement using global config.

    Iterates through LVDT channels, reads voltage, and applies the globally
    configured slope and intercept (`config.lvdt_slope`, `config.lvdt_intercept`)
    to calculate displacement. Handles potential reading errors.

    Args:
        lvdt_channels: A list of LVDT channel objects, each having a 'voltage' attribute.
        config: The system configuration object containing 'lvdt_slope' and
                'lvdt_intercept'.

    Returns:
        list: A list of dictionaries, each containing the calculated 'displacement'.
              Returns 0.0 displacement if a reading error occurs.
    """
    lvdt_values = []
    for ch in lvdt_channels:
        try:
            voltage = ch.voltage
            displacement = config.lvdt_slope * voltage + config.lvdt_intercept
            lvdt_values.append({"displacement": displacement})
        except:
            lvdt_values.append({"displacement": 0.0})
    return lvdt_values

def extract_data_from_event(event_data, start_time, config):
    """
    Extracts numerical sensor data from a buffered event and converts it to NumPy arrays.

    Processes a list of dictionaries (representing sensor readings over time for an event)
    and organizes the data into a dictionary of NumPy arrays. Calculates relative and
    absolute timestamps, and extracts accelerometer (X, Y, Z, Magnitude) and LVDT
    (Voltage, Displacement) data if enabled in the config.

    Args:
        event_data (list): A list of dictionaries, where each dictionary represents
                           a snapshot of sensor readings at a specific timestamp.
                           Expected format: [{'timestamp': dt, 'sensor_data': {'accel_data': [...], 'lvdt_data': [...]}}, ...]
        start_time (datetime): The approximate start time of the event (used if timestamps are missing).
        config: The system configuration object (used to check enabled sensors and counts).

    Returns:
        dict: A dictionary where keys are sensor/axis identifiers (e.g., 'timestamps',
              'accel1_x', 'lvdt1_displacement') and values are NumPy arrays of the
              corresponding data.
    """
    np_data = {}
    
    # Extract timestamps
    timestamps = []
    for data in event_data:
        timestamps.append(data["timestamp"])
    
    if timestamps:
        # Convert timestamps to seconds from event start
        np_data['timestamps'] = np.array([(ts - timestamps[0]).total_seconds() for ts in timestamps])
        np_data['absolute_timestamps'] = np.array([ts.timestamp() for ts in timestamps])
    else:
        # Fallback if no timestamps
        np_data['timestamps'] = np.array([0.0])
        np_data['absolute_timestamps'] = np.array([start_time.timestamp()])
    
    # Extract accelerometer data if enabled
    if config.enable_accel:
        for accel_idx in range(config.num_accelerometers):
            accel_x = []
            accel_y = []
            accel_z = []
            accel_mag = []
            
            for data in event_data:
                if "accel_data" in data["sensor_data"] and accel_idx < len(data["sensor_data"]["accel_data"]):
                    accel = data["sensor_data"]["accel_data"][accel_idx]
                    accel_x.append(accel['x'])
                    accel_y.append(accel['y'])
                    accel_z.append(accel['z'])
                    mag = np.sqrt(accel['x']**2 + accel['y']**2 + accel['z']**2)
                    accel_mag.append(mag)
            
            if accel_x:  # Only add if we have data
                np_data[f'accel{accel_idx+1}_x'] = np.array(accel_x)
                np_data[f'accel{accel_idx+1}_y'] = np.array(accel_y)
                np_data[f'accel{accel_idx+1}_z'] = np.array(accel_z)
                np_data[f'accel{accel_idx+1}_mag'] = np.array(accel_mag)
    
    # Extract LVDT data if enabled
    if config.enable_lvdt:
        for lvdt_idx in range(config.num_lvdts):
            lvdt_voltage = []
            lvdt_displacement = []
            
            for data in event_data:
                if "lvdt_data" in data["sensor_data"] and lvdt_idx < len(data["sensor_data"]["lvdt_data"]):
                    lvdt = data["sensor_data"]["lvdt_data"][lvdt_idx]
                    lvdt_voltage.append(lvdt['voltage'])
                    lvdt_displacement.append(lvdt['displacement'])
            
            if lvdt_voltage:  # Only add if we have data
                np_data[f'lvdt{lvdt_idx+1}_voltage'] = np.array(lvdt_voltage)
                np_data[f'lvdt{lvdt_idx+1}_displacement'] = np.array(lvdt_displacement)
    
    return np_data

def create_displacement_csv(event_data, event_folder, config):
    """
    Creates a CSV file containing LVDT data for a specific recorded event.

    Writes timestamp, expected relative time, voltage, and displacement for each
    LVDT sensor enabled in the configuration to a 'displacements.csv' file within
    the specified event folder.

    Args:
        event_data (list): The list of sensor data dictionaries for the event.
        event_folder (str): The path to the directory where the event's files are stored.
        config: The system configuration object.

    Returns:
        str or None: The full path to the created CSV file, or None if an error occurred
                     or LVDT data was not present/enabled.

    Side Effects:
        - Creates a 'displacements.csv' file in the `event_folder`.
        - Prints success or error messages to the console.
    """
    displacement_file = os.path.join(event_folder, 'displacements.csv')
    
    try:
        with open(displacement_file, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Create header
            header = ['Timestamp', 'Expected_Time']
            for i in range(config.num_lvdts):
                header.extend([f'LVDT{i+1}_Voltage', f'LVDT{i+1}_Displacement'])
            writer.writerow(header)
            
            # Get start time from first entry
            start_time = event_data[0]["timestamp"]
            
            # Write data
            for i, data in enumerate(event_data):
                if "lvdt_data" in data["sensor_data"]:
                    timestamp = data["timestamp"].strftime('%Y-%m-%d %H:%M:%S.%f')
                    expected_time = i * (1.0 / config.sampling_rate_lvdt)
                    row = [timestamp, f"{expected_time:.6f}"]
                    for lvdt in data["sensor_data"]["lvdt_data"]:
                        row.extend([f"{lvdt['voltage']:.6f}", f"{lvdt['displacement']:.6f}"])
                    writer.writerow(row)
                    
        print(f"Created displacement CSV file: {os.path.basename(displacement_file)}")
        return displacement_file
    except Exception as e:
        print(f"Error creating displacement CSV: {e}")
        return None

def create_acceleration_csv(event_data, event_folder, config):
    """
    Creates a CSV file containing accelerometer data for a specific recorded event.

    Writes timestamp, expected relative time, X, Y, Z, and Magnitude for each
    accelerometer sensor enabled in the configuration to an 'acceleration.csv' file
    within the specified event folder.

    Args:
        event_data (list): The list of sensor data dictionaries for the event.
        event_folder (str): The path to the directory where the event's files are stored.
        config: The system configuration object.

    Returns:
        str or None: The full path to the created CSV file, or None if an error occurred
                     or accelerometer data was not present/enabled.

    Side Effects:
        - Creates an 'acceleration.csv' file in the `event_folder`.
        - Prints success or error messages to the console.
    """
    acceleration_file = os.path.join(event_folder, 'acceleration.csv')
    
    try:
        with open(acceleration_file, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Create header
            header = ['Timestamp', 'Expected_Time']
            for i in range(config.num_accelerometers):
                header.extend([f'Accel{i+1}_X', f'Accel{i+1}_Y', f'Accel{i+1}_Z', f'Accel{i+1}_Magnitude'])
            writer.writerow(header)
            
            # Get start time from first entry
            start_time = event_data[0]["timestamp"]
            
            # Write data
            for i, data in enumerate(event_data):
                if "accel_data" in data["sensor_data"]:
                    timestamp = data["timestamp"].strftime('%Y-%m-%d %H:%M:%S.%f')
                    expected_time = i * (1.0 / config.sampling_rate_acceleration)
                    row = [timestamp, f"{expected_time:.6f}"]
                    for accel in data["sensor_data"]["accel_data"]:
                        magnitude = np.sqrt(accel['x']**2 + accel['y']**2 + accel['z']**2)
                        row.extend([
                            f"{accel['x']:.6f}", 
                            f"{accel['y']:.6f}", 
                            f"{accel['z']:.6f}",
                            f"{magnitude:.6f}"
                        ])
                    writer.writerow(row)
                    
        print(f"Created acceleration CSV file: {os.path.basename(acceleration_file)}")
        return acceleration_file
    except Exception as e:
        print(f"Error creating acceleration CSV: {e}")
        return None