import dash
from dash import html, dcc, callback, Input, Output, dash_table
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data import get_scores, get_model_summary, get_updates, get_org_summary
from theme import *

dash.register_page(__name__, path="/trends", name="Market Trends")

layout = html.Div([
    html.H1("Market Trends", style={"marginBottom": "0.5rem", "fontWeight": "700"}),
    html.P("LLM ecosystem evolution — performance over time, release velocity, and open vs proprietary gap",
           style={"color": "#8888aa", "marginBottom": "1.5rem"}),

    html.Div(id="trends-evolution", style={"marginBottom": "1.5rem"}),
    html.Div([
        html.Div(id="trends-velocity", style={"flex": "1"}),
        html.Div(id="trends-open-gap", style={"flex": "1"}),
    ], style={"display": "flex", "gap": "1.5rem", "marginBottom": "1.5rem", "flexWrap": "wrap"}),
    html.Div(id="trends-new-models"),
])


@callback(
    Output("trends-evolution", "children"),
    Output("trends-velocity", "children"),
    Output("trends-open-gap", "children"),
    Output("trends-new-models", "children"),
    Input("trends-evolution", "id"),
)
def update_trends(_):
    summary = get_model_summary()
    scores = get_scores()

    # Performance evolution by quarter
    scores_with_date = scores.merge(
        summary[["model_id", "release_date"]], on="model_id", how="left", suffixes=("", "_summary")
    )
    scores_with_date = scores_with_date[scores_with_date["release_date"].notna()]
    scores_with_date["quarter"] = pd.to_datetime(scores_with_date["release_date"]).dt.to_period("Q").astype(str)

    quarterly = scores_with_date.groupby(["quarter", "open_weight"])["score_pct"].mean().reset_index()
    quarterly["type"] = quarterly["open_weight"].map({True: "Open Weight", False: "Proprietary"})

    quarterly_all = scores_with_date.groupby("quarter")["score_pct"].mean().reset_index()
    quarterly_all["type"] = "All Models"

    combined = pd.concat([quarterly_all, quarterly[["quarter", "score_pct", "type"]]])

    fig_evo = px.line(combined, x="quarter", y="score_pct", color="type",
                      color_discrete_map={"All Models": "#fff", "Open Weight": ACCENT_5, "Proprietary": ACCENT_4},
                      labels={"score_pct": "Avg Score %", "quarter": "Quarter", "type": ""},
                      markers=True)
    chart_layout(fig_evo, title="Performance Evolution by Release Quarter", height=350,
                 yaxis=dict(tickformat=".0%"), legend=dict(orientation="h", y=-0.15))

    # Release velocity
    release_counts = summary[summary["release_date"].notna()].copy()
    release_counts["quarter"] = pd.to_datetime(release_counts["release_date"]).dt.to_period("Q").astype(str)
    velocity = release_counts.groupby("quarter").size().reset_index(name="count")
    velocity = velocity.sort_values("quarter")

    fig_vel = px.bar(velocity, x="quarter", y="count", text_auto=True,
                     labels={"count": "Models Released", "quarter": ""},
                     color_discrete_sequence=[ACCENT_3])
    chart_layout(fig_vel, title="Release Velocity (Models per Quarter)", height=300)

    # Open vs Proprietary gap
    gap_data = scores.groupby(["category", "open_weight"])["score_pct"].mean().reset_index()
    gap_data["type"] = gap_data["open_weight"].map({True: "Open", False: "Proprietary"})
    top_cats = scores.groupby("category")["model_id"].nunique().nlargest(8).index.tolist()
    gap_data = gap_data[gap_data["category"].isin(top_cats)]

    fig_gap = px.bar(gap_data, x="category", y="score_pct", color="type", barmode="group",
                     color_discrete_map={"Open": ACCENT_5, "Proprietary": ACCENT_4},
                     labels={"score_pct": "Avg Score %", "category": "", "type": ""},
                     text_auto=".0%")
    chart_layout(fig_gap, title="Open vs Proprietary Gap by Category", height=300,
                 yaxis=dict(tickformat=".0%"), legend=dict(orientation="h", y=-0.2))

    # New models table
    updates = get_updates()
    if not updates.empty:
        table_df = updates[["name", "organization_name", "release_date", "open_weight", "model_type", "added_at"]].copy()
        table_df["open_weight"] = table_df["open_weight"].map({True: "Open", False: "Proprietary"})
        table_df["added_at"] = pd.to_datetime(table_df["added_at"]).dt.strftime("%Y-%m-%d")
        table_df.columns = ["Model", "Organization", "Released", "License", "Type", "Added"]

        new_table = html.Div([
            html.H3("Recently Added Models (Last 30 Days)", style={"marginBottom": "0.5rem", "color": "#e8e8f0"}),
            dash_table.DataTable(
                data=table_df.to_dict("records"),
                columns=[{"name": c, "id": c} for c in table_df.columns],
                sort_action="native",
                sort_by=[{"column_id": "Added", "direction": "desc"}],
                page_size=15,
                style_table={"overflowX": "auto", "borderRadius": "8px"},
                style_header={"backgroundColor": "#1e1e3a", "color": "#e8e8f0", "fontWeight": "600", "border": "1px solid #2a2a4a"},
                style_cell={"backgroundColor": "rgba(15,15,30,0.8)", "color": "#d0d0e8", "border": "1px solid #1e1e3a", "padding": "8px", "fontSize": "0.85rem"},
            ),
        ])
    else:
        new_table = ""

    return dcc.Graph(figure=fig_evo), dcc.Graph(figure=fig_vel), dcc.Graph(figure=fig_gap), new_table
