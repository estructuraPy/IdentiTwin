"""Data analysis module for the IdentiTwin monitoring system.

Provides functions for analyzing sensor data collected during events, including:
    - Time-domain statistical calculations (RMS, peak-to-peak, crest factor).
    - Frequency-domain analysis using FFT (Fast Fourier Transform).
    - Peak frequency detection.
    - Generation of analysis plots (time series and FFT) using Matplotlib.
    - Creation of text-based event summary reports.
    - Saving processed event data and analysis results.
    - Basic timing drift detection and correction utilities.

Integrates with data processing functions to extract data and save results.
"""

import os
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from datetime import datetime
from .processing_data import extract_data_from_event  # Add this import
import traceback  # Add this import for exception handling

def calculate_fft(data, sampling_rate):
    """Calculates the one-sided Fast Fourier Transform (FFT) of 3-axis data.

    Applies detrending (removes mean), a Hanning window, and calculates the
    real FFT for the 'x', 'y', and 'z' components of the input data. Normalizes
    the amplitude spectrum correctly for a one-sided representation.

    Args:
        data (dict): A dictionary containing NumPy arrays for 'x', 'y', and 'z'
                     axis data. Missing axes are treated as zeros. NaNs are
                     replaced with 0.
        sampling_rate (float): The sampling rate of the input data in Hz. Must be > 0.

    Returns:
        tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]: A tuple containing:
            - freqs (np.ndarray): Array of frequency bins up to the Nyquist frequency.
            - fft_x (np.ndarray): Amplitude spectrum for the x-axis.
            - fft_y (np.ndarray): Amplitude spectrum for the y-axis.
            - fft_z (np.ndarray): Amplitude spectrum for the z-axis.
            Returns empty arrays if sampling_rate <= 0 or input data is empty.
    """
    if sampling_rate <= 0:
        print(f"Warning: Invalid sampling rate ({sampling_rate}) for FFT calculation.")
        return np.array([]), np.array([]), np.array([]), np.array([])

    # Datasets por eje
    n = len(data.get('x', []))
    if n == 0:
        return np.array([]), np.array([]), np.array([]), np.array([])

    # Detrend: restar media
    axes = {}
    for axis in ['x','y','z']:
        arr = np.nan_to_num(data.get(axis, np.zeros(n)))
        axes[axis] = arr - np.mean(arr)

    # Hanning window
    window = np.hanning(n)
    window_sum = np.sum(window)

    # FFT y normalización
    fft_results = {}
    for axis, signal in axes.items():
        y = np.fft.rfft(signal * window)
        # One-sided amplitude spectrum
        fft_results[axis] = 2.0 * np.abs(y) / window_sum

    # Frecuencias hasta Nyquist
    freqs = np.fft.rfftfreq(n, d=1.0/sampling_rate)
    return freqs, fft_results['x'], fft_results['y'], fft_results['z']

def calculate_rms(data):
    """Calculates the Root Mean Square (RMS) value of a data array.

    Args:
        data (np.ndarray): Input array of numerical data.

    Returns:
        float: The RMS value of the data.
    """
    return np.sqrt(np.mean(np.square(data)))

def calculate_peak_to_peak(data):
    """Calculates the peak-to-peak value (range) of a data array.

    Args:
        data (np.ndarray): Input array of numerical data.

    Returns:
        float: The difference between the maximum and minimum values in the data.
    """
    return np.max(data) - np.min(data)

def calculate_crest_factor(data):
    """Calculates the crest factor (peak amplitude / RMS) of a data array.

    Args:
        data (np.ndarray): Input array of numerical data.

    Returns:
        float: The crest factor. Returns 0 if the RMS value is zero.
    """
    rms = calculate_rms(data)
    if rms > 0:
        return np.max(np.abs(data)) / rms
    return 0

