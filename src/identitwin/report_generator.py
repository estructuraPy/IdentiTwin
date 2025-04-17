"""
Report Generation Module for IdentiTwin.

Handles the creation of various text-based reports summarizing system configuration,
monitoring session statistics, performance metrics, and detected events.

Key Features:
- Generation of system configuration reports.
- Generation of end-of-session summary reports including performance and event counts.
- Extraction of key details from individual event reports.
- File management for saving reports.
"""

import os
import time
from datetime import datetime

def generate_system_report(config, filename):
    """
    Generates a text report detailing the system configuration.

    Writes key configuration parameters like operational mode, sensor enablement,
    sampling rates, event detection settings, and data storage paths to a specified file.

    Args:
        config: The SystemConfig object containing the configuration parameters.
        filename (str): The full path to the file where the report will be saved.

    Returns:
        bool: True if the report was generated successfully, False otherwise.

    Side Effects:
        - Creates or overwrites the file specified by `filename`.
        - Prints success or error messages to the console.
    """
    try:
        with open(filename, 'w') as f:
            f.write("# IdentiTwin System Report\n")
            f.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Mode of Operation
            f.write("## Mode of Operation:\n")
            f.write(f"Operational Mode: {config.operational_mode}\n")
            f.write(f"LVDT Enabled: {config.enable_lvdt}\n")
            if config.enable_lvdt:
                f.write(f"Number of LVDTs: {config.num_lvdts}\n")
            f.write(f"Accelerometer Enabled: {config.enable_accel}\n")
            if config.enable_accel:
                f.write(f"Number of accelerometers: {config.num_accelerometers}\n")
            f.write("\n")
            
            # Sampling configuration
            f.write("## Sampling configuration:\n")
            f.write(f"  Accelerometer Rate: {config.sampling_rate_acceleration} Hz\n")
            f.write(f"  LVDT Rate: {config.sampling_rate_lvdt} Hz\n")
            f.write(f"  Plot Refresh Rate: {config.plot_refresh_rate} Hz\n\n")
            
            # Event detection parameters
            f.write("## Event detection parameters:\n")
            f.write(f"  Acceleration Threshold: {config.trigger_acceleration_threshold} m/s^2\n")
            f.write(f"  Displacement Threshold: {config.trigger_displacement_threshold} mm\n")
            f.write(f"  Pre-trigger Buffer: {config.pre_trigger_time} seconds\n")
            f.write(f"  Post-trigger Buffer: {config.post_trigger_time} seconds\n")
            f.write(f"  Minimum Event Duration: {config.min_event_duration} seconds\n\n")
            
            # Data Storage
            f.write("## Data Storage:\n")
            f.write(f"  Base Directory: {config.output_dir}\n")
            
        print(f"System report generated: {filename}")
        return True
    except Exception as e:
        print(f"Error generating system report: {e}")
        return False

def generate_summary_report(monitor_system, report_file):
    """
    Generates a summary report at the end of a monitoring session.

    Includes session statistics (total events), final performance metrics
    (sampling rates, jitter), and a brief summary of each detected event
    by reading details from individual event report files.

    Args:
        monitor_system: The MonitoringSystem instance containing runtime data
                        (config, event count, performance stats).
        report_file (str): The full path to the file where the summary report
                           will be saved.

    Returns:
        bool: True if the report was generated successfully, False otherwise.

    Side Effects:
        - Creates or overwrites the file specified by `report_file`.
        - Prints success or error messages to the console.
        - Calls `monitor_system._update_performance_stats()` to ensure final
          metrics are calculated.
    """
    try:
        config = monitor_system.config
        
        # Force a final update of performance stats before generating report
        monitor_system._update_performance_stats()
        
        with open(report_file, 'w') as f:
            f.write("==== IdentiTwin MONITORING SUMMARY ====\n")
            f.write(f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}\n\n")
            
            # Get most recent performance values from system
            accel_rate = monitor_system.performance_stats.get("sampling_rate_acceleration", 0.0)
            lvdt_rate = monitor_system.performance_stats.get("sampling_rate_lvdt", 0.0)
            accel_jitter = monitor_system.performance_stats.get("accel_jitter", 0.0)
            lvdt_jitter = monitor_system.performance_stats.get("lvdt_jitter", 0.0)
            
            # Operational statistics
            f.write("Session Statistics:\n")
            f.write(f"  Events Detected: {monitor_system.event_count}\n")
            
            # Performance statistics using real-time values
            f.write("\nPerformance Metrics:\n")
            if config.enable_accel:
                f.write(f"  Accelerometer Rate: {accel_rate:.2f} Hz (Target: {config.sampling_rate_acceleration} Hz)\n")
                f.write(f"  Accelerometer Jitter: {accel_jitter:.2f} ms\n")
            
            if config.enable_lvdt:
                f.write(f"  LVDT Rate: {lvdt_rate:.2f} Hz (Target: {config.sampling_rate_lvdt} Hz)\n")
                f.write(f"  LVDT Jitter: {lvdt_jitter:.2f} ms\n")
            
            # Event list and summaries
            if monitor_system.event_count > 0:
                f.write("\nEvents summary:\n")
                _add_event_summaries(f, config.events_dir)
            
            f.write("\n==== END OF SUMMARY ====\n")
        
        print(f"Summary report saved to: {report_file}")
        return True
    except Exception as e:
        print(f"Error generating summary report: {e}")
        return False

def _add_event_summaries(file_obj, events_dir):
    """
    Helper function to append summaries of detected events to an open report file.

    Iterates through event subdirectories within the specified `events_dir`,
    extracts the event timestamp from the folder name, and attempts to read
    key lines (containing "Maximum", "Peak", "Duration") from the 'report.txt'
    file within each event folder.

    Args:
        file_obj: An open file object to write the summaries to.
        events_dir (str): The path to the directory containing individual event folders.

    Returns:
        None

    Side Effects:
        - Writes event summary lines to the `file_obj`.
        - Prints error messages to the `file_obj` if reading an event report fails.

    Assumptions:
        - Event folders are named in a sortable format (e.g., YYYYMMDD_HHMMSS).
        - Each event folder may contain a 'report.txt' file with analysis details.
    """
    event_folders = [f for f in os.listdir(events_dir) if os.path.isdir(os.path.join(events_dir, f))]
    event_folders.sort()  # Sort chronologically
    
    for i, event_folder in enumerate(event_folders, 1):
        event_path = os.path.join(events_dir, event_folder)
        try:
            # Format event timestamp from folder name
            event_date = f"{event_folder[:4]}-{event_folder[4:6]}-{event_folder[6:8]} {event_folder[9:11]}:{event_folder[11:13]}:{event_folder[13:15]}"
        except:
            event_date = event_folder
            
        file_obj.write(f"  Event {i}: {event_date}\n")
        
        # Add report details if available
        event_report = os.path.join(event_path, "report.txt")
        if os.path.exists(event_report):
            try:
                with open(event_report, 'r') as event_f:
                    lines = event_f.readlines()
                    for line in lines:
                        if "Maximum" in line or "Peak" in line or "Duration" in line:
                            file_obj.write(f"    {line.strip()}\n")
            except Exception as e:
                file_obj.write(f"    Error reading event report: {e}\n")
