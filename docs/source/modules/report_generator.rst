Report Generation
==============

.. automodule:: identitwin.report_generator
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The ``report_generator`` module is responsible for creating text-based reports that summarize system configuration, monitoring session details, and detected events within the IdentiTwin system.

Key Features
-----------

* System configuration report: Documents operational mode, sensor setup, sampling rates, event parameters, and storage locations.
* Monitoring summary report: Provides session statistics (event count), performance metrics (sampling rates, jitter from `PerformanceMonitor`), and summaries of detected events.
* Event summarization: Reads key information (peak values, duration) from individual event report files (`report.txt`) located in event subfolders.
* File management: Saves generated reports to the designated reports directory specified in the configuration.
* Timestamping: Includes generation timestamps in reports.