def save_event_data(event_data, start_time, config, event_folder=None, displacement_file=None, acceleration_file=None):
    """Saves raw event data, generates analysis, plots, and reports for an event.

    Orchestrates the post-event processing workflow:
    1. Creates a unique event folder based on the start timestamp if not provided.
    2. Extracts numerical data from the raw `event_data` buffer into NumPy arrays.
    3. Saves the NumPy data to a `.npz` file within the event folder.
    4. Creates sensor-specific CSV files (`displacements.csv`, `acceleration.csv`)
       within the event folder if not already provided.
    5. Calls `generate_event_analysis` to perform FFT, create plots, and write
       a summary report (`report.txt`).

    Args:
        event_data (list[dict]): The raw data collected during the event.
        start_time (datetime): The timestamp when the event was triggered.
        config (SystemConfig or SimulatorConfig): The system configuration object.
        event_folder (str, optional): Path to the specific folder for this event.
            If None, a folder is created based on `start_time` inside `config.events_dir`.
            Defaults to None.
        displacement_file (str, optional): Path to an existing LVDT CSV file.
            If None, `create_displacement_csv` is called. Defaults to None.
        acceleration_file (str, optional): Path to an existing acceleration CSV file.
            If None, `create_acceleration_csv` is called. Defaults to None.

    Returns:
        str or None: The path to the generated event report file (`report.txt`)
                     if successful, otherwise None.
    """
    try:
        # Create event folder if not provided
        if event_folder is None:
            timestamp_str = start_time.strftime('%Y%m%d_%H%M%S')
            event_folder = os.path.join(config.events_dir, timestamp_str)
            
        # Ensure event folder exists
        os.makedirs(event_folder, exist_ok=True)

        # Define output files
        report_file = os.path.join(event_folder, "report.txt")
        npz_file = os.path.join(event_folder, "data.npz")

        # Create parent directories if they don't exist
        os.makedirs(os.path.dirname(report_file), exist_ok=True)

        # Load or create NPZ data
        if os.path.exists(npz_file):
            try:
                np_data = dict(np.load(npz_file))
            except Exception:
                np_data = extract_data_from_event(event_data, start_time, config)
                np.savez(npz_file, **np_data)
        else:
            np_data = extract_data_from_event(event_data, start_time, config)
            np.savez(npz_file, **np_data)

        # Create sensor-specific CSV files
        if config.enable_lvdt and displacement_file is None:
            from .processing_data import create_displacement_csv
            displacement_file = create_displacement_csv(event_data, event_folder, config)
            
        if config.enable_accel and acceleration_file is None:
            from .processing_data import create_acceleration_csv
            acceleration_file = create_acceleration_csv(event_data, event_folder, config)
        # Generate analysis
        success = generate_event_analysis(
            event_folder,
            np_data,
            start_time.strftime('%Y%m%d_%H%M%S'),
            config,
            acceleration_file,
            displacement_file
        )
        
        return report_file if success else None

    except Exception as e:
        print(f"Error in save_event_data: {e}")
        import traceback
        traceback.print_exc()
        return None

