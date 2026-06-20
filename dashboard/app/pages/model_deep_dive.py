import dash
from dash import html, dcc, callback, Input, Output, dash_table
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data import get_scores, get_model_summary, get_model_names
from theme import *

dash.register_page(__name__, path="/model", name="Model Deep Dive")

layout = html.Div([
    html.H1("Model Deep Dive", style={"marginBottom": "0.5rem", "fontWeight": "700"}),
    html.P("Explore individual model performance across all benchmarks",
           style={"color": "#8888aa", "marginBottom": "1.5rem"}),

    html.Div([
        html.Label("Select Model", style={"color": "#a0a0c0", "fontSize": "0.85rem"}),
        dcc.Dropdown(id="md-model", placeholder="Choose a model...", style={"width": "350px"}),
    ], style={"marginBottom": "1.5rem"}),

    html.Div(id="md-info-card", style={"marginBottom": "1.5rem"}),
    html.Div([
        html.Div(id="md-category-bar", style={"flex": "1"}),
        html.Div(id="md-radar", style={"flex": "1"}),
    ], style={"display": "flex", "gap": "1.5rem", "marginBottom": "1.5rem", "flexWrap": "wrap"}),
    html.Div(id="md-table", style={"marginTop": "1rem"}),
])


@callback(Output("md-model", "options"), Input("md-model", "id"))
def load_models(_):
    return [{"label": n, "value": n} for n in get_model_names()]


