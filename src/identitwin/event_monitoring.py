"""
Event Monitoring Module for IdentiTwin.

Continuously monitors the incoming sensor data stream for significant events
based on configured acceleration and/or displacement thresholds. Implements
a trigger/detrigger mechanism with pre- and post-trigger buffering to capture
complete event waveforms. Detected events are saved and analyzed.

Key Features:
- Real-time event detection using magnitude/displacement thresholds.
- Moving average filters for smoothing sensor readings before thresholding.
- Pre-trigger buffer to capture data leading up to an event.
- Post-trigger recording duration to capture the event's decay.
- Minimum event duration filtering to ignore short transients.
- Thread-based monitoring for non-blocking operation.
- Integration with `processing_analysis` for saving and analyzing event data.
- Shared state management via the `state` module.

Classes:
    EventMonitor: Manages the event detection logic and data buffering.
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
    """
    Monitors sensor data for events based on thresholds and manages event recording.

    Processes data from a queue, applies moving averages, checks against trigger
    and detrigger thresholds, manages data buffering (pre-trigger, event data),
    and initiates saving and analysis of confirmed events. Runs its monitoring
    logic in a separate thread.

    Attributes:
        config: The system configuration object.
        data_queue (deque): Shared queue from which sensor data is read.
        thresholds (dict): Dictionary containing trigger/detrigger thresholds and timing parameters.
        running_ref (callable): A function/lambda returning the system's running state (bool).
        event_count_ref (list): A mutable list containing the shared event count (e.g., [0]).
        event_in_progress (bool): Flag indicating if an event is currently being detected/recorded (internal use).
        event_data_buffer (queue.Queue): Queue to hold completed event data lists before saving (can be used for async saving).
        in_event_recording (bool): Flag indicating if currently recording an event.
        current_event_data (list): Buffer storing data for the event currently being recorded.
        pre_trigger_buffer (deque): Circular buffer storing recent data points before a trigger.
        last_trigger_time (float): Timestamp of the last trigger condition met.
        accel_buffer (deque): Buffer for calculating accelerometer moving average.
        disp_buffer (deque): Buffer for calculating displacement moving average.
        moving_avg_accel (float): Current moving average of acceleration magnitude.
        moving_avg_disp (float): Current moving average of displacement.
        error_count (int): Counter for consecutive errors during detection.
        max_errors (int): Threshold for consecutive errors before logging a warning.
    """

    def __init__(self, config, data_queue, thresholds, running_ref, event_count_ref):
        """
        Initializes the EventMonitor.

        Sets up internal state, buffers, moving average parameters, and references
        to shared objects based on the provided arguments. Initializes event-related
        variables in the shared `state` module.

        Args:
            config: The system configuration object.
            data_queue (deque): The shared deque from which to read sensor data.
            thresholds (dict): A dictionary containing trigger/detrigger thresholds
                               ('acceleration', 'displacement', 'detrigger_acceleration',
                               'detrigger_displacement') and timing parameters
                               ('pre_event_time', 'post_event_time', 'min_event_duration').
            running_ref (callable): A function or lambda that returns True if the main
                                    monitoring system is running, False otherwise.
            event_count_ref (list): A mutable list (e.g., [0]) used as a reference
                                    to the global event counter, allowing this class
                                    to increment it.

        Returns:
            None
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
        """
        Processes a single sensor data point to detect or continue recording an event.

        Updates moving averages, checks if current sensor readings exceed trigger
        thresholds. Manages the state transitions between 'not recording', 'recording',
        and 'event completion'. Handles pre-trigger buffering and post-trigger timing.

        Args:
            sensor_data (dict): A dictionary containing the timestamp and sensor readings
                                for a single time step. Expected format:
                                {'timestamp': datetime, 'sensor_data': {'accel_data': [...], 'lvdt_data': [...]}}

        Returns:
            bool: True if the data point was processed successfully, False if an error
                  occurred or the data was invalid.
        """
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
            instantaneous_disp = 0

            if accel_data and len(accel_data) > 0:
                accel = accel_data[0]
                if all(k in accel for k in ['x', 'y', 'z']):
                    magnitude = np.sqrt(accel["x"]**2 + accel["y"]**2 + accel["z"]**2)
                    self.accel_buffer.append(magnitude)
                    self.moving_avg_accel = np.mean(self.accel_buffer)

            if lvdt_data and len(lvdt_data) > 0:
                instantaneous_disp = abs(lvdt_data[0].get("displacement", 0))
                self.disp_buffer.append(instantaneous_disp)
                self.moving_avg_disp = np.mean(self.disp_buffer)

            # Event detection logic
            trigger_accel = self.thresholds.get("acceleration", 0.981)
            trigger_disp = self.thresholds.get("displacement", 2.0)
            
            accel_trigger = magnitude > trigger_accel
            lvdt_trigger = instantaneous_disp > trigger_disp

            if accel_trigger or lvdt_trigger:
                return self._handle_event_trigger(sensor_data, current_time, magnitude, instantaneous_disp)
            elif self.in_event_recording:
                return self._handle_event_recording(sensor_data, current_time)
                
            return True

        except Exception as e:
            self.error_count += 1
            if self.error_count >= self.max_errors:
                logging.error(f"Multiple errors in event detection: {e}")
                self.error_count = 0
            return False

    def _handle_event_trigger(self, sensor_data, current_time, magnitude, displacement):
        """
        Handles the logic when an event trigger condition is met.

        Sets the `last_trigger_time`. If not already recording, it transitions
        to the recording state, copies the pre-trigger buffer to the current event data,
        updates the shared state, and prints a detection message. Appends the current
        triggering data point to the event buffer.

        Args:
            sensor_data (dict): The sensor data point that caused the trigger.
            current_time (float): The timestamp (`time.time()`) of the trigger.
            magnitude (float): The acceleration magnitude at the trigger time.
            displacement (float): The displacement value at the trigger time.

        Returns:
            bool: True if handled successfully, False otherwise.

        Side Effects:
            - Updates `self.last_trigger_time`.
            - May set `self.in_event_recording` to True.
            - May update 'is_event_recording' and 'last_trigger_time' in the `state` module.
            - May copy data from `self.pre_trigger_buffer` to `self.current_event_data`.
            - Appends `sensor_data` to `self.current_event_data`.
            - May print a message to the console.
        """
        try:
            self.last_trigger_time = current_time
            
            if not self.in_event_recording:
                print(f"\n*** NEW EVENT DETECTED at {sensor_data['timestamp']} ***")
                self.in_event_recording = True
                state.set_event_variable("is_event_recording", True)
                state.set_event_variable("last_trigger_time", current_time)
                self.current_event_data = list(self.pre_trigger_buffer)
            
            self.current_event_data.append(sensor_data)
            return True
            
        except Exception as e:
            logging.error(f"Error in event trigger handling: {e}")
            return False

    def _handle_event_recording(self, sensor_data, current_time):
        """
        Handles logic while an event is actively being recorded.

        Appends the current sensor data to the buffer. Checks if the post-trigger
        duration has elapsed since the last trigger condition. If so, checks if the
        minimum event duration is met. If both conditions are true, it finalizes
        the event by putting the data into the `event_data_buffer`, incrementing
        the event count, initiating the save process, and resetting the recording state.

        Args:
            sensor_data (dict): The current sensor data point during recording.
            current_time (float): The timestamp (`time.time()`) of this data point.

        Returns:
            bool: True if handled successfully, False otherwise.

        Side Effects:
            - Appends `sensor_data` to `self.current_event_data`.
            - May transition `self.in_event_recording` to False.
            - May clear `self.current_event_data` and `self.pre_trigger_buffer`.
            - May update 'is_event_recording' in the `state` module.
            - May call `self._save_event_data`.
            - May increment `self.event_count_ref`.
            - May print messages to the console.
        """
        try:
            self.current_event_data.append(sensor_data)
            post_trigger_time = self.thresholds.get("post_event_time", 15.0)
            
            if current_time - self.last_trigger_time > post_trigger_time:
                event_duration = len(self.current_event_data) * self.config.time_step_acceleration
                min_duration = self.thresholds.get("min_event_duration", 2.0)
                
                if event_duration >= min_duration:
                    try:
                        self.event_data_buffer.put(self.current_event_data)
                        self.event_count_ref[0] += 1
                        event_time = self.current_event_data[0]["timestamp"]
                        self._save_event_data(self.current_event_data, event_time)
                        print(f"Event complete - duration={event_duration:.2f}s")
                    except Exception as e:
                        logging.error(f"Error saving event: {e}")
                
                # Reset event state
                self.in_event_recording = False
                self.current_event_data = []
                self.pre_trigger_buffer.clear()
                state.set_event_variable("is_event_recording", False)
            
            return True
            
        except Exception as e:
            logging.error(f"Error in event recording handling: {e}")
            return False

    def event_monitoring_thread(self):
        """
        Main function for the event monitoring background thread.

        Continuously reads data from the `data_queue`, passes it to `detect_event`
        for processing, and handles potential exceptions. Runs until `self.running_ref()`
        returns False. Calls cleanup logic upon exiting the loop.

        Returns:
            None

        Side Effects:
            - Consumes data from `self.data_queue`.
            - Calls `detect_event` repeatedly.
            - Calls `_cleanup_on_exit` before terminating.
            - Logs errors if exceptions occur.
        """
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
        """
        Performs cleanup actions when the monitoring thread is stopping.

        Specifically, checks if an event was in progress when the thread stopped
        and finalizes/saves it if necessary.

        Returns:
            None

        Side Effects:
            - May call `self._finalize_event`.
            - Logs errors if cleanup fails.
        """
        try:
            if self.in_event_recording and self.current_event_data:
                self._finalize_event()
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")

    def _save_event_data(self, event_data, start_time):
        """
        Processes and saves the data for a completed event.

        Filters out duplicate timestamps, calculates expected relative timestamps,
        and calls `processing_analysis.save_event_data` to handle the actual
        saving of NPZ data, CSV files, analysis, and plotting. Updates the shared
        event count in the `state` module upon successful saving.

        Args:
            event_data (list): The list of sensor data dictionaries for the completed event.
            start_time (datetime): The timestamp of the first data point in the event.

        Returns:
            bool: True if the event was saved and processed successfully, False otherwise.

        Side Effects:
            - Calls `processing_analysis.save_event_data`.
            - May update 'event_count' in the `state` module.
            - Prints success or error messages.
            - Logs errors if exceptions occur.
        """
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
        """
        Generates time-series plots for acceleration magnitude and displacement for an event.

        Extracts relevant data, calculates relative timestamps, and uses Matplotlib's
        object-oriented API (`Figure`, `FigureCanvasAgg`) to create and save plots
        without relying on the global `pyplot` state, making it more suitable for threading.

        Args:
            event_data (list): The list of sensor data dictionaries for the event.
            event_dir (str): The directory where the plot images should be saved.

        Returns:
            None

        Side Effects:
            - Creates 'acceleration_plot.png' and 'displacement_plot.png' in `event_dir`.
            - Logs warnings or errors if plotting fails or data is missing.
        """
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
        """
        Helper method to ensure an event is properly saved and state is reset.

        Called during cleanup or when an event naturally concludes. Calls
        `_save_event_data` and increments the event count if saving is successful.
        Resets all event-related state variables (`in_event_recording`, buffers, etc.)
        and updates the shared 'is_event_recording' state.

        Returns:
            None

        Side Effects:
            - Calls `_save_event_data`.
            - May increment `self.event_count_ref` and update 'event_count' state.
            - Resets internal event state flags and buffers.
            - Updates 'is_event_recording' state.
            - Prints messages or errors.
        """
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
    """
    Prints a simple banner to the console indicating an event is starting.

    Includes a short pause.

    Returns:
        None

    Side Effects:
        - Prints text to standard output.
        - Pauses execution for 2 seconds.
    """
    banner = """
===============================================================================
    Event is starting, please wait...
    Event Monitoring System...
===============================================================================
    """
    print(banner)
    time.sleep(2)  # Pause for 2 seconds