def generate_event_analysis(event_folder, np_data, timestamp_str, config, accel_file=None, lvdt_file=None,
                           event_start_time=0.0, event_end_time=0.0):
    """Performs analysis (FFT), generates plots, and writes a report for event data.

    Takes NumPy arrays of event data, calculates FFT for accelerometer channels,
    creates time-series and FFT plots using Matplotlib, finds dominant frequencies,
    and writes a detailed text report summarizing the event.

    Args:
        event_folder (str): Path to the directory where analysis results (plots, report)
            should be saved.
        np_data (dict): Dictionary containing NumPy arrays of the event data (timestamps,
            sensor readings) as generated by `extract_data_from_event`.
        timestamp_str (str): Timestamp string (YYYYMMDD_HHMMSS) identifying the event.
        config (SystemConfig or SimulatorConfig): The system configuration object.
        accel_file (str, optional): Path to the acceleration CSV file for reference in the report.
        lvdt_file (str, optional): Path to the displacement CSV file for reference in the report.
        event_start_time (float, optional): Relative time within the data where the
            trigger occurred (used for plotting markers). Defaults to 0.0.
        event_end_time (float, optional): Relative time within the data where the
            detrigger occurred (used for plotting markers). Defaults to 0.0.

    Returns:
        bool: True if analysis was generated successfully, False otherwise.
    """
    try:
        # Process each available accelerometer separately.
        fft_results = []  # List to store FFT results per accelerometer
        if config.enable_accel:
            # Use the MEASURED sampling rate from config
            sampling_rate = config.sampling_rate_acceleration
            if sampling_rate <= 0:
                 print("Warning: Accelerometer sampling rate is zero or negative. Skipping FFT.")
            else:
                for accel_idx in range(config.num_accelerometers):
                    key_x = f'accel{accel_idx+1}_x'
                    key_y = f'accel{accel_idx+1}_y'
                    key_z = f'accel{accel_idx+1}_z'
                    if key_x in np_data and key_y in np_data and key_z in np_data:
                        accel_data = {
                            'x': np.nan_to_num(np_data[key_x]), # Replace NaN with 0 for FFT
                            'y': np.nan_to_num(np_data[key_y]),
                            'z': np.nan_to_num(np_data[key_z])
                        }
                        freqs, fft_x, fft_y, fft_z = calculate_fft(accel_data, sampling_rate)
                        fft_results.append({
                            'freq': freqs,
                            'fft_x': fft_x,
                            'fft_y': fft_y,
                            'fft_z': fft_z
                        })

        # Create plots
        analysis_plot = os.path.join(event_folder, f"analysis_{timestamp_str}.png")
        create_analysis_plots(
            np_data,
            fft_results,
            timestamp_str,
            analysis_plot,
            config,
            event_start_time,
            event_end_time
        )
        
        # Fix FFT data access for report writing
        report_file = os.path.join(event_folder, f"report_{timestamp_str}.txt")
        # Calculate duration based on measured time step if available, else use timestamps
        duration = (np_data['timestamps'][-1] - np_data['timestamps'][0]) if 'timestamps' in np_data and len(np_data['timestamps']) > 1 else 0.0

        # Find dominant frequencies for the report (using first accelerometer's FFT results if available)
        dominant_freqs_x, dominant_freqs_y, dominant_freqs_z = [], [], []
        if fft_results:
            freqs = fft_results[0]['freq']
            dominant_freqs_x = find_dominant_frequencies(fft_results[0]['fft_x'], freqs)
            dominant_freqs_y = find_dominant_frequencies(fft_results[0]['fft_y'], freqs)
            dominant_freqs_z = find_dominant_frequencies(fft_results[0]['fft_z'], freqs)

        write_event_report(
            report_file,
            timestamp_str,
            duration, # Use calculated duration
            np.nanmax(np.abs(np_data.get(f'accel1_x', [np.nan]))), # Use nanmax for safety
            np.nanmax(np.abs(np_data.get(f'accel1_y', [np.nan]))),
            np.nanmax(np.abs(np_data.get(f'accel1_z', [np.nan]))),
            np.nanmax(np.abs(np_data.get(f'accel1_mag', [np.nan]))), # Use magnitude if available
            dominant_freqs_x, # Pass dominant frequencies
            dominant_freqs_y,
            dominant_freqs_z,
            accel_file,
            lvdt_file,
            analysis_plot,
            np_data,
            config
        )
            
        print(f"Generated analysis plots at: {analysis_plot}")
        return True
    except Exception as e:
        print(f"Error generating event analysis: {e}")
        import traceback
        traceback.print_exc()
        return False

def find_dominant_frequencies(fft_data, freqs, n_peaks=3):
    """Finds the frequencies corresponding to the N largest peaks in FFT data.

    Identifies local maxima in the FFT amplitude spectrum and returns the
    frequencies of the `n_peaks` highest amplitude peaks.

    Args:
        fft_data (np.ndarray): Array of FFT amplitude values.
        freqs (np.ndarray): Array of corresponding frequency values.
        n_peaks (int, optional): The number of dominant peaks to return. Defaults to 3.

    Returns:
        list[float]: A list containing the frequencies of the `n_peaks` most
                     dominant peaks, sorted by amplitude in descending order.
    """
    peaks = []
    for i in range(1, len(fft_data) - 1):
        if fft_data[i] > fft_data[i - 1] and fft_data[i] > fft_data[i + 1]:
            peaks.append((fft_data[i], freqs[i]))
    
    # Sort peaks by amplitude and get top n
    peaks.sort(reverse=True, key=lambda x: x[0])
    return [freq for _, freq in peaks[:n_peaks]]

