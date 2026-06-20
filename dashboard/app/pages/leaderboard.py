import dash
from dash import html, dcc, callback, Input, Output, dash_table
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data import get_model_summary, get_scores, get_org_summary, get_categories
from theme import *

dash.register_page(__name__, path="/", name="Leaderboard")

layout = html.Div([
    html.H1("LLM Leaderboard", style={"marginBottom": "0.5rem", "fontWeight": "700"}),
    html.P("Overall model rankings sorted by average benchmark score",
           style={"color": "#8888aa", "marginBottom": "1.5rem"}),

    html.Div([
        html.Div([
            html.Label("Category", style={"color": "#a0a0c0", "fontSize": "0.85rem"}),
            dcc.Dropdown(id="lb-category", placeholder="All Categories"),
        ], style={"width": "200px"}),
        html.Div([
            html.Label("License", style={"color": "#a0a0c0", "fontSize": "0.85rem"}),
            dcc.Dropdown(id="lb-open", options=[
                {"label": "All", "value": "all"},
                {"label": "Open Only", "value": "open"},
                {"label": "Proprietary Only", "value": "closed"},
            ], value="all", clearable=False),
        ], style={"width": "180px"}),
        html.Div([
            html.Label("Organization", style={"color": "#a0a0c0", "fontSize": "0.85rem"}),
            dcc.Dropdown(id="lb-org", placeholder="All Orgs"),
        ], style={"width": "200px"}),
    ], style={"display": "flex", "gap": "1rem", "marginBottom": "1.5rem", "flexWrap": "wrap"}),

    html.Div(id="lb-highlights", style={"marginBottom": "1.5rem"}),
    html.Div(id="lb-table-container"),
    html.Div([
        html.Div(id="lb-org-chart", style={"flex": "1"}),
        html.Div(id="lb-heatmap", style={"flex": "1.5"}),
    ], style={"display": "flex", "gap": "1.5rem", "marginTop": "1.5rem", "flexWrap": "wrap"}),
])


@callback(Output("lb-category", "options"), Input("lb-category", "id"))
def load_categories(_):
    cats = get_categories()
    return [{"label": c.replace("_", " ").title(), "value": c} for c in cats]


@callback(Output("lb-org", "options"), Input("lb-org", "id"))
def load_orgs(_):
    df = get_org_summary()
    return [{"label": row["organization"], "value": row["organization"]} for _, row in df.iterrows()]


