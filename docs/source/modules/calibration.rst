Calibration
==========

.. automodule:: identitwin.calibration
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The ``calibration`` module provides functions for calibrating LVDT displacement sensors and MPU6050 accelerometers. It includes methods for determining LVDT intercepts and calculating accelerometer bias offsets.

Key Features:
------------

* LVDT initialization: Determines zero-point intercepts.
* Accelerometer calibration: Calculates bias offsets (assumes stationary).
* Offset application: Applies calculated offsets to raw accelerometer data.
* Calibration logging: Saves calibration parameters to a log file.
* Configuration integration: Stores parameters in the system configuration.