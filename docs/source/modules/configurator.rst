Configuration
============

.. automodule:: identitwin.configurator
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The ``configurator`` module provides the ``SystemConfig`` class for managing system parameters, operational modes, and hardware initialization for the IdentiTwin system, primarily targeting Raspberry Pi. It handles the conditional import of hardware libraries and determines the operational mode (hardware or simulation) based on platform and library availability.

Key Features
-----------

* Hardware detection: Checks for Linux environment (Raspberry Pi) and I2C availability.
* Conditional library import: Attempts to import necessary hardware libraries (`gpiozero`, `adafruit_ads1x15`, `mpu6050`, etc.).
* Operational mode setting: Defaults to software simulation if hardware or libraries are unavailable.
* System settings management: Configures sensor enablement, sampling rates, event thresholds, file paths, GPIO pins, etc.
* Hardware initialization methods: Provides functions to set up LEDs, ADC (ADS1115), and accelerometers (MPU6050) if in hardware mode.
* Directory management: Creates necessary output directories for logs, events, and reports.
* Calibration storage: Holds LVDT and accelerometer calibration data.