@callback(
    Output("lb-highlights", "children"),
    Output("lb-table-container", "children"),
    Output("lb-org-chart", "children"),
    Output("lb-heatmap", "children"),
    Input("lb-category", "value"),
    Input("lb-open", "value"),
    Input("lb-org", "value"),
)
def update_leaderboard(category, open_filter, org_filter):
    scores = get_scores()
    summary = get_model_summary()

    if category:
        model_ids = scores[scores["category"] == category]["model_id"].unique()
        summary = summary[summary["model_id"].isin(model_ids)]
        scores = scores[scores["category"] == category]

    if open_filter == "open":
        summary = summary[summary["open_weight"] == True]
        scores = scores[scores["open_weight"] == True]
    elif open_filter == "closed":
        summary = summary[summary["open_weight"] == False]
        scores = scores[scores["open_weight"] == False]

    if org_filter:
        summary = summary[summary["organization"] == org_filter]
        scores = scores[scores["organization"] == org_filter]

    summary = summary.sort_values("avg_score_pct", ascending=False).reset_index(drop=True)
    summary["rank"] = range(1, len(summary) + 1)

    # Highlight cards
    highlights = []
    if len(summary) > 0:
        best = summary.iloc[0]
        highlights.append(_card("Best Overall", best["model_name"], f"{best['avg_score_pct']:.0%}", ACCENT_1))
    if len(summary[summary["open_weight"] == True]) > 0:
        best_open = summary[summary["open_weight"] == True].iloc[0]
        highlights.append(_card("Best Open", best_open["model_name"], f"{best_open['avg_score_pct']:.0%}", ACCENT_5))
    if len(summary) > 0:
        most_tested = summary.sort_values("num_benchmarks", ascending=False).iloc[0]
        highlights.append(_card("Most Tested", most_tested["model_name"], f"{most_tested['num_benchmarks']} benchmarks", ACCENT_4))
    if len(summary[summary["open_weight"] == False]) > 0:
        best_prop = summary[summary["open_weight"] == False].iloc[0]
        highlights.append(_card("Best Proprietary", best_prop["model_name"], f"{best_prop['avg_score_pct']:.0%}", ACCENT_2))

    highlight_div = html.Div(highlights, style={"display": "flex", "gap": "1rem", "flexWrap": "wrap"})

    # Table
    table_df = summary[["rank", "model_name", "organization", "open_weight", "num_benchmarks", "num_categories", "avg_score_pct"]].head(50).copy()
    table_df["avg_score_pct"] = (table_df["avg_score_pct"] * 100).round(1).astype(str) + "%"
    table_df["open_weight"] = table_df["open_weight"].map({True: "Open", False: "Proprietary"})
    table_df.columns = ["#", "Model", "Organization", "License", "Benchmarks", "Categories", "Avg Score"]

    table = dash_table.DataTable(
        data=table_df.to_dict("records"),
        columns=[{"name": c, "id": c} for c in table_df.columns],
        sort_action="native",
        sort_by=[{"column_id": "Avg Score", "direction": "desc"}],
        page_size=25,
        style_table={"overflowX": "auto", "borderRadius": "8px"},
        style_header={"backgroundColor": "#1e1e3a", "color": "#e8e8f0", "fontWeight": "600", "border": "1px solid #2a2a4a"},
        style_cell={"backgroundColor": "rgba(15,15,30,0.8)", "color": "#d0d0e8", "border": "1px solid #1e1e3a", "padding": "10px 12px", "fontSize": "0.9rem"},
        style_data_conditional=[
            {"if": {"row_index": 0}, "backgroundColor": "rgba(99,102,241,0.15)", "fontWeight": "bold"},
            {"if": {"row_index": 1}, "backgroundColor": "rgba(168,85,247,0.1)"},
            {"if": {"row_index": 2}, "backgroundColor": "rgba(6,182,212,0.1)"},
        ],
    )

    # Org bar chart
    org_df = get_org_summary().sort_values("avg_score_pct", ascending=True).tail(15)
    fig_org = px.bar(org_df, x="avg_score_pct", y="organization", orientation="h",
                     color="avg_score_pct", color_continuous_scale=["#1e1e3a", ACCENT_1, ACCENT_2],
                     labels={"avg_score_pct": "Avg Score %", "organization": ""})
    chart_layout(fig_org, title="Organization Performance", height=400, showlegend=False, coloraxis_showscale=False)
    fig_org.update_traces(texttemplate="%{x:.0%}", textposition="outside")

    # Heatmap
    top_models = summary.head(15)["model_name"].tolist()
    main_cats = ["code", "math", "reasoning", "general", "agents", "language", "biology", "multimodal"]
    heatmap_df = scores[scores["model_name"].isin(top_models) & scores["category"].isin(main_cats)]
    pivot = heatmap_df.pivot_table(index="model_name", columns="category", values="score_pct", aggfunc="mean")
    pivot = pivot.reindex(top_models)
    pivot = pivot[[c for c in main_cats if c in pivot.columns]]

    fig_hm = go.Figure(data=go.Heatmap(
        z=pivot.values, x=pivot.columns.tolist(), y=pivot.index.tolist(),
        colorscale=[[0, "#1e1e3a"], [0.4, "#6366f1"], [0.7, "#a855f7"], [1, "#06b6d4"]],
        zmin=0.3, zmax=1.0,
        texttemplate="%{z:.0%}", textfont={"size": 10, "color": "#fff"},
        hovertemplate="Model: %{y}<br>Category: %{x}<br>Score: %{z:.1%}<extra></extra>",
    ))
    chart_layout(fig_hm, title="Top Models × Category Heatmap", height=450)

    return highlight_div, table, dcc.Graph(figure=fig_org), dcc.Graph(figure=fig_hm)


def _card(title, value, metric, color):
    return html.Div([
        html.Div(title, style={"fontSize": "0.8rem", "color": "#8888aa", "marginBottom": "0.3rem", "textTransform": "uppercase", "letterSpacing": "0.5px"}),
        html.Div(value, style={"fontSize": "1.1rem", "fontWeight": "700", "color": "#fff"}),
        html.Div(metric, style={"fontSize": "1.3rem", "color": color, "fontWeight": "600", "marginTop": "0.2rem"}),
    ], style={
        "background": CARD_BG, "borderRadius": "10px", "padding": "1.2rem 1.5rem",
        "border": f"1px solid {CARD_BORDER}", "minWidth": "160px",
        "backdropFilter": "blur(10px)",
    })
