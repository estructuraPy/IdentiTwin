"""IdentiTwin Structural Monitoring System Library.

This library provides tools for monitoring structural vibrations using
LVDT sensors and accelerometers. It includes modules for configuration,
simulation, data acquisition, processing, analysis, visualization,
event detection, performance monitoring, calibration, and reporting.

Developed by:
    - Ing. Angel Navarro-Mora M.Sc, Escuela de Ingeniería en Construcción
    - Alvaro Perez-Mora, Escuela de Ingeniería Electrónica

Instituto Tecnologico de Costa Rica, 2025
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

__all__ = [
    "SystemConfig",
    "SimulatorConfig",
    "MonitoringSystem",
    "EventMonitor",
    "PerformanceMonitor",
    "calibration",
    "processing_data",
    "processing_analysis",
    "report_generator",
    "state",
]
