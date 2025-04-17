"""
System monitoring module for the IdentiTwin system.

This module provides high-level system monitoring functionality including:
- Sensor data acquisition
- Data queue management
- System health monitoring
- Performance tracking
- Status reporting
- Error handling

Key Features:
- Multi-threaded data acquisition
- Real-time sensor monitoring
- Performance statistics tracking
- Automated sensor calibration
- Data buffering and management
- System status reporting
- Error recovery mechanisms

Classes:
    MonitoringSystem: Main class for system-level monitoring

The module serves as the central coordinator for the entire monitoring
system, managing all aspects of data acquisition and system operation.
"""

import os
import csv
import time
import threading
import traceback
import numpy as np
from collections import deque
from datetime import datetime
import logging
import queue
import matplotlib.pyplot as plt # Added import for plt.close

from . import state
from . import processing_data, processing_analysis

# system_monitoring.py
class MonitoringSystem:
    """
    Manages the overall monitoring process for the IdentiTwin system.

    This class orchestrates sensor initialization, data acquisition,
    performance monitoring, event detection, data storage, and system cleanup.
    It utilizes multi-threading for concurrent data acquisition and event processing.

    Attributes:
        config: Configuration object containing system parameters.
        running (bool): Flag indicating if the monitoring system is active.
        data_queue (deque): Queue for storing recent sensor data points.
        acquisition_thread (threading.Thread): Thread responsible for acquiring data.
        event_thread (threading.Thread): Thread responsible for monitoring events.
        event_monitor (EventMonitor): Instance for handling event detection logic.
        sensors_initialized (bool): Flag indicating if sensors have been set up.
        performance_stats (dict): Dictionary holding performance metrics.
        last_lvdt_readings (list): Cache for the most recent LVDT readings.
        csv_file_general (str): Path to the general measurements CSV file.
        csv_file_displacement (str): Path to the LVDT displacement CSV file.
        csv_file_acceleration (str): Path to the accelerometer data CSV file.
        status_led: GPIO LED object for status indication.
        activity_led: GPIO LED object for activity indication.
        ads: ADS1115 ADC object for LVDT readings.
        lvdt_channels: List of ADC channels configured for LVDTs.
        accelerometers: List of accelerometer sensor objects.
        event_count (int): Counter for detected events.
    """

    def __init__(self, config):
        """
        Initializes the MonitoringSystem.

        Sets up initial state, data structures, performance monitoring variables,
        and LVDT reading cache based on the provided configuration.

        Args:
            config: An object containing all necessary configuration parameters
                    (e.g., sensor settings, sampling rates, file paths, thresholds).

        Returns:
            None

        Assumptions:
            - The `config` object is fully populated and valid.
        """
        self.config = config
        self.running = False
        self.data_queue = deque(maxlen=1000)  # Queue for storing acquired data
        self.acquisition_thread = None
        self.event_count = 0
        self.sensors_initialized = False
        self.last_status_time = 0
        self.status_interval = 2.0  # Print status every 2 seconds

        # Add performance monitoring variables
        self.performance_stats = {
            "accel_timestamps": deque(
                maxlen=100
            ),  # Store last 100 acquisition timestamps
            "lvdt_timestamps": deque(
                maxlen=100
            ),  # Store last 100 LVDT timestamps
            "accel_periods": deque(maxlen=99),  # Store periods between acquisitions
            "lvdt_periods": deque(maxlen=99),  # Store periods between LVDT readings
            "last_accel_time": None,
            "last_lvdt_time": None,
            "sampling_rate_acceleration": 0.0,
            "sampling_rate_lvdt": 0.0,
            "accel_jitter": 0.0,
            "lvdt_jitter": 0.0,
        }

        # Cache for last valid LVDT readings
        self.last_lvdt_readings = []
        if (
            config.enable_lvdt
            and hasattr(config, "num_lvdts")
            and config.num_lvdts > 0
        ):
            self.last_lvdt_readings = [
                {"voltage": 0.0, "displacement": 0.0} for _ in range(config.num_lvdts)
            ]

    def setup_sensors(self):
        """
        Initializes and configures hardware sensors based on the system configuration.

        Sets up LEDs for status/activity indication, the ADS1115 ADC for LVDTs
        (if enabled), and the accelerometer sensors (if enabled).

        Returns:
            None

        Raises:
            Exception: If any error occurs during sensor initialization (e.g.,
                       hardware connection issues, configuration errors).

        Side Effects:
            - Initializes hardware components (LEDs, ADC, Accelerometers).
            - Sets the `sensors_initialized` flag to True upon success.
            - Prints error messages and traceback if initialization fails.

        Assumptions:
            - The `config` object contains valid parameters for sensor setup.
        """
        try:
            # Initialize LEDs
            self.status_led, self.activity_led = self.config.initialize_leds()

            # Initialize ADS1115 ADC for LVDTs
            self.ads = self.config.create_ads1115()
            if self.ads:
                self.lvdt_channels = self.config.create_lvdt_channels(self.ads)
            else:
                self.lvdt_channels = None

            # Initialize accelerometers
            self.accelerometers = self.config.create_accelerometers()

            self.sensors_initialized = True
        except Exception as e:
            print(f"Error during sensor setup: {e}")
            traceback.print_exc()

    def initialize_processing(self):
        """
        Sets up data storage mechanisms, primarily CSV files.

        Creates and initializes header rows for the general measurements CSV file,
        and specific CSV files for displacement (LVDT) and acceleration data
        if those sensors are enabled in the configuration.

        Returns:
            None

        Side Effects:
            - Creates CSV files in the directory specified by `config.output_dir`.
            - Writes header rows to the created CSV files.
            - Stores file paths in `self.csv_file_general`, `self.csv_file_displacement`,
              and `self.csv_file_acceleration`.

        Assumptions:
            - `config.output_dir` specifies a writable directory path.
            - Sensor enablement flags (`config.enable_lvdt`, `config.enable_accel`)
              and counts (`config.num_lvdts`, `config.num_accelerometers`) are correctly set.
        """
        # Create general measurements CSV
        self.csv_file_general = os.path.join(
            self.config.output_dir, "general_measurements.csv"
        )
        processing_data.initialize_general_csv(
            num_lvdts=self.config.num_lvdts if self.config.enable_lvdt else 0,
            num_accelerometers=self.config.num_accelerometers
            if self.config.enable_accel
            else 0,
            filename=self.csv_file_general,
        )
        # Create LVDT-specific file if enabled
        if self.config.enable_lvdt:
            self.csv_file_displacement = os.path.join(
                self.config.output_dir, "displacements.csv"
            )
            processing_data.initialize_displacement_csv(
                filename=self.csv_file_displacement
            )
        # Create accelerometer-specific file if enabled
        if self.config.enable_accel:
            self.csv_file_acceleration = os.path.join(
                self.config.output_dir, "acceleration.csv"
            )
            processing_data.initialize_acceleration_csv(
                filename=self.csv_file_acceleration,
                num_accelerometers=self.config.num_accelerometers,
            )

    def start_monitoring(self):
        """
        Starts the main monitoring loop and associated threads.

        Activates the status LED, sets the `running` flag to True, and launches
        the data acquisition thread. If event detection is configured, it also
        initializes and starts the event monitoring thread.

        Returns:
            None

        Side Effects:
            - Turns on the status LED (if available).
            - Sets `self.running` to True.
            - Starts `self.acquisition_thread`.
            - Initializes `self.event_monitor` and starts `self.event_thread` if
              event detection thresholds are configured.
            - Prints an error message if sensors are not initialized first.

        Assumptions:
            - `setup_sensors()` has been called successfully.
            - `initialize_processing()` has been called successfully.
            - The configuration object (`self.config`) contains necessary parameters
              for threading and optional event monitoring.
        """
        if not self.sensors_initialized:
            print("Error: Sensors are not initialized. Call setup_sensors() first.")
            return

        # Turn on status LED if available
        if self.status_led:
            try:
                self.status_led.on()
            except Exception as e:
                print(f"")

        self.running = True
        # Start the data acquisition thread
        self.acquisition_thread = threading.Thread(
            target=self._data_acquisition_thread, daemon=True
        )
        self.acquisition_thread.start()

        # Start event monitoring if configured
        if hasattr(self.config, "trigger_acceleration_threshold") or hasattr(
            self.config, "trigger_displacement_threshold"
        ):
            # Threshold configuration for event detection - modificado para incluir todos los thresholds
            thresholds = {
                "acceleration": self.config.trigger_acceleration_threshold,
                "displacement": self.config.trigger_displacement_threshold,
                "detrigger_acceleration": self.config.detrigger_acceleration_threshold,
                "detrigger_displacement": self.config.detrigger_displacement_threshold,
                "pre_event_time": self.config.pre_trigger_time,
                "post_event_time": self.config.post_trigger_time,
                "min_event_duration": self.config.min_event_duration,
            }

            # Mutable reference for event count
            event_count_ref = [self.event_count]

            # Create instance of event monitor and connect with the data queue
            from . import event_monitoring

            self.event_monitor = event_monitoring.EventMonitor(
                self.config,
                self.data_queue,
                thresholds,
                lambda: self.running,  # Reference to self.running as callable
                event_count_ref,
            )

            # Start the event monitoring thread
            self.event_thread = threading.Thread(
                target=self.event_monitor.event_monitoring_thread, daemon=True
            )
            self.event_thread.start()


    def stop_monitoring(self):
        """
        Stops the monitoring system and all running threads gracefully.

        Sets the `running` flag to False, signals threads to terminate, waits for
        them to join, turns off status/activity LEDs, and updates the final event count.

        Returns:
            None

        Side Effects:
            - Sets `self.running` to False.
            - Joins `self.acquisition_thread` and `self.event_thread` (if running).
            - Turns off status and activity LEDs (if available).
            - Updates `self.event_count` from the event monitor's shared reference.
            - Prints a confirmation message.
        """
        self.running = False

        # Wait for threads to finish
        if self.acquisition_thread and self.acquisition_thread.is_alive():
            self.acquisition_thread.join(timeout=1.0)

        if (
            hasattr(self, "event_thread")
            and self.event_thread
            and self.event_thread.is_alive()
        ):
            self.event_thread.join(timeout=1.0)

        # Turn off LEDs
        if self.status_led:
            self.status_led.off()
        if self.activity_led:
            self.activity_led.off()

        # Update event count from reference
        if hasattr(self, "event_monitor"):
            # Update event count from reference
            self.event_count = self.event_monitor.event_count_ref[0]

        print("Monitoring system stopped.")

    def cleanup(self):
        """
        Performs cleanup operations after monitoring has stopped.

        Ensures monitoring is stopped, closes any open Matplotlib plots, and prints
        a confirmation message.

        Returns:
            None

        Side Effects:
            - Calls `self.stop_monitoring()`.
            - Closes all Matplotlib figures.
            - Prints a confirmation message.
        """
        self.stop_monitoring()
        # Use plt.close directly instead of non-existent visualization.close_all_plots
        plt.close("all")
        print("Resources cleaned up.")

    def wait_for_completion(self):
        """
        Blocks execution until the monitoring process is stopped.

        This method keeps the main thread alive while the data acquisition thread
        is running. It allows the system to run indefinitely until manually
        interrupted (e.g., by Ctrl+C) or stopped via `stop_monitoring()`.

        Returns:
            None

        Handles KeyboardInterrupt:
            Calls `stop_monitoring()` if a KeyboardInterrupt occurs.
        """
        try:
            # Keep waiting while the monitoring thread is active
            while (
                self.running
                and self.acquisition_thread
                and self.acquisition_thread.is_alive()
            ):
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\nMonitoring interrupted by user")
            self.stop_monitoring()

    def _data_acquisition_thread(self):
        """
        Core thread function for acquiring data from enabled sensors.

        This method runs in a loop while `self.running` is True. It precisely times
        the acquisition of data from accelerometers and LVDTs based on configured
        sampling rates, applies calibration, updates performance statistics,
        stores data in the shared queue (`self.data_queue`), writes data to
        respective CSV files, toggles the activity LED, and periodically prints
        status updates. It employs drift compensation logic to maintain accurate
        sampling intervals.

        Returns:
            None

        Side Effects:
            - Continuously reads data from sensors (accelerometers, LVDTs).
            - Appends acquired data to `self.data_queue`.
            - Writes data rows to `self.csv_file_general`, `self.csv_file_acceleration`,
              and `self.csv_file_displacement`.
            - Updates `self.performance_stats`.
            - Toggles the activity LED.
            - Prints status information to the console periodically.
            - Handles potential sensor reading errors gracefully.
            - Prints error messages and traceback if critical errors occur.

        Assumptions:
            - Sensors are initialized and configured correctly.
            - CSV files are initialized.
            - `self.running` flag controls the loop execution.
        """
        try:
            # Initialize timers for precise control
            start_time = time.perf_counter()
            next_acquisition_time = start_time
            next_lvdt_time = start_time
            next_plot_update_time = start_time
            last_print_time = start_time

            # Add intervals based on configuration
            accel_interval = 1.0 / self.config.sampling_rate_acceleration
            lvdt_interval = 1.0 / self.config.sampling_rate_lvdt
            plot_update_interval = 1.0 / self.config.plot_refresh_rate
            stats_interval = 1.0  # Interval for updating statistics (1 second)

            # Initialize performance_stats values
            self.performance_stats["last_accel_time"] = start_time
            self.performance_stats["last_lvdt_time"] = start_time

            # Counters for time drift compensation
            accel_sample_count = 0
            lvdt_sample_count = 0

            while self.running:
                current_time = time.perf_counter()

                # Data structure for this sample
                sensor_data = {"timestamp": datetime.now(), "sensor_data": {}}

                # Accelerometer data acquisition - Strict timing control
                if self.accelerometers and current_time >= next_acquisition_time:
                    # Precise time for acquisition
                    sleep_time = next_acquisition_time - current_time
                    if sleep_time > 0:
                        self._precise_sleep(sleep_time)

                    # Recalculate exact time for next acquisition based on sample count
                    # This avoids cumulative time drift
                    accel_sample_count += 1
                    next_acquisition_time = start_time + (
                        accel_sample_count * accel_interval
                    )

                    # Update performance statistics
                    current_perf_time = time.perf_counter()
                    period = current_perf_time - self.performance_stats["last_accel_time"]

                    if period > 0:
                        self.performance_stats["accel_timestamps"].append(
                            current_perf_time
                        )
                        self.performance_stats["accel_periods"].append(period)
                        self.performance_stats["last_accel_time"] = current_perf_time

                    # Read accelerometer data
                    accel_data = []
                    for i, accel in enumerate(self.accelerometers):
                        try:
                            data = accel.get_accel_data()

                            # Apply calibration using offset and scaling_factor
                            if (hasattr(self.config, "accel_offsets") and i < len(self.config.accel_offsets)):
                                offsets = self.config.accel_offsets[i] # Already are modified with scaling factor
                                scaling_factor = offsets["scaling_factor"]
                                data["x"] = (data["x"] + offsets["x"]) * scaling_factor
                                data["y"] = (data["y"] + offsets["y"]) * scaling_factor
                                data["z"] = (data["z"] + offsets["z"]) * scaling_factor

                            accel_data.append(data)
                        except Exception as e:
                            print(f"Error reading accelerometer {i+1}: {e}")
                            accel_data.append({"x": 0.0, "y": 0.0, "z": 0.0})

                    sensor_data["sensor_data"]["accel_data"] = accel_data

                    # Append accelerometer data to acceleration.csv
                    if self.config.enable_accel:
                        with open(self.csv_file_acceleration, mode="a", newline="") as file:
                            writer = csv.writer(file)
                            for accel in accel_data:
                                magnitude = np.sqrt(accel["x"]**2 + accel["y"]**2 + accel["z"]**2)
                                writer.writerow([
                                    sensor_data["timestamp"].strftime("%Y-%m-%d %H:%M:%S.%f"),
                                    accel["x"],
                                    accel["y"],
                                    accel["z"],
                                    magnitude
                                ])

                # LVDT data acquisition - Similar logic to avoid drift
                if self.lvdt_channels and current_time >= next_lvdt_time:
                    # Precise time for acquisition
                    sleep_time = next_lvdt_time - current_time
                    if sleep_time > 0:
                        self._precise_sleep(sleep_time)

                    # Recalculate exact time for next acquisition based on sample count
                    lvdt_sample_count += 1
                    next_lvdt_time = start_time + (lvdt_sample_count * lvdt_interval)

                    # Update performance statistics
                    current_perf_time = time.perf_counter()
                    period = current_perf_time - self.performance_stats["last_lvdt_time"]

                    if period > 0:
                        self.performance_stats["lvdt_timestamps"].append(current_perf_time)
                        self.performance_stats["lvdt_periods"].append(period)
                        self.performance_stats["last_lvdt_time"] = current_perf_time

                    # Read LVDT data
                    lvdt_data = []
                    for i, channel in enumerate(self.lvdt_channels):
                        try:
                            voltage = channel.voltage
                            # Calculate displacement using calibrated parameters
                            if hasattr(self.config, "lvdt_slope") and hasattr(self.config, "lvdt_intercept"):
                                displacement = self.config.lvdt_slope * voltage + self.config.lvdt_intercept
                            else:
                                print("No LVDT calibration data available")
                                displacement = 0.0
                            
                            lvdt_data.append({
                                "voltage": voltage,
                                "displacement": displacement
                            })
                            
                            # Update cache
                            if i < len(self.last_lvdt_readings):
                                self.last_lvdt_readings[i] = {
                                    "voltage": voltage,
                                    "displacement": displacement
                                }
                        except Exception as e:
                            print(f"Error reading LVDT {i+1}: {e}")
                            lvdt_data.append({"voltage": 0.0, "displacement": 0.0})

                    sensor_data["sensor_data"]["lvdt_data"] = lvdt_data

                    # Append LVDT data to displacement.csv
                    if self.config.enable_lvdt:
                        with open(self.csv_file_displacement, mode="a", newline="") as file:
                            writer = csv.writer(file)
                            for lvdt in lvdt_data:
                                writer.writerow([
                                    sensor_data["timestamp"].strftime("%Y-%m-%d %H:%M:%S.%f"),
                                    lvdt["voltage"],
                                    lvdt["displacement"]
                                ])

                # Append combined data to general_measurements.csv
                with open(self.csv_file_general, mode="a", newline="") as file:
                    writer = csv.writer(file)
                    row = [sensor_data["timestamp"].strftime("%Y-%m-%d %H:%M:%S.%f")]

                    # Add LVDT data
                    if "lvdt_data" in sensor_data["sensor_data"]:
                        for lvdt in sensor_data["sensor_data"]["lvdt_data"]:
                            row.extend([lvdt["voltage"], lvdt["displacement"]])

                    # Add accelerometer data
                    if "accel_data" in sensor_data["sensor_data"]:
                        for accel in sensor_data["sensor_data"]["accel_data"]:
                            magnitude = np.sqrt(accel["x"]**2 + accel["y"]**2 + accel["z"]**2)
                            row.extend([accel["x"], accel["y"], accel["z"], magnitude])

                    writer.writerow(row)

                # Add data to the queue if there is any sensor data
                if sensor_data["sensor_data"]:
                    try:
                        # Use append for deque instead of put for Queue
                        self.data_queue.append(sensor_data)
                    except Exception:
                        # If the queue is full, remove the oldest element
                        if len(self.data_queue) >= self.data_queue.maxlen:
                            self.data_queue.popleft()
                            self.data_queue.append(sensor_data)

                # Activity LED
                if self.activity_led:
                    self.activity_led.toggle()

                # Update performance statistics periodically
                if current_time - last_print_time >= stats_interval:
                    self._update_performance_stats()
                    self._print_status(sensor_data)

                    # Display tracking info for debugging
                    sampling_rate_acceleration = self.performance_stats["sampling_rate_acceleration"]
                    if (
                        sampling_rate_acceleration < 95.0 or sampling_rate_acceleration > 105.0
                    ):  # 5% tolerance
                        drift = abs(
                            sampling_rate_acceleration - self.config.sampling_rate_acceleration
                        )

                        # Recalibrate the acquisition interval if the deviation is significant
                        if drift > 10.0:  # More than 10 Hz offset
                            # Reset acquisition timers to fix drift
                            start_time = time.perf_counter()
                            accel_sample_count = 0
                            lvdt_sample_count = 0
                            next_acquisition_time = start_time
                            next_lvdt_time = start_time
                            print(
                                "Resetting acquisition timers to fix drift"
                            )

                    last_print_time = current_time

                # Small CPU break if we are far ahead
                if (next_acquisition_time - time.perf_counter()) > 0.001:
                    time.sleep(0.001)  # 1 microsecond

        except Exception as e:
            print(f"Error in data acquisition thread: {e}")
            traceback.print_exc()

    def _precise_sleep(self, sleep_time):
        """
        Implements a high-precision sleep function.

        Uses a combination of `time.sleep()` for longer durations and busy-waiting
        (`while time.perf_counter() < target: pass`) for the final milliseconds
        to achieve more accurate timing than `time.sleep()` alone, especially for
        short intervals.

        Args:
            sleep_time (float): The desired sleep duration in seconds.

        Returns:
            None
        """
        if sleep_time <= 0:
            return

        # For very short intervals (< 1ms), use active waiting only
        if (sleep_time < 0.001):
            target = time.perf_counter() + sleep_time
            while time.perf_counter() < target:
                pass
            return

        # For longer intervals, use a combination
        # Sleep until near the target time and then active waiting
        # Leaving 0.5ms for active waiting is sufficient on most systems
        time.sleep(sleep_time - 0.0005)
        target = time.perf_counter() + 0.0005
        while time.perf_counter() < target:
            pass

    def _update_performance_stats(self):
        """
        Calculates and updates performance metrics like sampling rate and jitter.

        Analyzes the timestamps of recent accelerometer and LVDT readings stored
        in `self.performance_stats` to compute the actual average sampling rate
        and the standard deviation of the sampling periods (jitter).

        Returns:
            None

        Side Effects:
            - Updates the `sampling_rate_acceleration`, `accel_jitter`,
              `sampling_rate_lvdt`, and `lvdt_jitter` keys within
              `self.performance_stats`.
        """
        # Calculate accelerometer performance
        if len(self.performance_stats["accel_periods"]) > 1:
            periods = np.array(self.performance_stats["accel_periods"])
            mean_period = np.mean(periods)

            # Ensure mean_period is greater than zero to avoid division by zero
            if mean_period > 0:
                self.performance_stats["sampling_rate_acceleration"] = 1.0 / mean_period
                self.performance_stats["accel_jitter"] = (
                    np.std(periods) * 1000
                )  # Convert to ms
            else:
                self.performance_stats["sampling_rate_acceleration"] = 0
                self.performance_stats["accel_jitter"] = 0

        # Calculate LVDT performance
        if len(self.performance_stats["lvdt_periods"]) > 1:
            periods = np.array(self.performance_stats["lvdt_periods"])
            mean_period = np.mean(periods)

            # Ensure mean_period is greater than zero to avoid division by zero
            if mean_period > 0:
                self.performance_stats["sampling_rate_lvdt"] = 1.0 / mean_period
                self.performance_stats["lvdt_jitter"] = (
                    np.std(periods) * 1000
                )  # Convert to ms
            else:
                self.performance_stats["sampling_rate_lvdt"] = 0
                self.performance_stats["lvdt_jitter"] = 0

    def _print_status(self, sensor_data):
        """
        Prints a formatted status update to the console.

        Displays the current time, performance statistics (sampling rates, jitter),
        the latest readings from LVDTs and accelerometers (using provided or cached data),
        the number of detected events, and the current event recording status.

        Args:
            sensor_data (dict): A dictionary containing the most recent sensor readings
                                for this cycle. Expected keys: 'timestamp', 'sensor_data'
                                (which contains 'accel_data' and/or 'lvdt_data').

        Returns:
            None

        Side Effects:
            - Prints formatted information to standard output.
            - Synchronizes the event count between the `EventMonitor` instance and the
              shared `state` module if discrepancies are found.

        Assumptions:
            - `self.performance_stats` contains up-to-date performance data.
            - `self.last_lvdt_readings` provides cached LVDT data if current data is missing.
            - The `state` module and `EventMonitor` (if active) provide event status.
        """
        print("\n============================ System Status Update =============================\n")
        print(f"Time: {datetime.now().strftime('%H:%M:%S')}")

        # Print performance stats
        print("Performance:")
        if self.config.enable_accel:
            print(
                f"  Accel Rate: {self.performance_stats['sampling_rate_acceleration']:.2f} Hz (Target: {self.config.sampling_rate_acceleration:.1f} Hz)"
            )
            print(
                f"  Accel Jitter: {self.performance_stats['accel_jitter']:.2f} ms"
            )

        if self.config.enable_lvdt:
            print(
                f"  LVDT Rate: {self.performance_stats['sampling_rate_lvdt']:.2f} Hz (Target: {self.config.sampling_rate_lvdt:.1f} Hz)"
            )
            print(
                f"  LVDT Jitter: {self.performance_stats['lvdt_jitter']:.2f} ms"
            )

        # Print LVDT status
        if self.config.enable_lvdt:
            print("\nLVDT Status:\n")
            lvdt_data = sensor_data.get("sensor_data", {}).get("lvdt_data", [])
            if lvdt_data:  # If we have current data
                for i, lvdt in enumerate(lvdt_data):
                    print(
                        f"  LVDT{i+1}: {lvdt['displacement']:.3f}mm ({lvdt['voltage']:.3f}V)"
                    )
            else:  # Use cached data if no current data
                for i, reading in enumerate(self.last_lvdt_readings):
                    print(
                        f"  LVDT{i+1}: {reading['displacement']:.3f}mm ({reading['voltage']:.3f}V)"
                    )

        # Print accelerometer status
        if self.config.enable_accel:
            print("\nAccelerometer Status:\n")
            accel_data = sensor_data.get("sensor_data", {}).get("accel_data", [])
            if accel_data:
                for i, accel in enumerate(accel_data):
                    magnitude = np.sqrt(accel["x"] ** 2 + accel["y"] ** 2 + accel["z"] ** 2)
                    print(
                        f"  Accel{i+1}: {magnitude:.3f} [X:{accel['x']:.3f}, Y:{accel['y']:.3f}, Z:{accel['z']:.3f}]"
                    )
            else:
                print("  No accelerometer data available")

        # Get event count from both state and monitor
        event_count = self.event_monitor.event_count_ref[0] if hasattr(self, 'event_monitor') else 0
        state_event_count = state.get_event_variable("event_count", 0)
        
        # Use the higher of the two counts to ensure we don't miss any
        current_event_count = max(event_count, state_event_count)
        print(f"\nEvents detected: {current_event_count}")
        
        # Resync counts if they differ
        if event_count != state_event_count:
            state.set_event_variable("event_count", current_event_count)
            if hasattr(self, 'event_monitor'):
                self.event_monitor.event_count_ref[0] = current_event_count

        # Print event count and monitoring status
        is_recording = state.get_event_variable("is_event_recording", False)
        formatted_time = "Not recording"
        if is_recording:
            last_trigger_time = state.get_event_variable("last_trigger_time")
            if last_trigger_time:
                elapsed = time.time() - last_trigger_time
                formatted_time = self._format_elapsed_time(elapsed)
        print(f"Recording Status: {formatted_time}")

        # Fix format specifier error and use consistent names
        if hasattr(self, "event_monitor"):
            if hasattr(self.event_monitor, "moving_avg_accel"):
                print(f"Acceleration Moving Average: {self.event_monitor.moving_avg_accel:.3f} (detrigger: {self.config.detrigger_acceleration_threshold:.3f}m/s2)")
            else:
                print(f"Acceleration Moving Average: N/A (detrigger: {self.config.detrigger_acceleration_threshold:.3f}m/s2)")
            if hasattr(self.event_monitor, "moving_avg_disp"):
                print(f"Displacement Moving Average: {self.event_monitor.moving_avg_disp:.3f} (detrigger: {self.config.detrigger_displacement_threshold:.3f}mm)")
            else:
                print(f"Displacement Moving Average: N/A (detrigger: {self.config.detrigger_displacement_threshold:.3f}mm)")

        print("\n===============================================================================")
        print("====================== `Ctrl + C` to finish monitoring ========================\n \n")

    def _format_elapsed_time(self, elapsed_seconds):
        """
        Formats a duration in seconds into a human-readable string (D H M S).

        Args:
            elapsed_seconds (float): The total number of seconds.

        Returns:
            str: A formatted string representing the duration (e.g., "1d 2h 3m 4s",
                 "5h 10m 30s", "15m 0s", "45s").
        """
        minutes, seconds = divmod(int(elapsed_seconds), 60)
        hours, minutes = divmod(minutes, 60)
        days, hours = divmod(hours, 24)

        if days > 0:
            return f"{days}d {hours}h {minutes}m {seconds}s"
        elif hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"