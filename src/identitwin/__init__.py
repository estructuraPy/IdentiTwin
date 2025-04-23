"""
IdentiTwin - Structural Vibration Monitoring Library

This library provides tools for monitoring structural vibrations using
LVDT sensors and accelerometers.
"""

__version__ = '0.1.0'

# Expose main classes and functions
from .configurator import SystemConfig
from .simulator import SimulatorConfig
from .system_monitoring import MonitoringSystem
from .event_monitoring import EventMonitor
from .performance_monitor import PerformanceMonitor
from . import calibration
from . import processing_data
from . import processing_analysis
from . import report_generator
from . import state

# Optionally expose specific functions if needed, e.g.:
# from .calibration import initialize_lvdt, multiple_accelerometers
# from .processing_data import initialize_general_csv, create_acceleration_csv, create_displacement_csv
# from .processing_analysis import generate_event_analysis, calculate_fft
# from .report_generator import generate_summary_report, generate_system_report
