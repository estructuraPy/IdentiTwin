Event Monitoring
==============

.. automodule:: identitwin.event_monitoring
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The ``event_monitoring`` module provides the `EventMonitor` class, which runs in a separate thread to detect structural events in real-time. It analyzes sensor data from a queue, using configurable acceleration and displacement thresholds to identify and record events.

Key Features
-----------

* Real-time event detection: Uses trigger and detrigger thresholds for acceleration and displacement.
* Data buffering: Manages pre-event data buffering (`pre_trigger_buffer`).
* Configurable recording duration: Includes post-event recording time (`post_event_time`) and minimum event duration (`min_event_duration`).
* Moving average calculation: Uses moving averages for robust detriggering logic.
* Background processing: Spawns threads for saving event data and generating analysis, preventing blocking of the monitoring loop.
* Thread-safe state management: Updates system state (e.g., event count, recording status) using the `state` module.
* Multi-sensor logic: Handles trigger/detrigger conditions based on readings from multiple sensors.