Event Monitoring
==============

.. automodule:: identitwin.event_monitoring
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The ``event_monitoring`` module provides the `EventMonitor` class, which runs in a thread to detect events in real-time. It analyzes sensor data from a queue using configurable thresholds.

Key Features
-----------

* Real-time event detection: Uses trigger and detrigger thresholds.
* Data buffering: Manages pre-event data buffering.
* Configurable recording duration: Includes post-event recording time.
* Moving average calculation: Used for detriggering logic.
* Background processing: Uses threads for saving event data and analysis.
* Thread-safe state management: Updates system state via the `state` module.
* Multi-sensor logic: Handles conditions based on multiple sensor readings.