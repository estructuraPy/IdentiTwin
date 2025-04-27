State Management
==============

.. automodule:: identitwin.state
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The ``state`` module provides thread-safe management for global state variables within the system. It helps prevent race conditions when state is accessed concurrently from different threads.

Key Components
------------

* Sensor State: Stores sensor-related variables. Access controlled by `_sensor_lock`.
* Event State: Stores event-related variables. Access controlled by `_event_lock`.
* Configuration State: Provides read-only access to configuration. Access controlled by `_config_lock`.
* System State: Stores system-wide operational states. Access controlled by `_system_lock`.
* Access Functions: Provides `set_*_variable` and `get_*_variable` functions for safe access.
