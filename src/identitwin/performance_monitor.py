"""
Performance monitoring module for the IdentiTwin system.

This module tracks and analyzes system performance metrics including:
- Sampling rate accuracy
- Timing jitter
- CPU and memory usage
- System responsiveness
- Data acquisition reliability

Key Features:
- Real-time performance monitoring
- Statistical analysis of timing accuracy
- Resource usage tracking
- Performance data logging
- Alert generation for performance issues

Classes:
    PerformanceMonitor: Main class for tracking system performance

The module helps ensure reliable data acquisition and system operation by
monitoring key performance indicators and alerting when issues arise.
"""
import time
import csv
import threading
import os
import numpy as np
from datetime import datetime
from collections import deque
import logging

# performance_monitor.py
class PerformanceMonitor:
    """Monitors and logs system performance metrics."""

    def __init__(self, config, log_file=None):
        """
        Initialize the performance monitor.

        Args:
            config: Configuration object containing system settings.
            log_file: Path to the log file for performance data (optional).

        Returns:
            None

        Assumptions:
            - The configuration object has attributes for sampling rates and jitter thresholds.
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
        Initialize the performance log file.

        Returns:
            None
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
        Start performance monitoring.

        Returns:
            None
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
        Stop performance monitoring.

        Returns:
            None
        """
        self.running = False
        if self.monitor_thread and self.monitor_thread.is_alive():
            self.monitor_thread.join(timeout=1.0)

    def record_accel_timestamp(self, timestamp=None):
        """
        Record accelerometer acquisition timestamp.

        Args:
            timestamp: Timestamp to record (optional, defaults to current time).

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
        Record LVDT acquisition timestamp.

        Args:
            timestamp: Timestamp to record (optional, defaults to current time).

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
        Update accelerometer performance statistics.

        Returns:
            None
        """
        if len(self.accel_periods) > 0:
            periods = np.array(self.accel_periods)
            mean_period = np.mean(periods)
            self.stats["sampling_rate_acceleration"] = (
                1.0 / mean_period if mean_period > 0 else 0
            )
            target_rate = self.config.sampling_rate_acceleration
            if (
                target_rate
                and abs(self.stats["sampling_rate_acceleration"] - target_rate) / target_rate > 0.1
            ):
                print(
                    f"{SPECIAL}WARNING: Accelerometer rate {self.stats['sampling_rate_acceleration']:.1f}Hz differs from target {target_rate}Hz"
                )

    def _update_lvdt_stats(self):
        """
        Update LVDT performance statistics.

        Returns:
            None
        """
        if len(self.lvdt_periods) > 0:
            periods = np.array(self.lvdt_periods)
            mean_period = np.mean(periods)
            self.stats["sampling_rate_lvdt"] = 1.0 / mean_period if mean_period > 0 else 0
            target_rate = self.config.sampling_rate_lvdt
            if (
                target_rate
                and abs(self.stats["sampling_rate_lvdt"] - target_rate) / target_rate > 0.1
            ):
                print(
                    f"{SPECIAL}WARNING: LVDT rate {self.stats['sampling_rate_lvdt']:.1f}Hz differs from target {target_rate}Hz"
                )

    def _monitor_thread(self):
        """
        Thread for monitoring system resources and logging performance.

        Returns:
            None
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
        Log performance data to file.

        Returns:
            None
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
        Get a formatted status report for display.

        Returns:
            A list of strings, each representing a line in the status report.
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