"""
Simulation configuration module.
Este módulo reemplaza configurator.py en modo simulación, proporcionando una API similar
pero con implementaciones dummy para evitar el uso de hardware real.
"""
import os
import platform
from datetime import datetime
import time
import numpy as np

# Clases dummy para simular hardware
class DummyLED:
    def off(self):
        print("DummyLED off")

class DummyADS:
    def __init__(self):
        self.gain = None

class DummyAnalogIn:
    def __init__(self, ads, channel):
        self.ads = ads
        self.channel = channel
    def read(self):
        return 0  # valor simulado

class DummyMPU6050:
    def __init__(self, addr):
        self.addr = addr
    def get_accel_data(self):
        return {"x": 0, "y": 0, "z": 0}

# Clase de configuración simulada
class SimulatorConfig:
    """Configuration class for simulation mode."""
    def __init__(
        self,
        enable_lvdt=True,
        enable_accel=True,
        output_dir=None,
        num_lvdts=2,
        num_accelerometers=2,
        sampling_rate_acceleration=200.0,
        sampling_rate_lvdt=5.0,
        plot_refresh_rate=10.0,
        gpio_pins=None,
        trigger_acceleration_threshold=None,
        detrigger_acceleration_threshold=None,
        trigger_displacement_threshold=None,
        detrigger_displacement_threshold=None,
        pre_trigger_time=2.0,
        post_trigger_time=5.0,
        min_event_duration=1.0,
    ):
        # Configuración de directorios y archivos
        self.output_dir = output_dir or os.path.join("repository", datetime.now().strftime("%Y%m%d"))
        os.makedirs(self.output_dir, exist_ok=True)
        self.events_dir = os.path.join(self.output_dir, "events")
        self.logs_dir = os.path.join(self.output_dir, "logs")
        self.reports_dir = os.path.join(self.output_dir, "reports")
        for directory in [self.events_dir, self.logs_dir, self.reports_dir]:
            os.makedirs(directory, exist_ok=True)
        self.acceleration_file = os.path.join(self.output_dir, "acceleration.csv")
        self.displacement_file = os.path.join(self.output_dir, "displacement.csv")
        self.general_file = os.path.join(self.output_dir, "general_measurements.csv")
        self.enable_performance_monitoring = True
        self.performance_log_file = os.path.join(self.logs_dir, "performance_log.csv")
        
        # Configuración de sensores
        self.enable_lvdt = enable_lvdt
        self.enable_accel = enable_accel
        self.num_lvdts = num_lvdts
        self.num_accelerometers = num_accelerometers
        
        self.sampling_rate_acceleration = sampling_rate_acceleration
        self.sampling_rate_lvdt = sampling_rate_lvdt
        self.plot_refresh_rate = plot_refresh_rate
        self.time_step_acceleration = 1.0 / self.sampling_rate_acceleration
        self.time_step_lvdt = 1.0 / self.sampling_rate_lvdt
        self.time_step_plot_refresh = 1.0 / self.plot_refresh_rate
        
        self.window_duration = 5
        self.gravity = 9.81
        self.max_accel_jitter = 1.5
        self.max_lvdt_jitter = 5.0
        
        self.trigger_acceleration_threshold = trigger_acceleration_threshold or (0.3 * self.gravity)
        self.trigger_displacement_threshold = trigger_displacement_threshold or 1.0
        self.detrigger_acceleration_threshold = detrigger_acceleration_threshold or (self.trigger_acceleration_threshold * 0.5)
        self.detrigger_displacement_threshold = detrigger_displacement_threshold or (self.trigger_displacement_threshold * 0.5)
        
        self.pre_trigger_time = pre_trigger_time
        self.post_trigger_time = post_trigger_time
        self.min_event_duration = min_event_duration
        
        # Parámetros de simulación para LVDT
        self.lvdt_gain = 2.0 / 3.0
        self.lvdt_scale_factor = 0.1875
        self.lvdt_slope = 19.86
        self.lvdt_intercept = 0.0
        
        # Configuración del acelerómetro (valores dummy)
        self.accel_offsets = [{"x": 0.0, "y": 0.0, "z": 0.0} for _ in range(self.num_accelerometers)]
        
        # En simulación no se usan pines GPIO reales
        self.gpio_pins = gpio_pins or [None, None]
        
        # Imprime información de la plataforma en modo simulación
        print(f"Platform: {platform.system()} {platform.release()}")
        print("Running in Simulation Mode")

    def initialize_thresholds(self):
        """Initialize the thresholds for event detection."""
        return {
            "acceleration": self.trigger_acceleration_threshold if self.enable_accel else None,
            "displacement": self.trigger_displacement_threshold if self.enable_lvdt else None,
            "pre_event_time": self.pre_trigger_time,
            "post_event_time": self.post_trigger_time,
            "min_event_duration": self.min_event_duration,
        }

    def initialize_leds(self):
        """Return dummy LED objects."""
        return DummyLED(), DummyLED()

    def create_ads1115(self):
        """Return a dummy ADS instance."""
        dummy = DummyADS()
        dummy.gain = self.lvdt_gain
        return dummy

    def create_lvdt_channels(self, ads):
        """Create dummy LVDT channels using a cyclic mapping (simulation)."""
        channels = []
        # Uso de 4 "canales" dummy para simular ADS1115
        dummy_channel_list = [0, 1, 2, 3]
        for i in range(self.num_lvdts):
            ch = dummy_channel_list[i % len(dummy_channel_list)]
            channels.append(DummyAnalogIn(ads, ch))
        return channels

    def create_accelerometers(self):
        """Return dummy MPU6050 accelerometer objects."""
        mpu_list = []
        for i in range(self.num_accelerometers):
            mpu_list.append(DummyMPU6050(0x68 + i))
        return mpu_list


# Utilidades simuladas (similar a configurator, pero dummy)
def leds(gpio_pins):
    return DummyLED(), DummyLED()

def ads1115():
    dummy = DummyADS()
    dummy.gain = 2.0 / 3.0
    return dummy

def thresholds(trigger_acceleration, trigger_displacement, pre_time, enable_accel, enable_lvdt):
    return {
        "acceleration": trigger_acceleration if enable_accel else None,
        "displacement": trigger_displacement if enable_lvdt else None,
        "pre_event_time": pre_time,
        "post_event_time": pre_time,
    }
