"""Performance monitoring module for the IdentiTwin system.

Tracks and logs key performance indicators (KPIs) related to data acquisition
timing and system resource usage.

Key Features:
    - Real-time calculation of actual sampling rates for accelerometers and LVDTs.
    - Calculation of timing jitter (standard deviation of sample periods).
    - Optional tracking of CPU and memory usage (requires `psutil`).
    - Logging of performance metrics to a CSV file at regular intervals.
    - Provides status reports for display.

Classes:
    PerformanceMonitor: Main class for tracking and logging performance.
"""
import time
import csv
import threading
import os
import numpy as np
from datetime import datetime
from collections import deque
import logging

# Check if psutil is available for resource monitoring
try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False
    logging.warning("psutil not found. CPU and memory usage monitoring disabled.")

# Define console color codes (consider moving to a central utility module)
TITLE = "\033[95m"  # Purple
CONTENT = "\033[94m" # Blue
SPECIAL = "\033[93m" # Yellow
RESET = "\033[0m"   # Reset color

class PerformanceMonitor:
    """Monitors and logs system performance metrics like sampling rates and jitter.

    Calculates actual sampling rates based on timestamps recorded via
    `record_accel_timestamp` and `record_lvdt_timestamp`. Optionally logs these
    metrics along with CPU/memory usage to a CSV file.

    Attributes:
        config (SystemConfig or SimulatorConfig): System configuration object.
        log_file (str or None): Path to the performance log CSV file.
        accel_timestamps (deque): Buffer storing recent accelerometer timestamps.
        lvdt_timestamps (deque): Buffer storing recent LVDT timestamps.
        accel_periods (deque): Buffer storing recent periods between accel samples.
        lvdt_periods (deque): Buffer storing recent periods between LVDT samples.
        stats (dict): Dictionary holding the latest calculated performance metrics
            (sampling rates, jitter, cpu, memory, uptime).
        running (bool): Flag indicating if the monitoring thread is active.
        monitor_thread (threading.Thread or None): Background thread for periodic
            logging and resource usage checks.
    """

    def __init__(self, config, log_file=None):
        """Initializes the PerformanceMonitor.

        Args:
            config (SystemConfig or SimulatorConfig): Configuration object with
                sampling rate targets.
            log_file (str, optional): Path to the CSV file for logging performance
                data. If None, logging to file is disabled. Defaults to None.
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
        """Initializes the performance log CSV file with a header row."""
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
        """Starts the background performance monitoring thread."""
        if self.running:
            return
        self.running = True
        self.monitor_thread = threading.Thread(
            target=self._monitor_thread, daemon=True
        )
        self.monitor_thread.start()
        print(f"{TITLE}Performance monitoring started")

    def stop(self):
        """Stops the background performance monitoring thread."""
        self.running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1.0)

    def record_accel_timestamp(self, timestamp=None):
        """Records an accelerometer acquisition timestamp.

        Appends the timestamp to `accel_timestamps`, calculates the period
        since the last sample, appends it to `accel_periods`, and triggers
        a statistics update if enough periods are collected.

        Args:
            timestamp (float, optional): The timestamp (preferably from
                `time.perf_counter()`) to record. If None, the current time
                is used. Defaults to None.
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
        """Records an LVDT acquisition timestamp.

        Appends the timestamp to `lvdt_timestamps`, calculates the period
        since the last sample, appends it to `lvdt_periods`, and triggers
        a statistics update if enough periods are collected.

        Args:
            timestamp (float, optional): The timestamp (preferably from
                `time.perf_counter()`) to record. If None, the current time
                is used. Defaults to None.
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
        """Updates accelerometer sampling rate and jitter statistics.

        Calculates the mean sampling rate and standard deviation of periods (jitter)
        from the `accel_periods` buffer. Stores results in `self.stats`.
        Prints a warning if the measured rate deviates significantly from the target.
        """
        if len(self.accel_periods) > 0:
            periods = np.array(self.accel_periods)
            mean_period = np.mean(periods)
            self.stats["sampling_rate_acceleration"] = (
                1.0 / mean_period if mean_period > 0 else 0
            )
            # Calculate jitter (standard deviation of periods in milliseconds)
            jitter_ms = np.std(periods) * 1000
            self.stats["accel_jitter"] = jitter_ms

            target_rate = self.config.sampling_rate_acceleration
            if (
                target_rate
                and abs(self.stats["sampling_rate_acceleration"] - target_rate) / target_rate > 0.1
            ):
                print(
                    f"{SPECIAL}WARNING: Accelerometer rate {self.stats['sampling_rate_acceleration']:.1f}Hz differs from target {target_rate}Hz"
                )

    def _update_lvdt_stats(self):
        """Updates LVDT sampling rate and jitter statistics.

        Calculates the mean sampling rate and standard deviation of periods (jitter)
        from the `lvdt_periods` buffer. Stores results in `self.stats`.
        Prints a warning if the measured rate deviates significantly from the target.
        """
        if len(self.lvdt_periods) > 0:
            periods = np.array(self.lvdt_periods)
            mean_period = np.mean(periods)
            self.stats["sampling_rate_lvdt"] = 1.0 / mean_period if mean_period > 0 else 0
            # Calculate jitter (standard deviation of periods in milliseconds)
            jitter_ms = np.std(periods) * 1000
            self.stats["lvdt_jitter"] = jitter_ms

            target_rate = self.config.sampling_rate_lvdt
            if (
                target_rate
                and abs(self.stats["sampling_rate_lvdt"] - target_rate) / target_rate > 0.1
            ):
                print(
                    f"{SPECIAL}WARNING: LVDT rate {self.stats['sampling_rate_lvdt']:.1f}Hz differs from target {target_rate}Hz"
                )

    def _monitor_thread(self):
        """Background thread for periodic performance logging and resource checks.

        Periodically updates uptime, checks CPU/memory usage (if `psutil` is
        available), and calls `_log_performance` if file logging is enabled.
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
        """Logs the current performance statistics to the CSV file."""
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
        """Generates a list of strings summarizing the current performance status.

        Formats the latest sampling rates, jitter, resource usage (if available),
        and uptime for display.

        Returns:
            list[str]: A list of formatted strings suitable for printing as a status report.
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