@callback(
    Output("md-info-card", "children"),
    Output("md-category-bar", "children"),
    Output("md-radar", "children"),
    Output("md-table", "children"),
    Input("md-model", "value"),
)
def update_model(model_name):
    if not model_name:
        return html.Div("Select a model to view details", style={"color": "#6666aa", "padding": "2rem"}), "", "", ""

    summary = get_model_summary()
    scores = get_scores()
    model_info = summary[summary["model_name"] == model_name]
    model_scores = scores[scores["model_name"] == model_name]

    if model_info.empty:
        return html.Div("Model not found", style={"color": ACCENT_6}), "", "", ""

    info = model_info.iloc[0]

    # Info card
    info_card = html.Div([
        html.Div([
            html.H2(model_name, style={"margin": "0", "color": "#fff", "fontWeight": "700"}),
            html.Div([
                _badge(info["organization"], ACCENT_1),
                _badge("Open" if info["open_weight"] else "Proprietary", ACCENT_5 if info["open_weight"] else ACCENT_4),
                _badge(f"Rank #{int(info['overall_rank'])}", ACCENT_2),
                _badge(f"{info['num_benchmarks']} benchmarks", ACCENT_3),
            ], style={"display": "flex", "gap": "0.5rem", "marginTop": "0.5rem", "flexWrap": "wrap"}),
        ], style={"flex": "1"}),
        html.Div([
            html.Div("Overall", style={"color": "#8888aa", "fontSize": "0.85rem"}),
            html.Div(f"{info['avg_score_pct']:.0%}", style={
                "fontSize": "2.8rem", "fontWeight": "700",
                "background": f"linear-gradient(135deg, {ACCENT_1}, {ACCENT_2})",
                "WebkitBackgroundClip": "text", "WebkitTextFillColor": "transparent",
            }),
        ], style={"textAlign": "center"}),
    ], style={
        "display": "flex", "justifyContent": "space-between", "alignItems": "center",
        "background": CARD_BG, "borderRadius": "10px", "padding": "1.5rem",
        "border": f"1px solid {CARD_BORDER}",
    })

    # Category bar chart
    cat_scores = model_scores.groupby("category")["score_pct"].mean().reset_index()
    cat_scores = cat_scores.sort_values("score_pct", ascending=True)
    global_avg = scores.groupby("category")["score_pct"].mean()

    fig_bar = go.Figure()
    fig_bar.add_trace(go.Bar(
        x=cat_scores["score_pct"], y=cat_scores["category"],
        orientation="h",
        marker=dict(color=cat_scores["score_pct"], colorscale=[[0, ACCENT_6], [0.5, ACCENT_1], [1, ACCENT_5]]),
        text=[f"{v:.0%}" for v in cat_scores["score_pct"]], textposition="outside",
        textfont=dict(color="#c8c8e0"),
        name=model_name,
    ))
    for _, row in cat_scores.iterrows():
        avg = global_avg.get(row["category"], 0)
        fig_bar.add_shape(type="line", x0=avg, x1=avg,
                         y0=row["category"], y1=row["category"],
                         line=dict(color=ACCENT_6, width=2, dash="dash"),
                         xref="x", yref="y")

    chart_layout(fig_bar, title="Score by Category (pink dash = global avg)",
                 height=max(300, len(cat_scores) * 40),
                 xaxis=dict(range=[0, 1.1], tickformat=".0%"), showlegend=False)
    fig_bar.update_layout(margin=dict(l=10, r=60, t=40, b=10))

    # Radar chart
    radar_cats = cat_scores["category"].tolist()
    radar_vals = cat_scores["score_pct"].tolist()
    radar_avg = [global_avg.get(c, 0) for c in radar_cats]

    fig_radar = go.Figure()
    fig_radar.add_trace(go.Scatterpolar(
        r=radar_vals + [radar_vals[0]], theta=radar_cats + [radar_cats[0]],
        fill="toself", name=model_name, line_color=ACCENT_1,
        fillcolor="rgba(99,102,241,0.2)",
    ))
    fig_radar.add_trace(go.Scatterpolar(
        r=radar_avg + [radar_avg[0]], theta=radar_cats + [radar_cats[0]],
        fill="toself", name="Global Average", line_color=ACCENT_6,
        fillcolor="rgba(244,63,94,0.08)", line_dash="dash",
    ))
    chart_layout(fig_radar, title="Performance vs Global Average", height=400,
                 polar=dict(radialaxis=dict(range=[0, 1], tickformat=".0%", gridcolor="#2a2a4a"),
                           angularaxis=dict(gridcolor="#2a2a4a"), bgcolor="rgba(0,0,0,0)"))
    fig_radar.update_layout(margin=dict(l=60, r=60, t=40, b=40))

    # Detail table
    table_df = model_scores[["benchmark_name", "category", "score_pct", "score", "max_score", "verified"]].copy()
    table_df["vs_avg"] = table_df.apply(lambda r: r["score_pct"] - global_avg.get(r["category"], 0), axis=1)
    table_df = table_df.sort_values("score_pct", ascending=False)
    table_df["score_pct"] = (table_df["score_pct"] * 100).round(1).astype(str) + "%"
    table_df["vs_avg"] = table_df["vs_avg"].apply(lambda x: f"+{x*100:.1f}%" if x >= 0 else f"{x*100:.1f}%")
    table_df["verified"] = table_df["verified"].map({True: "Yes", False: "No"})
    table_df.columns = ["Benchmark", "Category", "Score %", "Raw Score", "Max Score", "Verified", "vs Avg"]
    table_df = table_df[["Benchmark", "Category", "Score %", "vs Avg", "Raw Score", "Max Score", "Verified"]]

    detail_table = dash_table.DataTable(
        data=table_df.to_dict("records"),
        columns=[{"name": c, "id": c} for c in table_df.columns],
        sort_action="native", filter_action="native",
        sort_by=[{"column_id": "Score %", "direction": "desc"}],
        page_size=20,
        style_table={"overflowX": "auto", "borderRadius": "8px"},
        style_header={"backgroundColor": "#1e1e3a", "color": "#e8e8f0", "fontWeight": "600", "border": "1px solid #2a2a4a"},
        style_cell={"backgroundColor": "rgba(15,15,30,0.8)", "color": "#d0d0e8", "border": "1px solid #1e1e3a", "padding": "8px", "fontSize": "0.85rem"},
    )

    return info_card, dcc.Graph(figure=fig_bar), dcc.Graph(figure=fig_radar), detail_table


def _badge(text, color):
    return html.Span(text, style={
        "background": f"{color}18", "color": color, "padding": "0.25rem 0.7rem",
        "borderRadius": "5px", "fontSize": "0.8rem", "border": f"1px solid {color}40", "fontWeight": "500",
    })
