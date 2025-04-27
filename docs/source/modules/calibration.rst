Calibration
==========

.. automodule:: identitwin.calibration
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The ``calibration`` module provides functionality for calibrating and initializing sensors for the IdentiTwin system, specifically LVDT displacement sensors and MPU6050 accelerometers. It handles determining zero-point intercepts for LVDTs and calculating bias offsets for accelerometers.

Key Features:
------------

* LVDT initialization: Determines zero-point intercepts based on initial voltage and sensitivity slopes.
* Accelerometer calibration: Calculates bias offsets assuming sensors are stationary.
* Offset application: Provides functions to apply calculated offsets to raw accelerometer data.
* Calibration logging: Saves LVDT intercepts and accelerometer offsets to a log file.
* Configuration integration: Stores calibration parameters within the system configuration object.