def create_analysis_plots(np_data, fft_results_list, timestamp_str, filename, config, 
                          event_start_time, event_end_time):
    """Creates and saves Matplotlib plots for event analysis.

    Generates separate PNG files for:
    - Each accelerometer: Showing time series (X, Y, Z) and FFT (X, Y, Z).
    - All LVDTs combined: Showing time series displacement.

    Includes markers for event start/end times and trigger/detrigger thresholds.

    Args:
        np_data (dict): Dictionary of NumPy arrays containing event data.
        fft_results_list (list[dict]): List containing FFT results (freq, fft_x, etc.)
            for each accelerometer.
        timestamp_str (str): Timestamp string for titles (YYYYMMDD_HHMMSS).
        filename (str): Base filename for saving plots. Specific sensor identifiers
            (e.g., "_accel1", "_lvdt_all") will be appended.
        config (SystemConfig or SimulatorConfig): System configuration object.
        event_start_time (float): Relative time of event start for plotting markers.
        event_end_time (float): Relative time of event end for plotting markers.

    Returns:
        bool: True if plots were generated successfully, False otherwise.
    """
    try:
        if 'timestamps' not in np_data or len(np_data['timestamps']) == 0:
             print("Error: No timestamps available for plotting.")
             return False
             
        t_main = np_data['timestamps']
        total_duration = t_main[-1] if len(t_main) > 0 else 0.0
        
        # Compute the actual event boundaries within the recorded data.
        actual_event_start = config.pre_event_time
        actual_event_end = total_duration - config.post_event_time
        
        # Plot each accelerometer separately
        for accel_idx in range(config.num_accelerometers):
            accel_key_x = f'accel{accel_idx+1}_x'
            if accel_key_x not in np_data:
                 print(f"Warning: Data for {accel_key_x} not found, skipping plot.")
                 continue
                 
            try:
                fig = plt.figure(figsize=(12, 10))
                
                # Time series plot
                ax_time = fig.add_subplot(2, 1, 1)
                ax_time.plot(t_main, np.ma.masked_invalid(np_data[f'accel{accel_idx+1}_x']), 'r', label='X', alpha=0.8)
                ax_time.plot(t_main, np.ma.masked_invalid(np_data[f'accel{accel_idx+1}_y']), 'g', label='Y', alpha=0.8)
                ax_time.plot(t_main, np.ma.masked_invalid(np_data[f'accel{accel_idx+1}_z']), 'b', label='Z', alpha=0.8)
                
                ax_time.axvline(x=actual_event_start, color='k', linestyle='--', alpha=0.7, label='Start')
                ax_time.axvline(x=actual_event_end, color='m', linestyle='--', alpha=0.7, label='End')

                if hasattr(config, 'trigger_acceleration_threshold'):
                    trigger_threshold_accel = config.trigger_acceleration_threshold
                    ax_time.axhline(y=trigger_threshold_accel, color='orange', linestyle=':', alpha=0.8, label='Trigger')
                    ax_time.axhline(y=-trigger_threshold_accel, color='orange', linestyle=':', alpha=0.8)
                if hasattr(config, 'detrigger_acceleration_threshold'):
                    detrigger_threshold_accel = config.detrigger_acceleration_threshold
                    ax_time.axhline(y=detrigger_threshold_accel, color='purple', linestyle=':', alpha=0.8, label='Detrigger')
                    ax_time.axhline(y=-detrigger_threshold_accel, color='purple', linestyle=':', alpha=0.8)

                ax_time.set_xlabel('Time (s)')
                ax_time.set_ylabel('Acceleration (m/s²)')
                ax_time.set_title(f'Accelerometer {accel_idx+1} - Time Series')
                ax_time.grid(True, alpha=0.3)
                ax_time.legend()
                
                # FFT plot
                ax_fft = fig.add_subplot(2, 1, 2)  # Create FFT subplot BEFORE using it
                
                # Retrieve FFT for this accelerometer from fft_results_list
                if fft_results_list and len(fft_results_list) > accel_idx:
                    current_fft = fft_results_list[accel_idx]
                    freqs = current_fft['freq']
                    
                    # Plot FFT data on linear scale
                    for data, color, label in [
                        (current_fft['fft_x'], 'r', 'X'),
                        (current_fft['fft_y'], 'g', 'Y'),
                        (current_fft['fft_z'], 'b', 'Z')
                    ]:
                        mask = freqs > 0.5
                        data_filtered = data[mask]
                        freqs_filtered = freqs[mask]
                        ax_fft.plot(
                            freqs_filtered,
                            data_filtered,
                            color=color,
                            label=label,
                            alpha=0.8,
                            linewidth=1
                        )

                    # Set FFT plot parameters
                    ax_fft.set_xlabel('Frequency (Hz)')
                    ax_fft.set_ylabel('Amplitude')  # switched from log scale
                    ax_fft.set_title('Frequency Analysis')
                    ax_fft.grid(True, which='both', alpha=0.3)
                    ax_fft.legend()

                    # Adjust FFT plot limits for better visualization
                    nyquist = config.sampling_rate_acceleration / 2
                    ax_fft.set_xlim(0.5, nyquist)

                    # Use dynamic ylim based on actual data range
                    min_val = 1e-4
                    max_values = []
                    for arr in [current_fft['fft_x'], current_fft['fft_y'], current_fft['fft_z']]:
                        if len(arr[mask]) > 0:
                            max_values.append(np.max(arr[mask]))
                    if max_values:
                        ax_fft.set_ylim(min_val, max(max_values) * 2)
                    else:
                        ax_fft.set_ylim(1e-6, 1e2)
                    
                fig.suptitle(f'Accelerometer {accel_idx+1} Analysis - {timestamp_str}\nTotal Duration: {total_duration:.2f}s', fontsize=14, y=0.995)
                plt.tight_layout(rect=[0, 0, 1, 0.97])
                accel_filename = f"{os.path.splitext(filename)[0]}_accel{accel_idx+1}.png"
                plt.savefig(accel_filename, dpi=300, bbox_inches='tight')
                plt.close(fig)
                print(f"Generated accelerometer {accel_idx+1} plot at: {accel_filename}")
            
            except Exception as e:
                print(f"Error creating plot for accelerometer {accel_idx+1}: {e}")
                traceback.print_exc()
                if 'fig' in locals() and plt.fignum_exists(fig.number):
                     plt.close(fig)
        
        # Create single plot for all LVDTs
        if config.enable_lvdt:
            try:
                fig = plt.figure(figsize=(12, 6))
                ax = fig.add_subplot(111)
                plotted_lvdt = False
                
                # Plot each LVDT on the same axes
                for lvdt_idx in range(config.num_lvdts):
                    time_key = f'lvdt{lvdt_idx+1}_time'
                    disp_key = f'lvdt{lvdt_idx+1}_displacement'
                    
                    if time_key in np_data and disp_key in np_data:
                        lvdt_times = np_data[time_key]
                        lvdt_data = np_data[disp_key]
                        
                        if len(lvdt_times) > 0:
                            ax.plot(lvdt_times, lvdt_data, 
                                   label=f'LVDT {lvdt_idx+1}', linestyle='-', alpha=0.8)
                            plotted_lvdt = True
                        
                if plotted_lvdt:
                    # Draw vertical lines at the actual event boundaries 
                    ax.axvline(x=actual_event_start, color='k', linestyle='--', alpha=0.7, label='Start')
                    ax.axvline(x=actual_event_end, color='m', linestyle='--', alpha=0.7, label='End')

                    # Líneas horizontales para thresholds de trigger y detrigger (desplazamientos)
                    if hasattr(config, 'trigger_displacement_threshold'):
                        trigger_threshold_disp = config.trigger_displacement_threshold
                        ax.axhline(y=trigger_threshold_disp, color='orange', linestyle=':', alpha=0.8, label='Trigger')
                        ax.axhline(y=-trigger_threshold_disp, color='orange', linestyle=':', alpha=0.8)
                    if hasattr(config, 'detrigger_displacement_threshold'):
                        detrigger_threshold_disp = config.detrigger_displacement_threshold
                        ax.axhline(y=detrigger_threshold_disp, color='purple', linestyle=':', alpha=0.8, label='Detrigger')
                        ax.axhline(y=-detrigger_threshold_disp, color='purple', linestyle=':', alpha=0.8)

                    ax.set_xlabel('Time (s)')
                    ax.set_ylabel('Displacement (mm)')
                    ax.set_title('LVDT Displacements')
                    ax.grid(True, alpha=0.3)
                    ax.legend(loc='best')
                    
                    fig.suptitle(f'LVDT Analysis - {timestamp_str}\nTotal Duration: {total_duration:.2f}s',
                               fontsize=14, y=0.95)
                    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
                    
                    lvdt_filename = f"{os.path.splitext(filename)[0]}_lvdt_all.png"
                    plt.savefig(lvdt_filename, dpi=300, bbox_inches='tight')
                    
                plt.close(fig)
                
            except Exception as e:
                logging.error(f"Error creating LVDT plot: {e}")
                traceback.print_exc()
                if 'fig' in locals() and plt.fignum_exists(fig.number):
                    plt.close(fig)
        
        return True
        
    except Exception as e:
        print(f"Error creating analysis plots: {e}")
        traceback.print_exc()
        plt.close('all')
        return False

