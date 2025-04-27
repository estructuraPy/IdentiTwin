# IdentiTwin

![Identitwin logo](https://github.com/estructuraPy/IdentiTwin/raw/main/identitwin.png)

**IdentiTwin** is a Python library for structural health monitoring using sensors like LVDTs and accelerometers, primarily designed for use with Raspberry Pi. It was developed as part of a research project at the Instituto Tecnológico de Costa Rica (ITCR).

## Overview

The library provides modules for:

*   **Configuration**: Setting up system parameters and hardware.
*   **Calibration**: Calibrating LVDT and accelerometer sensors.
*   **Data Acquisition**: Reading sensor data in real-time (typically implemented in the main application script).
*   **Event Monitoring**: Detecting structural events based on configurable thresholds.
*   **Data Processing**: Handling sensor data, applying calibration, and logging.
*   **Data Analysis**: Performing time and frequency domain analysis on event data.
*   **Performance Monitoring**: Tracking acquisition timing and system resources.
*   **Reporting**: Generating summary reports for configuration and monitoring sessions.
*   **Simulation**: Allowing the system to run without actual hardware for testing.

## Key Features

*   Supports LVDT displacement sensors and MPU6050 accelerometers.
*   Real-time event detection with pre/post-event buffering.
*   Automated calibration procedures.
*   Data logging to CSV files.
*   Analysis of event data including FFT.
*   Generation of plots and reports for events.
*   Performance tracking (sampling rate, jitter, CPU/memory usage).
*   Designed for Raspberry Pi but includes a simulation mode.

## Installation

```bash
pip install identitwin
```

## Documentation

For more detailed information, please refer to the [documentation](https://estructurapy.github.io/IdentiTwin/).

## Project Information

*   **Authors**:
    *   Ing. Angel Navarro-Mora, M.Sc (ahnavarro@itcr.ac.cr, ahnavarro@anmingenieria.com)
    *   Alvaro Perez-Mora (alvaroenrique2001@estudiantec.cr)
*   **Organization**: Instituto Tecnológico de Costa Rica (ITCR)
*   **License**: MIT

