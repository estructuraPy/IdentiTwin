"""
Data Analysis Module for IdentiTwin.

Provides functions for analyzing sensor data recorded during monitoring sessions,
especially for events. Includes FFT calculation, statistical analysis (RMS, peak),
peak frequency detection, data visualization (plotting), and report generation
for individual events.

Key Features:
- Fast Fourier Transform (FFT) calculation with Hanning windowing.
- Calculation of time-domain statistics: RMS, Peak-to-Peak, Crest Factor.
- Identification of dominant frequencies in FFT results.
- Generation of time-series and FFT plots for accelerometer and LVDT data.
- Saving of processed event data (NumPy arrays) and analysis results (reports, plots).
- Functions for checking and potentially correcting timing drift.
"""

import os
import numpy as np
import matplotlib
import matplotlib.pyplot as plt
from datetime import datetime
from .processing_data import extract_data_from_event  # Add this import

def calculate_fft(data, sampling_rate):
    """
    Calculates the Fast Fourier Transform (FFT) for 3-axis accelerometer data.

    Applies a Hanning window, performs FFT using NumPy's rfft (real FFT),
    and scales the magnitude appropriately. Zero-pads data to the next power of 2
    for efficiency.

    Args:
        data (dict): A dictionary containing NumPy arrays for 'x', 'y', and 'z'
                     axis acceleration data.
        sampling_rate (float): The sampling rate of the acceleration data in Hz.

    Returns:
        tuple: A tuple containing:
            - freqs (np.ndarray): Array of frequencies corresponding to the FFT bins.
            - fft_x (np.ndarray): Magnitude of the FFT for the X-axis.
            - fft_y (np.ndarray): Magnitude of the FFT for the Y-axis.
            - fft_z (np.ndarray): Magnitude of the FFT for the Z-axis.
    """
    # Find the next power of 2 length
    n = max(len(data['x']), len(data['y']), len(data['z']))
    n_fft = 2**int(np.ceil(np.log2(n)))
    
    # Create Hanning window of appropriate length
    window = np.hanning(n_fft)
    
    # Process each axis
    fft_results = {}
    for axis in ['x', 'y', 'z']:
        # Zero pad data to n_fft length
        padded_data = np.zeros(n_fft)
        padded_data[:len(data[axis])] = data[axis]
        
        # Apply window and calculate FFT
        windowed_data = padded_data * window
        fft_result = np.fft.rfft(windowed_data)
        fft_magnitude = np.abs(fft_result) * 2.0 / n_fft
        fft_results[axis] = fft_magnitude
    
    # Calculate frequency array (same for all axes)
    freqs = np.fft.rfftfreq(n_fft, 1.0 / sampling_rate)
    
    return freqs, fft_results['x'], fft_results['y'], fft_results['z']

def calculate_rms(data):
    """
    Calculates the Root Mean Square (RMS) value of a data array.

    Args:
        data (np.ndarray): A NumPy array of numerical data.

    Returns:
        float: The RMS value of the input data.
    """
    return np.sqrt(np.mean(np.square(data)))

def calculate_peak_to_peak(data):
    """
    Calculates the peak-to-peak amplitude of a data array.

    Args:
        data (np.ndarray): A NumPy array of numerical data.

    Returns:
        float: The difference between the maximum and minimum values in the data.
    """
    return np.max(data) - np.min(data)

def calculate_crest_factor(data):
    """
    Calculates the crest factor (Peak Amplitude / RMS) of a data array.

    Args:
        data (np.ndarray): A NumPy array of numerical data.

    Returns:
        float: The crest factor. Returns 0 if the RMS value is zero to avoid
               division by zero.
    """
    rms = calculate_rms(data)
    if rms > 0:
        return np.max(np.abs(data)) / rms
    return 0

