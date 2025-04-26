"""
Visualization module for real-time data display in the IdentiTwin system.
Uses Dash/Plotly for efficient real-time plotting.
"""

import dash
from dash import dcc, html
from dash.dependencies import Input, Output
import plotly.graph_objects as go
import threading
import plotly.io as pio
import random
import time                               # added
from collections import deque            # added

# Set template for consistent styling
pio.templates.default = "plotly_dark"

PALETTE = ['#C6203E', '#00217E', '#BCBEC0', '#000000']

# Store historical LVDT/ACC data for scatter plots (legacy, unused)
LVDT_HISTORY = {}
ACC_HISTORY = {}          
MAX_POINTS = 1000        

# Real‐time sampling buffers
LVDT_BUFFER = {}     # sensor_index -> deque of (t, displacement)
ACC_BUFFER = {}      # sensor_index -> deque of (t, magnitude)

# Custom color set for sensor lines
SENSOR_COLORS = [
    '#FF5733', '#33FF57', '#3357FF', '#FF33A8', 
    '#33FFF5', '#F533FF', '#FF8C33', '#8CFF33', 
    '#338CFF', '#FF338C', '#33FFC4', '#C433FF'
]

def create_dashboard(system_monitor):
    """Create and configure the Dash application."""
    app = dash.Dash(__name__)
    
    # Build tabs based on config options
    if system_monitor.config.enable_plots:
        default_tab = None
        tabs_children = []
        
        if system_monitor.config.enable_plot_displacement:
            tab_value = "displacements"
            if default_tab is None:
                default_tab = tab_value
            tabs_children.append(
                dcc.Tab(
                    label="Displacements",
                    value=tab_value,
                    children=[
                        html.H3("LVDT Displacements", style={'textAlign': 'center', 'color': PALETTE[1]}),
                        html.Div([
                            html.Label("Select LVDT:"),
                            dcc.Dropdown(
                                id='lvdt-selector',
                                options=[{'label': 'All', 'value': 'all'}] +
                                        [{'label': f'LVDT {i+1}', 'value': str(i)} 
                                         for i in range(system_monitor.config.num_lvdts)],
                                value='all',
                                multi=True,
                                style={'color': 'black', 'backgroundColor': PALETTE[2]}
                            ),
                        ], style={'width': '50%', 'margin': 'auto', 'marginBottom': '20px'}),
                        dcc.Graph(id='lvdt-plot')
                    ]
                )
            )
            
        if system_monitor.config.enable_accel_plots:
            tab_value = "accelerations"
            if default_tab is None:
                default_tab = tab_value
            tabs_children.append(
                dcc.Tab(
                    label="Accelerations",
                    value=tab_value,
                    children=[
                        html.H3("Accelerations", style={'textAlign': 'center', 'color': PALETTE[1]}),
                        html.Div([
                            html.Label("Select Accelerometer:"),
                            dcc.Dropdown(
                                id='acc-selector',
                                options=[{'label': 'All', 'value': 'all'}] +
                                        [{'label': f'ACC {i+1}', 'value': str(i)} 
                                         for i in range(system_monitor.config.num_accelerometers)],
                                value='all',
                                multi=True,
                                style={'color': 'black', 'backgroundColor': PALETTE[2]}
                            ),
                        ], style={'width': '50%', 'margin': 'auto', 'marginBottom': '20px'}),
                        dcc.Graph(id='acceleration-plot')
                    ]
                )
            )
            
        if system_monitor.config.enable_fft_plots:
            tab_value = "fft"
            if default_tab is None:
                default_tab = tab_value
            tabs_children.append(
                dcc.Tab(
                    label="FFT",
                    value=tab_value,
                    children=[
                        html.H3("FFT Analysis", style={'textAlign': 'center', 'color': PALETTE[1]}),
                        dcc.Graph(id='fft-plot')
                    ]
                )
            )
            
        layout_children = [
            html.H1("IdentiTwin Real-Time Monitoring",
                    style={'textAlign': 'center', 'color': PALETTE[0]}),
            dcc.Tabs(id='tabs', value=default_tab, children=tabs_children),
            dcc.Interval(
                id='interval-component',
                interval=int(1000/system_monitor.config.plot_refresh_rate),  # ms per update
                n_intervals=0
            )
        ]
    else:
        # Fallback layout if enable_plots is False
        layout_children = [html.H1("IdentiTwin", style={'textAlign': 'center'})]
    
    app.layout = html.Div(layout_children)
    
    @app.callback(
        Output('lvdt-plot', 'figure'),
        [Input('interval-component', 'n_intervals'),
         Input('lvdt-selector', 'value')]
    )
    def update_lvdt_graph(n, selected_lvdts):
        # if no data sampled yet
        if not LVDT_BUFFER:
            return go.Figure()

        fig = go.Figure()

        # normalize selection
        if selected_lvdts is None:
            selected_lvdts = ['all']
        elif not isinstance(selected_lvdts, list):
            selected_lvdts = [selected_lvdts]
        show_all = 'all' in selected_lvdts
        sel_idxs = [int(i) for i in selected_lvdts if i != 'all']

        # plot from buffer
        for i, buf in LVDT_BUFFER.items():
            if show_all or i in sel_idxs:
                xs, ys = zip(*buf) if buf else ([], [])
                fig.add_trace(go.Scatter(
                    x=list(xs),
                    y=list(ys),
                    mode='lines',
                    line={'color': SENSOR_COLORS[i % len(SENSOR_COLORS)]},
                    name=f'LVDT {i+1}'
                ))

        # Calculate offset for relative time display
        offset = 0
        for sensor in LVDT_BUFFER.values():
            if sensor:
                t_end = sensor[-1][0]
                offset = t_end - system_monitor.config.window_duration if t_end >= system_monitor.config.window_duration else 0
                break
        xr = [0, system_monitor.config.window_duration]
        # Adjust each trace to show relative times
        for trace in fig.data:
            trace.x = [x - offset for x in trace.x]
        
        # Calculate dynamic range for Y axis
        y_vals = []
        for trace in fig.data:
            y_vals.extend(trace.y)
        if y_vals:
            y_min = min(y_vals)
            y_max = max(y_vals)
            padding = (y_max - y_min) * 0.1 if y_max != y_min else 1
            dyn_y_range = [y_min - padding, y_max + padding]
        else:
            dyn_y_range = [-50, 50]
        
        fig.update_layout(
            xaxis={'title': 'Time (s)', 'range': xr, 'color': PALETTE[3]},
            yaxis={'title': 'Displacement', 'range': dyn_y_range, 'color': PALETTE[3]},
            height=400,
            margin=dict(l=40, r=40, t=60, b=40),
            paper_bgcolor=PALETTE[2],
            plot_bgcolor=PALETTE[2],
            font={'color': PALETTE[3]},
            showlegend=True,
            legend={'bgcolor': 'white'}
        )
        return fig

    @app.callback(
        Output('acceleration-plot', 'figure'),
        [Input('interval-component', 'n_intervals'),
         Input('acc-selector', 'value')]
    )
    def update_acceleration_graph(n, selected_accs):
        if not ACC_BUFFER:
            return go.Figure()

        fig = go.Figure()
        if selected_accs is None:
            selected_accs = ['all']
        elif not isinstance(selected_accs, list):
            selected_accs = [selected_accs]
        show_all = 'all' in selected_accs
        sel_idxs = [int(i) for i in selected_accs if i != 'all']

        for i, buf in ACC_BUFFER.items():
            if show_all or i in sel_idxs:
                xs, ys = zip(*buf) if buf else ([], [])
                fig.add_trace(go.Scatter(
                    x=list(xs),
                    y=list(ys),
                    mode='lines',
                    line={'color': SENSOR_COLORS[i % len(SENSOR_COLORS)]},
                    name=f'ACC {i+1}'
                ))

        # Calculate offset for relative time display
        offset = 0
        for sensor in ACC_BUFFER.values():
            if sensor:
                t_end = sensor[-1][0]
                offset = t_end - system_monitor.config.window_duration if t_end >= system_monitor.config.window_duration else 0
                break
        xr = [0, system_monitor.config.window_duration]
        
        for trace in fig.data:
            trace.x = [x - offset for x in trace.x]
        
        # Calculate dynamic range for Y axis
        y_vals = []
        for trace in fig.data:
            y_vals.extend(trace.y)
        if y_vals:
            y_min = min(y_vals)
            y_max = max(y_vals)
            padding = (y_max - y_min) * 0.1 if y_max != y_min else 1
            dyn_y_range = [y_min - padding, y_max + padding]
        else:
            dyn_y_range = [-50, 50]
        
        fig.update_layout(
            xaxis={'title': 'Time (s)', 'range': xr, 'color': PALETTE[3]},
            yaxis={'title': 'Acceleration', 'range': dyn_y_range, 'color': PALETTE[3]},
            height=400,
            margin=dict(l=40, r=40, t=60, b=40),
            paper_bgcolor=PALETTE[2],
            plot_bgcolor=PALETTE[2],
            font={'color': PALETTE[3]},
            showlegend=True,
            legend={'bgcolor': 'white'}
        )
        return fig

    # New FFT callback if FFT tab is enabled
    if system_monitor.config.enable_fft_plots:
        @app.callback(
            Output('fft-plot', 'figure'),
            [Input('interval-component', 'n_intervals')]
        )
        def update_fft_graph(n):
            # Dummy FFT handling - replace with your FFT processing as needed.
            # For example, you could perform FFT on one of the sensor data arrays.
            return go.Figure()
    
    return app

