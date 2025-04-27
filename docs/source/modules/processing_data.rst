Data Processing
============

.. automodule:: identitwin.processing_data
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The ``processing_data`` module manages reading, applying calibration, and storing sensor data. It handles CSV file creation and writing for logging and event data, and provides utilities for extracting data from event buffers.

Key Features
-----------

* CSV initialization: Sets up CSV files with headers.
* LVDT data reading: Reads voltage and applies calibration.
* Calibration handling: Manages missing LVDT calibration data.
* Event data extraction: Converts buffered event data into NumPy arrays.
* Event CSV creation: Generates event-specific CSV files.
* Time synchronization: Formats timestamps for CSV output.
* Error handling: Includes checks for missing data and file errors.