def save_event_data(event_data, start_time, config, event_folder=None, displacement_file=None, acceleration_file=None):
    """
    Orchestrates the saving and analysis of data for a detected event.

    Creates an event-specific folder (if not provided), extracts numerical data
    into NumPy arrays, saves the arrays to a .npz file, creates sensor-specific
    CSV files (if not provided), and triggers the generation of analysis reports
    and plots.

    Args:
        event_data (list): The raw list of sensor data dictionaries for the event.
        start_time (datetime): The timestamp of the start of the event.
        config: The system configuration object.
        event_folder (str, optional): Path to the specific folder for this event.
                                      If None, a folder is created based on the timestamp.
                                      Defaults to None.
        displacement_file (str, optional): Path to an existing displacement CSV file.
                                           If None, one will be created. Defaults to None.
        acceleration_file (str, optional): Path to an existing acceleration CSV file.
                                           If None, one will be created. Defaults to None.

    Returns:
        str or None: The path to the generated event report file if successful,
                     otherwise None.

    Side Effects:
        - Creates an event folder if `event_folder` is None.
        - Creates/overwrites 'data.npz' file in the event folder.
        - May create 'displacements.csv' and 'acceleration.csv' files.
        - Calls `generate_event_analysis` which creates report and plot files.
        - Prints status and error messages.
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

def generate_event_analysis(event_folder, np_data, timestamp_str, config, accel_file=None, lvdt_file=None):
    """
    Performs analysis on extracted event data (NumPy arrays) and generates outputs.

    Calculates statistics (max values), performs FFT analysis on accelerometer data,
    finds dominant frequencies, generates time-series and FFT plots for all sensors,
    and writes a summary text report.

    Args:
        event_folder (str): Path to the directory for storing analysis outputs.
        np_data (dict): Dictionary of NumPy arrays containing the event's sensor data
                        (output from `extract_data_from_event`).
        timestamp_str (str): Timestamp string for naming output files (e.g., 'YYYYMMDD_HHMMSS').
        config: The system configuration object.
        accel_file (str, optional): Path to the acceleration CSV file for reference in the report.
                                    Defaults to None.
        lvdt_file (str, optional): Path to the displacement CSV file for reference in the report.
                                   Defaults to None.

    Returns:
        bool: True if analysis was generated successfully, False otherwise.

    Side Effects:
        - Creates plot image files (e.g., 'analysis_YYYYMMDD_HHMMSS_accel1.png') in `event_folder`.
        - Creates a text report file (e.g., 'report_YYYYMMDD_HHMMSS.txt') in `event_folder`.
        - Prints status and error messages.
    """
    try:
        # Calculate statistics for accelerometer data
        if config.enable_accel and 'accel1_x' in np_data:
            # Prepare data dictionary for FFT
            accel_data = {
                'x': np_data['accel1_x'],
                'y': np_data['accel1_y'],  # Fix: remove np. prefix
                'z': np_data['accel1_z']   # Fix: remove np. prefix
            }
            
            # Calculate FFT for all axes
            sampling_rate = 1.0 / config.time_step_acceleration
            freqs, fft_x, fft_y, fft_z = calculate_fft(accel_data, sampling_rate)
            
            # Rest of the analysis remains the same
            n = len(freqs)  # We now have the correct length from FFT calculation
            
            # Calculate other statistics
            max_accel_x = np.max(np.abs(np_data['accel1_x']))
            max_accel_y = np.max(np.abs(np_data['accel1_y']))
            max_accel_z = np.max(np.abs(np_data['accel1_z']))
            max_magnitude = np.sqrt(max_accel_x**2 + max_accel_y**2 + max_accel_z**2)
            duration = len(np_data['timestamps']) * config.time_step_acceleration

            # Calculate domninant frequencies
            top_freqs_x = find_dominant_frequencies(fft_x, freqs, 3)
            top_freqs_y = find_dominant_frequencies(fft_y, freqs, 3)
            top_freqs_z = find_dominant_frequencies(fft_z, freqs, 3)

            # Generate plots
            analysis_plot = os.path.join(event_folder, f"analysis_{timestamp_str}.png")
            create_analysis_plots(
                np_data, freqs, fft_x, fft_y, fft_z,
                timestamp_str, analysis_plot, config
            )

            # Generate report
            report_file = os.path.join(event_folder, f"report_{timestamp_str}.txt")
            write_event_report(
                report_file,
                timestamp_str,
                duration,
                max_accel_x,
                max_accel_y,
                max_accel_z,
                max_magnitude,
                top_freqs_x,
                top_freqs_y,
                top_freqs_z,
                accel_file,
                lvdt_file,
                analysis_plot,
                np_data,  # Pass the complete data for LVDT analysis
                config    # Pass config for sensor status
            )
            
            print(f"Generated analysis plots at: {analysis_plot}")
            return True
    except Exception as e:
        print(f"Error generating event analysis: {e}")
        import traceback
        traceback.print_exc()
        return False

def find_dominant_frequencies(fft_data, freqs, n_peaks=3):
    """
    Identifies the frequencies corresponding to the highest peaks in FFT magnitude data.

    Finds local maxima in the FFT magnitude array (excluding very low frequencies < 0.5 Hz)
    and returns the frequencies of the `n_peaks` highest amplitude peaks.

    Args:
        fft_data (np.ndarray): Array of FFT magnitude values.
        freqs (np.ndarray): Array of frequencies corresponding to `fft_data`.
        n_peaks (int): The number of dominant frequencies to return. Defaults to 3.

    Returns:
        list: A list of the `n_peaks` most dominant frequencies (float values in Hz),
              sorted by amplitude in descending order.
    """
    peaks = []
    for i in range(1, len(fft_data)-1):
        if (fft_data[i] > fft_data[i-1] and 
            fft_data[i] > fft_data[i+1] and 
            freqs[i] > 0.5):  # Ignore very low frequencies
            peaks.append((fft_data[i], freqs[i]))
    
    # Sort peaks by amplitude and get top n
    peaks.sort(reverse=True)
    return [freq for _, freq in peaks[:n_peaks]]

def create_analysis_plots(np_data, freqs, fft_x, fft_y, fft_z, timestamp_str, filename, config):
    """
    Generates and saves analysis plots for event data (time series and FFT).

    Creates separate plots for each accelerometer (time series and FFT) and a
    combined plot for all LVDTs (time series only). Saves plots as PNG files.
    Uses Matplotlib's object-oriented API for better control.

    Args:
        np_data (dict): Dictionary of NumPy arrays containing the event's sensor data.
        freqs (np.ndarray): Frequency array for the primary FFT calculation (used if needed,
                            but FFT is recalculated per accelerometer).
        fft_x (np.ndarray): FFT magnitude for X-axis (primary calculation, potentially unused).
        fft_y (np.ndarray): FFT magnitude for Y-axis (primary calculation, potentially unused).
        fft_z (np.ndarray): FFT magnitude for Z-axis (primary calculation, potentially unused).
        timestamp_str (str): Timestamp string for titles and filenames.
        filename (str): Base path and filename for saving plots (e.g., 'event_folder/analysis_ts').
                        Sensor-specific suffixes will be added.
        config: The system configuration object.

    Returns:
        bool: True if plots were generated successfully, False otherwise.

    Side Effects:
        - Creates multiple PNG plot files (e.g., '..._accel1.png', '..._lvdt_all.png').
        - Prints status and error messages.
        - Closes Matplotlib figures to free memory.
    """
    try:
        # Get base filename without extension
        base_path = os.path.splitext(filename)[0]
        
        # Plot each accelerometer separately
        for accel_idx in range(config.num_accelerometers):
            try:
                fig = plt.figure(figsize=(12, 10))
                
                # Time series plot
                ax_time = fig.add_subplot(2, 1, 1)
                t = np.arange(len(np_data[f'accel{accel_idx+1}_x'])) * config.time_step_acceleration
                
                ax_time.plot(t, np_data[f'accel{accel_idx+1}_x'], 'r', label='X', alpha=0.8)
                ax_time.plot(t, np_data[f'accel{accel_idx+1}_y'], 'g', label='Y', alpha=0.8)
                ax_time.plot(t, np_data[f'accel{accel_idx+1}_z'], 'b', label='Z', alpha=0.8)
                ax_time.set_xlabel('Time (s)')
                ax_time.set_ylabel('Acceleration (m/s²)')
                ax_time.set_title(f'Accelerometer {accel_idx+1} - Time Series')
                ax_time.grid(True, alpha=0.3)
                ax_time.legend()
                
                # FFT plot for this accelerometer
                ax_fft = fig.add_subplot(2, 1, 2)
                
                # Calculate FFT for this specific accelerometer
                accel_data = {
                    'x': np_data[f'accel{accel_idx+1}_x'],
                    'y': np_data[f'accel{accel_idx+1}_y'],
                    'z': np_data[f'accel{accel_idx+1}_z']
                }
                freqs_accel, fft_x, fft_y, fft_z = calculate_fft(accel_data, 1.0/config.time_step_acceleration)
                
                ax_fft.plot(freqs_accel, fft_x, 'r', label='X', alpha=0.8)
                ax_fft.plot(freqs_accel, fft_y, 'g', label='Y', alpha=0.8)
                ax_fft.plot(freqs_accel, fft_z, 'b', label='Z', alpha=0.8)
                ax_fft.set_xlabel('Frequency (Hz)')
                ax_fft.set_ylabel('Amplitude')
                ax_fft.set_title(f'Accelerometer {accel_idx+1} - Frequency Analysis')
                ax_fft.grid(True, alpha=0.3)
                ax_fft.legend()
                
                # Add timestamp and save
                fig.suptitle(f'Accelerometer {accel_idx+1} Analysis - {timestamp_str}', fontsize=14, y=0.995)
                plt.tight_layout(rect=[0, 0, 1, 0.97])
                accel_filename = f"{base_path}_accel{accel_idx+1}.png"
                plt.savefig(accel_filename, dpi=300, bbox_inches='tight')
                plt.close()
                print(f"Generated accelerometer {accel_idx+1} plot at: {accel_filename}")
            
            except Exception as e:
                print(f"Error creating plot for accelerometer {accel_idx+1}: {e}")
                traceback.print_exc()
        
        # Create single plot for all LVDTs
        if config.enable_lvdt:
            try:
                # Define a color palette for multiple LVDTs
                colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd', '#8c564b']
                
                # Create figure only if we have LVDT data
                has_lvdt_data = any(f'lvdt{i+1}_displacement' in np_data for i in range(config.num_lvdts))
                
                if has_lvdt_data:
                    fig = plt.figure(figsize=(12, 6))
                    ax = fig.add_subplot(111)
                    
                    # Plot each LVDT on the same axes
                    for lvdt_idx in range(config.num_lvdts):
                        if f'lvdt{lvdt_idx+1}_displacement' in np_data:
                            t = np.arange(len(np_data[f'lvdt{lvdt_idx+1}_displacement'])) * config.time_step_lvdt
                            color = colors[lvdt_idx % len(colors)]  # Cycle through colors if more LVDTs than colors
                            ax.plot(t, np_data[f'lvdt{lvdt_idx+1}_displacement'], 
                                   label=f'LVDT {lvdt_idx+1}', 
                                   color=color,
                                   alpha=0.8,
                                   linewidth=1.5)
                    
                    ax.set_xlabel('Time (s)')
                    ax.set_ylabel('Displacement (mm)')
                    ax.set_title('LVDT Displacements')
                    ax.grid(True, alpha=0.3)
                    ax.legend(loc='best')
                    
                    # Add timestamp and save
                    fig.suptitle(f'LVDT Analysis - {timestamp_str}', fontsize=14, y=0.95)
                    plt.tight_layout(rect=[0, 0.03, 1, 0.95])
                    lvdt_filename = f"{base_path}_lvdt_all.png"
                    plt.savefig(lvdt_filename, dpi=300, bbox_inches='tight')
                    plt.close()
                    print(f"Generated combined LVDT plot at: {lvdt_filename}")
                    
            except Exception as e:
                print(f"Error creating combined LVDT plot: {e}")
                traceback.print_exc()
        
        return True
        
    except Exception as e:
        print(f"Error creating analysis plots: {e}")
        traceback.print_exc()
        plt.close()
        return False

def write_event_report(report_file, timestamp_str, duration, max_x, max_y, max_z, max_mag,
                      freqs_x, freqs_y, freqs_z, accel_file, lvdt_file, plot_file, 
                      lvdt_data=None, config=None):
    """
    Writes a detailed text report summarizing the analysis of an event.

    Includes event time, duration, peak acceleration values (X, Y, Z, magnitude),
    dominant frequencies for each accelerometer axis, peak displacement for each LVDT
    (if available), and references to related data/plot files.

    Args:
        report_file (str): Full path to the report file to be created.
        timestamp_str (str): Timestamp string for the event.
        duration (float): Duration of the event in seconds.
        max_x (float): Peak absolute acceleration on the X-axis.
        max_y (float): Peak absolute acceleration on the Y-axis.
        max_z (float): Peak absolute acceleration on the Z-axis.
        max_mag (float): Peak resultant acceleration magnitude.
        freqs_x (list): List of dominant frequencies for the X-axis.
        freqs_y (list): List of dominant frequencies for the Y-axis.
        freqs_z (list): List of dominant frequencies for the Z-axis.
        accel_file (str): Path to the associated acceleration CSV file.
        lvdt_file (str): Path to the associated displacement CSV file.
        plot_file (str): Base path to the associated analysis plot files.
        lvdt_data (dict, optional): Dictionary containing LVDT data arrays (e.g., 'lvdt1_displacement').
                                    Required if LVDT results are to be included. Defaults to None.
        config (SystemConfig, optional): System configuration object. Required to check if sensors
                                         are enabled. Defaults to None.

    Returns:
        None

    Side Effects:
        - Creates or overwrites the specified `report_file`.
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
        f.write(f"  - {os.path.basename(plot_file)}\n")

