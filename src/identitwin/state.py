"""
State Management Module for IdentiTwin.

Provides thread-safe global dictionaries to manage the shared state across
different modules of the IdentiTwin monitoring system. This includes sensor status,
event tracking information, and configuration parameters. Locks are used to ensure
atomic updates and prevent race conditions in multi-threaded environments.

Key Features:
- Thread-safe access to shared state variables using locks.
- Separate dictionaries for sensor, event, and configuration states.
- Functions to get, set, and reset state variables.
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
    """
    Sets or updates a variable in the sensor state dictionary in a thread-safe manner.

    Args:
        key: The key (name) of the sensor state variable.
        value: The value to assign to the state variable.

    Returns:
        None
    """
    with _sensor_lock:
        _sensor_state[key] = value

def get_sensor_variable(key, default=None):
    """
    Retrieves a variable from the sensor state dictionary in a thread-safe manner.

    Args:
        key: The key (name) of the sensor state variable to retrieve.
        default: The value to return if the key is not found (default is None).

    Returns:
        The value associated with the key, or the default value if the key is not found.
    """
    with _sensor_lock:
        return _sensor_state.get(key, default)

# Event state functions
def set_event_variable(key, value):
    """
    Sets or updates a variable in the event state dictionary in a thread-safe manner.

    Args:
        key: The key (name) of the event state variable.
        value: The value to assign to the state variable.

    Returns:
        None
    """
    with _event_lock:
        _event_state[key] = value

def get_event_variable(key, default=None):
    """
    Retrieves a variable from the event state dictionary in a thread-safe manner.

    Args:
        key: The key (name) of the event state variable to retrieve.
        default: The value to return if the key is not found (default is None).

    Returns:
        The value associated with the key, or the default value if the key is not found.
    """
    with _event_lock:
        return _event_state.get(key, default)

# Configuration state functions
def set_config_variable(key, value):
    """
    Sets or updates a variable in the configuration state dictionary in a thread-safe manner.

    Args:
        key: The key (name) of the configuration state variable.
        value: The value to assign to the state variable.

    Returns:
        None
    """
    with _config_lock:
        _config_state[key] = value

def get_config_variable(key, default=None):
    """
    Retrieves a variable from the configuration state dictionary in a thread-safe manner.

    Args:
        key: The key (name) of the configuration state variable to retrieve.
        default: The value to return if the key is not found (default is None).

    Returns:
        The value associated with the key, or the default value if the key is not found.
    """
    with _config_lock:
        return _config_state.get(key, default)

def get_config():
    """
    Retrieves a copy of the entire configuration state dictionary in a thread-safe manner.

    Returns:
        dict: A shallow copy of the current configuration state dictionary.
    """
    with _config_lock:
        return dict(_config_state)

def reset_state():
    """
    Clears all state dictionaries (sensor, event, config) in a thread-safe manner.

    Useful primarily for testing purposes to ensure a clean state between test runs.

    Returns:
        None
    """
    with _sensor_lock:
        _sensor_state.clear()
    with _event_lock:
        _event_state.clear()
    with _config_lock:
        _config_state.clear()
