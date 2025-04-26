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
import numpy as np
from scipy.fft import fft, fftfreq

# Set template for consistent styling
pio.templates.default = "plotly_dark"

PALETTE = ['#C6203E', '#00217E', '#BCBEC0', '#000000']

# Store historical LVDT/ACC data for scatter plots (legacy, unused)
LVDT_HISTORY = {}
ACC_HISTORY = {}          
MAX_POINTS = 1000        
# Añadir buffer FFT potencia de 2
FFT_BUFFER_SIZE = 1024  # potencia de 2 >= muestras necesarias
FFT_BUFFERS = {
    'x': deque([0.0]*FFT_BUFFER_SIZE, maxlen=FFT_BUFFER_SIZE),
    'y': deque([0.0]*FFT_BUFFER_SIZE, maxlen=FFT_BUFFER_SIZE),
    'z': deque([0.0]*FFT_BUFFER_SIZE, maxlen=FFT_BUFFER_SIZE)
}

# Real‐time sampling buffers
LVDT_BUFFER = {}     # sensor_index -> deque of (t, displacement)
ACC_BUFFER = {}      # sensor_index -> deque of (t, magnitude, x, y, z)

# Custom color set for sensor lines
SENSOR_COLORS = [
    '#FF5733', '#33FF57', '#3357FF', '#FF33A8', 
    '#33FFF5', '#F533FF', '#FF8C33', '#8CFF33', 
    '#338CFF', '#FF338C', '#33FFC4', '#C433FF'
]

# add base colors per component
COMPONENT_COLORS = {
    'magnitude': '#BCBEC0',
    'x': '#FF5733',
    'y': '#33FF57',
    'z': '#3357FF'
}
def _shade_color(hex_color, dark=False):
    # darken by factor or leave as is
    hex_color = hex_color.lstrip('#')
    r, g, b = (int(hex_color[i:i+2],16) for i in (0,2,4))
    factor = 0.6 if dark else 1.0
    r, g, b = [max(0, min(255,int(c*factor))) for c in (r,g,b)]
    return f'#{r:02X}{g:02X}{b:02X}'

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
                        html.Div([   # new component selector
                            html.Label("Select Component:"),
                            dcc.Dropdown(
                                id='acc-component-selector',
                                options=[
                                    {'label': 'All', 'value': 'all'},
                                    {'label': 'Magnitude', 'value': 'magnitude'},
                                    {'label': 'X', 'value': 'x'},
                                    {'label': 'Y', 'value': 'y'},
                                    {'label': 'Z', 'value': 'z'}
                                ],
                                value='magnitude',
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
         Input('acc-selector', 'value'),
         Input('acc-component-selector', 'value')]
    )
    def update_acceleration_graph(n, selected_accs, selected_comp):
        if not ACC_BUFFER:
            return go.Figure()

        fig = go.Figure()
        # sensor filtering
        if selected_accs is None:
            selected_accs = ['all']
        elif not isinstance(selected_accs, list):
            selected_accs = [selected_accs]
        show_all = 'all' in selected_accs
        sel_idxs = [int(i) for i in selected_accs if i != 'all']

        # component filtering
        comp = selected_comp or 'magnitude'
        comp_map = {'magnitude':1, 'x':2, 'y':3, 'z':4}

        for i, buf in ACC_BUFFER.items():
            if show_all or i in sel_idxs:
                times = [entry[0] for entry in buf]
                if comp == 'all':
                    for name, idx in comp_map.items():
                        vals = [entry[idx] for entry in buf]
                        base = COMPONENT_COLORS[name]
                        color = _shade_color(base, dark=(i % 2 == 1))
                        fig.add_trace(go.Scatter(
                            x=times, y=vals, mode='lines',
                            line={'color': color}, name=f'ACC {i+1} {name.upper()}'
                        ))
                else:
                    idx = comp_map.get(comp, 1)
                    vals = [entry[idx] for entry in buf]
                    base = COMPONENT_COLORS.get(comp, COMPONENT_COLORS['magnitude'])
                    color = _shade_color(base, dark=(i % 2 == 1))
                    fig.add_trace(go.Scatter(
                        x=times, y=vals, mode='lines',
                        line={'color': color}, name=f'ACC {i+1} {comp.upper()}'
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
            # usar buffers prellenados
            data_x = np.array(FFT_BUFFERS['x'])
            data_y = np.array(FFT_BUFFERS['y'])
            data_z = np.array(FFT_BUFFERS['z'])
            # ventana Hanning
            w = np.hanning(len(data_x))
            xw, yw, zw = data_x*w, data_y*w, data_z*w
            # FFT
            fx, fy, fz = np.abs(fft(xw)), np.abs(fft(yw)), np.abs(fft(zw))
            # frecuencias
            dt = 1.0 / system_monitor.config.sampling_rate_acceleration
            freqs = fftfreq(FFT_BUFFER_SIZE, dt)
            n2 = len(freqs)//2
            # construir figura
            fig = go.Figure()
            fig.add_trace(go.Scatter(x=freqs[:n2], y=fx[:n2], name='X', line={'color': COMPONENT_COLORS['x']}))
            fig.add_trace(go.Scatter(x=freqs[:n2], y=fy[:n2], name='Y', line={'color': COMPONENT_COLORS['y']}))
            fig.add_trace(go.Scatter(x=freqs[:n2], y=fz[:n2], name='Z', line={'color': COMPONENT_COLORS['z']}))
            fig.update_layout(
                title='FFT Acelerómetro 1',
                xaxis={'title':'Frecuencia (Hz)'}, yaxis={'title':'Amplitud'},
                paper_bgcolor=PALETTE[2], plot_bgcolor=PALETTE[2], font={'color': PALETTE[3]},
                height=500, margin={'l':40,'r':40,'t':80,'b':40}, showlegend=True
            )
            return fig
    
    return app

def run_dashboard(system_monitor):
    """Initialize and run the dashboard in a separate thread."""
    app = create_dashboard(system_monitor)

    def run():
        import logging, socket, webbrowser, time as _t
        logging.getLogger('werkzeug').setLevel(logging.ERROR)

        # Automatic IP detection
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            external_ip = s.getsockname()[0]
            s.close()
        except:
            external_ip = "127.0.0.1"

        dashboard_url = f"http://{external_ip}:8050"
        print(f"\nAccess dashboard at: {dashboard_url}\n")

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
                    buf[i].append((
                        t,
                        s.get('magnitude', 0),
                        s.get('x', 0),
                        s.get('y', 0),
                        s.get('z', 0)
                    ))
                    # actualizar FFT buffer solo para el sensor 0
                    if i == 0:
                        FFT_BUFFERS['x'].append(s.get('x', 0))
                        FFT_BUFFERS['y'].append(s.get('y', 0))
                        FFT_BUFFERS['z'].append(s.get('z', 0))
                _t.sleep(period)

        threading.Thread(target=lvdt_sampler, daemon=True).start()
        threading.Thread(target=acc_sampler, daemon=True).start()
        # --- end sampling threads ---

        # Attempt to open browser (will silently fail if headless)
        def open_browser():
            _t.sleep(1.5)
            try:
                webbrowser.open_new(dashboard_url)
            except:
                pass

        threading.Thread(target=open_browser, daemon=True).start()

        try:
            app.run(debug=False, host='0.0.0.0', port=8050)
        except Exception as e:
            print(f"ERROR starting dashboard: {e}")
            print("Try accessing at http://127.0.0.1:8050 instead\n")

    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread
