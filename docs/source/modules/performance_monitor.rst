Performance Monitoring
===================

.. automodule:: identitwin.performance_monitor
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The ``performance_monitor`` module tracks and logs key performance indicators (KPIs) for the IdentiTwin system, focusing on data acquisition timing and system resource usage. It provides the `PerformanceMonitor` class for these tasks.

Key Features
-----------

* Real-time sampling rate calculation: Determines actual sampling rates for accelerometers and LVDTs based on timestamps.
* Timing jitter calculation: Measures the standard deviation of sample periods (jitter) in milliseconds.
* Resource monitoring (optional): Tracks CPU and memory usage if the `psutil` library is available.
* Performance logging: Logs metrics (rates, jitter, CPU/memory usage, uptime) to a CSV file at regular intervals.
* Status reporting: Generates formatted strings summarizing current performance for display.
* Background operation: Runs monitoring tasks in a separate thread.
