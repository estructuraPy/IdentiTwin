"""System monitoring core module for the IdentiTwin system.

Provides the main `MonitoringSystem` class that orchestrates sensor setup,
data acquisition, queue management, system health monitoring, performance
tracking, status reporting, and error handling.

Key Features:
    - Multi-threaded data acquisition for concurrent sensor reading.
    - Real-time sensor monitoring and data buffering.
    - Performance statistics tracking (sampling rate, jitter).
    - Automated sensor calibration integration.
    - System status reporting via console output.
    - Error handling and recovery mechanisms for sensor communication.
    - Integration with event detection and performance monitoring modules.
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
import matplotlib.pyplot as plt
import sys

from . import state
from . import processing_data, processing_analysis
from . import calibration

class MonitoringSystem:
    """Manages the overall structural monitoring process.

    Handles sensor initialization, starts data acquisition threads, manages
    data flow, coordinates event monitoring, tracks performance, and provides
    methods for starting, stopping, and cleaning up the system.

    Attributes:
        config (SystemConfig or SimulatorConfig): Configuration object holding
            system parameters and settings.
        running (bool): Flag indicating if the monitoring system is active.
        data_queue (deque): Queue for storing raw sensor data packets.
        acquisition_thread (threading.Thread): Thread for acquiring data from sensors.
        event_thread (threading.Thread): Thread for monitoring events.
        event_monitor (EventMonitor): Instance for detecting and handling events.
        event_count (int): Counter for detected events.
        sensors_initialized (bool): Flag indicating if sensors have been set up.
        last_status_time (float): Timestamp of the last status printout.
        status_interval (float): Interval (in seconds) for printing status updates.
        ads (object): Instance of the ADS1115 ADC (or dummy).
        lvdt_channels (list): List of LVDT channel objects (or dummy).
        accelerometers (list): List of accelerometer objects (or dummy).
        status_led (gpiozero.LED or None): Hardware LED for system status.
        activity_led (gpiozero.LED or None): Hardware LED for recording/activity status.
        accel_io_error_counts (list): Counters for consecutive I/O errors per accelerometer.
        accel_io_error_log_threshold (int): Threshold for logging repeated I/O errors.
        performance_stats (dict): Dictionary storing performance metrics like
            sampling rates and timestamps.
        last_lvdt_readings (list): Stores the most recent LVDT readings.
        display_buffer (dict): Buffer for data used in status updates to avoid
            using potentially stale `last_lvdt_readings`.
        lvdt_calibration (list): List storing calibration parameters for LVDTs.
    """

    def __init__(self, config):
        """Initializes the MonitoringSystem.

        Sets up internal state, queues, buffers, and performance tracking
        structures based on the provided configuration.

        Args:
            config (SystemConfig or SimulatorConfig): The configuration object
                containing all settings for the monitoring session.
        """
        self.config = config
        self.running = False
        self.data_queue = deque(maxlen=50000)
        self.acquisition_thread = None
        self.event_count = 0
        self.sensors_initialized = False
        self.last_status_time = 0
        self.status_interval = 2.0

        # Initialize sensor attributes to avoid AttributeError
        self.ads = None
        self.lvdt_channels = None
        self.accelerometers = None
        self.status_led = None
        self.activity_led = None

        # Add counters for consecutive I/O errors per accelerometer
        self.accel_io_error_counts = [0] * (config.num_accelerometers if config.enable_accel else 0)
        self.accel_io_error_log_threshold = 100 # Log every 100 errors after the first

        self.performance_stats = {
            "accel_timestamps": deque(maxlen=50000),
            "lvdt_timestamps": deque(maxlen=10000),
            "accel_periods": deque(maxlen=50000),
            "lvdt_periods": deque(maxlen=10000),
            "last_accel_time": None,
            "last_lvdt_time": None,
            "sampling_rate_acceleration": 0.0,
            "sampling_rate_lvdt": 0.0,
        }

        self.last_lvdt_readings = []
        if (
            config.enable_lvdt
            and hasattr(config, "num_lvdts")
            and config.num_lvdts > 0
        ):
            self.last_lvdt_readings = [
                {"voltage": 0.0, "displacement": 0.0} for _ in range(config.num_lvdts)
            ]

        # Add display buffer for status updates
        self.display_buffer = {
            'accel_data': [],  # List of latest accelerometer readings
            'lvdt_data': [],   # List of latest LVDT readings
            'last_update': 0,  # Time of last buffer update
            'buffer_max_age': 0.5  # Maximum age of data in seconds
        }

        self.lvdt_calibration = []  # Lista para almacenar calibración de LVDTs

    def setup_sensors(self):
        """Initializes and configures sensors and hardware components.

        Sets up LVDTs (via ADS1115), accelerometers (MPU6050), and hardware
        LEDs based on the configuration. Handles potential hardware errors
        or unavailability (simulation mode).

        Raises:
            Exception: If a critical error occurs during sensor setup that
                       prevents the system from proceeding.
        """
        print("\n========================= Setting up sensors =========================\n")
        try:
            # Initialize LEDs first - check if hardware is available via config
            print("\nSetting up LEDs...")
            # initialize_leds now returns None if hardware is unavailable
            self.status_led, self.activity_led = self.config.initialize_leds()
            if self.status_led and self.activity_led:
                print("Hardware LEDs initialized.")
                self.status_led.off() # Ensure status LED is off initially
                self.activity_led.off() # Ensure activity LED is off initially
            else:
                print("Hardware LED control not available or initialization failed.")
                self.status_led, self.activity_led = None, None # Ensure they are None

            # Initialize LVDT-related components
            if self.config.enable_lvdt:
                print("\nSetting up LVDTs...")
                self.ads = self.config.create_ads1115()
                if self.ads:
                    self.lvdt_channels = self.config.create_lvdt_channels(self.ads) # Creates channels
                    if self.lvdt_channels:
                        # === Add check for lvdt_slopes here ===
                        if not self.config.lvdt_slopes or len(self.config.lvdt_slopes) < len(self.lvdt_channels):
                            print(f"ERROR: LVDT slopes are missing or insufficient in the configuration.")
                            print(f"  Expected {len(self.lvdt_channels)} slopes, found: {self.config.lvdt_slopes}")
                            raise ValueError("LVDT slopes missing or insufficient in configuration.")
                        # =======================================

                        # Call calibration AFTER channels are created and slopes are verified
                        self.lvdt_calibration = calibration.initialize_lvdt( # Calls calibration
                            self.lvdt_channels,
                            self.config.lvdt_slopes, # Pass verified slopes
                            self.config
                        )
                        # Check if calibration failed for any sensor
                        if any(cal is None for cal in self.lvdt_calibration):
                             print("Warning: One or more LVDT calibrations failed. Check logs.")
                             # Decide how to handle: maybe disable LVDT? or just warn?
                             # For now, just warn. Data processing needs to handle None calibration.
                        else:
                             print("LVDT channels initialized and calibrated successfully.")
                    else:
                        print("LVDT channel creation failed.")
                else:
                    print("ADS1115 initialization failed, cannot set up LVDTs.")
            else:
                print("LVDT setup skipped (disabled in configuration).")

            # Initialize accelerometer-related components
            if self.config.enable_accel:
                print("\nSetting up Accelerometers...")
                self.accelerometers = self.config.create_accelerometers()
                if self.accelerometers:
                    print("Accelerometers initialized successfully.")
                    # Calibrate accelerometers
                    accel_offsets = calibration.multiple_accelerometers(
                        mpu_list=self.accelerometers,
                        calibration_time=2.0,
                        config=self.config
                    )
                    if accel_offsets:
                        self.config.accel_offsets = accel_offsets
                        print("Accelerometer calibration complete.\n\n")
                    else:
                        print("Accelerometer calibration failed.")
                else:
                    print("Failed to initialize accelerometers.")
            else:
                print("Accelerometer setup skipped (disabled in configuration).")

            self.sensors_initialized = True  # Set sensors_initialized to True after successful setup

        except Exception as e:
            print(f"\nError setting up sensors: {e}\n")
            traceback.print_exc()
            raise


    def start_monitoring(self):
        """Starts the data acquisition and event monitoring threads.

        Sets the system state to running, turns on the status LED (if available),
        and launches the background threads for data collection and event detection.
        """
        if not self.sensors_initialized:
            print("Error: Sensors are not initialized. Call setup_sensors() first.")
            return

        if self.status_led:
            try:
                self.status_led.on() # Turn ON Status LED (Green)
            except Exception as e:
                print(f"Warning: Could not turn on status LED: {e}")

        self.running = True
        state.set_system_variable('system_running', True) # Set global state
        self.acquisition_thread = threading.Thread(
            target=self._data_acquisition_thread, daemon=True
        )
        self.acquisition_thread.start()

        if hasattr(self.config, "trigger_acceleration_threshold") or hasattr(
            self.config, "trigger_displacement_threshold"
        ):
            thresholds = {
                "acceleration": self.config.trigger_acceleration_threshold,
                "displacement": self.config.trigger_displacement_threshold,
                "detrigger_acceleration": self.config.detrigger_acceleration_threshold,
                "detrigger_displacement": self.config.detrigger_displacement_threshold,
                "pre_event_time": self.config.pre_event_time,
                "post_event_time": self.config.post_event_time,
                "min_event_duration": self.config.min_event_duration,
            }

            event_count_ref = [self.event_count]

            from .event_monitoring import EventMonitor
            self.event_monitor = EventMonitor(
                self.config, self.data_queue, thresholds, self.running, event_count_ref
            )
            self.event_thread = threading.Thread(
                target=self.event_monitor.event_monitoring_thread, daemon=True
            )
            self.event_thread.start()
            print("Event monitoring thread started.")

    def stop_monitoring(self):
        """Stops the monitoring system and associated threads.

        Sets the running flag to False, waits for acquisition and event threads
        to join, turns off hardware LEDs, and updates the final event count.
        """
        print("Stopping monitoring system...")
        self.running = False
        state.set_system_variable('system_running', False) # Reset global state

        if self.acquisition_thread and self.acquisition_thread.is_alive():
            print("Waiting for acquisition thread to finish...")
            self.acquisition_thread.join(timeout=2.0)

        if (
            hasattr(self, "event_thread")
            and self.event_thread
            and self.event_thread.is_alive()
        ):
            print("Waiting for event thread to finish...")
            self.event_thread.join(timeout=2.0)

        if self.status_led:
            try:
                self.status_led.off() # Turn OFF Status LED (Green)
            except Exception as e:
                print(f"Warning: Could not turn off status LED: {e}")
        if self.activity_led:
            try:
                self.activity_led.off() # Turn OFF Activity/Recording LED (Blue)
            except Exception as e:
                print(f"Warning: Could not turn off activity LED: {e}")

        if hasattr(self, "event_monitor"):
            self.event_count = self.event_monitor.event_count_ref[0]

        print("Monitoring system stopped.")

    def cleanup(self):
        """Stops monitoring and releases resources.

        Calls `stop_monitoring()` and closes any open Matplotlib plots.
        """
        self.stop_monitoring()
        plt.close("all")
        print("Resources cleaned up.")

    def wait_for_completion(self):
        """Blocks execution until monitoring is stopped.

        Useful for keeping the main thread alive while background threads run.
        Typically interrupted by Ctrl+C, which triggers `stop_monitoring`.
        """
        try:
            while self.running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\nKeyboardInterrupt received. Stopping monitoring...")
            self.stop_monitoring()

    def _data_acquisition_thread(self):
        """Background thread function for continuous sensor data acquisition.

        Reads data from enabled LVDT and accelerometer sensors at their respective
        target sampling rates using precise timing. Enqueues the collected data
        packet into `data_queue`. Manages the physical activity/recording LED
        (blinking blue). Calculates and updates performance statistics periodically.
        Handles sensor communication errors and attempts recovery.
        """
        if not self.sensors_initialized:
             print("Error: Data acquisition thread cannot start, sensors not initialized.", file=sys.stderr)
             return

        try:
            accel_rate_target = self.config.sampling_rate_acceleration
            lvdt_rate_target = self.config.sampling_rate_lvdt

            accel_interval = 1.0 / accel_rate_target if accel_rate_target > 0 else float('inf')
            lvdt_interval = 1.0 / lvdt_rate_target if lvdt_rate_target > 0 else float('inf')

            stats_interval = 1.0

            accel_sample_count = 0
            lvdt_sample_count  = 0
            loop_start_time    = time.perf_counter()
            next_accel_time    = loop_start_time
            next_lvdt_time     = loop_start_time
            last_stats_update_time = loop_start_time

            last_accel_actual_time = None
            last_lvdt_actual_time = None

            blink_cycle_duration = 0.75  # 0.5s ON + 0.25s OFF
            blink_on_duration = 0.5

            while self.running:
                now_perf = time.perf_counter() # Use perf_counter for blinking timing
                now_time = time.time() # Use time for general timestamps and logging checks
                sensor_data_packet = None
                data_acquired = False

                # --- Control Physical Activity/Recording LED (Blue) ---
                is_recording = state.get_event_variable("is_event_recording", False)
                if self.activity_led:
                    try:
                        if is_recording:
                            # Calculate phase in blink cycle
                            time_in_cycle = now_perf % blink_cycle_duration
                            if time_in_cycle < blink_on_duration:
                                self.activity_led.on() # Turn ON if in the first 0.5s
                            else:
                                self.activity_led.off() # Turn OFF if in the last 0.25s
                        else:
                            self.activity_led.off() # Ensure LED is OFF if not recording
                    except Exception as e:
                        # Log infrequently to avoid flooding console
                        if now_time % 10 < 0.1: # Log roughly every 10 seconds
                             print(f"Warning: Could not control activity LED: {e}", file=sys.stderr)
                # --- End LED Control ---


                if self.config.enable_accel and self.accelerometers and now_perf >= next_accel_time:
                    # Add a mutex or lock for accelerometer access
                    self.accel_lock = threading.Lock()
                    with self.accel_lock:
                        target_accel_time = loop_start_time + accel_sample_count * accel_interval
                        sleep_needed = target_accel_time - now_perf
                        if sleep_needed > 0:
                            self._precise_sleep(sleep_needed)
                        actual_accel_time = time.perf_counter()
                        expected_relative_time = accel_sample_count * accel_interval

                        if last_accel_actual_time is not None:
                            period = actual_accel_time - last_accel_actual_time
                            self.performance_stats["accel_periods"].append(period)
                        last_accel_actual_time = actual_accel_time

                        accel_data_list = []
                        for i, accel in enumerate(self.accelerometers):
                            try:
                                raw_data = accel.get_accel_data()
                                # Reset error counter on successful read
                                if i < len(self.accel_io_error_counts):
                                    if self.accel_io_error_counts[i] > 0:
                                        logging.info(f"Accelerometer {i+1} communication restored.")
                                    self.accel_io_error_counts[i] = 0

                                calibrated_data = raw_data
                                if i < len(self.config.accel_offsets):
                                    try:
                                        offsets = self.config.accel_offsets[i]
                                        if isinstance(offsets, dict):
                                            from .calibration import calibrate_accelerometer
                                            calibrated_data = calibrate_accelerometer(raw_data, offsets)
                                        else:
                                            logging.warning(f"Invalid calibration data structure for accelerometer {i+1}. Expected dict, got {type(offsets)}. Using raw data.")
                                    except Exception as cal_err:
                                        logging.error(f"Failed to calibrate accelerometer {i+1}: {cal_err}. Data acquisition stopped.")
                                        self.running = False  # Stop acquisition due to calibration failure
                                        raise  # Re-raise the exception to exit the thread
                                else:
                                    logging.warning(f"No calibration offset found for accelerometer {i+1}. Using raw data.")

                                mag = np.sqrt(calibrated_data['x']**2 + calibrated_data['y']**2 + calibrated_data['z']**2)
                                calibrated_data['magnitude'] = mag
                                accel_data_list.append(calibrated_data)

                            except OSError as read_err:
                                if read_err.errno == 121: # Specific I/O error
                                    if i < len(self.accel_io_error_counts):
                                        self.accel_io_error_counts[i] += 1
                                        # Log less frequently
                                        if self.accel_io_error_counts[i] == 1 or \
                                           self.accel_io_error_counts[i] % self.accel_io_error_log_threshold == 0:
                                            logging.warning(f"I/O Error reading accelerometer {i+1} (Count: {self.accel_io_error_counts[i]}): {read_err}")
                                else: # Other OS errors
                                    logging.warning(f"Failed to read accelerometer {i+1}: {read_err}")
                                    if i < len(self.accel_io_error_counts): # Reset counter for other errors
                                        self.accel_io_error_counts[i] = 0
                                accel_data_list.append({'x': np.nan, 'y': np.nan, 'z': np.nan, 'magnitude': np.nan})
                            except Exception as e:
                                logging.error(f"Unexpected error processing accelerometer {i+1}: {e}", exc_info=True)
                                if i < len(self.accel_io_error_counts): # Reset counter for other errors
                                    self.accel_io_error_counts[i] = 0
                                accel_data_list.append({'x': np.nan, 'y': np.nan, 'z': np.nan, 'magnitude': np.nan})

                        timestamp = datetime.now()
                        sensor_data_packet = {
                            'timestamp': timestamp,
                            'expected_relative_time': expected_relative_time,
                            'sensor_type': 'accel',
                            'sensor_data': {'accel_data': accel_data_list}
                        }
                        accel_sample_count += 1
                        next_accel_time = loop_start_time + accel_sample_count * accel_interval
                        data_acquired = True

                elif self.config.enable_lvdt and self.lvdt_channels and now_perf >= next_lvdt_time:
                    # Add similar timing logic as accelerometer
                    if last_lvdt_actual_time is not None:
                        period = now_perf - last_lvdt_actual_time
                        self.performance_stats["lvdt_periods"].append(period)
                    last_lvdt_actual_time = now_perf

                    # Add a mutex or lock for LVDT access
                    self.lvdt_lock = threading.Lock()
                    with self.lvdt_lock:
                        lvdt_data_list = []
                        for i, ch in enumerate(self.lvdt_channels):
                            try:
                                # Add delay before ALL channel readings (not just after first one)
                                time.sleep(0.001)  # 1ms delay for ALL channels
                                
                                # Check if channel is valid
                                if ch is None:
                                    print(f"Warning: LVDT channel {i+1} is None")
                                    lvdt_data_list.append({'voltage': 0.0, 'displacement': 0.0})
                                    continue
                                
                                # Try reading with a retry mechanism
                                retry_count = 0
                                max_retries = 3
                                while retry_count < max_retries:
                                    try:
                                        raw_voltage = ch.voltage
                                        # If voltage is exactly 0, this might indicate a connection issue
                                        if abs(raw_voltage) < 1e-6:
                                            print(f"Warning: LVDT {i+1} voltage is exactly zero, possible connection issue")
                                        break
                                    except Exception as retry_err:
                                        retry_count += 1
                                        if retry_count >= max_retries:
                                            raise retry_err
                                        time.sleep(0.002)  # Wait before retry
                                
                                # Calculate displacement using calibration from monitoring system
                                calib = self.lvdt_calibration[i]
                                slope = calib['slope']
                                intercept = calib['intercept']
                                disp = slope * raw_voltage + intercept
                                
                                lvdt_data_list.append({
                                    'voltage': raw_voltage,
                                    'displacement': disp
                                })
                                
                                # Update last valid reading
                                if i < len(self.last_lvdt_readings):
                                    self.last_lvdt_readings[i] = {
                                        'voltage': raw_voltage,
                                        'displacement': disp
                                    }
                            except Exception as e:
                                print(f"Error reading LVDT {i+1}: {str(e)}", file=sys.stderr)
                                # Use last valid reading if available
                                if i < len(self.last_lvdt_readings):
                                    lvdt_data_list.append(self.last_lvdt_readings[i])
                                else:
                                    lvdt_data_list.append({'voltage': 0.0, 'displacement': 0.0})

                        timestamp = datetime.now()
                        expected_relative_time = lvdt_sample_count * lvdt_interval
                        sensor_data_packet = {
                            'timestamp': timestamp,
                            'expected_relative_time': expected_relative_time,
                            'sensor_type': 'lvdt',
                            'sensor_data': {'lvdt_data': lvdt_data_list}
                        }
                        
                        # Update display buffer with latest LVDT data
                        self.display_buffer['lvdt_data'] = lvdt_data_list
                        self.display_buffer['last_update'] = time.time()
                        
                        lvdt_sample_count += 1
                        next_lvdt_time = loop_start_time + lvdt_sample_count * lvdt_interval
                        data_acquired = True

                if sensor_data_packet:
                    self.data_queue.append(sensor_data_packet)
                    # Update display buffer with fresh data
                    now = time.time()
                    if sensor_data_packet.get('sensor_type') == 'accel':
                        self.display_buffer['accel_data'] = sensor_data_packet.get('sensor_data', {}).get('accel_data', [])
                        self.display_buffer['last_update'] = now
                    elif sensor_data_packet.get('sensor_type') == 'lvdt':
                        self.display_buffer['lvdt_data'] = sensor_data_packet.get('sensor_data', {}).get('lvdt_data', [])
                        self.display_buffer['last_update'] = now
                    if self.activity_led:
                        try:
                            self.activity_led.blink(on_time=0.01, off_time=0.01, n=1, background=True)
                        except Exception:
                            pass

                if now_time - last_stats_update_time >= stats_interval:
                    self._update_performance_stats(
                        self.performance_stats["accel_periods"],
                        self.performance_stats["lvdt_periods"]
                    )
                    self._print_status(sensor_data_packet if sensor_data_packet else {})
                    last_stats_update_time = now_time

                if not data_acquired:
                    earliest_next_time = float('inf')
                    if self.config.enable_accel and accel_interval != float('inf'):
                        earliest_next_time = min(earliest_next_time, next_accel_time)
                    if self.config.enable_lvdt and lvdt_interval != float('inf'):
                        earliest_next_time = min(earliest_next_time, next_lvdt_time)

                    if earliest_next_time != float('inf'):
                        sleep_duration = earliest_next_time - time.perf_counter() - 0.001
                        if sleep_duration > 0.0001:
                            self._precise_sleep(sleep_duration)
                    else:
                        time.sleep(0.01)

        except Exception as e:
            print(f"Fatal error in data acquisition thread: {e}", file=sys.stderr)
            traceback.print_exc()
        finally:
            # Ensure LEDs are off when thread exits unexpectedly
            if self.status_led: self.status_led.off()
            if self.activity_led: self.activity_led.off()
            state.set_system_variable('system_running', False) # Ensure state reflects stop
            print("--- Data acquisition thread finished ---")

    def _precise_sleep(self, sleep_time):
        """Provides a more accurate sleep duration than `time.sleep()` alone.

        Uses a combination of `time.sleep()` for the majority of the duration
        and busy-waiting for the final millisecond to improve timing precision,
        especially important for achieving target sampling rates.

        Args:
            sleep_time (float): The desired sleep duration in seconds.
        """
        if sleep_time <= 0:
            return

        if (sleep_time < 0.001): #
            target = time.perf_counter() + sleep_time
            while time.perf_counter() < target:
                pass
            return

        time.sleep(sleep_time - 0.0005)
        target = time.perf_counter() + 0.0005
        while time.perf_counter() < target:
            pass

    def _update_performance_stats(self, recent_accel_periods, recent_lvdt_periods):
        """Calculates and updates sampling rate statistics.

        Computes the mean sampling rate based on the collected inter-sample
        periods for both accelerometers and LVDTs. Stores the results in
        `self.performance_stats`.

        Args:
            recent_accel_periods (deque): Deque containing recent time periods
                between accelerometer samples.
            recent_lvdt_periods (deque): Deque containing recent time periods
                between LVDT samples.
        """
        if len(recent_accel_periods) > 1:
            periods_np = np.array(recent_accel_periods)
            mean_period = np.mean(periods_np)
            std_dev_period = np.std(periods_np)
            self.performance_stats["sampling_rate_acceleration"] = 1.0 / mean_period if mean_period > 0 else 0.0
        else:
            self.performance_stats["sampling_rate_acceleration"] = 0.0

        if len(recent_lvdt_periods) > 1:
            periods_np = np.array(recent_lvdt_periods)
            mean_period = np.mean(periods_np)
            std_dev_period = np.std(periods_np)
            self.performance_stats["sampling_rate_lvdt"] = 1.0 / mean_period if mean_period > 0 else 0.0
        else:
            self.performance_stats["sampling_rate_lvdt"] = 0.0

    def _print_status(self, sensor_data):
        """Prints a formatted system status update to the console.

        Displays current time, measured sampling rates vs. targets, latest
        sensor readings (LVDT voltage/displacement, accelerometer components),
        event count, and recording status (including elapsed recording time).
        Uses the `display_buffer` for recent sensor data if available and fresh.

        Args:
            sensor_data (dict): The latest sensor data packet acquired. Used
                primarily as a fallback if the display buffer is stale.
        """
        print("\n============================ System Status Update =============================\n")
        print(f"Time: {datetime.now().strftime('%H:%M:%S')}")

        print("Performance:")
        if self.config.enable_accel:
            accel_rate_measured = self.performance_stats.get("sampling_rate_acceleration", 0.0)
            print(f"  Accel Rate: {accel_rate_measured:.2f} Hz (Target: {self.config.sampling_rate_acceleration:.1f} Hz)")

        if self.config.enable_lvdt:
            lvdt_rate_measured = self.performance_stats.get("sampling_rate_lvdt", 0.0)
            print(f"  LVDT Rate: {lvdt_rate_measured:.2f} Hz (Target: {self.config.sampling_rate_lvdt:.1f} Hz)")

        if self.config.enable_lvdt:
            print("\nLVDT Status:")
            # First try to use the most recent display buffer data
            now = time.time()
            buffer_age = now - self.display_buffer.get('last_update', 0)
            
            if buffer_age <= self.display_buffer.get('buffer_max_age', 0.5) and 'lvdt_data' in self.display_buffer:
                lvdt_data = self.display_buffer['lvdt_data']
                for i, reading in enumerate(lvdt_data):
                    if isinstance(reading, dict):
                        disp = reading.get('displacement', float('nan'))
                        volt = reading.get('voltage', float('nan'))
                        print(f"  LVDT{i+1}: {disp:.3f}mm ({volt:.3f}V)")
            else:
                # Fall back to last_lvdt_readings if buffer data is too old
                for i, reading in enumerate(self.last_lvdt_readings):
                    disp = reading.get('displacement', float('nan'))
                    volt = reading.get('voltage', float('nan'))
                    print(f"  LVDT{i+1}: {disp:.3f}mm ({volt:.3f}V)")

        if self.config.enable_accel:
            print("\nAccelerometer Status:")
            now = time.time()
            buffer_age = now - self.display_buffer['last_update']
            
            if buffer_age <= self.display_buffer['buffer_max_age']:
                accel_data = self.display_buffer['accel_data']
                if accel_data:
                    for i, accel in enumerate(accel_data):
                        if isinstance(accel, dict):
                            x = accel.get('x', 0.0)
                            y = accel.get('y', 0.0)
                            z = accel.get('z', 0.0)
                            mag = np.sqrt(x*x + y*y + z*z)
                            print(f"  Accel{i+1}: X={x:.3f} Y={y:.3f} Z={z:.3f} (Mag: {mag:.3f}) m/s^2")
                else:
                    print("  Waiting for accelerometer data...")
            else:
                print("  Data not updated in the last 500ms")

        event_count = self.event_monitor.event_count_ref[0] if hasattr(self, 'event_monitor') else 0
        state_event_count = state.get_event_variable("event_count", 0)

        current_event_count = max(event_count, state_event_count)
        print("\n-------------------------------------------------------------------------------")
        print(f"\nEvents detected: {current_event_count}")

        if event_count != state_event_count:
            state.set_event_variable("event_count", event_count)

        is_recording = state.get_event_variable("is_event_recording", False)
        formatted_time = "Not recording"
        if is_recording:
            last_trigger = state.get_event_variable("last_trigger_time", 0)
            if last_trigger > 0:
                elapsed = time.time() - last_trigger
                formatted_time = f"Recording event... ({elapsed:.1f}s elapsed)"
        print(f"Recording Status: {formatted_time}")

        if hasattr(self, "event_monitor"):
            avg_accel = self.event_monitor.moving_avg_accel
            avg_disp = self.event_monitor.moving_avg_disp
            detrig_accel = self.config.detrigger_acceleration_threshold
            detrig_disp = self.config.detrigger_displacement_threshold


        print("\n===============================================================================")
        print("---  Press 'Ctrl + C' to stop monitoring ---")
        print("===============================================================================\n \n")

    def _format_elapsed_time(self, elapsed_seconds):
        """Formats a duration in seconds into a human-readable string (d, h, m, s).

        Args:
            elapsed_seconds (float): The duration in seconds.

        Returns:
            str: A formatted string representing the elapsed time (e.g.,
                 "1h 15m 30s", "45s").
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
