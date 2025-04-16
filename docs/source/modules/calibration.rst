Calibration
==========

.. automodule:: identitwin.calibration
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The ``calibration`` module provides functionality for calibrating and initializing various sensors in the IdentiTwin monitoring system:

* LVDT (Linear Variable Differential Transformer) displacement sensors initialization and zeroing
* Accelerometer (MPU6050) calibration including bias and scale factor adjustments
* Calibration data persistence and loading
* Multi-sensor calibration support

Key Features:
------------

* Automatic zero-point detection for LVDTs
* Multiple sensor support with individual calibration parameters
* Calibration data logging with timestamps
* Error handling and validation
* Support for custom calibration slopes
* Persistent storage of calibration data