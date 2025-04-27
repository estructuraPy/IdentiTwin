Performance Monitoring
===================

.. automodule:: identitwin.performance_monitor
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The ``performance_monitor`` module tracks and logs performance indicators for the system, focusing on data acquisition timing and resource usage. It provides the `PerformanceMonitor` class.

Key Features
-----------

* Sampling rate calculation: Determines actual sampling rates based on timestamps.
* Timing jitter calculation: Measures standard deviation of sample periods.
* Resource monitoring (optional): Tracks CPU and memory usage (`psutil`).
* Performance logging: Logs metrics to a CSV file.
* Status reporting: Generates strings summarizing current performance.
* Background operation: Runs monitoring tasks in a separate thread.
