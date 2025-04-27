State Management
==============

.. automodule:: identitwin.state
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The ``state`` module provides global, thread-safe management for various state variables within the IdentiTwin system. It ensures atomic updates and prevents race conditions when state is accessed concurrently from different threads (e.g., acquisition, event monitoring, visualization). State variables are categorized for clarity.

Key Components
------------

* Sensor State: Stores sensor-related variables (e.g., calibration data). Access controlled by `_sensor_lock`.
* Event State: Stores event-related variables (e.g., recording status, event count, trigger times). Access controlled by `_event_lock`.
* Configuration State: Provides read-only access to configuration parameters. Access controlled by `_config_lock`.
* System State: Stores system-wide operational states (e.g., overall running status). Access controlled by `_system_lock`.
* Access Functions: Provides `set_*_variable` and `get_*_variable` functions for safe access to each state category.
