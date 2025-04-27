"""Thread-safe state management for the IdentiTwin system.

Provides global, thread-safe access to various state variables categorized into:
    - Sensor states (e.g., calibration data)
    - Event states (e.g., recording status, event count)
    - Configuration parameters (read-only access to config)
    - System operational states (e.g., running status)

Uses threading locks to ensure atomic updates and prevent race conditions
when accessed from multiple threads (e.g., acquisition, event, visualization).

Attributes:
    _sensor_state (dict): Stores sensor-related state variables.
    _event_state (dict): Stores event-related state variables.
    _config_state (dict): Stores configuration parameters.
    _system_state (dict): Stores system-wide operational states.
    _sensor_lock (threading.Lock): Lock for accessing `_sensor_state`.
    _event_lock (threading.Lock): Lock for accessing `_event_state`.
    _config_lock (threading.Lock): Lock for accessing `_config_state`.
    _system_lock (threading.Lock): Lock for accessing `_system_state`.
"""
import threading

# Global dictionaries to store state information
_sensor_state = {}
_event_state = {}
_config_state = {}
_system_state = {} # Added for system-wide states

# Thread locks for concurrent access
_sensor_lock = threading.Lock()
_event_lock = threading.Lock()
_config_lock = threading.Lock()
_system_lock = threading.Lock() # Added lock for system state

# Sensor state functions
def set_sensor_variable(key, value):
    """Sets a sensor state variable in a thread-safe manner.

    Args:
        key (str): The name (key) of the sensor state variable.
        value (any): The value to assign to the variable.
    """
    with _sensor_lock:
        _sensor_state[key] = value

def get_sensor_variable(key, default=None):
    """Gets a sensor state variable in a thread-safe manner.

    Args:
        key (str): The name (key) of the sensor state variable.
        default (any, optional): The value to return if the key is not found.
            Defaults to None.

    Returns:
        any: The value of the sensor state variable, or the default value if
             the key is not found.
    """
    with _sensor_lock:
        return _sensor_state.get(key, default)

# Event state functions
def set_event_variable(key, value):
    """Sets an event state variable in a thread-safe manner.

    Args:
        key (str): The name (key) of the event state variable.
        value (any): The value to assign to the variable.
    """
    with _event_lock:
        _event_state[key] = value

def get_event_variable(key, default=None):
    """Gets an event state variable in a thread-safe manner.

    Args:
        key (str): The name (key) of the event state variable.
        default (any, optional): The value to return if the key is not found.
            Defaults to None.

    Returns:
        any: The value of the event state variable, or the default value if
             the key is not found.
    """
    with _event_lock:
        return _event_state.get(key, default)

# Configuration state functions
def set_config_variable(key, value):
    """Sets a configuration state variable in a thread-safe manner.

    Note: Typically used internally during initialization. Modifying config
          during runtime might have unintended consequences.

    Args:
        key (str): The name (key) of the configuration variable.
        value (any): The value to assign to the variable.
    """
    with _config_lock:
        _config_state[key] = value

def get_config_variable(key, default=None):
    """Gets a configuration state variable in a thread-safe manner.

    Args:
        key (str): The name (key) of the configuration variable.
        default (any, optional): The value to return if the key is not found.
            Defaults to None.

    Returns:
        any: The value of the configuration variable, or the default value if
             the key is not found.
    """
    with _config_lock:
        return _config_state.get(key, default)

def get_config():
    """Gets a copy of the entire configuration state dictionary.

    Returns:
        dict: A copy of the configuration state dictionary.
    """
    with _config_lock:
        return dict(_config_state)

# System state functions (New)
def set_system_variable(key, value):
    """Sets a system state variable in a thread-safe manner.

    Args:
        key (str): The name (key) of the system state variable.
        value (any): The value to assign to the variable.
    """
    with _system_lock:
        _system_state[key] = value

def get_system_variable(key, default=None):
    """Gets a system state variable in a thread-safe manner.

    Args:
        key (str): The name (key) of the system state variable.
        default (any, optional): The value to return if the key is not found.
            Defaults to None.

    Returns:
        any: The value of the system state variable, or the default value if
             the key is not found.
    """
    with _system_lock:
        return _system_state.get(key, default)

def reset_state():
    """Resets all state dictionaries (sensor, event, config, system).

    Useful primarily for testing purposes to ensure a clean state between tests.
    """
    with _sensor_lock:
        _sensor_state.clear()
    with _event_lock:
        _event_state.clear()
    with _config_lock:
        _config_state.clear()
    with _system_lock: # Added reset for system state
        _system_state.clear()
