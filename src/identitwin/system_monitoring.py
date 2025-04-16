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

from . import state
from . import processing_data, processing_analysis

# system_monitoring.py
class MonitoringSystem:
    """
    System-level monitoring class for the IdentiTwin system.
    Handles sensor setup, data acquisition, and system-level operations.
    """

    def __init__(self, config):
        """
        Initialize the monitoring system with the provided configuration.

        Args:
            config: Configuration object for the system.

        Returns:
            None

        Assumptions:
            - The configuration object (config) is properly initialized and contains necessary parameters.
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
        Set up sensors based on the configuration.
        Initializes LVDTs, accelerometers, and LEDs.

        Returns:
            None

        Assumptions:
            - The configuration object contains the necessary information to initialize sensors.
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
        Initialize data processing and CSV file creation.
        Creates CSV files and plot variables necessary for data storage and visualization.

        Returns:
            None

        Assumptions:
            - Configuration object is properly initialized and contains necessary parameters
              such as output directory, number of LVDTs/accelerometers, sampling rates, etc.
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
        Start the monitoring system.
        Initializes threads for data acquisition and starts hardware components.

        Returns:
            None

        Assumptions:
            - Sensors are initialized before calling this method.
            - Configuration includes necessary parameters.
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
        Stop the monitoring system.
        Terminates threads and turns off LEDs.

        Returns:
            None
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
            try:
                self.status_led.off()
            except Exception as e:
                print(f"Error turning off Status LED: {e}")
        if self.activity_led:
            try:
                self.activity_led.off()
            except Exception as e:
                print(f"Error turning off Activity LED: {e}")

        # Update event count from reference
        if hasattr(self, "event_monitor"):
            # Update event count from reference
            self.event_count = self.event_monitor.event_count_ref[0]

        print("Monitoring system stopped.")

    def cleanup(self):
        """
        Clean up resources used by the monitoring system.
        Closes plots and releases hardware resources.

        Returns:
            None
        """
        print("Initiating cleanup...") # Add print statement
        self.stop_monitoring()

        # Explicitly close LEDs if they exist
        if hasattr(self, 'status_led') and self.status_led:
            try:
                self.status_led.close()
                print("Status LED closed.")
            except Exception as e:
                print(f"Error closing status LED: {e}")
            finally:
                 self.status_led = None # Ensure reference is removed

        if hasattr(self, 'activity_led') and self.activity_led:
            try:
                self.activity_led.close()
                print("Activity LED closed.")
            except Exception as e:
                print(f"Error closing activity LED: {e}")
            finally:
                 self.activity_led = None # Ensure reference is removed

        # Close plots if matplotlib is used directly here (unlikely now)
        # Use plt.close directly instead of non-existent visualization.close_all_plots
        # Check if plt was imported and might have figures open
        try:
            import matplotlib.pyplot as plt
            plt.close("all")
            print("Closed plot windows.")
        except ImportError:
            pass # Matplotlib might not be used directly
        except Exception as e:
            print(f"Error closing plot windows: {e}")


        print("Resources cleaned up.")

    def wait_for_completion(self):
        """
        Wait for monitoring to complete (blocks until interrupted).

        Returns:
            None
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
        Thread for data acquisition from sensors.
        Collects data from LVDTs and accelerometers and stores it in the queue and CSV files.

        Returns:
            None
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
                data_acquired_this_cycle = False # Flag to check if any data was read

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
                    data_acquired_this_cycle = True

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
                            displacement = np.nan # Default to NaN
                            # Apply calibration using per-channel parameters
                            if (hasattr(self.config, "lvdt_calibration_params") and
                                i < len(self.config.lvdt_calibration_params) and
                                self.config.lvdt_calibration_params[i] is not None):
                                cal_params = self.config.lvdt_calibration_params[i]
                                slope = cal_params.get('lvdt_slope', 19.86) # Use default if missing
                                intercept = cal_params.get('lvdt_intercept', 0.0) # Use default if missing
                                displacement = slope * voltage + intercept
                            else:
                                # Print warning only once if calibration is missing
                                if not hasattr(self, '_lvdt_cal_warning_printed'):
                                    print(f"Warning: LVDT {i+1} calibration data missing or incomplete. Displacement calculation might be incorrect.")
                                    self._lvdt_cal_warning_printed = True
                                # Fallback to default if no calibration params available at all
                                if hasattr(self.config, "lvdt_slope"):
                                     displacement = self.config.lvdt_slope * voltage + self.config.lvdt_intercept


                            lvdt_reading = {"voltage": voltage, "displacement": displacement}
                            lvdt_data.append(lvdt_reading)

                            # Update cache only if displacement is not NaN
                            if i < len(self.last_lvdt_readings) and not np.isnan(displacement):
                                self.last_lvdt_readings[i] = lvdt_reading

                        except Exception as e:
                            print(f"Error reading LVDT {i+1}: {e}")
                            # Append placeholder data on error
                            lvdt_data.append({"voltage": np.nan, "displacement": np.nan})

                    if lvdt_data: # Only add if we got some data (even NaNs)
                        sensor_data["sensor_data"]["lvdt_data"] = lvdt_data
                        data_acquired_this_cycle = True

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

                # Append combined data to general_measurements.csv only if data was acquired
                if data_acquired_this_cycle:
                    # ... (CSV writing logic - ensure it handles potential NaNs gracefully, e.g., write empty strings or 'NaN') ...
                    # Example modification for CSV writing:
                    with open(self.csv_file_general, mode="a", newline="") as file:
                        writer = csv.writer(file)
                        row = [sensor_data["timestamp"].strftime("%Y-%m-%d %H:%M:%S.%f")]

                        # Add LVDT data (handle missing/NaN)
                        num_lvdt_expected = self.config.num_lvdts if self.config.enable_lvdt else 0
                        lvdt_list = sensor_data.get("sensor_data", {}).get("lvdt_data", [])
                        for i in range(num_lvdt_expected):
                            if i < len(lvdt_list) and lvdt_list[i] is not None:
                                volt = lvdt_list[i].get('voltage', '')
                                disp = lvdt_list[i].get('displacement', '')
                                row.extend([f"{volt:.6f}" if isinstance(volt, (int, float)) and not np.isnan(volt) else '',
                                            f"{disp:.6f}" if isinstance(disp, (int, float)) and not np.isnan(disp) else ''])
                            else:
                                row.extend(['', '']) # Placeholder for missing LVDT

                        # Add accelerometer data (handle missing/NaN)
                        num_accel_expected = self.config.num_accelerometers if self.config.enable_accel else 0
                        accel_list = sensor_data.get("sensor_data", {}).get("accel_data", [])
                        for i in range(num_accel_expected):
                             if i < len(accel_list) and accel_list[i] is not None:
                                 x = accel_list[i].get('x', '')
                                 y = accel_list[i].get('y', '')
                                 z = accel_list[i].get('z', '')
                                 if isinstance(x, (int, float)) and not np.isnan(x) and \
                                    isinstance(y, (int, float)) and not np.isnan(y) and \
                                    isinstance(z, (int, float)) and not np.isnan(z):
                                     magnitude = np.sqrt(x**2 + y**2 + z**2)
                                     row.extend([f"{x:.6f}", f"{y:.6f}", f"{z:.6f}", f"{magnitude:.6f}"])
                                 else:
                                     row.extend(['', '', '', '']) # Placeholder for NaN accel
                             else:
                                 row.extend(['', '', '', '']) # Placeholder for missing accel

                        writer.writerow(row)


                    # Add data to the queue
                    try:
                        self.data_queue.append(sensor_data)
                    except IndexError: # Catch potential error if deque is full and popleft fails (shouldn't happen with append)
                         pass # Or log error

                # Activity LED toggle only if data was acquired
                if data_acquired_this_cycle and self.activity_led:
                    try:
                        self.activity_led.toggle()
                    except Exception: # Catch potential GPIO errors
                        self.activity_led = None # Disable LED if it fails

                # Update performance statistics periodically
                if current_time - last_print_time >= stats_interval:
                    self._update_performance_stats()
                    self._print_status(sensor_data) # Pass latest data for status
                    last_print_time = current_time
                    # ... (Drift detection/reset logic remains the same) ...

                # Small CPU break
                # Calculate time until the *next* event (either accel or lvdt)
                next_event_time = float('inf')
                if self.config.enable_accel:
                    next_event_time = min(next_event_time, next_acquisition_time)
                if self.config.enable_lvdt:
                    next_event_time = min(next_event_time, next_lvdt_time)

                sleep_duration = next_event_time - time.perf_counter()
                if sleep_duration > 0.0001: # Sleep only if significant time remains
                    self._precise_sleep(sleep_duration * 0.9) # Sleep for 90% of the interval

        except Exception as e:
            print(f"FATAL Error in data acquisition thread: {e}")
            traceback.print_exc()
            self.running = False # Stop the thread on fatal error

    def _precise_sleep(self, sleep_time):
        """
        Implements precise sleep using a combination of sleep and active waiting.

        Args:
            sleep_time: Time in seconds to sleep.

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
        Calculate performance statistics for sampling rates and jitter.

        Returns:
            None
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
        Print current system status information.

        Args:
            sensor_data: A dictionary containing sensor data.

        Returns:
            None
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
        Format elapsed time in human-readable format.

        Args:
            elapsed_seconds: Time in seconds.

        Returns:
            Formatted time string.
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