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

# Set template for consistent styling
pio.templates.default = "plotly_dark"

PALETTE = ['#C6203E', '#00217E', '#BCBEC0', '#000000']

# Store historical LVDT data for scatter plots
LVDT_HISTORY = {}
ACC_HISTORY = {}          
MAX_POINTS = 1000        

# Custom color set for sensor lines - distinct from PALETTE
SENSOR_COLORS = [
    '#FF5733', '#33FF57', '#3357FF', '#FF33A8', 
    '#33FFF5', '#F533FF', '#FF8C33', '#8CFF33', 
    '#338CFF', '#FF338C', '#33FFC4', '#C433FF'
]

def create_dashboard(system_monitor):
    """Create and configure the Dash application."""
    app = dash.Dash(__name__)

    app.layout = html.Div([
        html.H1("IdentiTwin Real-Time Monitoring",
                style={'textAlign': 'center', 'color': PALETTE[0]}),

        # LVDT section with dropdown selector
        html.Div([
            html.H3("LVDT Displacements", 
                    style={'textAlign': 'center', 'color': PALETTE[1]}),
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
            dcc.Graph(id='lvdt-plot'),
        ]) if system_monitor.config.enable_plot_displacement else None,
        
        # Acceleration section with dropdown selector
        html.Div([
            html.H3("Accelerations", 
                    style={'textAlign': 'center', 'color': PALETTE[1]}),
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
            dcc.Graph(id='acceleration-plot'),
        ]) if system_monitor.config.enable_plot_displacement else None,
        
        # Update interval
        dcc.Interval(
            id='interval-component',
            interval=int(1000/system_monitor.config.plot_refresh_rate),  # ms per update
            n_intervals=0
        )
    ])

    @app.callback(
        Output('lvdt-plot', 'figure'),
        [Input('interval-component', 'n_intervals'),
         Input('lvdt-selector', 'value')]
    )
    def update_lvdt_graph(n, selected_lvdts):
        # Get latest LVDT data from display buffer
        if not system_monitor.display_buffer or 'lvdt_data' not in system_monitor.display_buffer:
            return go.Figure()

        lvdt_data = system_monitor.display_buffer['lvdt_data']
        
        fig = go.Figure()
        
        # Check if 'all' is selected or if there are no selections
        show_all = 'all' in selected_lvdts if isinstance(selected_lvdts, list) else selected_lvdts == 'all'
        selected_indices = [int(i) for i in selected_lvdts if i != 'all'] if isinstance(selected_lvdts, list) else []
        
        for i, lvdt in enumerate(lvdt_data):
            # Skip if this LVDT is not selected
            if not show_all and i not in selected_indices:
                continue
                
            displacement = lvdt.get('displacement', 0)
            
            # accumulate history using update rate
            hist = LVDT_HISTORY.setdefault(i, {'x': [], 'y': []})
            DT = 1.0/system_monitor.config.plot_refresh_rate
            t = hist['x'][-1] + DT if hist['x'] else 0.0

            hist['x'].append(t)
            hist['y'].append(displacement)
            # trim to fixed window
            hist['x'] = hist['x'][-MAX_POINTS:]
            hist['y'] = hist['y'][-MAX_POINTS:]
            
            # Use custom colors for sensor lines
            fig.add_trace(go.Scatter(
                x=hist['x'], y=hist['y'],
                mode='lines',
                line={'color': SENSOR_COLORS[i % len(SENSOR_COLORS)]},
                name=f'LVDT {i+1}'
            ))
        
        # Calculate offset for relative time display
        offset = 0
        for sensor in LVDT_HISTORY.values():
            if sensor['x']:
                t_end = sensor['x'][-1]
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
        # Get latest Acceleration data from display buffer
        if not system_monitor.display_buffer or 'accel_data' not in system_monitor.display_buffer:
            return go.Figure()

        accel_data = system_monitor.display_buffer['accel_data']
        
        fig = go.Figure()
        
        # Check if 'all' is selected or if there are no selections
        show_all = 'all' in selected_accs if isinstance(selected_accs, list) else selected_accs == 'all'
        selected_indices = [int(i) for i in selected_accs if i != 'all'] if isinstance(selected_accs, list) else []
        
        for i, acc in enumerate(accel_data):
            # Skip if this accelerometer is not selected
            if not show_all and i not in selected_indices:
                continue
                
            # Get magnitude value
            acceleration = acc.get('magnitude', 0)
            
            # accumulate history using update rate
            hist = ACC_HISTORY.setdefault(i, {'x': [], 'y': []})
            DT = 1.0/system_monitor.config.plot_refresh_rate
            t = hist['x'][-1] + DT if hist['x'] else 0.0

            hist['x'].append(t)
            hist['y'].append(acceleration)
            # trim to fixed window
            hist['x'] = hist['x'][-MAX_POINTS:]
            hist['y'] = hist['y'][-MAX_POINTS:]
            
            # Use custom colors for sensor lines
            fig.add_trace(go.Scatter(
                x=hist['x'], y=hist['y'],
                mode='lines',
                line={'color': SENSOR_COLORS[i % len(SENSOR_COLORS)]},
                name=f'ACC {i+1}'
            ))
        
        # Calculate offset for relative time display
        offset = 0
        for sensor in ACC_HISTORY.values():
            if sensor['x']:
                t_end = sensor['x'][-1]
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

    return app

def run_dashboard(system_monitor):
    """Initialize and run the dashboard in a separate thread."""
    app = create_dashboard(system_monitor)
    
    def run():
        import logging
        import socket
        import webbrowser
        import time
        
        # Configure logging for better error feedback
        logging.getLogger('werkzeug').setLevel(logging.ERROR)
        
        # Use specific IP address for external access
        try:
            external_ip = "192.168.5.199"
            dashboard_url = f"http://{external_ip}:8050"
            external_url = f"http://{external_ip}:8050"
            print(f"\nAccess from other devices at: {external_url}\n")
            
            # Open browser in a separate thread after a short delay
            # to ensure server is ready
            def open_browser():
                time.sleep(1.5)  # Give the server a bit of time to start
                webbrowser.open_new(dashboard_url)
                
            browser_thread = threading.Thread(target=open_browser)
            browser_thread.daemon = True
            browser_thread.start()
            
            # Start the server with specific host binding
            app.run(debug=False, host='0.0.0.0', port=8050)
        except Exception as e:
            print(f"ERROR starting dashboard: {e}")
            print("Try accessing the dashboard at http://127.0.0.1:8050 instead \n")
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    return thread
