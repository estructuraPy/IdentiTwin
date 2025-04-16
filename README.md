# IdentiTwin

<p align="center">
  <img src="https://github.com/estructuraPy/IdentiTwin/raw/main/identitwin.png" alt="IdentiTwin Logo" width="200"/>
</p>

A Python library for structural monitoring and vibration analysis, developed by ANM Ingeniería.

## Overview

IdentiTwin is developed under the project ``Gemelo digital como herramienta de gestión del plan de conservación programada. Caso de estudio: foyer y fumadores del Teatro Nacional de Costa Rica``. The library provides comprehensive tools for structural vibration and displacement acquisition.

## Core Features

### Real-time Monitoring
- Multi-threaded data acquisition system
- Support for LVDT and MPU6050 accelerometers
- Continuous performance tracking
- Automated event detection and recording
- Thread-safe data handling

### Event Detection
- Configurable trigger/detrigger thresholds
- Pre-event and post-event data buffering
- Duration-based event classification
- Automated data persistence
- Event analysis and reporting

### Signal Processing
- Fast Fourier Transform (FFT) analysis
- Statistical calculations (RMS, peak-to-peak, crest factor)
- Time-domain analysis
- Moving average filtering
- Data validation and cleaning

### Hardware Support
- LVDT sensors via ADS1115 ADC
- MPU6050 accelerometers
- LED status indicators
- Raspberry Pi GPIO integration
- Simulation mode for testing

## Installation

```bash
pip install identitwin
```

## Documentation

Detailed documentation is available at [Documentation Link].

## Requirements

- Python 3.8+
- numpy
- matplotlib
- gpiozero (for Raspberry Pi)
- adafruit-circuitpython-ads1x15
- mpu6050-raspberrypi

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Author

- Ing. Angel Navarro-Mora M.Sc (ahnavarro@itcr.ac.cr / ahnavarro@anmingenieria.com)
- Alvaro Perez-Mora (alvaroenrique2001@estudiantec.cr)
 
## Copyright

© 2025 ITCR. All rights reserved.

## Version

Current version: 0.1.0