def write_event_report(report_file, timestamp_str, duration, max_x, max_y, max_z, max_mag,
                      freqs_x, freqs_y, freqs_z, accel_file, lvdt_file, plot_file, 
                      lvdt_data=None, config=None):
    """Writes a detailed text report summarizing an event.

    Includes event time, duration, peak accelerometer readings (X, Y, Z, Mag),
    dominant frequencies (X, Y, Z), peak LVDT displacements (if available),
    and references to related data (CSV) and plot (PNG) files.

    Args:
        report_file (str): Path to the text file where the report will be written.
        timestamp_str (str): Timestamp string identifying the event (YYYYMMDD_HHMMSS).
        duration (float): Duration of the recorded event data in seconds.
        max_x (float): Peak absolute acceleration on the X-axis (m/s²).
        max_y (float): Peak absolute acceleration on the Y-axis (m/s²).
        max_z (float): Peak absolute acceleration on the Z-axis (m/s²).
        max_mag (float): Peak absolute resultant acceleration magnitude (m/s²).
        freqs_x (list[float]): List of dominant frequencies found on the X-axis (Hz).
        freqs_y (list[float]): List of dominant frequencies found on the Y-axis (Hz).
        freqs_z (list[float]): List of dominant frequencies found on the Z-axis (Hz).
        accel_file (str or None): Path to the associated acceleration CSV file.
        lvdt_file (str or None): Path to the associated displacement CSV file.
        plot_file (str): Base path to the associated analysis plot files (PNG).
        lvdt_data (dict, optional): Dictionary containing NumPy arrays of LVDT data,
            used to calculate peak displacements. Defaults to None.
        config (SystemConfig or SimulatorConfig, optional): System configuration, used
            to check if sensors are enabled and get sensor counts. Defaults to None.
    """
    with open(report_file, 'w') as f:
        f.write(f"EVENT ANALYSIS REPORT\n")
        f.write(f"===================\n\n")
        f.write(f"Time: {timestamp_str}\n")
        f.write(f"Duration: {duration:.2f} seconds\n\n")
        
        # Accelerometer section - only if enabled
        if config and config.enable_accel:
            f.write(f"PEAK ACCELERATIONS:\n")
            f.write(f"  X-axis: {max_x:.4f} m/s2\n")
            f.write(f"  Y-axis: {max_y:.4f} m/s2\n")
            f.write(f"  Z-axis: {max_z:.4f} m/s2\n")
            f.write(f"  Resultant magnitude: {max_mag:.4f} m/s2\n\n")
            
            f.write(f"FREQUENCY ANALYSIS:\n")
            f.write(f"  Dominant X frequencies: {', '.join([f'{f:.2f} Hz' for f in freqs_x])}\n")
            f.write(f"  Dominant Y frequencies: {', '.join([f'{f:.2f} Hz' for f in freqs_y])}\n")
            f.write(f"  Dominant Z frequencies: {', '.join([f'{f:.2f} Hz' for f in freqs_z])}\n\n")
        
        # LVDT section - only if enabled and data provided
        if config and config.enable_lvdt and lvdt_data:
            f.write(f"PEAK DISPLACEMENTS:\n")
            for i in range(config.num_lvdts):
                if f'lvdt{i+1}_displacement' in lvdt_data:
                    max_disp = np.max(np.abs(lvdt_data[f'lvdt{i+1}_displacement']))
                    f.write(f"  LVDT {i+1}: {max_disp:.4f} mm\n")
            f.write("\n")
        
        f.write(f"Related files:\n")
        if accel_file and config and config.enable_accel:
            f.write(f"  - {os.path.basename(accel_file)}\n")
        if lvdt_file and config and config.enable_lvdt:
            f.write(f"  - {os.path.basename(lvdt_file)}\n")
            
        # Include all generated plot files
        plot_files = []
        if config and config.enable_accel:
            for accel_idx in range(config.num_accelerometers):
                accel_plot_file = f"{os.path.splitext(plot_file)[0]}_accel{accel_idx+1}.png"
                if os.path.exists(accel_plot_file):
                    plot_files.append(accel_plot_file)
        if config and config.enable_lvdt:
            lvdt_plot_file = f"{os.path.splitext(plot_file)[0]}_lvdt_all.png"
            if os.path.exists(lvdt_plot_file):
                plot_files.append(lvdt_plot_file)
        
        for pfile in plot_files:
             f.write(f"  - {os.path.basename(pfile)}\n")

