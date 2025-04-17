"""
Entry point for the IdentiTwin structural monitoring system.
Uses existing Identitwin modules for configuration, sensor setup,
data acquisition, event detection, and reporting.
"""
import sys
import os
import argparse
import time
from datetime import datetime

from identitwin import configurator, calibration, report_generator
from identitwin.system_monitoring import MonitoringSystem

# default thresholds and rates
ACCEL_RATE = 200.0
LVDT_RATE = 5.0
PLOT_RATE = 10.0

# ===== START: Simulated sensor functions =====
def simulated_create_ads1115(self):
    class SimulatedADS1115:
        def __init__(self):
            self.gain = 2.0 / 3.0
    return SimulatedADS1115()

def simulated_create_lvdt_channels(self, ads):
    class SimulatedAnalogIn:
        def __init__(self, ads, channel, slope=19.86):
            self.ads = ads
            self.channel = channel
            self.cycle_start_time = time.time()
            self.amplitude = 5.0
            self.frequency = 0.1
            self.slope = slope
            self._raw_value = 0
        def _calculate_displacement(self):
            elapsed = time.time() - self.cycle_start_time
            phase = self.channel * (math.pi / self.num_lvdts)
            disp = self.amplitude * math.sin(2 * math.pi * self.frequency * elapsed + phase)
            disp += np.random.normal(0, 0.1)
            return disp
        def _update_raw_value(self):
            disp = self._calculate_displacement()
            volt = disp / self.slope if self.slope else 0.0
            raw = int((volt * 1000.0) / 0.1875)
            self._raw_value = max(-32768, min(raw, 32767))
        @property
        def voltage(self):
            self._update_raw_value()
            v = (self._raw_value * 0.1875) / 1000.0
            return v
        @property
        def raw_value(self):
            self._update_raw_value()
            return self._raw_value
        @property
        def value(self):
            return self.raw_value
    SimulatedAnalogIn.num_lvdts = self.num_lvdts
    return [SimulatedAnalogIn(ads, i, (LVDT_SLOPES[i] if i < len(LVDT_SLOPES) else 19.86))
            for i in range(self.num_lvdts)]

def simulated_create_accelerometers(self):
    class SimulatedMPU6050:
        def __init__(self, address, offsets):
            self.address = address
            self.offsets = offsets
        def get_accel_data(self):
            t = time.time()
            return {
                'x': 0.1 * math.sin(100 * t) + self.offsets.get('x', 0.0),
                'y': 0.5 * math.cos(200 * t) + self.offsets.get('y', 0.0),
                'z': 9.81 + 0.25 * math.sin(5 * t) + self.offsets.get('z', 0.0)
            }
        @property
        def accel_data(self):
            return self.get_accel_data()
    return [
        SimulatedMPU6050(0x68 + i,
            (self.accel_offsets[i] if i < len(self.accel_offsets)
             else {'x': 0.0, 'y': 0.0, 'z': 0.0}))
        for i in range(self.num_accelerometers)
    ]
# ===== END: Simulated sensor functions =====

def parse_args():
    parser = argparse.ArgumentParser(
        description="IdentiTwin Structural Monitoring"
    )
    parser.add_argument('--no-lvdt', action='store_true',
                        help='disable LVDT measurements')
    parser.add_argument('--no-accel', action='store_true',
                        help='disable accelerometer measurements')
    parser.add_argument('--simulation', action='store_true',
                        help='run in simulation mode')
    parser.add_argument('--output-dir', type=str,
                        help='custom output directory')
    parser.add_argument('--accel-rate', type=float,
                        help=f'accel rate (Hz), default {ACCEL_RATE}')
    parser.add_argument('--lvdt-rate', type=float,
                        help=f'lvdt rate (Hz), default {LVDT_RATE}')
    parser.add_argument('--plot-rate', type=float,
                        help=f'plot refresh rate (Hz), default {PLOT_RATE}')
    return parser.parse_args()

def main():
    args = parse_args()
    # set enable flags
    enable_lvdt = not args.no_lvdt
    enable_accel = not args.no_accel

    # adjust rates
    accel_rate = args.accel_rate or ACCEL_RATE
    lvdt_rate = args.lvdt_rate or LVDT_RATE
    plot_rate = args.plot_rate or PLOT_RATE

    # build config
    config = configurator.SystemConfig(
        enable_lvdt=enable_lvdt,
        enable_accel=enable_accel,
        sampling_rate_acceleration=accel_rate,
        sampling_rate_lvdt=lvdt_rate,
        plot_refresh_rate=plot_rate,
        output_dir=args.output_dir
    )
    config.operational_mode = ("Simulation" if args.simulation
                               else "Hardware")

    # Simulation mode override (no more broken import)
    if args.simulation:
        original_init = configurator.SystemConfig.__init__
        def new_init(self, *a, **kw):
            original_init(self, *a, **kw)
            self.create_ads1115 = simulated_create_ads1115.__get__(self, configurator.SystemConfig)
            self.create_lvdt_channels = simulated_create_lvdt_channels.__get__(self, configurator.SystemConfig)
            self.create_accelerometers = simulated_create_accelerometers.__get__(self, configurator.SystemConfig)
        configurator.SystemConfig.__init__ = new_init
        print("Simulation mode enabled: Using simulated sensors.")

    # report system config
    sys_report = os.path.join(config.reports_dir, "system_report.txt")
    report_generator.generate_system_report(config, sys_report)

    # start monitoring
    monitor = MonitoringSystem(config)
    monitor.setup_sensors()
    monitor.initialize_processing()
    monitor.start_monitoring()

    print(f"Monitoring started in {config.operational_mode} mode.")
    try:
        while monitor.running:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("Stopping by user request.")
    finally:
        monitor.stop_monitoring()
        # final summary
        summary = os.path.join(config.reports_dir, "summary_report.txt")
        report_generator.generate_summary_report(monitor, summary)
        monitor.cleanup()
        print("Monitoring finished.")

if __name__ == "__main__":
    main()