def generate_fft_plot(np_data, fs, filename, config):
    """
    Generates and saves an FFT plot comparing multiple accelerometers.

    Calculates FFT for each enabled accelerometer and plots their X, Y, and Z
    frequency responses on separate subplots within a single figure.

    Args:
        np_data (dict): Dictionary of NumPy arrays containing event sensor data.
        fs (float): The sampling frequency (rate) in Hz.
        filename (str): The full path to save the output PNG plot file.
        config: The system configuration object.

    Returns:
        bool: True if the plot was generated successfully, False otherwise.

    Side Effects:
        - Creates a PNG plot file at the specified `filename`.
        - Prints status or error messages.
        - Closes the Matplotlib figure.
    """
    try:
        fig, axes = plt.subplots(3, 1, figsize=(10, 12))
        for accel_idx in range(1, config.num_accelerometers + 1):
            accel_data = {
                'x': np_data[f'accel{accel_idx}_x'],  # Fix: use dictionary format
                'y': np_data[f'accel{accel_idx}_y'],
                'z': np_data[f'accel{accel_idx}_z']
            }
            freq_x, fft_x, fft_y, fft_z = calculate_fft(accel_data, fs)  # Fix: unpack all returned values
            
            axes[0].plot(freq_x, fft_x, label=f'Accel {accel_idx}')
            axes[1].plot(freq_x, fft_y, label=f'Accel {accel_idx}')  # Fix: use freq_x consistently
            axes[2].plot(freq_x, fft_z, label=f'Accel {accel_idx}')
            
        plt.tight_layout()
        plt.savefig(filename, dpi=300)
        plt.close()
        print(f"Generated FFT plot at: {filename}")
        return True
    except Exception as e:
        print(f"Error generating FFT plot: {e}")
        import traceback
        traceback.print_exc()
        return False

def find_peaks(data, threshold=0.0):
    """
    Finds indices of peaks (local maxima) in a 1D array above a threshold.

    A peak is defined as a point higher than its immediate neighbors.

    Args:
        data (np.ndarray): A 1D NumPy array.
        threshold (float): Minimum value for a point to be considered a peak.
                           Defaults to 0.0.

    Returns:
        list: A list of indices where peaks occur.
    """
    peaks = []
    if len(data) < 3:
        return peaks
    for i in range(1, len(data) - 1):
        if data[i] > data[i - 1] and data[i] > data[i + 1] and data[i] > threshold:
            peaks.append(i)
    return peaks

def check_timing_drift(elapsed_time, expected_samples, actual_samples, sampling_rate, max_drift_percent=1.0):
    """
    Checks for significant timing drift based on expected vs. actual samples.

    Compares the time elapsed calculated from the number of samples and sampling rate
    against the actual measured elapsed time. Determines if the drift exceeds a
    specified percentage.

    Args:
        elapsed_time (float): The actual measured time duration in seconds.
        expected_samples (int): The number of samples expected for the `elapsed_time`
                                based on the `sampling_rate`. (Note: This seems unused,
                                the calculation uses `actual_samples`).
        actual_samples (int): The actual number of samples collected.
        sampling_rate (float): The target sampling rate in Hz.
        max_drift_percent (float): The maximum allowable drift percentage. Defaults to 1.0.

    Returns:
        tuple: A tuple containing:
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
    """
    Adjusts timestamps within event data if significant drift is detected.

    Checks for timing drift in both accelerometer and LVDT data streams (if enabled)
    using `check_timing_drift`. If drift exceeds the threshold, it recalculates
    evenly spaced timestamps based on the first and last recorded timestamps and
    the number of samples, storing them under new keys ('accel_timestamps',
    'lvdt_timestamps').

    Args:
        np_data (dict): Dictionary of NumPy arrays containing event data, including 'timestamps'.
        config: The system configuration object.

    Returns:
        None

    Side Effects:
        - May add 'accel_timestamps' and/or 'lvdt_timestamps' keys to the `np_data` dictionary
          if drift is detected and corrected.
        - Prints warning messages if timers are reset.
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