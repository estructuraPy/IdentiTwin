Data Processing
============

.. automodule:: identitwin.processing_data
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The ``processing_data`` module manages the reading, calibration application, and storage of sensor data for the IdentiTwin system. It handles the creation and writing of CSV files for both continuous logging and event-specific data, and provides utilities for extracting numerical data from event buffers.

Key Features
-----------

* CSV initialization: Sets up CSV files with appropriate headers for combined, displacement, and acceleration data.
* LVDT data reading: Reads voltage from LVDT channels and applies calibration (slope/intercept) to calculate displacement.
* Calibration handling: Manages missing or incomplete LVDT calibration data using default values and warnings.
* Event data extraction: Converts buffered event data (timestamps, accel, LVDT readings) into NumPy arrays for analysis.
* Event CSV creation: Generates event-specific CSV files (`displacements.csv`, `acceleration.csv`) with timestamps and sensor readings.
* Time synchronization: Formats timestamps and calculates relative time for CSV output.
* Error handling: Includes checks for missing data and logs errors during file operations.
