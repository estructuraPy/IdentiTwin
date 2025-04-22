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
from datetime import datetime

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
    
    print(f"Processing event data: {len(timestamps)} samples.")
    print(f"  Absolute Start Time: {first_ts.strftime('%Y-%m-%d %H:%M:%S.%f')}")
    print(f"  Absolute End Time:   {last_ts.strftime('%Y-%m-%d %H:%M:%S.%f')}")
    print(f"  Actual Duration:     {actual_duration:.3f}s")

    # Extract accelerometer data
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
        print("LVDT extraction enabled.")
        for lvdt_idx in range(config.num_lvdts):
            lvdt_times = []
            lvdt_displacements = []
            
            print(f"Processing LVDT {lvdt_idx+1}")
            valid_count = 0
            
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
                        valid_count += 1
                        
                        if valid_count <= 5:  # Log first 5 valid readings
                            print(f"    Sample at {rel_time:.3f}s: {disp:.3f}mm")

            if lvdt_times:
                key_time = f'lvdt{lvdt_idx+1}_time'
                key_disp = f'lvdt{lvdt_idx+1}_displacement'
                np_data[key_time] = np.array(lvdt_times)
                np_data[key_disp] = np.array(lvdt_displacements)
                
                print(f"  Stored {valid_count} valid readings for LVDT {lvdt_idx+1}")
                print(f"  Time range: {min(lvdt_times):.3f}s to {max(lvdt_times):.3f}s")
                print(f"  Value range: {min(lvdt_displacements):.3f}mm to {max(lvdt_displacements):.3f}mm")
            else:
                print(f"  No valid readings found for LVDT {lvdt_idx+1}")

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