Data Processing and Analysis
=========================

.. automodule:: identitwin.processing_analysis
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The ``processing_analysis`` module provides functions for analyzing sensor data collected during detected events within the IdentiTwin system. It handles calculations in both the time and frequency domains, generates visualizations, and creates summary reports.

Key Features
-----------

* Time-domain analysis: Calculates statistical metrics like RMS, peak-to-peak, and crest factor.
* Frequency-domain analysis: Performs Fast Fourier Transform (FFT) on accelerometer data, including detrending and windowing.
* Peak frequency detection: Identifies dominant frequencies in the FFT spectrum.
* Plot generation: Creates time-series and FFT plots for accelerometer and LVDT data using Matplotlib, saving them as PNG files.
* Event report generation: Creates detailed text-based summary reports (`report.txt`) for each event, including peak values, dominant frequencies, and file references.
* Data saving: Saves extracted numerical event data into NumPy `.npz` files.
* Integration: Works with `processing_data` to extract data and orchestrates the post-event analysis workflow.
* Timing drift utilities: Includes basic functions for checking and potentially correcting timing drift (conceptual).
