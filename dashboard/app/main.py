import dash
from dash import html, dcc
import os

app = dash.Dash(
    __name__,
    use_pages=True,
    suppress_callback_exceptions=True,
    title="LLM Stats Dashboard",
    meta_tags=[{"name": "viewport", "content": "width=device-width, initial-scale=1"}],
    external_stylesheets=[
        "https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap"
    ],
)

app.index_string = '''<!DOCTYPE html>
<html>
    <head>
        {%metas%}
        <title>{%title%}</title>
        {%favicon%}
        {%css%}
        <style>
            * { box-sizing: border-box; }
            body {
                margin: 0;
                background: linear-gradient(135deg, #0a0a1a 0%, #1a1035 50%, #0d1b2a 100%);
                color: #e8e8f0;
                font-family: 'Inter', -apple-system, sans-serif;
                min-height: 100vh;
            }
            .nav-link {
                color: #a0a0c0;
                text-decoration: none;
                padding: 0.5rem 1rem;
                border-radius: 6px;
                font-size: 0.9rem;
                font-weight: 500;
                transition: all 0.2s;
            }
            .nav-link:hover, .nav-link:focus {
                color: #fff;
                background: rgba(99, 102, 241, 0.2);
            }
            .Select-control, .Select-menu-outer {
                background: #1e1e3a !important;
                border-color: #3a3a5c !important;
                color: #e8e8f0 !important;
            }
            .Select-value-label, .Select-placeholder {
                color: #e8e8f0 !important;
            }
            .Select-option {
                background: #1e1e3a !important;
                color: #e8e8f0 !important;
            }
            .Select-option.is-focused {
                background: #2d2d5a !important;
            }
            .dash-table-container .dash-spreadsheet-container {
                border-radius: 8px;
                overflow: hidden;
            }
            ::-webkit-scrollbar { width: 8px; height: 8px; }
            ::-webkit-scrollbar-track { background: #1a1a2e; }
            ::-webkit-scrollbar-thumb { background: #4a4a6a; border-radius: 4px; }
        </style>
    </head>
    <body>
        {%app_entry%}
        <footer>
            {%config%}
            {%scripts%}
            {%renderer%}
        </footer>
    </body>
</html>'''

app.layout = html.Div([
    html.Div([
        html.Div([
            html.H2("LLM Stats", style={
                "margin": "0", "color": "#fff", "fontWeight": "700",
                "background": "linear-gradient(90deg, #6366f1, #a855f7)",
                "WebkitBackgroundClip": "text", "WebkitTextFillColor": "transparent",
            }),
        ]),
        html.Nav([
            dcc.Link("Leaderboard", href="/", className="nav-link"),
            dcc.Link("Deep Dive", href="/model", className="nav-link"),
            dcc.Link("Category", href="/category", className="nav-link"),
            dcc.Link("Trends", href="/trends", className="nav-link"),
            dcc.Link("Cost", href="/cost", className="nav-link"),
            dcc.Link("Compare", href="/compare", className="nav-link"),
        ], style={"display": "flex", "gap": "0.5rem", "flexWrap": "wrap"}),
    ], style={
        "display": "flex", "justifyContent": "space-between", "alignItems": "center",
        "padding": "1rem 2rem",
        "background": "rgba(15, 15, 35, 0.95)",
        "borderBottom": "1px solid rgba(99, 102, 241, 0.3)",
        "backdropFilter": "blur(10px)",
        "position": "sticky", "top": "0", "zIndex": "100",
    }),
    html.Div(dash.page_container, style={
        "padding": "2rem",
        "maxWidth": "1400px",
        "margin": "0 auto",
    }),
])

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8050, debug=os.environ.get("DEBUG", "0") == "1")
