CHART_TEMPLATE = "plotly_dark"
CHART_BG = "rgba(0,0,0,0)"
PAPER_BG = "rgba(0,0,0,0)"
ACCENT_1 = "#6366f1"  # indigo
ACCENT_2 = "#a855f7"  # purple
ACCENT_3 = "#06b6d4"  # cyan
ACCENT_4 = "#f59e0b"  # amber
ACCENT_5 = "#10b981"  # emerald
ACCENT_6 = "#f43f5e"  # rose
CARD_BG = "rgba(30, 30, 58, 0.6)"
CARD_BORDER = "rgba(99, 102, 241, 0.2)"
COLOR_SCALE = ["#6366f1", "#a855f7", "#06b6d4", "#10b981", "#f59e0b", "#f43f5e", "#3b82f6", "#ec4899"]


def chart_layout(fig, **kwargs):
    fig.update_layout(
        template=CHART_TEMPLATE,
        paper_bgcolor=PAPER_BG,
        plot_bgcolor=CHART_BG,
        font=dict(color="#c8c8e0"),
        margin=dict(l=10, r=10, t=40, b=10),
        **kwargs,
    )
    return fig
