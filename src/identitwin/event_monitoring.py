"""
Event monitoring module for the IdentiTwin system.

This module provides real-time monitoring and detection of structural events based on:
- Acceleration thresholds
- Displacement thresholds
- Event duration analysis

Key Features:
- Continuous sensor data monitoring
- Pre-trigger and post-trigger data buffering
- Event data persistence and analysis
- Multi-threaded event processing
- Moving average filtering for noise reduction
- Adaptive trigger/detrigger mechanism

Classes:
    EventMonitor: Main class for event detection and handling

The module integrates with the data processing and analysis modules for complete
event lifecycle management from detection to analysis and storage.
"""

import os
import csv
import time
import queue
import traceback
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import logging
from collections import deque
from datetime import datetime

from . import state
from .processing_data import read_lvdt_data
from . import processing_analysis

# event_monitoring.py
class EventMonitor:
    """Monitors events based on sensor data and saves relevant information."""

    def __init__(self, config, data_queue, thresholds, running_ref, event_count_ref):
        """
        Initializes the EventMonitor.

        Args:
            config: The system configuration object.
            data_queue: A queue containing sensor data.
            thresholds: A dictionary of thresholds for event detection.
            running_ref: A reference to a boolean indicating whether the system is running.
            event_count_ref: A reference to an integer tracking the number of events.

        Returns:
            None

        Assumptions:
            - The configuration object is properly set up.
            - The data queue provides sensor data in a consistent format.
            - Thresholds for acceleration and displacement are provided.
            - The running_ref is a shared boolean to control the thread.
            - The event_count_ref is a shared counter for events.
        """
        self.config = config
        self.data_queue = data_queue
        self.thresholds = thresholds
        self.running_ref = running_ref
        self.event_count_ref = event_count_ref
        self.event_in_progress = False
        self.event_data_buffer = queue.Queue(maxsize=1000)
        
        self.in_event_recording = False
        self.current_event_data = []
        self.pre_trigger_buffer = deque(maxlen=1000)  # adjust buffer size as needed
        self.last_trigger_time = 0
        
        # Initialize moving averages with deque buffers
        window_size = int(0.5 * config.sampling_rate_acceleration)  # 0.5 segundos de muestras
        self.accel_buffer = deque(maxlen=200)
        self.disp_buffer = deque(maxlen=10)
        self.moving_avg_accel = 0.0
        self.moving_avg_disp = 0.0

        # Initialize event count in state with current value
        state.set_event_variable("event_count", event_count_ref[0])
        state.set_event_variable("is_event_recording", False)
        
        self.error_count = 0
        self.max_errors = 100  # Maximum number of consecutive errors before warning

    def detect_event(self, sensor_data):
        """Detect and record event data using trigger/detrigger mechanism."""
        if not sensor_data or "sensor_data" not in sensor_data:
            return False

        try:
            self.pre_trigger_buffer.append(sensor_data)
            current_time = time.time()

            # Extract and validate sensor data
            accel_data = sensor_data.get("sensor_data", {}).get("accel_data", [])
            lvdt_data = sensor_data.get("sensor_data", {}).get("lvdt_data", [])

            if not accel_data and not lvdt_data:
                return False

            # Process sensor data safely
            magnitude = 0
            max_instantaneous_disp = 0 # Track maximum displacement across all LVDTs

            if accel_data and len(accel_data) > 0:
                # Use the first accelerometer for magnitude calculation (or adapt if needed)
                accel = accel_data[0]
                if all(k in accel for k in ['x', 'y', 'z']):
                    magnitude = np.sqrt(accel["x"]**2 + accel["y"]**2 + accel["z"]**2)
                    self.accel_buffer.append(magnitude)
                    self.moving_avg_accel = np.mean(self.accel_buffer)

            if lvdt_data:
                # Iterate through all LVDTs to find the maximum absolute displacement
                for lvdt in lvdt_data:
                    disp = abs(lvdt.get("displacement", 0))
                    if not np.isnan(disp): # Ignore NaN values
                        max_instantaneous_disp = max(max_instantaneous_disp, disp)

                # Update moving average buffer with the maximum displacement found
                self.disp_buffer.append(max_instantaneous_disp)
                self.moving_avg_disp = np.mean(self.disp_buffer)


            # Event detection logic
            trigger_accel_threshold = self.thresholds.get("acceleration", float('inf')) # Use infinity if not set
            trigger_disp_threshold = self.thresholds.get("displacement", float('inf')) # Use infinity if not set

            # Check if *any* sensor exceeds its trigger threshold
            accel_triggered = magnitude > trigger_accel_threshold
            # Check if the *maximum* displacement across LVDTs exceeds the threshold
            lvdt_triggered = max_instantaneous_disp > trigger_disp_threshold

            # Check detrigger conditions using moving averages
            detrigger_accel_threshold = self.thresholds.get("detrigger_acceleration", trigger_accel_threshold * 0.5)
            detrigger_disp_threshold = self.thresholds.get("detrigger_displacement", trigger_disp_threshold * 0.5)

            # Trigger condition
            if accel_triggered or lvdt_triggered:
                # Pass the maximum displacement found for logging/handling if needed
                return self._handle_event_trigger(sensor_data, current_time, magnitude, max_instantaneous_disp)
            # Detrigger condition (only if currently recording)
            elif self.in_event_recording:
                 # Check if *both* moving averages are below their detrigger thresholds
                 accel_below_detrigger = self.moving_avg_accel < detrigger_accel_threshold
                 disp_below_detrigger = self.moving_avg_disp < detrigger_disp_threshold

                 # If both are below, handle potential end of event
                 if accel_below_detrigger and disp_below_detrigger:
                     return self._handle_event_detrigger(sensor_data, current_time)
                 else:
                     # Still above detrigger, continue recording
                     self.last_trigger_time = current_time # Keep updating last trigger time while above detrigger
                     self.current_event_data.append(sensor_data)
                     return True # Indicate processing happened

            # No trigger and not recording, just buffer
            return True # Indicate processing happened (buffering)


        except Exception as e:
            self.error_count += 1
            if self.error_count >= self.max_errors:
                logging.error(f"Multiple errors in event detection: {e}")
                self.error_count = 0 # Reset after logging
            # Optionally log the specific error
            # logging.exception("Error during event detection:")
            return False # Indicate error occurred

    def _handle_event_trigger(self, sensor_data, current_time, magnitude, displacement):
        """Handle event trigger logic"""
        try:
            self.last_trigger_time = current_time # Update last time a trigger condition was met

            if not self.in_event_recording:
                print(f"\n*** NEW EVENT TRIGGERED at {sensor_data['timestamp']} ***")
                print(f"    Trigger values: Accel Mag={magnitude:.3f}, Max Disp={displacement:.3f}")
                self.in_event_recording = True
                state.set_event_variable("is_event_recording", True)
                state.set_event_variable("last_trigger_time", current_time) # Store initial trigger time
                # Include pre-trigger buffer in the current event data
                self.current_event_data = list(self.pre_trigger_buffer)
                # Ensure the triggering sample is included if not already in buffer
                if sensor_data not in self.current_event_data:
                     self.current_event_data.append(sensor_data)
            else:
                 # Already recording, just append data
                 self.current_event_data.append(sensor_data)

            return True

        except Exception as e:
            logging.error(f"Error in event trigger handling: {e}")
            return False

    def _handle_event_detrigger(self, sensor_data, current_time):
        """Handles the logic when moving averages fall below detrigger thresholds."""
        try:
            self.current_event_data.append(sensor_data) # Add the current sample
            post_trigger_duration = self.thresholds.get("post_event_time", 15.0)

            # Check if enough time has passed since the *last* time a trigger condition was met
            if current_time - self.last_trigger_time >= post_trigger_duration:
                # Calculate event duration based on actual data points and sampling rate
                # Use acceleration rate as it's likely higher or equal
                event_duration_samples = len(self.current_event_data)
                event_duration_time = event_duration_samples * self.config.time_step_acceleration # Approximate duration

                min_duration = self.thresholds.get("min_event_duration", 2.0)

                if event_duration_time >= min_duration:
                    try:
                        # Save the event data
                        event_start_time = self.current_event_data[0]["timestamp"]
                        self._save_event_data(self.current_event_data, event_start_time)
                        print(f"Event complete - duration={event_duration_time:.2f}s")
                    except Exception as e:
                        logging.error(f"Error saving event: {e}")
                else:
                    print(f"Event discarded - duration ({event_duration_time:.2f}s) less than minimum ({min_duration}s)")

                # Reset event state regardless of saving outcome
                self.in_event_recording = False
                self.current_event_data = []
                self.pre_trigger_buffer.clear() # Clear pre-trigger buffer for next event
                state.set_event_variable("is_event_recording", False)
                # Reset moving averages? Optional, maybe better to let them decay naturally
                # self.accel_buffer.clear()
                # self.disp_buffer.clear()
                # self.moving_avg_accel = 0.0
                # self.moving_avg_disp = 0.0

            # If not enough post-trigger time has passed, just continue recording
            return True

        except Exception as e:
            logging.error(f"Error in event detrigger handling: {e}")
            return False

    def event_monitoring_thread(self):
        """Thread function for monitoring events."""
        while self.running_ref:
            try:
                if not self.data_queue:
                    time.sleep(0.001)
                    continue
                    
                sensor_data = self.data_queue.popleft()
                if not self.detect_event(sensor_data):
                    continue
                    
            except Exception as e:
                logging.error(f"Error in monitoring thread: {e}")
                time.sleep(0.1)  # Prevent tight error loop
                
        self._cleanup_on_exit()

    def _cleanup_on_exit(self):
        """Clean up resources when thread exits"""
        try:
            if self.in_event_recording and self.current_event_data:
                self._finalize_event()
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")

    def _save_event_data(self, event_data, start_time):
        """Save event data to CSV file and generate plots."""
        try:
            # Initialize tracking variables
            seen_timestamps = set()
            processed_data = []
            sample_count = 0
            
            # Process each data point
            for data in event_data:
                if 'timestamp' not in data:
                    continue
                    
                if data['timestamp'] not in seen_timestamps:
                    seen_timestamps.add(data['timestamp'])
                    
                    # Add expected time based on sample number
                    expected_time = sample_count * (1.0 / self.config.sampling_rate_acceleration)
                    data['expected_time'] = expected_time
                    processed_data.append(data)
                    sample_count += 1

            if not processed_data:
                logging.error("No valid data to save")
                return False

            # Save processed data
            report_file = processing_analysis.save_event_data(
                event_data=processed_data,
                start_time=start_time,
                config=self.config
            )

            if report_file:
                current_count = self.event_count_ref[0]
                state.set_event_variable("event_count", current_count)
                print(f"Event {current_count} saved successfully to {report_file}")
                return True

            return False

        except Exception as e:
            logging.error(f"Error saving event data: {e}")
            traceback.print_exc()
            return False

    def _generate_plots(self, event_data, event_dir):
        """Generates plots for acceleration and displacement using thread-safe approach."""
        timestamps = []
        accel_magnitudes = []
        displacements = []

        for entry in event_data:
            try:
                timestamps.append(entry["timestamp"])

                accel_magnitude = 0
                if (
                    "sensor_data" in entry
                    and "accel_data" in entry["sensor_data"]
                ):
                    accel = entry["sensor_data"]["accel_data"][0]
                    accel_magnitude = np.sqrt(
                        accel["x"] ** 2 + accel["y"] ** 2 + accel["z"] ** 2
                    )

                displacements_value = 0
                if (
                    "sensor_data" in entry
                    and "lvdt_data" in entry["sensor_data"]
                ):
                    displacements_value = entry["sensor_data"]["lvdt_data"][0]["displacement"]

                accel_magnitudes.append(accel_magnitude)
                displacements.append(displacements_value)

            except KeyError as e:
                logging.error(f"Missing key in event data: {e}")
                continue
            except Exception as e:
                logging.error(f"Error processing data for plotting: {e}")
                continue

        # Check if we have any data to plot
        if not timestamps or not accel_magnitudes or not displacements:
            logging.warning("No data to generate plots.")
            return

        try:
            # Calculate expected timestamps based on acceleration rate
            sample_count = len(timestamps)
            relative_timestamps = [i * self.config.time_step_acceleration for i in range(sample_count)]

            # Use a thread-safe approach without pyplot
            from matplotlib.figure import Figure
            from matplotlib.backends.backend_agg import FigureCanvasAgg as FigureCanvas
            
            # Create acceleration plot
            fig = Figure(figsize=(10, 6))
            canvas = FigureCanvas(fig)
            ax = fig.add_subplot(111)
            ax.plot(relative_timestamps, accel_magnitudes)
            ax.set_title("Acceleration Magnitude vs Time")
            ax.set_xlabel("Time (seconds)")
            ax.set_ylabel("Acceleration (m/s2)")
            ax.grid(True)
            fig.tight_layout()
            fig.savefig(os.path.join(event_dir, "acceleration_plot.png"))
            
            # Create displacement plot with a new figure
            fig = Figure(figsize=(10, 6))
            canvas = FigureCanvas(fig)
            ax = fig.add_subplot(111)
            ax.plot(relative_timestamps, displacements)
            ax.set_title("Displacement vs Time")
            ax.set_xlabel("Time (seconds)")
            ax.set_ylabel("Displacement (mm)")
            ax.grid(True)
            fig.tight_layout()
            fig.savefig(os.path.join(event_dir, "displacement_plot.png"))

        except Exception as e:
            logging.error(f"Error generating plots: {e}")
            traceback.print_exc()

    def _finalize_event(self):
        """Helper method to finalize and save event data."""
        try:
            event_time = self.current_event_data[0]["timestamp"]
            if self._save_event_data(self.current_event_data, event_time):
                # Only increment counter if event was successfully saved
                self.event_count_ref[0] += 1
                state.set_event_variable("event_count", self.event_count_ref[0])
                print(f"Event {self.event_count_ref[0]} successfully recorded and saved")
        except Exception as e:
            print(f"Error saving event: {e}")
        
        # Reset all event state
        self.in_event_recording = False
        self.current_event_data = []
        self.pre_trigger_buffer.clear()
        self.last_detrigger_time = 0
        self.min_duration_met = False
        state.set_event_variable("is_event_recording", False)

def print_event_banner():
    """Print a  banner when the event starts"""
    banner = """
===============================================================================
    Event is starting, please wait...
    Event Monitoring System...
===============================================================================
    """
    print(banner)
    time.sleep(2)  # Pause for 2 seconds