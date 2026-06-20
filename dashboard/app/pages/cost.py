import dash
from dash import html, dcc, callback, Input, Output, dash_table
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data import get_pricing, get_scores, get_model_summary
from theme import *

dash.register_page(__name__, path="/cost", name="Cost Efficiency")

layout = html.Div([
    html.H1("Cost Efficiency", style={"marginBottom": "0.5rem", "fontWeight": "700"}),
    html.P("Find the best value — performance per dollar across models",
           style={"color": "#8888aa", "marginBottom": "1.5rem"}),

    html.Div([
        html.Label("Filter", style={"color": "#a0a0c0", "fontSize": "0.85rem"}),
        dcc.Dropdown(id="cost-open", options=[
            {"label": "All", "value": "all"},
            {"label": "Open Only", "value": "open"},
            {"label": "Proprietary Only", "value": "closed"},
        ], value="all", clearable=False, style={"width": "180px"}),
    ], style={"marginBottom": "1.5rem"}),

    html.Div(id="cost-scatter", style={"marginBottom": "1.5rem"}),
    html.Div([
        html.Div(id="cost-tier", style={"flex": "1"}),
        html.Div(id="cost-efficiency-bar", style={"flex": "1"}),
    ], style={"display": "flex", "gap": "1.5rem", "marginBottom": "1.5rem", "flexWrap": "wrap"}),
    html.Div(id="cost-table"),
])


@callback(
    Output("cost-scatter", "children"),
    Output("cost-tier", "children"),
    Output("cost-efficiency-bar", "children"),
    Output("cost-table", "children"),
    Input("cost-open", "value"),
)
def update_cost(open_filter):
    pricing = get_pricing()

    if pricing.empty:
        msg = html.Div("No pricing data available", style={"color": "#6666aa", "textAlign": "center", "padding": "3rem"})
        return msg, "", "", ""

    if open_filter == "open":
        pricing = pricing[pricing["open_weight"] == True]
    elif open_filter == "closed":
        pricing = pricing[pricing["open_weight"] == False]

    pricing = pricing[pricing["avg_score_pct"].notna()]

    # Scatter
    fig_scatter = px.scatter(
        pricing, x="input_price", y="avg_score_pct",
        text="model_name", color="open_weight",
        color_discrete_map={True: ACCENT_5, False: ACCENT_4},
        size="num_benchmarks", size_max=25,
        labels={"input_price": "Input Price ($/M tokens)", "avg_score_pct": "Avg Score %", "open_weight": ""},
        hover_data={"model_name": True, "organization": True, "input_price": ":.2f", "avg_score_pct": ":.1%"},
    )
    fig_scatter.update_traces(textposition="top center", textfont_size=8)

    # Efficiency frontier
    frontier = pricing.sort_values("input_price")
    best_score = 0
    frontier_points = []
    for _, row in frontier.iterrows():
        if row["avg_score_pct"] >= best_score:
            best_score = row["avg_score_pct"]
            frontier_points.append(row)
    if frontier_points:
        fp = pd.DataFrame(frontier_points)
        fig_scatter.add_trace(go.Scatter(
            x=fp["input_price"], y=fp["avg_score_pct"],
            mode="lines", line=dict(color=ACCENT_2, dash="dash", width=2),
            name="Efficiency Frontier", showlegend=True,
        ))

    chart_layout(fig_scatter,
                 title="Price vs Performance (size = # benchmarks, dashed = efficiency frontier)",
                 height=450, yaxis=dict(tickformat=".0%"), legend=dict(orientation="h", y=-0.12))

    # Cost tiers
    pricing["tier"] = pd.cut(pricing["input_price"], bins=[0, 1, 5, 100], labels=["Budget (<$1)", "Mid ($1-5)", "Premium (>$5)"])
    tier_stats = pricing.groupby("tier", observed=True).agg(
        models=("model_id", "count"),
        avg_score=("avg_score_pct", "mean"),
    ).reset_index()

    tier_colors = [ACCENT_5, ACCENT_3, ACCENT_2]
    fig_tier = go.Figure()
    for i, row in tier_stats.iterrows():
        fig_tier.add_trace(go.Bar(
            x=[row["tier"]], y=[row["avg_score"]],
            name=str(row["tier"]), marker_color=tier_colors[i % 3],
            text=f"{row['avg_score']:.0%}<br>({int(row['models'])} models)",
            textposition="inside", textfont=dict(color="#fff"),
        ))
    chart_layout(fig_tier, title="Performance by Price Tier", height=300, showlegend=False,
                 yaxis=dict(tickformat=".0%"))

    # Score per dollar bar
    top_efficiency = pricing[pricing["score_per_dollar"].notna()].nlargest(15, "score_per_dollar")
    top_efficiency = top_efficiency.sort_values("score_per_dollar", ascending=True)
    fig_eff = px.bar(top_efficiency, x="score_per_dollar", y="model_name", orientation="h",
                     color="open_weight", color_discrete_map={True: ACCENT_5, False: ACCENT_4},
                     text_auto=".1f", labels={"score_per_dollar": "Score per $ (higher = better value)", "model_name": ""})
    chart_layout(fig_eff, title="Best Value — Score per Dollar (Top 15)", height=400, showlegend=False)

    # Table
    table_df = pricing[["model_name", "organization", "avg_score_pct", "input_price", "output_price",
                        "score_per_dollar", "throughput_tps", "open_weight", "num_benchmarks"]].copy()
    table_df["avg_score_pct"] = (table_df["avg_score_pct"] * 100).round(1).astype(str) + "%"
    table_df["input_price"] = table_df["input_price"].apply(lambda x: f"${x:.2f}")
    table_df["output_price"] = table_df["output_price"].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "—")
    table_df["score_per_dollar"] = table_df["score_per_dollar"].apply(lambda x: f"{x:.1f}" if pd.notna(x) else "—")
    table_df["throughput_tps"] = table_df["throughput_tps"].apply(lambda x: f"{x:.0f} tps" if pd.notna(x) else "—")
    table_df["open_weight"] = table_df["open_weight"].map({True: "Open", False: "Proprietary"})
    table_df.columns = ["Model", "Org", "Avg Score", "In $/M", "Out $/M", "Score/$", "Throughput", "License", "Benchmarks"]

    cost_table = dash_table.DataTable(
        data=table_df.to_dict("records"),
        columns=[{"name": c, "id": c} for c in table_df.columns],
        sort_action="native",
        sort_by=[{"column_id": "Score/$", "direction": "desc"}],
        page_size=20,
        style_table={"overflowX": "auto", "borderRadius": "8px"},
        style_header={"backgroundColor": "#1e1e3a", "color": "#e8e8f0", "fontWeight": "600", "border": "1px solid #2a2a4a"},
        style_cell={"backgroundColor": "rgba(15,15,30,0.8)", "color": "#d0d0e8", "border": "1px solid #1e1e3a", "padding": "8px", "fontSize": "0.85rem"},
    )

    return dcc.Graph(figure=fig_scatter), dcc.Graph(figure=fig_tier), dcc.Graph(figure=fig_eff), cost_table
