"""
Data processing module for the IdentiTwin monitoring system.

This module handles all aspects of sensor data processing including:
- Data acquisition and validation
- CSV file management and data storage
- Real-time data processing
- Multi-sensor data synchronization
- Data format conversions

Key Features:
- Multiple sensor type support (LVDT, accelerometer)
- Automated file creation and management
- Data validation and cleaning
- Time synchronization between sensors
- Error detection and handling
- Efficient data structure management

The module provides core functionality for handling all sensor data
throughout the monitoring system lifecycle.
"""

import csv
import os
import numpy as np
import logging
from datetime import datetime, timedelta

def initialize_general_csv(num_lvdts, num_accelerometers, filename='general_measurements.csv'):
    """Initialize a CSV file for storing both LVDT and accelerometer data."""
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
    """Initialize a CSV file for LVDT displacement measurements."""
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Create header with both absolute and relative time
        header = ['Timestamp', 'Expected_Time']
        for i in range(num_lvdts):
            header.extend([f'LVDT{i+1}_Voltage', f'LVDT{i+1}_Displacement'])
            
        writer.writerow(header)
    return filename

def initialize_acceleration_csv(filename='acceleration.csv', num_accelerometers=2):
    """Initialize a CSV file for accelerometer measurements."""
    with open(filename, 'w', newline='') as f:
        writer = csv.writer(f)
        
        # Create header with both absolute and relative time
        header = ['Timestamp', 'Expected_Time']
        for i in range(num_accelerometers):
            header.extend([f'Accel{i+1}_X', f'Accel{i+1}_Y', f'Accel{i+1}_Z', f'Accel{i+1}_Magnitude'])
            
        writer.writerow(header)
    return filename

def multiple_lvdt(channels, lvdt_systems):
    """Process readings from multiple LVDT sensors."""
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
    Reads each LVDT channel and applies slope/intercept calibration.
    Returns a list of dicts under the key 'lvdt_data' with 'displacement'.
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
    """Extract numerical data from event_data structure for analysis."""
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
    """Create CSV file for LVDT displacement data."""
    displacement_file = os.path.join(event_folder, 'displacements.csv')
    
    try:
        with open(displacement_file, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Create header
            header = ['Timestamp', 'Expected_Time']
            for i in range(config.num_lvdts):
                header.extend([f'LVDT{i+1}_Voltage', f'LVDT{i+1}_Displacement'])
            writer.writerow(header)
            
            # Correct start time to cover pre-event period.
            if not event_data:
                logging.warning("No event data provided for displacement CSV creation.")
                return displacement_file # Return empty file path
                
            # Use the timestamp of the first data point as the reference start time (t=0)
            start_time = event_data[0]["timestamp"] 
            
            rows_to_write = []
            # Collect data rows: use elapsed seconds from corrected start_time
            for data in event_data:
                # Check if 'sensor_data' and 'lvdt_data' exist and are not empty
                if "sensor_data" in data and "lvdt_data" in data["sensor_data"] and data["sensor_data"]["lvdt_data"]:
                    timestamp = data["timestamp"].strftime('%Y-%m-%d %H:%M:%S.%f')
                    # Calculate time relative to the first data point's timestamp
                    expected_time = (data["timestamp"] - start_time).total_seconds() 
                    row = [timestamp, f"{expected_time:.6f}"]
                    for lvdt in data["sensor_data"]["lvdt_data"]:
                        # Ensure lvdt dictionary has the required keys
                        voltage = lvdt.get('voltage', float('nan')) # Use NaN as default if key missing
                        displacement = lvdt.get('displacement', float('nan'))
                        row.extend([f"{voltage:.6f}", f"{displacement:.6f}"])
                    rows_to_write.append(row)
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
    """Create CSV file for accelerometer data."""
    acceleration_file = os.path.join(event_folder, 'acceleration.csv')
    
    try:
        with open(acceleration_file, 'w', newline='') as f:
            writer = csv.writer(f)
            
            # Create header
            header = ['Timestamp', 'Expected_Time']
            for i in range(config.num_accelerometers):
                header.extend([f'Accel{i+1}_X', f'Accel{i+1}_Y', f'Accel{i+1}_Z', f'Accel{i+1}_Magnitude'])
            writer.writerow(header)
            
            # Correct start time to cover pre-event period.
            if not event_data:
                logging.warning("No event data provided for acceleration CSV creation.")
                return acceleration_file # Return empty file path

            # Use the timestamp of the first data point as the reference start time (t=0)
            start_time = event_data[0]["timestamp"] 
            
            rows_to_write = []
            # Collect data rows: compute expected_time as elapsed seconds from corrected start_time
            for data in event_data:
                 # Check if 'sensor_data' and 'accel_data' exist and are not empty
                if "sensor_data" in data and "accel_data" in data["sensor_data"] and data["sensor_data"]["accel_data"]:
                    timestamp = data["timestamp"].strftime('%Y-%m-%d %H:%M:%S.%f')
                    # Calculate time relative to the first data point's timestamp
                    expected_time = (data["timestamp"] - start_time).total_seconds() 
                    row = [timestamp, f"{expected_time:.6f}"]
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