"""
Reusable chart components for the dashboard.
"""

from typing import Any

import plotly.express as px
import plotly.graph_objects as go


def create_metric_card(
    title: str,
    value: Any,
    delta: str | None = None,
    color: str = "#667eea",
):
    """Create a styled metric card."""
    return {
        "title": title,
        "value": value,
        "delta": delta,
        "color": color,
    }


def create_job_type_pie_chart(data: list[dict[str, Any]]) -> go.Figure:
    """Create a pie chart for job type distribution."""
    if not data:
        return go.Figure()

    labels = [item.get("type", "Unknown") for item in data]
    values = [item.get("count", 0) for item in data]

    fig = go.Figure(
        data=[
            go.Pie(
                labels=labels,
                values=values,
                hole=0.4,
                marker_colors=["#667eea", "#764ba2", "#f093fb", "#f5576c", "#4facfe"],
                textinfo="label+percent",
                textfont_size=12,
            ),
        ],
    )

    fig.update_layout(
        showlegend=True,
        margin={"t": 20, "b": 20, "l": 20, "r": 20},
        height=300,
    )

    return fig


def create_application_status_bar(data: dict[str, int]) -> go.Figure:
    """Create a bar chart for application status."""
    if not data:
        return go.Figure()

    status_colors = {
        "saved": "#94a3b8",
        "applied": "#3b82f6",
        "interview": "#f59e0b",
        "assessment": "#8b5cf6",
        "rejected": "#ef4444",
        "offer": "#10b981",
        "joined": "#059669",
    }

    statuses = list(data.keys())
    counts = list(data.values())
    colors = [status_colors.get(s, "#6b7280") for s in statuses]

    fig = go.Figure(
        data=[
            go.Bar(
                x=statuses,
                y=counts,
                marker_color=colors,
                text=counts,
                textposition="auto",
            ),
        ],
    )

    fig.update_layout(
        xaxis_title="Status",
        yaxis_title="Count",
        margin={"t": 20, "b": 20, "l": 20, "r": 20},
        height=300,
    )

    return fig


def create_application_timeline(data: list[dict[str, Any]]) -> go.Figure:
    """Create a line chart for application timeline."""
    if not data:
        return go.Figure()

    import pandas as pd

    df = pd.DataFrame(data)

    if df.empty:
        return go.Figure()

    fig = px.line(
        df,
        x="date",
        y="count",
        color="status",
        markers=True,
        color_discrete_sequence=[
            "#667eea",
            "#764ba2",
            "#f093fb",
            "#f5576c",
            "#4facfe",
            "#10b981",
            "#f59e0b",
        ],
    )

    fig.update_layout(
        xaxis_title="Date",
        yaxis_title="Applications",
        margin={"t": 20, "b": 20, "l": 20, "r": 20},
        height=350,
        legend={"orientation": "h", "yanchor": "bottom", "y": -0.2},
    )

    return fig


def create_top_companies_bar(data: list[dict[str, Any]]) -> go.Figure:
    """Create a horizontal bar chart for top companies."""
    if not data:
        return go.Figure()

    companies = [item.get("company", "Unknown") for item in data]
    counts = [item.get("jobs", 0) for item in data]

    fig = go.Figure(
        data=[
            go.Bar(
                y=companies,
                x=counts,
                orientation="h",
                marker_color="#667eea",
                text=counts,
                textposition="auto",
            ),
        ],
    )

    fig.update_layout(
        xaxis_title="Number of Jobs",
        yaxis={"autorange": "reversed"},
        margin={"t": 20, "b": 20, "l": 20, "r": 20},
        height=300,
    )

    return fig


def create_salary_distribution(data: dict[str, Any]) -> go.Figure:
    """Create a visual representation of salary statistics."""
    fig = go.Figure()

    min_salary = data.get("min_salary", 0)
    max_salary = data.get("max_salary", 0)
    avg_min = data.get("avg_min", 0)
    avg_max = data.get("avg_max", 0)

    if min_salary and max_salary:
        fig.add_trace(
            go.Bar(
                x=["Salary Range"],
                y=[max_salary],
                name="Max",
                marker_color="#e2e8f0",
            ),
        )

        fig.add_trace(
            go.Bar(
                x=["Salary Range"],
                y=[avg_max - avg_min if avg_max and avg_min else 0],
                name="Average Range",
                marker_color="#667eea",
                base=avg_min,
            ),
        )

        fig.add_trace(
            go.Bar(
                x=["Salary Range"],
                y=[avg_min],
                name="Min",
                marker_color="#e2e8f0",
            ),
        )

    fig.update_layout(
        barmode="stack",
        showlegend=True,
        margin={"t": 20, "b": 20, "l": 20, "r": 20},
        height=200,
        yaxis_title="Salary (USD)",
    )

    return fig


def create_skill_demand_chart(data: list[dict[str, Any]]) -> go.Figure:
    """Create a bar chart for skill demand."""
    if not data:
        return go.Figure()

    skills = [item.get("skill", "Unknown") for item in data[:10]]
    demand = [item.get("demand", 0) for item in data[:10]]

    fig = go.Figure(
        data=[
            go.Bar(
                x=skills,
                y=demand,
                marker_color="#764ba2",
                text=demand,
                textposition="auto",
            ),
        ],
    )

    fig.update_layout(
        xaxis_title="Skill",
        yaxis_title="Demand",
        margin={"t": 20, "b": 20, "l": 20, "r": 20},
        height=300,
    )

    return fig
