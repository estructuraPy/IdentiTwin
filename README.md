# IdentiTwin

<p align="center">
  <img src="https://github.com/estructuraPy/IdentiTwin/raw/main/identitwin.png" alt="IdentiTwin Logo" width="200"/>
</p>

## Overview

IdentiTwin is developed under the project ``Gemelo digital como herramienta de gestión del plan de conservación programada. Caso de estudio: foyer y fumadores del Teatro Nacional de Costa Rica``. The library provides comprehensive tools for structural vibration and displacement acquisition using Raspberry Pi and associated sensors.

## Core Features

### Real-time Monitoring
- Multi-threaded data acquisition system optimized for Raspberry Pi.
- Support for LVDT displacement sensors (via ADS1115 ADC) and MPU6050 accelerometers.
- Continuous performance tracking (sampling rate, jitter).
- Automated event detection based on configurable thresholds.
- Thread-safe data handling and buffering (pre-event and post-event).
- Status reporting and LED indicators.

### Event Detection & Recording
- Configurable trigger/detrigger thresholds for acceleration and displacement.
- Pre-event and post-event data buffering to capture the full event context.
- Minimum event duration setting to filter noise.
- Automated data persistence: saves event data to CSV and NPZ files.
- Background processing for saving data and generating analysis without interrupting acquisition.

### Signal Processing & Analysis
- Basic time-domain analysis (peak values).
- Fast Fourier Transform (FFT) analysis for frequency domain insights.
- Calculation of dominant frequencies.
- Automated generation of analysis plots (time series and FFT) for each event.
- Generation of summary reports for monitoring sessions and individual events.

### Hardware Support & Configuration
- Designed for Raspberry Pi with specific hardware (ADS1115, MPU6050).
- Utilizes `gpiozero` for LED indicators.
- I2C communication setup for sensors.
- Simulation mode for development and testing on non-Raspberry Pi platforms.
- Flexible configuration via Python script (`initialization.py`).

## Installation

```bash
pip install identitwin
```

### Prerequisites
- Raspberry Pi (tested on Raspberry Pi 5) with Raspberry Pi OS (or compatible Linux distribution).
- Python 3.8+
- Git

### Hardware Setup
- Connect ADS1115 ADC and MPU6050 sensors to the Raspberry Pi's I2C pins (SDA, SCL, VCC, GND). Ensure unique I2C addresses if using multiple MPU6050 sensors (e.g., 0x68, 0x69).
- Connect LVDTs to the ADS1115 analog input channels.
- Connect status and activity LEDs to the specified GPIO pins.

### Software Setup (Raspberry Pi)

1.  **Clone the Repository:**
    ```bash
    git clone https://github.com/estructuraPy/IdentiTwin.git
    cd IdentiTwin
    ```

2.  **Set up Virtual Environment (Recommended):**
    *   Give execute permissions to the setup script:
        ```bash
        chmod +x setup_env/setup_env.sh
        ```
    *   Run the setup script:
        ```bash
        ./setup_env/setup_env.sh
        ```
        This creates a virtual environment named `venv` and installs dependencies.

3.  **Activate the Virtual Environment:**
    ```bash
    source venv/bin/activate
    ```
    *(Your terminal prompt should now show `(venv)`)*

4.  **Install the Library (if not done by setup script):**
    If you didn't use the setup script or need to reinstall:
    ```bash
    pip install .
    ```
    *(The `.` refers to the current directory where `setup.py` is located)*

5.  **Configure and Run:**
    *   Navigate to the examples directory:
        ```bash
        cd examples
        ```
    *   *(Optional)* Copy the example initialization file if you want to keep the original:
        ```bash
        # cp initialization.py my_config.py
        # nano my_config.py
        ```
    *   Edit `initialization.py` (or your copy) to match your hardware setup:
        *   Set `NUM_LVDTS`, `NUM_ACCELS`.
        *   Define correct `LVDT_SLOPES` based on your sensor calibration.
        *   Adjust sampling rates (`ACCEL_SAMPLING_RATE`, `LVDT_SAMPLING_RATE`) if needed.
        *   Modify trigger/detrigger thresholds and event timing parameters as required.
        ```bash
        nano initialization.py
        ```
    *   Run the initialization script:
        ```bash
        python initialization.py
        ```
        *(Add command-line arguments if needed, e.g., `--output-dir /path/to/data`)*

6.  **Deactivate Virtual Environment (When finished):**
    ```bash
    deactivate
    ```

## Setup

1.  **Prerequisites:** Ensure you have Python 3.9+ installed. Conda is recommended but optional.
2.  **Clone the repository:**
    ```bash
    git clone <repository_url>
    cd identitwin
    ```
3.  **Set up the environment:**
    *   **Windows:** Double-click or run `setup_env\setup_env.bat` from the command prompt. This script will detect if Conda is available and create a Conda environment named `identitwin`. If Conda is not found, it will create a standard Python virtual environment (`venv`) in the project root. It will then install all necessary dependencies from `requirements.txt`.
    *   **Linux/macOS:** Run `setup_env/setup_env.sh` (assuming this script exists or will be created with similar functionality).
        ```bash
        cd setup_env
        bash setup_env.sh
        cd ..
        ```

## Running the Application

After setting up the environment, you can run the simulation or the main system using the provided scripts. These scripts automatically activate the correct virtual environment (Conda or venv) before execution.

*   **Run Simulation:**
    *   **Windows:** Double-click or run `run_simulation.bat`.
    *   **Linux/macOS:** Run `run_simulation_linux.sh`.
        ```bash
        ./run_simulation_linux.sh
        ```

*   **Run System:**
    *   **Linux/macOS:** Run `run_system_linux.sh`.
        ```bash
        ./run_system_linux.sh
        ```


## Documentation

Full documentation is available at [Read the Docs](https://identitwin.readthedocs.io/).

Further details on configuration options, data formats, and analysis interpretation can be found in the project's technical documentation (link to be added).

## Requirements

- Python 3.8+
- numpy
- matplotlib

**Raspberry Pi Specific:**
- gpiozero
- lgpio # Required by gpiozero on newer Raspberry Pi OS versions
- adafruit-circuitpython-ads1x15
- mpu6050-raspberrypi
- adafruit-blinka (for CircuitPython compatibility)

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.

## Authors

- Ing. Angel Navarro-Mora M.Sc (ahnavarro@itcr.ac.cr / ahnavarro@anmingenieria.com)
- Alvaro Perez-Mora (alvaroenrique2001@estudiantec.cr)

## Copyright

© 2025 Instituto Tecnológico de Costa Rica (ITCR). All rights reserved.

# Identitwin Project

This project implements the Identitwin system.

