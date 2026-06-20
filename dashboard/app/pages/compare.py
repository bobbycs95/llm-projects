import dash
from dash import html, dcc, callback, Input, Output, dash_table
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data import get_scores, get_model_summary, get_model_names
from theme import *

dash.register_page(__name__, path="/compare", name="Compare Models")

COLORS_MAP = {"A": ACCENT_1, "B": ACCENT_3, "C": ACCENT_4}

layout = html.Div([
    html.H1("Model Comparison", style={"marginBottom": "0.5rem", "fontWeight": "700"}),
    html.P("Compare up to 3 models side by side across all benchmarks and categories",
           style={"color": "#8888aa", "marginBottom": "1.5rem"}),

    html.Div([
        html.Div([
            html.Label("Model A", style={"color": ACCENT_1, "fontWeight": "600", "fontSize": "0.85rem"}),
            dcc.Dropdown(id="cmp-model-a", placeholder="Select Model A..."),
        ], style={"flex": "1", "minWidth": "220px"}),
        html.Div([
            html.Label("Model B", style={"color": ACCENT_3, "fontWeight": "600", "fontSize": "0.85rem"}),
            dcc.Dropdown(id="cmp-model-b", placeholder="Select Model B..."),
        ], style={"flex": "1", "minWidth": "220px"}),
        html.Div([
            html.Label("Model C", style={"color": ACCENT_4, "fontWeight": "600", "fontSize": "0.85rem"}),
            dcc.Dropdown(id="cmp-model-c", placeholder="Select Model C..."),
        ], style={"flex": "1", "minWidth": "220px"}),
    ], style={"display": "flex", "gap": "1rem", "marginBottom": "2rem", "flexWrap": "wrap"}),

    html.Div(id="cmp-summary-cards", style={"marginBottom": "1.5rem"}),
    html.Div(id="cmp-radar", style={"marginBottom": "1.5rem"}),
    html.Div(id="cmp-category-bar", style={"marginBottom": "1.5rem"}),
    html.Div(id="cmp-benchmark-bar", style={"marginBottom": "1.5rem"}),
    html.Div(id="cmp-table"),
])


@callback(
    Output("cmp-model-a", "options"),
    Output("cmp-model-b", "options"),
    Output("cmp-model-c", "options"),
    Input("cmp-model-a", "id"),
)
def load_model_options(_):
    names = get_model_names()
    opts = [{"label": n, "value": n} for n in names]
    return opts, opts, opts