def generate_fft_plot(np_data, fs, filename_template, config):
    """Generates and saves separate FFT plots for each accelerometer channel.

    Args:
        np_data (dict): Dictionary containing NumPy arrays of accelerometer data
            (e.g., 'accel1_x', 'accel1_y', ...).
        fs (float): The sampling rate (Hz) of the accelerometer data.
        filename_template (str): A template string for the output plot filenames.
            Should contain '{accel}' which will be replaced by the accelerometer
            index (e.g., "fft_plot_accel{accel}.png").
        config (SystemConfig or SimulatorConfig): System configuration object, used
            to get `num_accelerometers`.

    Returns:
        bool: True if plots were generated successfully, False otherwise.
    """
    try:
        for accel_idx in range(1, config.num_accelerometers + 1):
            x_key = f'accel{accel_idx}_x'
            y_key = f'accel{accel_idx}_y'
            z_key = f'accel{accel_idx}_z'
            if x_key not in np_data or y_key not in np_data or z_key not in np_data:
                continue  # Skip if data for this accelerometer is missing

            accel_data = {
                'x': np.nan_to_num(np_data[x_key]), # Replace NaN with 0 for FFT
                'y': np.nan_to_num(np_data[y_key]),
                'z': np.nan_to_num(np_data[z_key])
            }
            # Use the measured sampling rate (fs)
            if fs <= 0:
                 print(f"Warning: Skipping FFT for Accel {accel_idx} due to invalid sampling rate ({fs}).")
                 continue
            freq, fft_x, fft_y, fft_z = calculate_fft(accel_data, fs)
            
            fig, axes = plt.subplots(3, 1, figsize=(10, 12))
            axes[0].plot(freq, fft_x, label=f'Accel {accel_idx} X')
            axes[0].set_xlabel('Frequency (Hz)')
            axes[0].set_ylabel('Amplitude')
            axes[0].legend()
            
            axes[1].plot(freq, fft_y, label=f'Accel {accel_idx} Y')
            axes[1].set_xlabel('Frequency (Hz)')
            axes[1].set_ylabel('Amplitude')
            axes[1].legend()
            
            axes[2].plot(freq, fft_z, label=f'Accel {accel_idx} Z')
            axes[2].set_xlabel('Frequency (Hz)')
            axes[2].set_ylabel('Amplitude')
            axes[2].legend()
            
            plt.tight_layout()
            plot_filename = filename_template.replace("{accel}", str(accel_idx))
            plt.savefig(plot_filename, dpi=300, bbox_inches='tight')
            plt.close(fig)
            print(f"Generated FFT plot for Accelerometer {accel_idx} at: {plot_filename}")
        return True
    except Exception as e:
        print(f"Error generating FFT plot: {e}")
        import traceback
        traceback.print_exc()
        return False

