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
            
            # Add bar/gauge for each LVDT
            fig.add_trace(go.Indicator(
                mode="number+gauge",
                value=displacement,
                domain={'x': [i/len(lvdt_data), (i+1)/len(lvdt_data)]},
                title={'text': f'LVDT {i+1}'},
                gauge={
                    'axis': {'range': [-50, 50]},
                    'bar': {'color': '#2196F3'},
                    'threshold': {
                        'line': {'color': 'red', 'width': 4},
                        'thickness': 0.75,
                        'value': system_monitor.config.trigger_displacement_threshold
                    },
                    'steps': [
                        {'range': [-system_monitor.config.trigger_displacement_threshold, 
                                  system_monitor.config.trigger_displacement_threshold], 
                         'color': 'rgba(255, 255, 255, 0.1)'},
                        {'range': [-system_monitor.config.detrigger_displacement_threshold, 
                                  system_monitor.config.detrigger_displacement_threshold], 
                         'color': 'rgba(255, 255, 255, 0.2)'}
                    ],
                }
            ))
            
        # Update layout
        fig.update_layout(
            height=400,
            margin=dict(l=40, r=40, t=60, b=40),
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font={'color': '#90CAF9'},
            showlegend=False
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
