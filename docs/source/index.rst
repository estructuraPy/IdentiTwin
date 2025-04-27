.. IdentiTwin documentation master file.

Welcome to IdentiTwin's Documentation
===================================

.. image:: https://github.com/estructuraPy/IdentiTwin/raw/main/identitwin.png
   :alt: Identitwin logo
   :align: center
   :width: 200px

**IdentiTwin** is a Python library developed under the research project of the **Instituto Tecnológico Nacional de Costa Rica (ITCR)**,
called **Gemelo digital como herramienta de gestión del plan de conservación programada. Caso de estudio: foyer y fumadores del
Teatro Nacional de Costa Rica**.


Project Information
-----------------

:Authors:
    * Ing. Angel Navarro-Mora, M.Sc (ahnavarro@itcr.ac.cr, ahnavarro@anmingenieria.com)
    * Alvaro Perez-Mora (alvaroenrique2001@estudiantec.cr)
:Organization: Instituto Tecnológico de Costa Rica (ITCR)
:Copyright: 2025, Instituto Tecnológico de Costa Rica (ITCR)
:Version: 0.1.0
:License: MIT

Core Modules
-----------

* **Configuration (`configurator`)**: Manages system settings and hardware setup for Raspberry Pi.
* **Calibration (`calibration`)**: Functions for LVDT and accelerometer calibration.
* **Data Acquisition (`acquisition`)**: (Implied) Handles real-time sensor data reading.
* **State Management (`state`)**: Provides thread-safe state variables.
* **Event Monitoring (`event_monitoring`)**: Detects events based on sensor thresholds.
* **Data Processing (`processing_data`)**: Processes and logs sensor data, extracts event data.
* **Data Analysis (`processing_analysis`)**: Performs time/frequency analysis and generates plots/reports for events.
* **Performance Monitoring (`performance_monitor`)**: Tracks acquisition timing and system resource usage.
* **Report Generation (`report_generator`)**: Creates configuration and session summary reports.
* **Visualization (`visualization`)**: (Implied/Future) Real-time data plotting.
* **Simulation (`simulator`)**: Allows running without hardware.

Key Features
-----------

* **Monitoring & Acquisition**:
    - Multi-threaded data acquisition support (implied).
    - Support for LVDT and MPU6050 sensors.
    - Hardware detection for Raspberry Pi.
    - Software simulation mode.

* **Event Detection & Recording**:
    - Configurable trigger/detrigger thresholds.
    - Pre/post-event data buffering.
    - Background saving and analysis of event data.
    - Event-specific file organization.

* **Calibration & Configuration**:
    - LVDT zero-point calculation.
    - Accelerometer bias offset calculation.
    - Storage of calibration parameters.
    - Centralized configuration management.

* **Data Processing & Analysis**:
    - Application of calibration parameters.
    - Time-domain analysis (RMS, peak-to-peak).
    - Frequency-domain analysis (FFT).
    - Generation of plots (Matplotlib).
    - Saving event data (CSV, NumPy).

* **System Performance & Reporting**:
    - Calculation of sampling rates and jitter.
    - Optional CPU/memory monitoring (`psutil`).
    - Performance metric logging.
    - Generation of system and session reports.
    - Detailed reports for detected events.

Installation
-----------

Install IdentiTwin using pip:

.. code-block:: bash

   pip install identitwin

.. toctree::
   :maxdepth: 4
   :caption: Contents:

   modules

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
