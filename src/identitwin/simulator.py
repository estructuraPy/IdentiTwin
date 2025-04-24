"""
Simulation configuration module.
Este módulo reemplaza configurator.py en modo simulación, proporcionando una API similar
pero con implementaciones dummy para evitar el uso de hardware real.
"""
import os
import platform
from datetime import datetime
import time
import math
import numpy as np
import random  # Añadir esta importación


# Clases dummy para simular hardware
class DummyLED:
    def __init__(self, verbose=False):  # Default verbosity to False
        self.verbose = verbose  # Control whether messages are printed

    def off(self):
        if self.verbose:
            print("DummyLED off")

    def toggle(self):
        if self.verbose:
            print("DummyLED toggled")  # Simulate toggling the LED

class DummyADS:
    def __init__(self):
        self.gain = None

class DummyAnalogIn:
    def __init__(self, ads, channel, slope=19.86, intercept=0.0):
        self.ads = ads
        self.channel = channel
        self.slope = slope
        self.intercept = intercept
        self._raw_value = 0  # Internal state for raw value
        self.last_voltage = 0.0
        self.cycle_start_time = time.time()
        self.amplitude = 5.0  # mm
        self.frequency = 0.1  # Hz

    def _calculate_displacement(self):
        """Calculates the simulated displacement."""
        current_time = time.time()
        elapsed_time = current_time - self.cycle_start_time
        phase_shift = self.channel * (math.pi / 4)  # Adjust phase shift for each channel
        displacement = self.amplitude * math.sin(2 * math.pi * self.frequency * elapsed_time + phase_shift)
        noise = np.random.normal(0, 0.1)  # Gaussian noise with std dev 0.1mm
        displacement += noise
        return displacement

    def _update_raw_value(self):
        """Updates the internal raw value based on simulated displacement."""
        displacement = self._calculate_displacement()
        voltage = displacement / self.slope if self.slope != 0 else 0.0
        simulated_raw = int((voltage * 1000.0) / 0.1875)
        self._raw_value = max(-32768, min(simulated_raw, 32767))

    @property
    def voltage(self):
        """Calculates voltage from the simulated raw value."""
        self._update_raw_value()  # Ensure raw value is current
        voltage = (self._raw_value * 0.1875) / 1000.0
        self.last_voltage = voltage
        return voltage

    def elongation(self):
        """Calculates elongation based on the simulated voltage."""
        voltage = self.voltage
        return self.slope * voltage + self.intercept

class DummyMPU6050:
    def __init__(self, addr):
        self.addr = addr
        self._cycle_start_time = time.time()
        self._current_interval = self._generate_random_interval()
        self.state = "noise"  # Estado inicial: solo ruido
        self.transition_progress = 0  # Progreso de la transición (0 a 1)

    def _generate_random_interval(self):
        """Genera un intervalo aleatorio entre 20 y 40 segundos."""
        return random.uniform(30, 35)

    def _update_state(self, t):
        """Actualiza el estado y reinicia el ciclo si se excede el intervalo."""
        if t >= self._current_interval:
            self._cycle_start_time = time.time()
            self._current_interval = self._generate_random_interval()
            self.state = "periodic" if self.state == "noise" else "noise"
            self.transition_progress = 0  # Reinicia la transición

    def _apply_transition(self, value, transition_type):
        """Aplica una transición suave o abrupta."""
        if transition_type == "smooth":
            # Usar una interpolación lineal
            return value * (1 - self.transition_progress)
        elif transition_type == "abrupt":
            # Usar un cambio abrupto pero con cierta aleatoriedad
            return value if self.transition_progress < 0.75 else 0
        return value

    def get_accel_data(self, transition_type="smooth"):
        """Simula datos del acelerómetro con ruido constante y señales periódicas."""
        t = time.time() - self._cycle_start_time

        # Actualiza el estado si es necesario
        self._update_state(t)

        # Incrementa el progreso de la transición
        self.transition_progress = min(self.transition_progress + 0.01, 1)  # Progreso en cada llamada

        # Ruido constante
        noise_x = 0.005 * math.sin(t * 2 * math.pi * 50) + 0.003 * math.sin(t * 2 * math.pi * 80)
        noise_y = 0.006 * math.cos(t * 2 * math.pi * 60) + 0.004 * math.cos(t * 2 * math.pi * 100)
        noise_z = 0.007 * math.sin(t * 2 * math.pi * 70) + 0.005 * math.cos(t * 2 * math.pi * 90)

        if self.state == "periodic":
            # Señales periódicas superpuestas
            periodic_signal_x = 0.75 * math.sin(t * 2 * math.pi * 18) + 0.05 * math.sin(t * 2 * math.pi * 43)
            periodic_signal_y = 0.05 * math.cos(t * 2 * math.pi * 19) + 0.55 * math.cos(t * 2 * math.pi * 42)
            periodic_signal_z = 0.75 * math.sin(t * 2 * math.pi * 21) + 0.05 * math.sin(t * 2 * math.pi * 40)

            # Aplica la transición a las señales periódicas
            periodic_signal_x = self._apply_transition(periodic_signal_x, transition_type)
            periodic_signal_y = self._apply_transition(periodic_signal_y, transition_type)
            periodic_signal_z = self._apply_transition(periodic_signal_z, transition_type)

            return {
                'x': noise_x + periodic_signal_x,
                'y': noise_y + periodic_signal_y,
                'z': 9.81 + noise_z + periodic_signal_z  # Gravedad + ruido + señales periódicas
            }
        else:
            # Solo ruido
            return {
                'x': noise_x,
                'y': noise_y,
                'z': 9.81 + noise_z  # Gravedad + ruido
            }

        
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
        pre_event_time=5.0,
        post_event_time=15.0,
        min_event_duration=2.0,
        verbose=False,  # Add verbosity flag
    ):
        self.verbose = verbose  # Store verbosity setting
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
        
        self.pre_event_time = pre_event_time # Corrected
        self.post_event_time = post_event_time # Corrected
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
            "pre_event_time": self.pre_event_time, # Corrected
            "post_event_time": self.post_event_time, # Corrected
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

    def process_lvdt_data(self, lvdt_data, lvdt_index=None):
        """Process LVDT data without any logging."""
        return lvdt_data  # Return data directly without any logging


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
