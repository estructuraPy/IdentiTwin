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

# Set template for consistent styling
pio.templates.default = "plotly_dark"

# Store historical LVDT data for scatter plots
LVDT_HISTORY = {}          # key: sensor idx → {'x':[], 'y':[]}
MAX_POINTS = 10000           # max samples in window
DT = 0.2                   # seconds per update (interval ms/1000)

def create_dashboard(system_monitor):
    """Create and configure the Dash application."""
    app = dash.Dash(__name__)

    app.layout = html.Div([
        html.H1("IdentiTwin Real-Time Monitoring",
                style={'textAlign': 'center', 'color': '#2196F3'}),
        
        # Only create LVDT plot if enabled
        html.Div([
            html.H3("LVDT Displacements", 
                   style={'textAlign': 'center', 'color': '#90CAF9'}),
            dcc.Graph(id='lvdt-plot'),
        ]) if system_monitor.config.enable_plot_displacement else None,
        
        # Update interval
        dcc.Interval(
            id='interval-component',
            interval=200,  # Update every 200ms
            n_intervals=0
        )
    ])

    @app.callback(
        Output('lvdt-plot', 'figure'),
        Input('interval-component', 'n_intervals')
    )
    def update_lvdt_graph(n):
        # Get latest LVDT data from display buffer
        if not system_monitor.display_buffer or 'lvdt_data' not in system_monitor.display_buffer:
            return go.Figure()

        lvdt_data = system_monitor.display_buffer['lvdt_data']
        
        fig = go.Figure()
        for i, lvdt in enumerate(lvdt_data):
            displacement = lvdt.get('displacement', 0)
            
            # accumulate history
            hist = LVDT_HISTORY.setdefault(i, {'x': [], 'y': []})
            t = hist['x'][-1] + DT if hist['x'] else 0.0
            hist['x'].append(t)
            hist['y'].append(displacement)
            # trim to fixed window
            hist['x'] = hist['x'][-MAX_POINTS:]
            hist['y'] = hist['y'][-MAX_POINTS:]
            
            # scatter line
            fig.add_trace(go.Scatter(
                x=hist['x'], y=hist['y'],
                mode='lines',
                line={'color': '#2196F3'},
                name=f'LVDT {i+1}'
            ))
        
        # define x‑range
        if LVDT_HISTORY:
            xvals = next(iter(LVDT_HISTORY.values()))['x']
            xr = [xvals[0], xvals[-1]]
        else:
            xr = [0, DT*MAX_POINTS]
        
        fig.update_layout(
            xaxis={'title':'Time (s)', 'range': xr},
            yaxis={'title':'Displacement', 'range': [-50, 50]},
            height=400,
            margin=dict(l=40, r=40, t=60, b=40),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font={'color': '#90CAF9'},
            showlegend=True
        )
        return fig

    return app

def run_dashboard(system_monitor):
    """Initialize and run the dashboard in a separate thread."""
    app = create_dashboard(system_monitor)
    
    def run():
        app.run(debug=False, host='0.0.0.0', port=8050)
    
    thread = threading.Thread(target=run, daemon=True)
    thread.start()
    print("Dashboard started at http://localhost:8050")
    return thread
