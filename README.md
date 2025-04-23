# IdentiTwin

<p align="center">
  <img src="https://github.com/estructuraPy/IdentiTwin/raw/main/identitwin.png" alt="IdentiTwin Logo" width="200"/>
</p>

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

### Step-by-Step Setup (Raspberry Pi)

1. Set execute permissions for setup script:
```bash
chmod +x setup_env/setup_env.sh
```

2. Run the setup script to create virtual environment:
```bash
./setup_env/setup_env.sh
```

3. Activate the virtual environment:
```bash
source venv/bin/activate
```

4. Install IdentiTwin library:
```bash
pip install identitwin
```

5. Configure and run initialization:
```bash
# Copy and modify the example initialization file
cp examples/initialization.py my_initialization.py
# Edit my_initialization.py according to your setup
nano my_initialization.py
# Run initialization
python my_initialization.py
```

To deactivate the virtual environment when finished:
```bash
deactivate
```

### Standard Installation

```bash
pip install identitwin
```

## Documentation

Detailed documentation is available at [Documentation Link].

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Author

- Ing. Angel Navarro-Mora M.Sc (ahnavarro@itcr.ac.cr / ahnavarro@anmingenieria.com)
- Alvaro Perez-Mora (alvaroenrique2001@estudiantec.cr)
 
## Copyright

© 2025 ITCR. All rights reserved.
