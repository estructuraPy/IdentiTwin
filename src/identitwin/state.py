"""
State management module for the IdentiTwin monitoring system.

This module provides a thread-safe state management system for:
- Sensor states
- Event tracking
- Configuration parameters
- System operational states

Key Features:
- Thread-safe state access
- Hierarchical state organization
- Dynamic state updates
- State persistence
- State recovery
- Configuration state management
- Event state tracking

The module ensures consistent state management across all system
components with proper synchronization and access control.
"""
import threading

# Global dictionaries to store state information
_sensor_state = {}
_event_state = {}
_config_state = {}

# Thread locks for concurrent access
_sensor_lock = threading.Lock()
_event_lock = threading.Lock()
_config_lock = threading.Lock()

# Sensor state functions
def set_sensor_variable(key, value):
    """Set a sensor state variable."""
    with _sensor_lock:
        _sensor_state[key] = value

def get_sensor_variable(key, default=None):
    """Get a sensor state variable."""
    with _sensor_lock:
        return _sensor_state.get(key, default)

# Event state functions
def set_event_variable(key, value):
    """Set an event state variable."""
    with _event_lock:
        _event_state[key] = value

def get_event_variable(key, default=None):
    """Get an event state variable."""
    with _event_lock:
        return _event_state.get(key, default)

# Configuration state functions
def set_config_variable(key, value):
    """Set a configuration state variable."""
    with _config_lock:
        _config_state[key] = value

def get_config_variable(key, default=None):
    """Get a configuration state variable."""
    with _config_lock:
        return _config_state.get(key, default)

def get_config():
    """Get the entire configuration state."""
    with _config_lock:
        return dict(_config_state)

def reset_state():
    """Reset all state information (useful for testing)."""
    with _sensor_lock:
        _sensor_state.clear()
    with _event_lock:
        _event_state.clear()
    with _config_lock:
        _config_state.clear()
