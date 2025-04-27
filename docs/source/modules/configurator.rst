Configuration
============

.. automodule:: identitwin.configurator
   :members:
   :undoc-members:
   :show-inheritance:

Overview
--------

The ``configurator`` module provides the ``SystemConfig`` class for managing system parameters and hardware initialization, primarily for Raspberry Pi. It handles conditional import of hardware libraries and sets the operational mode (hardware or simulation).

Key Features
-----------

* Hardware detection: Checks for Linux environment and I2C.
* Conditional library import: Imports hardware libraries (`gpiozero`, `adafruit_ads1x15`, etc.) if available.
* Operational mode setting: Sets hardware or simulation mode.
* System settings management: Configures sensors, sampling rates, thresholds, paths, etc.
* Hardware initialization: Provides methods to set up LEDs, ADC, and accelerometers.
* Directory management: Creates output directories.
* Calibration storage: Holds calibration data.