def find_peaks(data, threshold=0.0):
    """Finds indices of local maxima (peaks) in data above a threshold.

    Args:
        data (np.ndarray): 1D array of data (e.g., FFT amplitude spectrum).
        threshold (float, optional): Minimum value for a peak to be considered.
            Defaults to 0.0.

    Returns:
        list[int]: A list of indices where peaks occur in the `data` array.
    """
    peaks = []
    if len(data) < 3:
        return peaks
    for i in range(1, len(data) - 1):
        if data[i] > data[i - 1] and data[i] > data[i + 1] and data[i] > threshold:
            peaks.append(i)
    return peaks

def check_timing_drift(elapsed_time, expected_samples, actual_samples, sampling_rate, max_drift_percent=1.0):
    """Checks for significant timing drift in data acquisition.

    Compares the expected time based on the number of samples and sampling rate
    against the actual elapsed time measured by timestamps.

    Args:
        elapsed_time (float): Total actual time elapsed for the samples (s).
        expected_samples (int): Number of samples expected in `elapsed_time`.
            (Note: This argument seems redundant if `actual_samples` and
            `sampling_rate` are provided, as expected time is calculated from them).
        actual_samples (int): The actual number of samples collected.
        sampling_rate (float): The target sampling rate (Hz).
        max_drift_percent (float, optional): Maximum allowed drift percentage.
            Defaults to 1.0.

    Returns:
        tuple[bool, float]: A tuple containing:
            - needs_reset (bool): True if the calculated drift exceeds `max_drift_percent`.
            - drift_percent (float): The calculated drift percentage.
    """
    expected_time = actual_samples / sampling_rate
    drift_time = abs(elapsed_time - expected_time)
    drift_percent = (drift_time / expected_time) * 100
    
    # Si la deriva es mayor que el porcentaje máximo permitido
    needs_reset = drift_percent > max_drift_percent
    
    return needs_reset, drift_percent

