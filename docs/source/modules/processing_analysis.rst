Data Processing and Analysis
=========================

.. automodule:: identitwin.processing_analysis
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The ``processing_analysis`` module provides functions for analyzing sensor data collected during events. It includes time and frequency domain calculations, visualization generation, and summary report creation.

Key Features
-----------

* Time-domain analysis: Calculates metrics like RMS, peak-to-peak.
* Frequency-domain analysis: Performs FFT on accelerometer data.
* Peak frequency detection: Identifies dominant frequencies.
* Plot generation: Creates time-series and FFT plots (Matplotlib).
* Event report generation: Creates text summary reports for events.
* Data saving: Saves numerical event data (`.npz` files).
* Integration: Works with `processing_data` for post-event analysis.
* Timing drift utilities: Basic functions for checking timing drift.