@callback(
    Output("cmp-summary-cards", "children"),
    Output("cmp-radar", "children"),
    Output("cmp-category-bar", "children"),
    Output("cmp-benchmark-bar", "children"),
    Output("cmp-table", "children"),
    Input("cmp-model-a", "value"),
    Input("cmp-model-b", "value"),
    Input("cmp-model-c", "value"),
)
def update_comparison(model_a, model_b, model_c):
    selected = [m for m in [model_a, model_b, model_c] if m]
    if not selected:
        return html.Div("Select at least one model to begin comparison",
                        style={"color": "#6666aa", "padding": "2rem"}), "", "", "", ""

    scores = get_scores()
    summary = get_model_summary()
    labels = {}
    for m, lbl in [(model_a, "A"), (model_b, "B"), (model_c, "C")]:
        if m:
            labels[m] = lbl

    model_scores = scores[scores["model_name"].isin(selected)]
    model_info = summary[summary["model_name"].isin(selected)]

    # Summary cards
    cards = []
    for model in selected:
        info = model_info[model_info["model_name"] == model]
        if info.empty:
            continue
        info = info.iloc[0]
        label = labels.get(model, "?")
        color = COLORS_MAP[label]
        cards.append(html.Div([
            html.Div(f"Model {label}", style={"fontSize": "0.75rem", "color": color, "fontWeight": "700", "textTransform": "uppercase", "letterSpacing": "1px"}),
            html.Div(model, style={"fontSize": "1.1rem", "fontWeight": "600", "color": "#fff", "marginTop": "0.3rem"}),
            html.Div([
                html.Span(info["organization"], style={"color": "#a0a0c0"}),
                html.Span(" · ", style={"color": "#444"}),
                html.Span("Open" if info["open_weight"] else "Proprietary", style={"color": "#a0a0c0"}),
            ], style={"fontSize": "0.8rem", "marginTop": "0.3rem"}),
            html.Div([
                html.Div(f"{info['avg_score_pct']:.0%}", style={"fontSize": "2rem", "fontWeight": "700", "color": color}),
                html.Div(f"Rank #{int(info['overall_rank'])} · {info['num_benchmarks']} benchmarks",
                         style={"fontSize": "0.75rem", "color": "#8888aa"}),
            ], style={"marginTop": "0.5rem"}),
        ], style={
            "background": CARD_BG, "borderRadius": "10px", "padding": "1.2rem 1.5rem",
            "border": f"2px solid {color}60", "flex": "1", "minWidth": "200px",
        }))
    summary_div = html.Div(cards, style={"display": "flex", "gap": "1rem", "flexWrap": "wrap"})

    # Radar chart
    cat_avg = model_scores.groupby(["model_name", "category"])["score_pct"].mean().reset_index()
    all_cats = cat_avg["category"].unique().tolist()

    fig_radar = go.Figure()
    for model in selected:
        label = labels.get(model, "?")
        color = COLORS_MAP[label]
        mdata = cat_avg[cat_avg["model_name"] == model].set_index("category")["score_pct"]
        cats = sorted(all_cats)
        vals = [mdata.get(c, 0) for c in cats]
        fig_radar.add_trace(go.Scatterpolar(
            r=vals + [vals[0]], theta=cats + [cats[0]],
            fill="toself", name=model, line_color=color,
            fillcolor=f"rgba({_hex_to_rgb(color)},0.12)",
        ))
    chart_layout(fig_radar, title="Category Performance Radar", height=450,
                 polar=dict(radialaxis=dict(range=[0, 1], tickformat=".0%", gridcolor="#2a2a4a"),
                           angularaxis=dict(gridcolor="#2a2a4a"), bgcolor="rgba(0,0,0,0)"))
    fig_radar.update_layout(margin=dict(l=60, r=60, t=40, b=40))

    # Category grouped bar
    fig_cat = px.bar(
        cat_avg[cat_avg["model_name"].isin(selected)].sort_values("category"),
        x="category", y="score_pct", color="model_name", barmode="group",
        color_discrete_map={m: COLORS_MAP[labels[m]] for m in selected if m in labels},
        labels={"score_pct": "Avg Score %", "category": "", "model_name": ""},
        text_auto=".0%",
    )
    chart_layout(fig_cat, title="Category Score Comparison", height=400,
                 yaxis=dict(tickformat=".0%"), legend=dict(orientation="h", y=-0.15))

    # Benchmark grouped bar (common benchmarks)
    bench_scores = model_scores.groupby(["model_name", "benchmark_name"])["score_pct"].mean().reset_index()
    common_benchmarks = bench_scores.groupby("benchmark_name")["model_name"].nunique()
    common_benchmarks = common_benchmarks[common_benchmarks == len(selected)].index.tolist()
    bench_common = bench_scores[bench_scores["benchmark_name"].isin(common_benchmarks)]

    if not bench_common.empty:
        fig_bench = px.bar(
            bench_common.sort_values("benchmark_name"), x="benchmark_name", y="score_pct",
            color="model_name", barmode="group",
            color_discrete_map={m: COLORS_MAP[labels[m]] for m in selected if m in labels},
            labels={"score_pct": "Score %", "benchmark_name": "", "model_name": ""},
            text_auto=".0%",
        )
        chart_layout(fig_bench, title=f"Benchmark Comparison ({len(common_benchmarks)} common benchmarks)",
                     height=400, yaxis=dict(tickformat=".0%"), legend=dict(orientation="h", y=-0.2),
                     xaxis=dict(tickangle=-45))
        fig_bench.update_layout(margin=dict(l=10, r=10, t=40, b=80))
    else:
        fig_bench = go.Figure()
        fig_bench.add_annotation(text="No common benchmarks between selected models",
                                 x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False, font_color="#6666aa")
        chart_layout(fig_bench, height=200)

    # Pivot table
    pivot_data = model_scores[model_scores["model_name"].isin(selected)].pivot_table(
        index=["benchmark_name", "category"], columns="model_name", values="score_pct", aggfunc="mean"
    ).reset_index()

    if not pivot_data.empty:
        model_cols = [c for c in pivot_data.columns if c in selected]
        if model_cols:
            pivot_data["Winner"] = pivot_data[model_cols].idxmax(axis=1)
        for col in model_cols:
            pivot_data[col] = (pivot_data[col] * 100).round(1).astype(str) + "%"
            pivot_data[col] = pivot_data[col].replace("nan%", "—")

        cmp_table = dash_table.DataTable(
            data=pivot_data.to_dict("records"),
            columns=[{"name": c, "id": c} for c in pivot_data.columns],
            sort_action="native", filter_action="native",
            sort_by=[{"column_id": "benchmark_name", "direction": "asc"}],
            page_size=25,
            style_table={"overflowX": "auto", "borderRadius": "8px"},
            style_header={"backgroundColor": "#1e1e3a", "color": "#e8e8f0", "fontWeight": "600", "border": "1px solid #2a2a4a"},
            style_cell={"backgroundColor": "rgba(15,15,30,0.8)", "color": "#d0d0e8", "border": "1px solid #1e1e3a", "padding": "8px", "fontSize": "0.85rem"},
            style_data_conditional=[
                {"if": {"column_id": "Winner"}, "fontWeight": "bold", "color": ACCENT_5},
            ],
        )
    else:
        cmp_table = html.Div("No data to compare", style={"color": "#6666aa"})

    return summary_div, dcc.Graph(figure=fig_radar), dcc.Graph(figure=fig_cat), dcc.Graph(figure=fig_bench), cmp_table


def _hex_to_rgb(hex_color):
    h = hex_color.lstrip("#")
    return ",".join(str(int(h[i:i+2], 16)) for i in (0, 2, 4))