def run_dashboard(system_monitor):
    """Initialize and run the dashboard in a separate thread."""
    app = create_dashboard(system_monitor)

    def run():
        import logging, socket, webbrowser, time as _t
        logging.getLogger('werkzeug').setLevel(logging.ERROR)
        external_ip = "192.168.5.199"
        dashboard_url = f"http://{external_ip}:8050"
        print(f"\nAccess from other devices at: {dashboard_url}\n")

        # --- start sampling threads ---
        start_time = time.time()

        def lvdt_sampler():
            period = 1.0 / system_monitor.config.sampling_rate_lvdt
            while True:
                buf = LVDT_BUFFER
                disp = system_monitor.display_buffer.get('lvdt_data', [])
                t = time.time() - start_time
                for i, s in enumerate(disp):
                    if i not in buf:
                        buf[i] = deque(maxlen=MAX_POINTS)
                    buf[i].append((t, s.get('displacement', 0)))
                _t.sleep(period)

        def acc_sampler():
            period = 1.0 / system_monitor.config.sampling_rate_acceleration
            while True:
                buf = ACC_BUFFER
                data = system_monitor.display_buffer.get('accel_data', [])
                t = time.time() - start_time
                for i, s in enumerate(data):
                    if i not in buf:
                        buf[i] = deque(maxlen=MAX_POINTS)
                    buf[i].append((t, s.get('magnitude', 0)))
                _t.sleep(period)

        threading.Thread(target=lvdt_sampler, daemon=True).start()
        threading.Thread(target=acc_sampler, daemon=True).start()
        # --- end sampling threads ---

        # open browser after delay
        def open_browser():
            _t.sleep(1.5)
            webbrowser.open_new(dashboard_url)
        threading.Thread(target=open_browser, daemon=True).start()

        try:
            app.run(debug=False, host='0.0.0.0', port=8050)
        except Exception as e:
            print(f"ERROR starting dashboard: {e}")
            print("Try http://127.0.0.1:8050 instead\n")

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread
