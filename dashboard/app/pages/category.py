import dash
from dash import html, dcc, callback, Input, Output, dash_table
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from data import get_category_leaderboard, get_category_stats, get_categories, get_scores
from theme import *

dash.register_page(__name__, path="/category", name="Category Leaderboard")

layout = html.Div([
    html.H1("Category Leaderboard", style={"marginBottom": "0.5rem", "fontWeight": "700"}),
    html.P("TrueSkill rankings and benchmark breakdown per category",
           style={"color": "#8888aa", "marginBottom": "1.5rem"}),

    html.Div([
        html.Label("Select Category", style={"color": "#a0a0c0", "fontSize": "0.85rem"}),
        dcc.Dropdown(id="cat-select", value="coding", style={"width": "250px"}),
    ], style={"marginBottom": "1.5rem"}),

    html.Div(id="cat-stats-cards", style={"marginBottom": "1.5rem"}),
    html.Div(id="cat-ranking-bar", style={"marginBottom": "1.5rem"}),
    html.Div([
        html.Div(id="cat-open-vs-closed", style={"flex": "1"}),
        html.Div(id="cat-price-scatter", style={"flex": "1"}),
    ], style={"display": "flex", "gap": "1.5rem", "marginBottom": "1.5rem", "flexWrap": "wrap"}),
    html.Div(id="cat-full-table"),
])


@callback(Output("cat-select", "options"), Input("cat-select", "id"))
def load_cats(_):
    cats = get_categories()
    return [{"label": c.replace("_", " ").title(), "value": c} for c in cats]


@callback(
    Output("cat-stats-cards", "children"),
    Output("cat-ranking-bar", "children"),
    Output("cat-open-vs-closed", "children"),
    Output("cat-price-scatter", "children"),
    Output("cat-full-table", "children"),
    Input("cat-select", "value"),
)
def update_category(category):
    if not category:
        return "", "", "", "", ""

    stats = get_category_stats()
    cat_stat = stats[stats["category"] == category]
    leaderboard = get_category_leaderboard(category)
    scores = get_scores()
    cat_scores = scores[scores["category"] == category]

    # Stats cards
    cards = []
    if not cat_stat.empty:
        s = cat_stat.iloc[0]
        cards = html.Div([
            _stat_card("Models", str(int(s["num_models"])), ACCENT_1),
            _stat_card("Benchmarks", str(int(s["num_benchmarks"])), ACCENT_3),
            _stat_card("Avg Score", f"{s['avg_score_pct']:.0%}", ACCENT_4),
            _stat_card("Top Score", f"{s['max_score_pct']:.0%}", ACCENT_5),
        ], style={"display": "flex", "gap": "1rem", "flexWrap": "wrap"})

    # Ranking bar
    top15 = leaderboard.head(15).copy()
    if top15.empty:
        fig_rank = go.Figure()
        chart_layout(fig_rank, title="No ranking data available", height=300)
    else:
        top15 = top15.sort_values("conservative_rating", ascending=True)
        colors = [ACCENT_5 if ow else ACCENT_4 for ow in top15["open_weight"]]
        fig_rank = go.Figure(go.Bar(
            x=top15["conservative_rating"], y=top15["model_name"],
            orientation="h", marker_color=colors,
            text=[f"#{int(r)}" for r in top15["rank"]], textposition="inside",
            textfont=dict(color="#fff", size=11),
            hovertemplate="Model: %{y}<br>Rating: %{x:.1f}<extra></extra>",
        ))
        chart_layout(fig_rank,
                     title=f"TrueSkill Ranking — {category.replace('_', ' ').title()} (Green=Open, Amber=Proprietary)",
                     height=max(300, len(top15) * 35), xaxis_title="Conservative Rating (μ − 3σ)")

    # Open vs Closed
    open_closed = cat_scores.groupby("open_weight")["score_pct"].agg(["mean", "count"]).reset_index()
    open_closed["label"] = open_closed["open_weight"].map({True: "Open Weight", False: "Proprietary"})
    fig_oc = px.bar(open_closed, x="label", y="mean", color="label",
                    color_discrete_map={"Open Weight": ACCENT_5, "Proprietary": ACCENT_4},
                    text_auto=".0%", labels={"mean": "Avg Score %", "label": ""})
    chart_layout(fig_oc, title="Open vs Proprietary", height=300, showlegend=False,
                 yaxis=dict(tickformat=".0%"))

    # Price scatter
    if not leaderboard.empty and "min_input_price" in leaderboard.columns:
        scatter_df = leaderboard[leaderboard["min_input_price"].notna()].copy()
        if not scatter_df.empty:
            fig_scatter = px.scatter(
                scatter_df, x="min_input_price", y="conservative_rating",
                text="model_name", color="open_weight",
                color_discrete_map={True: ACCENT_5, False: ACCENT_4},
                labels={"min_input_price": "Min Input Price ($/M)", "conservative_rating": "TrueSkill Rating"},
                size="benchmarks_evaluated", size_max=20,
            )
            fig_scatter.update_traces(textposition="top center", textfont_size=9)
            chart_layout(fig_scatter, title="Price vs Performance", height=300, showlegend=False)
        else:
            fig_scatter = _empty_fig("No price data available")
    else:
        fig_scatter = _empty_fig("No price data available")

    # Full table
    if not leaderboard.empty:
        table_df = leaderboard[["rank", "model_name", "organization", "conservative_rating", "open_weight", "min_input_price", "benchmarks_evaluated"]].copy()
        table_df["open_weight"] = table_df["open_weight"].map({True: "Open", False: "Proprietary"})
        table_df["conservative_rating"] = table_df["conservative_rating"].round(2)
        table_df["min_input_price"] = table_df["min_input_price"].apply(lambda x: f"${x:.2f}" if pd.notna(x) else "—")
        table_df.columns = ["#", "Model", "Organization", "Rating", "License", "Price $/M", "Benchmarks"]

        full_table = dash_table.DataTable(
            data=table_df.to_dict("records"),
            columns=[{"name": c, "id": c} for c in table_df.columns],
            sort_action="native",
            sort_by=[{"column_id": "Rating", "direction": "desc"}],
            page_size=20,
            style_table={"overflowX": "auto", "borderRadius": "8px"},
            style_header={"backgroundColor": "#1e1e3a", "color": "#e8e8f0", "fontWeight": "600", "border": "1px solid #2a2a4a"},
            style_cell={"backgroundColor": "rgba(15,15,30,0.8)", "color": "#d0d0e8", "border": "1px solid #1e1e3a", "padding": "8px", "fontSize": "0.85rem"},
            style_data_conditional=[
                {"if": {"row_index": 0}, "backgroundColor": "rgba(99,102,241,0.15)", "fontWeight": "bold"},
            ],
        )
    else:
        full_table = html.Div("No ranking data for this category", style={"color": "#6666aa"})

    return cards, dcc.Graph(figure=fig_rank), dcc.Graph(figure=fig_oc), dcc.Graph(figure=fig_scatter), full_table


def _stat_card(title, value, color):
    return html.Div([
        html.Div(title, style={"fontSize": "0.8rem", "color": "#8888aa", "textTransform": "uppercase", "letterSpacing": "0.5px"}),
        html.Div(value, style={"fontSize": "1.6rem", "fontWeight": "700", "color": color, "marginTop": "0.3rem"}),
    ], style={
        "background": CARD_BG, "borderRadius": "10px", "padding": "1rem 1.5rem",
        "border": f"1px solid {CARD_BORDER}", "minWidth": "130px", "textAlign": "center",
    })


def _empty_fig(msg):
    fig = go.Figure()
    fig.add_annotation(text=msg, x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False, font_color="#6666aa")
    chart_layout(fig, height=300)
    return fig
