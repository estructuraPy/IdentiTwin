"""Event detection and monitoring module for the IdentiTwin system.

Provides the `EventMonitor` class which runs in a separate thread, continuously
analyzing sensor data from a queue to detect structural events based on
configurable acceleration and displacement thresholds.

Key Features:
    - Real-time event detection using trigger and detrigger thresholds.
    - Pre-event data buffering (`pre_trigger_buffer`).
    - Post-event data recording duration (`post_event_time`).
    - Minimum event duration enforcement (`min_event_duration`).
    - Moving average calculation for detriggering logic.
    - Spawning background threads for saving event data and generating analysis
      to avoid blocking the main monitoring loop.
    - Thread-safe state updates using the `state` module.
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
import threading

from . import state
from .processing_data import read_lvdt_data
from . import processing_analysis

# event_monitoring.py
class EventMonitor:
    """Monitors sensor data queue for events and manages event recording.

    Detects events based on thresholds, manages data buffering (pre-trigger,
    during event, post-trigger), and triggers background saving and analysis
    of event data.

    Attributes:
        config (SystemConfig or SimulatorConfig): System configuration object.
        data_queue (deque): Queue holding incoming sensor data packets from the
            main acquisition thread.
        thresholds (dict): Dictionary containing trigger/detrigger thresholds and
            timing parameters (pre/post event time, min duration).
        running_ref (bool): Reference to the main system running flag (controls thread loop).
        event_count_ref (list[int]): Mutable reference (list containing one int)
            to the global event counter, allowing updates.
        event_in_progress (bool): Flag indicating if an event is currently being detected
            (trigger condition met). (Note: `in_event_recording` seems more actively used).
        event_data_buffer (queue.Queue): Intermediate buffer (currently unused, potentially
            for decoupling detection and saving).
        in_event_recording (bool): Flag indicating if the system is actively recording
            an event (triggered and not yet finalized).
        current_event_data (list): Buffer storing data for the event currently being recorded.
        pre_trigger_buffer (deque): Circular buffer storing recent data before a trigger.
        last_trigger_time (float): Timestamp of the last time a trigger condition was met.
        accel_buffer (deque): Buffer for calculating moving average of acceleration magnitude.
        disp_buffer (deque): Buffer for calculating moving average of displacement.
        moving_avg_accel (float): Current moving average of acceleration magnitude.
        moving_avg_disp (float): Current moving average of displacement.
        error_count (int): Counter for consecutive errors during event detection.
        max_errors (int): Threshold for logging repeated errors.
        finalize_thread_started (bool): Flag to prevent multiple saving threads for one event.
        event_start_ts (datetime or None): Timestamp when the current event was triggered.
    """

    def __init__(self, config, data_queue, thresholds, running_ref, event_count_ref):
        """Initializes the EventMonitor.

        Args:
            config (SystemConfig or SimulatorConfig): The system configuration object.
            data_queue (deque): The queue from which to read sensor data packets.
            thresholds (dict): Event detection thresholds and timing parameters.
            running_ref (bool): A reference to the main system running flag.
            event_count_ref (list[int]): A mutable reference (list) to the event counter.
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
        # Calculate pre_trigger_buffer size based on MEASURED config rate
        # Ensure sampling rate is positive before calculating buffer size
        accel_rate = config.sampling_rate_acceleration
        if accel_rate <= 0:
            print("Warning: Accelerometer sampling rate is zero or negative. Using default pre-trigger buffer size.")
            pre_trigger_samples = 1000 # Default size if rate is invalid
        else:
            pre_trigger_samples = int(config.pre_event_time * accel_rate) # Use measured rate

        self.pre_trigger_buffer = deque(maxlen=pre_trigger_samples)
        self.last_trigger_time = 0

        if accel_rate > 0:
             window_size_accel = int(0.5 * accel_rate) # 0.5 seconds of samples
        else:
             window_size_accel = 100 # Default if rate invalid
        lvdt_rate = config.sampling_rate_lvdt
        if lvdt_rate > 0:
             window_size_lvdt = int(0.5 * lvdt_rate)
        else:
             window_size_lvdt = 5 # Default if rate invalid

        self.accel_buffer = deque(maxlen=max(1, window_size_accel)) # Ensure maxlen >= 1
        self.disp_buffer = deque(maxlen=max(1, window_size_lvdt)) # Ensure maxlen >= 1
        self.moving_avg_accel = 0.0
        self.moving_avg_disp = 0.0

        # Initialize event count in state with current value
        state.set_event_variable("event_count", event_count_ref[0])
        state.set_event_variable("is_event_recording", False)
        
        self.error_count = 0
        self.max_errors = 100  # Maximum number of consecutive errors before warning
        self.finalize_thread_started = False  # Prevent multiple thread launches
        self.event_start_ts = None  # Store trigger timestamp

    def detect_event(self, sensor_data):
        """Analyzes a sensor data packet to detect event trigger/detrigger conditions.

        Appends data to the pre-trigger buffer. Calculates current acceleration
        magnitudes and displacements. Updates moving average buffers. Compares
        sensor readings and moving averages against trigger/detrigger thresholds.
        Calls helper methods (`_handle_event_trigger`, `_handle_event_recording`)
        based on the detection logic.

        Args:
            sensor_data (dict): A dictionary containing the latest sensor readings
                (timestamp, sensor_data: {accel_data, lvdt_data}).

        Returns:
            bool: True if the system should continue processing data (e.g., event
                  triggered or ongoing), False if processing should pause (e.g.,
                  event ended and saving started). Returns False on error.
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
            accel_magnitudes = []
            disp_values = []

            # Calculate magnitudes for all accelerometers
            for accel in accel_data:
                if all(k in accel for k in ['x', 'y', 'z']):
                    mag = np.sqrt(accel["x"]**2 + accel["y"]**2 + accel["z"]**2)
                    accel_magnitudes.append(mag)
            # Calculate displacements for all LVDTs
            for lvdt in lvdt_data:
                disp = abs(lvdt.get("displacement", 0))
                disp_values.append(disp)

            # Update buffers for moving averages (optional, can use first sensor as before)
            if accel_magnitudes:
                self.accel_buffer.append(accel_magnitudes[0])
                self.moving_avg_accel = np.mean(self.accel_buffer)
            if disp_values:
                self.disp_buffer.append(disp_values[0])
                self.moving_avg_disp = np.mean(self.disp_buffer)

            # Event detection logic (multi-sensor, multi-channel)
            trigger_accel = self.thresholds.get("acceleration", 0.981)
            trigger_disp = self.thresholds.get("displacement", 2.0)
            detrigger_accel = self.thresholds.get("detrigger_acceleration", trigger_accel * 0.5)
            detrigger_disp = self.thresholds.get("detrigger_displacement", trigger_disp * 0.5)

            # Check if any sensor is above trigger threshold
            accel_trigger = any(mag > trigger_accel for mag in accel_magnitudes)
            lvdt_trigger = any(disp > trigger_disp for disp in disp_values)

            # Use moving averages to determine detrigger
            accel_below_detrigger = self.moving_avg_accel < detrigger_accel
            lvdt_below_detrigger = self.moving_avg_disp < detrigger_disp
            # --- fin del cambio ---

            # Start event if any sensor triggers
            if accel_trigger or lvdt_trigger:
                return self._handle_event_trigger(sensor_data, current_time, accel_magnitudes, disp_values)
            # Stop event only if all sensors are below detrigger
            elif self.in_event_recording and accel_below_detrigger and lvdt_below_detrigger:
                return self._handle_event_recording(sensor_data, current_time)
            # If still in event, keep recording
            elif self.in_event_recording:
                self.current_event_data.append(sensor_data)
                return True
            return True

        except Exception as e:
            self.error_count += 1
            if self.error_count >= self.max_errors:
                logging.error(f"Multiple errors in event detection: {e}")
                self.error_count = 0
            return False

    def _handle_event_trigger(self, sensor_data, current_time, accel_magnitudes, disp_values):
        """Handles the logic when an event trigger condition is met.

        Sets the `last_trigger_time`. If not already recording, it marks the
        start of a new event: sets `in_event_recording` to True, updates global
        state, copies the `pre_trigger_buffer` to `current_event_data`, stores
        the trigger timestamp (`event_start_ts`), and prints a notification.
        Appends the triggering data point to `current_event_data`.

        Args:
            sensor_data (dict): The sensor data packet that caused the trigger.
            current_time (float): The current time (`time.time()`).
            accel_magnitudes (list[float]): List of current acceleration magnitudes.
            disp_values (list[float]): List of current absolute displacements.

        Returns:
            bool: True if handled successfully, False on error.
        """
        try:
            self.last_trigger_time = current_time
            
            if not self.in_event_recording:
                print(f"\n*** NEW EVENT DETECTED at {sensor_data['timestamp']} ***")
                self.in_event_recording = True
                state.set_event_variable("is_event_recording", True)
                state.set_event_variable("last_trigger_time", current_time)
                # Initialize current_event_data with the full pre_trigger_buffer content
                self.current_event_data = list(self.pre_trigger_buffer) 
                self.event_start_ts = sensor_data["timestamp"]  # Store trigger timestamp
            
            # Append the triggering data point if it's not already the last one from the buffer
            if not self.current_event_data or sensor_data != self.current_event_data[-1]:
                 self.current_event_data.append(sensor_data)
            return True
            
        except Exception as e:
            logging.error(f"Error in event trigger handling: {e}")
            return False

    def _handle_event_recording(self, sensor_data, current_time):
        """Handles logic while an event is actively being recorded.

        Appends the current `sensor_data` to `current_event_data`. Checks if the
        `post_event_time` duration has elapsed since the `last_trigger_time`.
        If the duration is met and a saving thread hasn't started yet, it copies
        the `current_event_data`, sets `finalize_thread_started` to True, and
        launches the `_finalize_record_event` method in a new background thread
        to handle saving and analysis.

        Args:
            sensor_data (dict): The current sensor data packet.
            current_time (float): The current time (`time.time()`).

        Returns:
            bool: False, indicating that the main event loop should pause processing
                  while the event is finalized in the background. Returns False on error.
        """
        try:
            self.current_event_data.append(sensor_data)
            post_trigger_time = self.thresholds.get("post_event_time", 15.0)

            # Only when post_event_time is met and background thread not started
            if (current_time - self.last_trigger_time > post_trigger_time
                    and not self.finalize_thread_started):
                data_to_save = list(self.current_event_data)
                start_ts = self.event_start_ts  # Use trigger timestamp

                # Mark that the thread has been started and prevent further launches
                self.finalize_thread_started = True

                # Launch daemon thread to save and plot
                threading.Thread(
                    target=self._finalize_record_event,
                    args=(data_to_save, start_ts),
                    daemon=True
                ).start()

            # Do not process more data during post-event
            return False  
        except Exception as e:
            logging.error(f"Error in event recording handling: {e}")
            traceback.print_exc()
            return False

    def _finalize_record_event(self, complete_event_data, start_time):
        """Runs in a background thread to save and analyze completed event data.

        Waits a brief moment, then calls `_save_event_data` to process and save
        the collected data. If saving is successful, increments the event counter
        (both local reference and global state). Finally, resets the event recording
        state (`in_event_recording`, `finalize_thread_started`, `event_start_ts`)
        to allow detection of new events.

        Args:
            complete_event_data (list): The complete data buffer for the event.
            start_time (datetime): The timestamp when the event was triggered.
        """
        try:
            time.sleep(0.5)  # extra margin

            # ...existing code to drain buffer and collect data...

            # Save and generate reports/plots
            saved = self._save_event_data(complete_event_data, start_time)
            if saved:
                self.event_count_ref[0] += 1
                state.set_event_variable("event_count", self.event_count_ref[0])

        except Exception as e:
            logging.error(f"Error in background finalize: {e}")
            traceback.print_exc()
        finally:
            # Now reset state after completing save
            self.in_event_recording = False
            state.set_event_variable("is_event_recording", False)
            self.finalize_thread_started = False  # Allow new future event
            self.event_start_ts = None  # Reset start timestamp

    def event_monitoring_thread(self):
        """Main loop for the event monitoring thread.

        Continuously reads sensor data packets from the `data_queue` (if available)
        and passes them to `detect_event` as long as the `running_ref` flag is True.
        Includes error handling and a small sleep to prevent busy-waiting. Calls
        `_cleanup_on_exit` when the loop terminates.
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
        """Performs cleanup actions when the monitoring thread stops.

        If an event was in progress when the thread stopped, it calls
        `_finalize_event` to ensure the partially recorded data is saved.
        """
        try:
            if self.in_event_recording and self.current_event_data:
                self._finalize_event()
        except Exception as e:
            logging.error(f"Error during cleanup: {e}")

    def _save_event_data(self, event_data, start_time):
        """Passes event data to the analysis module for saving and processing.

        Calls `processing_analysis.save_event_data` to handle the creation of
        event folders, NPZ files, CSV files, plots, and reports.

        Args:
            event_data (list): The complete data buffer for the event.
            start_time (datetime): The timestamp when the event was triggered.

        Returns:
            bool: True if the data was successfully passed to the saving function
                  (doesn't guarantee saving completed without errors), False if
                  an error occurred before calling the saving function or if
                  `event_data` was empty.
        """
        try:
            # Pass the original event_data directly
            if not event_data:
                 logging.error("No event data to save.")
                 return False

            report_file = processing_analysis.save_event_data(
                event_data=event_data, # Pass original data
                start_time=start_time,
                config=self.config
            )

            if report_file:
                current_count = self.event_count_ref[0] # Read current count
                # Incrementing is handled in _finalize_record_event after successful save
                # state.set_event_variable("event_count", current_count) # State updated in _finalize_record_event
                print(f"Event {current_count + 1} data passed for saving. Report: {report_file}") # Log passing data
                return True # Indicate success passing data

            return False # Indicate failure passing data

        except Exception as e:
            logging.error(f"Error preparing event data for saving: {e}") # Changed error message context
            traceback.print_exc()
            return False

    def _generate_plots(self, event_data, event_dir):
        """Generates acceleration and displacement plots for an event.

        Deprecated/Potentially Unused: Plot generation is now primarily handled
        within `processing_analysis.create_analysis_plots`. This function uses
        a thread-safe Matplotlib approach (`FigureCanvasAgg`) but might be redundant.

        Args:
            event_data (list): The event data buffer.
            event_dir (str): The directory where plots should be saved.
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
            # Use the MEASURED acceleration rate from config
            accel_rate = self.config.sampling_rate_acceleration
            if accel_rate > 0:
                time_step = 1.0 / accel_rate
                relative_timestamps = [i * time_step for i in range(sample_count)]
            else:
                logging.warning("Cannot calculate relative timestamps due to invalid acceleration rate.")
                relative_timestamps = list(range(sample_count)) # Fallback to sample index


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
        """Helper method to finalize and save event data, and reset state.

        Calls `_save_event_data`. If successful, increments the event counter.
        Resets all event-related state variables (`in_event_recording`,
        `current_event_data`, `pre_trigger_buffer`, etc.) regardless of
        saving success.

        Note: Similar logic exists in `_finalize_record_event`. Consolidating
        might be beneficial.
        """
        try:
            event_time = self.event_start_ts  # Use trigger timestamp
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
        self.event_start_ts = None  # Reset start timestamp

def print_event_banner():
    """Prints a simple banner to the console indicating an event is starting."""
    banner = """
===============================================================================
    Event is starting, please wait...
    Event Monitoring System...
===============================================================================
    """
    print(banner)
    time.sleep(2)  # Pause for 2 seconds