"""
Event monitoring module for the IdentiTwin system.

This module provides real-time monitoring and detection of structural events based on:
- Acceleration thresholds
- Displacement thresholds
- Event duration analysis

Key Features:
- Continuous sensor data monitoring
- Pre-trigger and post-trigger data buffering
- Event data persistence
- Multi-threaded event processing
- Moving average filtering for noise reduction
- Adaptive trigger/detrigger mechanism
"""

import os
import time
import queue
import traceback
import logging
from collections import deque
from datetime import datetime

import numpy as np
import matplotlib
matplotlib.use('Agg')  # Ensure Agg backend for non-interactive environments
import matplotlib.pyplot as plt

from . import state
from . import processing_analysis


class EventMonitor:
    """Monitors events based on sensor data and saves relevant information."""

    def __init__(self, config, data_queue, thresholds, running_ref, event_count_ref):
        """
        Initializes the EventMonitor.

        Args:
            config: The system configuration object.
            data_queue: A deque containing sensor data.
            thresholds: A dictionary of thresholds for event detection.
            running_ref: A shared boolean indicating whether the system is running.
            event_count_ref: A shared integer tracking the number of events.

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

        self.in_event_recording = False
        self.current_event_data = []
        self.pre_trigger_buffer = deque(maxlen=1000)

        # Moving averages
        window_size = int(0.5 * config.sampling_rate_acceleration)
        self.accel_buffer = deque(maxlen=window_size)
        self.disp_buffer = deque(maxlen=10)
        self.moving_avg_accel = 0.0
        self.moving_avg_disp = 0.0

        # Initialize event state
        state.set_event_variable("event_count", event_count_ref[0])
        state.set_event_variable("is_event_recording", False)

        self.error_count = 0
        self.max_errors = 100

    def detect_event(self, sensor_data):
        """
        Detects and records event data using a trigger/detrigger mechanism.

        Args:
            sensor_data: Dictionary containing sensor data, including 'timestamp', 'accel_data', and 'lvdt_data'.

        Returns:
            True if processed successfully, False otherwise.

        Assumptions:
            - Sensor data is in a consistent format.
        """
        if not sensor_data or "sensor_data" not in sensor_data:
            return False

        try:
            self.pre_trigger_buffer.append(sensor_data)
            current_time = time.time()

            accel_data = sensor_data.get("sensor_data", {}).get("accel_data", [])
            lvdt_data = sensor_data.get("sensor_data", {}).get("lvdt_data", [])

            if not accel_data and not lvdt_data:
                return False

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

            trigger_accel = self.thresholds.get("acceleration", 0.981)
            trigger_disp = self.thresholds.get("displacement", 2.0)

            accel_trigger = magnitude > trigger_accel
            lvdt_trigger = instantaneous_disp > trigger_disp

            if accel_trigger or lvdt_trigger:
                return self._handle_event_trigger(sensor_data, current_time)
            elif self.in_event_recording:
                return self._handle_event_recording(sensor_data, current_time)

            return True

        except Exception as e:
            self.error_count += 1
            if self.error_count >= self.max_errors:
                logging.error(f"Multiple errors in event detection: {e}")
                self.error_count = 0
            return False

    def _handle_event_trigger(self, sensor_data, current_time):
        """Handles event trigger logic.

        Args:
            sensor_data: The data that triggered the event.
            current_time: The time the event was triggered.

        Returns:
            True if the trigger was handled successfully, False otherwise.
        """
        try:
            if not self.in_event_recording:
                print(f"\n*** NEW EVENT DETECTED at {sensor_data['timestamp']} ***")
                self.in_event_recording = True
                state.set_event_variable("is_event_recording", True)
                self.current_event_data = list(self.pre_trigger_buffer)

            self.current_event_data.append(sensor_data)
            self.last_trigger_time = current_time
            return True

        except Exception as e:
            logging.error(f"Error in event trigger handling: {e}")
            return False

    def _handle_event_recording(self, sensor_data, current_time):
        """Handles ongoing event recording and checks for completion.

        Args:
            sensor_data: Current sensor data.
            current_time: Current time.

        Returns:
            True if the recording was handled successfully, False otherwise.
        """
        try:
            self.current_event_data.append(sensor_data)
            post_trigger_time = self.thresholds.get("post_event_time", 15.0)

            if current_time - self.last_trigger_time > post_trigger_time:
                event_duration = len(self.current_event_data) * self.config.time_step_acceleration
                min_duration = self.thresholds.get("min_event_duration", 2.0)

                if event_duration >= min_duration:
                    try:
                        event_time = self.current_event_data[0]["timestamp"]
                        self._save_event_data(self.current_event_data, event_time)
                        self.event_count_ref[0] += 1
                        print(f"Event complete - duration={event_duration:.2f}s")
                    except Exception as e:
                        logging.error(f"Error saving event: {e}")

                self._reset_event_state()
            return True

        except Exception as e:
            logging.error(f"Error in event recording handling: {e}")
            return False

    def event_monitoring_thread(self):
        """Thread function for monitoring events."""
        while self.running_ref:
            try:
                sensor_data = self.data_queue.popleft() if self.data_queue else None

                if sensor_data is None:
                    time.sleep(0.001)  # Queue is empty
                    continue

                if not self.detect_event(sensor_data):
                    continue

            except Exception as e:
                logging.error(f"Error in monitoring thread: {e}")
                time.sleep(0.1)  # Prevent tight error loop

        self._cleanup_on_exit()

    def _reset_event_state(self):
        """Resets the event state to prepare for a new event."""
        self.in_event_recording = False
        self.current_event_data = []
        self.pre_trigger_buffer.clear()
        state.set_event_variable("is_event_recording", False)

    def _cleanup_on_exit(self):
        """Cleans up resources when the thread exits."""
        try:
            if self.in_event_recording and self.current_event_data:
                event_time = self.current_event_data[0]["timestamp"]
                self._save_event_data(self.current_event_data, event_time)

        except Exception as e:
            logging.error(f"Error during cleanup: {e}")

    def _save_event_data(self, event_data, start_time):
        """
        Saves event data to a CSV file and generates plots.

        Args:
            event_data: The data associated with the event.
            start_time: The timestamp of the event start.

        Returns:
            True if the event data was saved successfully, False otherwise.

        Assumptions:
            - processing_analysis.save_event_data function exists and properly handles event data saving.
        """
        try:
            processed_data = []
            seen_timestamps = set()

            for data in event_data:
                if 'timestamp' not in data:
                    continue

                if data['timestamp'] not in seen_timestamps:
                    seen_timestamps.add(data['timestamp'])
                    processed_data.append(data)

            if not processed_data:
                logging.error("No valid data to save")
                return False

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
        Generates plots for acceleration and displacement in a thread-safe manner.

        Args:
            event_data: The data to be plotted.
            event_dir: The directory to save the plots.

        Assumptions:
            - The data contains 'timestamp', 'accel_data', and 'lvdt_data'.
        """
        timestamps = []
        accel_magnitudes = []
        displacements = []

        for entry in event_data:
            try:
                timestamps.append(entry["timestamp"])

                accel_magnitude = 0
                if "sensor_data" in entry and "accel_data" in entry["sensor_data"]:
                    accel = entry["sensor_data"]["accel_data"][0]
                    accel_magnitude = np.sqrt(
                        accel["x"] ** 2 + accel["y"] ** 2 + accel["z"] ** 2
                    )

                displacements_value = 0
                if "sensor_data" in entry and "lvdt_data" in entry["sensor_data"]:
                    displacements_value = entry["sensor_data"]["lvdt_data"][0]["displacement"]

                accel_magnitudes.append(accel_magnitude)
                displacements.append(displacements_value)

            except KeyError as e:
                logging.error(f"Missing key in event data: {e}")
                continue
            except Exception as e:
                logging.error(f"Error processing data for plotting: {e}")
                continue

        if not timestamps or not accel_magnitudes or not displacements:
            logging.warning("No data to generate plots.")
            return

        try:
            sample_count = len(timestamps)
            relative_timestamps = [i * self.config.time_step_acceleration for i in range(sample_count)]

            # Use thread-safe approach without pyplot
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


def print_event_banner():
    """Prints a banner when the event starts."""
    banner = """
===============================================================================
    Event is starting, please wait...
    Event Monitoring System...
===============================================================================
    """
    print(banner)
    time.sleep(2)