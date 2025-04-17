"""
Performance Monitoring Module for IdentiTwin.

Tracks and logs key system performance metrics, focusing on data acquisition
timing accuracy (sampling rate and jitter) and optionally system resource usage
(CPU, memory) if the `psutil` library is available.

Key Features:
- Real-time calculation of actual sampling rates and jitter for LVDTs and accelerometers.
- Optional logging of performance metrics to a CSV file over time.
- Optional monitoring of CPU and memory usage via `psutil`.
- Warning messages for significant deviations from target rates or high jitter.
- Thread-based monitoring for periodic updates and logging.

Classes:
    PerformanceMonitor: Manages the tracking, calculation, and logging of performance metrics.
"""
import time
import csv
import threading
import os
import numpy as np
from datetime import datetime
from collections import deque
import logging

# Attempt to import psutil for system resource monitoring
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    print("Warning: 'psutil' library not found. CPU and memory usage monitoring disabled.")

# Define constants for console output styling (optional, adjust as needed)
TITLE = "\033[1;34m"  # Bold Blue
CONTENT = "\033[0;32m" # Green
SPECIAL = "\033[1;33m" # Bold Yellow
RESET = "\033[0m"      # Reset color

# performance_monitor.py
class PerformanceMonitor:
    """
    Monitors and logs system performance metrics like sampling rates and jitter.

    Tracks timestamps of sensor readings to calculate actual sampling rates and
    timing jitter. Optionally monitors CPU/memory usage and logs metrics
    periodically to a CSV file. Runs monitoring tasks in a separate thread.

    Attributes:
        config: The system configuration object.
        log_file (str): Path to the performance log CSV file.
        accel_timestamps (deque): Stores recent accelerometer timestamps.
        lvdt_timestamps (deque): Stores recent LVDT timestamps.
        accel_periods (deque): Stores recent periods between accelerometer readings.
        lvdt_periods (deque): Stores recent periods between LVDT readings.
        stats (dict): Dictionary holding the latest calculated performance metrics.
        running (bool): Flag indicating if the monitoring thread is active.
        monitor_thread (threading.Thread): The background thread for monitoring.
    """

    def __init__(self, config, log_file=None):
        """
        Initializes the PerformanceMonitor.

        Sets up data structures for tracking timestamps and periods, initializes
        the statistics dictionary, and prepares the log file if specified.

        Args:
            config: The system configuration object, containing target sampling rates
                    and jitter thresholds (e.g., `sampling_rate_acceleration`,
                    `max_accel_jitter`).
            log_file (str, optional): Path to the CSV file for logging performance
                                      metrics. If None, logging is disabled.
                                      Defaults to None.

        Returns:
            None
        """
        self.config = config
        self.log_file = log_file

        # Sampling rate tracking
        self.accel_timestamps = deque(maxlen=100)
        self.lvdt_timestamps = deque(maxlen=100)
        self.accel_periods = deque(maxlen=99)
        self.lvdt_periods = deque(maxlen=99)

        # Statistics
        self.stats = {
            "sampling_rate_acceleration": 0.0,
            "sampling_rate_lvdt": 0.0,
            "accel_jitter": 0.0,
            "lvdt_jitter": 0.0,
            "cpu_usage": 0.0,
            "memory_usage": 0.0,
            "start_time": time.time(),
            "uptime": 0.0,
        }

        # Initialize log file if provided
        if self.log_file:
            self._init_log_file()

        # Initialize monitoring thread
        self.running = False
        self.monitor_thread = None

    def _init_log_file(self):
        """
        Initializes the performance log CSV file with a header row.

        Creates the file (or overwrites if it exists) and writes headers for
        timestamp, uptime, sampling rates, jitter, and optionally CPU/memory usage.

        Returns:
            None

        Side Effects:
            - Creates or overwrites the file specified by `self.log_file`.
            - Writes header row to the file.
            - Prints a confirmation message or logs an error.
        """
        try:
            with open(self.log_file, "w", newline="") as f:
                writer = csv.writer(f)
                header = [
                    "Timestamp",
                    "Uptime",
                    "sampling_rate_acceleration",
                    "sampling_rate_lvdt",
                    "Accel_Jitter",
                    "LVDT_Jitter",
                ]
                if HAS_PSUTIL:
                    header.extend(["CPU_Usage", "Memory_Usage"])
                writer.writerow(header)
            print(f"{CONTENT}Initialized performance log file at {self.log_file}")
        except Exception as e:
            logging.error(f"Error initializing log file: {e}")

    def start(self):
        """
        Starts the background performance monitoring thread.

        Sets the `running` flag to True and starts the `_monitor_thread` if it's
        not already running.

        Returns:
            None

        Side Effects:
            - Starts the `self.monitor_thread`.
            - Prints a confirmation message.
        """
        if self.running:
            return
        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_thread, daemon=True
        )
        self.monitor_thread.start()
        print(f"{TITLE}Performance monitoring started")

    def stop(self):
        """
        Stops the background performance monitoring thread.

        Sets the `running` flag to False and waits for the `_monitor_thread`
        to terminate.

        Returns:
            None

        Side Effects:
            - Stops and joins the `self.monitor_thread`.
        """
        self.running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1.0)

    def record_accel_timestamp(self, timestamp=None):
        """
        Records a timestamp for an accelerometer reading.

        Appends the timestamp to `accel_timestamps`, calculates the period from the
        previous timestamp, appends it to `accel_periods`, and triggers an update
        of accelerometer statistics if enough data is available.

        Args:
            timestamp (float, optional): The timestamp (from `time.perf_counter()`)
                                         to record. If None, the current time is used.
                                         Defaults to None.

        Returns:
            None
        """
        if timestamp is None:
            timestamp = time.perf_counter()
        self.accel_timestamps.append(timestamp)
        if len(self.accel_timestamps) >= 2:
            period = self.accel_timestamps[-1] - self.accel_timestamps[-2]
            self.accel_periods.append(period)
        if len(self.accel_periods) > 10:
            self._update_accel_stats()

    def record_lvdt_timestamp(self, timestamp=None):
        """
        Records a timestamp for an LVDT reading.

        Appends the timestamp to `lvdt_timestamps`, calculates the period from the
        previous timestamp, appends it to `lvdt_periods`, and triggers an update
        of LVDT statistics if enough data is available.

        Args:
            timestamp (float, optional): The timestamp (from `time.perf_counter()`)
                                         to record. If None, the current time is used.
                                         Defaults to None.

        Returns:
            None
        """
        if timestamp is None:
            timestamp = time.perf_counter()
        self.lvdt_timestamps.append(timestamp)
        if len(self.lvdt_timestamps) >= 2:
            period = self.lvdt_timestamps[-1] - self.lvdt_timestamps[-2]
            self.lvdt_periods.append(period)
        if len(self.lvdt_periods) > 2:
            self._update_lvdt_stats()

    def _update_accel_stats(self):
        """
        Calculates and updates accelerometer sampling rate and jitter statistics.

        Computes the mean period and standard deviation from `accel_periods` to
        determine the actual sampling rate and jitter (in ms). Updates the `self.stats`
        dictionary. Prints warnings if the rate deviates significantly from the target
        or if jitter exceeds the configured maximum.

        Returns:
            None

        Side Effects:
            - Updates `self.stats['sampling_rate_acceleration']` and `self.stats['accel_jitter']`.
            - May print warning messages to the console.
        """
        if len(self.accel_periods) > 0:
            periods = np.array(self.accel_periods)
            mean_period = np.mean(periods)
            self.stats["sampling_rate_acceleration"] = (
                1.0 / mean_period if mean_period > 0 else 0
            )
            self.stats["accel_jitter"] = np.std(periods) * 1000  # in ms
            target_rate = self.config.sampling_rate_acceleration
            if (
                target_rate
                and abs(self.stats["sampling_rate_acceleration"] - target_rate) / target_rate > 0.1
            ):
                print(
                    f"{SPECIAL}WARNING: Accelerometer rate {self.stats['sampling_rate_acceleration']:.1f}Hz differs from target {target_rate}Hz"
                )
            if self.stats["accel_jitter"] > self.config.max_accel_jitter:
                print(
                    f"{SPECIAL}WARNING: High accelerometer jitter: {self.stats['accel_jitter']:.2f}ms"
                )

    def _update_lvdt_stats(self):
        """
        Calculates and updates LVDT sampling rate and jitter statistics.

        Computes the mean period and standard deviation from `lvdt_periods` to
        determine the actual sampling rate and jitter (in ms). Updates the `self.stats`
        dictionary. Prints warnings if the rate deviates significantly from the target
        or if jitter exceeds the configured maximum.

        Returns:
            None

        Side Effects:
            - Updates `self.stats['sampling_rate_lvdt']` and `self.stats['lvdt_jitter']`.
            - May print warning messages to the console.
        """
        if len(self.lvdt_periods) > 0:
            periods = np.array(self.lvdt_periods)
            mean_period = np.mean(periods)
            self.stats["sampling_rate_lvdt"] = 1.0 / mean_period if mean_period > 0 else 0
            self.stats["lvdt_jitter"] = np.std(periods) * 1000  # in ms
            target_rate = self.config.sampling_rate_lvdt
            if (
                target_rate
                and abs(self.stats["sampling_rate_lvdt"] - target_rate) / target_rate > 0.1
            ):
                print(
                    f"{SPECIAL}WARNING: LVDT rate {self.stats['sampling_rate_lvdt']:.1f}Hz differs from target {target_rate}Hz"
                )
            if self.stats["lvdt_jitter"] > self.config.max_lvdt_jitter:
                print(
                    f"{SPECIAL}WARNING: High LVDT jitter: {self.stats['lvdt_jitter']:.2f}ms"
                )

    def _monitor_thread(self):
        """
        Background thread function for periodic performance monitoring and logging.

        Runs in a loop while `self.running` is True. Periodically updates uptime,
        fetches CPU/memory usage (if `psutil` is available), and calls `_log_performance`
        at the specified `log_interval`.

        Returns:
            None

        Side Effects:
            - Periodically updates `self.stats`.
            - Periodically calls `_log_performance`.
            - Logs errors if exceptions occur during monitoring.
        """
        last_log_time = time.time()
        log_interval = 5.0  # Log every 5 seconds
        while self.running:
            try:
                current_time = time.time()
                self.stats["uptime"] = current_time - self.stats["start_time"]
                if HAS_PSUTIL:
                    self.stats["cpu_usage"] = psutil.cpu_percent()
                    self.stats["memory_usage"] = psutil.virtual_memory().percent
                if self.log_file and current_time - last_log_time >= log_interval:
                    self._log_performance()
                    last_log_time = current_time
                time.sleep(1.0)
            except Exception as e:
                logging.error(f"Error in performance monitoring: {e}")
                time.sleep(5.0)

    def _log_performance(self):
        """
        Writes the current performance statistics to the log file.

        Appends a new row to the CSV log file containing the current timestamp,
        uptime, sampling rates, jitter, and optionally CPU/memory usage.

        Returns:
            None

        Side Effects:
            - Appends a row to the file specified by `self.log_file`.
            - Logs errors if writing to the file fails.
        """
        if not self.log_file:
            return
        try:
            with open(self.log_file, "a", newline="") as f:
                writer = csv.writer(f)
                row = [
                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    f"{self.stats['uptime']:.1f}",
                    f"{self.stats['sampling_rate_acceleration']:.2f}",
                    f"{self.stats['sampling_rate_lvdt']:.2f}",
                    f"{self.stats['accel_jitter']:.2f}",
                    f"{self.stats['lvdt_jitter']:.2f}",
                ]
                if HAS_PSUTIL:
                    row.extend(
                        [
                            f"{self.stats['cpu_usage']:.1f}",
                            f"{self.stats['memory_usage']:.1f}",
                        ]
                    )
                writer.writerow(row)
        except Exception as e:
            logging.error(f"Error logging performance data: {e}")

    def get_status_report(self):
        """
        Generates a list of strings summarizing the current performance status.

        Formats the latest statistics from `self.stats` into human-readable strings
        suitable for display (e.g., in the console status update).

        Returns:
            list: A list of strings, each representing a line of the performance report.
        """
        report = []
        report.append(
            f"Accelerometer Rate: {self.stats['sampling_rate_acceleration']:.2f} Hz (Target: {self.config.sampling_rate_acceleration:.1f} Hz)"
        )
        report.append(
            f"Accelerometer Jitter: {self.stats['accel_jitter']:.2f} ms"
        )
        report.append(
            f"LVDT Rate: {self.stats['sampling_rate_lvdt']:.2f} Hz (Target: {self.config.sampling_rate_lvdt:.1f} Hz)"
        )
        report.append(f"LVDT Jitter: {self.stats['lvdt_jitter']:.2f} ms")
        if HAS_PSUTIL:
            report.append(f"CPU Usage: {self.stats['cpu_usage']:.1f}%")
            report.append(f"Memory Usage: {self.stats['memory_usage']:.1f}%")
        report.append(f"Uptime: {self.stats['uptime'] / 60:.1f} minutes")
        return report