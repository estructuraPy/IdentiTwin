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
