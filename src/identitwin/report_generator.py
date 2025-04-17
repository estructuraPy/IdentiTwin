"""
Report generation module for the IdentiTwin monitoring system.

This module handles the creation of various system reports including:
- System configuration reports
- Event summaries
- Performance reports
- Calibration reports
- Analysis summaries

Key Features:
- Multiple report format support
- Automated report generation
- Event data summarization
- Performance metric reporting
- System configuration documentation
- Temporal data organization
- Report file management

The module provides comprehensive reporting capabilities for system
operation, events, and analysis results.
"""

import os
import time
from datetime import datetime

def generate_system_report(config, filename):
    """Generate a system configuration report."""
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
    """Generate and save a summary report of the monitoring session."""
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
    """Helper function to add event summaries to a report."""
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