def reset_acquisition_timers(np_data, config):
    """Resets acquisition timing based on detected drift (Conceptual).

    Note: This function currently recalculates timestamps based on the assumption
    that the *number* of samples is correct but their *timing* drifted linearly.
    It modifies the timestamp arrays within the `np_data` dictionary in place if
    significant drift is detected. This might not be the correct approach for
    all drift scenarios.

    Args:
        np_data (dict): Dictionary containing NumPy arrays of acquisition data,
            including 'timestamps'. This dictionary is modified in place.
        config (SystemConfig or SimulatorConfig): System configuration object.
    """
    if 'timestamps' in np_data:
        # Calcular tiempo transcurrido real
        elapsed_time = np_data['timestamps'][-1] - np_data['timestamps'][0]
        
        # Verificar deriva para acelerómetros
        if config.enable_accel and 'accel1_x' in np_data:
            accel_samples = len(np_data['accel1_x'])
            needs_reset, drift = check_timing_drift(
                elapsed_time,
                int(elapsed_time * config.sampling_rate_acceleration),
                accel_samples,
                config.sampling_rate_acceleration
            )
            if needs_reset:
                print(f"Resetting acceleration timers (drift: {drift:.2f}%)")
                # Recalcular timestamps para acelerómetros
                np_data['accel_timestamps'] = np.linspace(
                    np_data['timestamps'][0],
                    np_data['timestamps'][-1],
                    accel_samples
                )
        
        # Verificar deriva para LVDTs
        if config.enable_lvdt and 'lvdt1_displacement' in np_data:
            lvdt_samples = len(np_data['lvdt1_displacement'])
            needs_reset, drift = check_timing_drift(
                elapsed_time,
                int(elapsed_time * config.sampling_rate_lvdt),
                lvdt_samples,
                config.sampling_rate_lvdt
            )
            if needs_reset:
                print(f"Resetting LVDT timers (drift: {drift:.2f}%)")
                # Recalcular timestamps para LVDTs
                np_data['lvdt_timestamps'] = np.linspace(
                    np_data['timestamps'][0],
                    np_data['timestamps'][-1],
                    lvdt_samples
                )