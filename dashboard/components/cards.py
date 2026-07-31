"""
Reusable card components for the dashboard.
"""

import streamlit as st
from typing import Any, Optional, List


def metric_card(title: str, value: Any, delta: Optional[str] = None, icon: str = ""):
    """Display a metric card with gradient background."""
    delta_html = ""
    if delta:
        delta_color = "green" if delta.startswith("+") or delta.startswith("↑") else "red"
        delta_html = f'<div style="font-size: 0.9em; color: {delta_color}; margin-top: 5px;">{delta}</div>'

    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 12px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
        margin-bottom: 10px;
    ">
        <div style="font-size: 0.9em; opacity: 0.9;">{icon} {title}</div>
        <div style="font-size: 2.2em; font-weight: bold; margin: 5px 0;">{value}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)


def job_card(
    title: str,
    company: str,
    location: Optional[str] = None,
    salary_min: Optional[int] = None,
    salary_max: Optional[int] = None,
    url: Optional[str] = None,
    tags: Optional[List[str]] = None,
    source: Optional[str] = None,
):
    """Display a job listing card."""
    location_text = f"📍 {location}" if location else "📍 Remote"
    
    salary_text = "💰 Salary not specified"
    if salary_min and salary_max:
        salary_text = f"💰 ${salary_min:,.0f} - ${salary_max:,.0f}"
    elif salary_min:
        salary_text = f"💰 From ${salary_min:,.0f}"

    tags_html = ""
    if tags:
        tags_html = " ".join([
            f'<span style="background: #e2e8f0; padding: 2px 8px; border-radius: 4px; font-size: 0.8em; margin-right: 5px;">{tag}</span>'
            for tag in tags[:5]
        ])

    source_badge = ""
    if source:
        source_colors = {
            "linkedin": "#0077b5",
            "indeed": "#2164f3",
            "glassdoor": "#0caa41",
            "remote_ok": "#8b5cf6",
            "hackernews": "#ff6600",
            "rss_feed": "#f59e0b",
        }
        color = source_colors.get(source, "#6b7280")
        source_badge = f'<span style="background: {color}; color: white; padding: 2px 8px; border-radius: 4px; font-size: 0.75em;">{source}</span>'

    st.markdown(f"""
    <div style="
        background: white;
        border: 1px solid #e2e8f0;
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 15px;
        box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
        transition: box-shadow 0.2s;
    ">
        <div style="display: flex; justify-content: space-between; align-items: start;">
            <div>
                <h3 style="margin: 0; color: #1e293b; font-size: 1.2em;">{title}</h3>
                <p style="margin: 5px 0; color: #64748b; font-size: 1em;">🏢 {company}</p>
            </div>
            {source_badge}
        </div>
        <div style="margin: 10px 0; color: #475569;">
            <p style="margin: 3px 0;">{location_text}</p>
            <p style="margin: 3px 0;">{salary_text}</p>
        </div>
        <div style="margin-top: 10px;">
            {tags_html}
        </div>
    </div>
    """, unsafe_allow_html=True)


def application_card(
    job_title: str,
    company: str,
    status: str,
    applied_at: Optional[str] = None,
    notes: Optional[str] = None,
):
    """Display an application tracking card."""
    status_colors = {
        "saved": {"bg": "#f1f5f9", "text": "#475569", "icon": "💾"},
        "applied": {"bg": "#dbeafe", "text": "#1e40af", "icon": "📤"},
        "interview": {"bg": "#fef3c7", "text": "#92400e", "icon": "🎤"},
        "assessment": {"bg": "#ede9fe", "text": "#5b21b6", "icon": "📝"},
        "rejected": {"bg": "#fee2e2", "text": "#991b1b", "icon": "❌"},
        "offer": {"bg": "#d1fae5", "text": "#065f46", "icon": "🎉"},
        "joined": {"bg": "#a7f3d0", "text": "#064e3b", "icon": "🚀"},
    }

    style = status_colors.get(status, {"bg": "#f1f5f9", "text": "#475569", "icon": "📋"})

    applied_text = f"📅 Applied: {applied_at}" if applied_at else ""
    notes_text = f"📝 {notes}" if notes else ""

    st.markdown(f"""
    <div style="
        background: white;
        border-left: 4px solid {style['text']};
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 10px;
        box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
    ">
        <div style="display: flex; justify-content: space-between; align-items: center;">
            <div>
                <h4 style="margin: 0; color: #1e293b;">{job_title}</h4>
                <p style="margin: 3px 0; color: #64748b;">{company}</p>
            </div>
            <span style="
                background: {style['bg']};
                color: {style['text']};
                padding: 4px 12px;
                border-radius: 20px;
                font-size: 0.85em;
                font-weight: 500;
            ">{style['icon']} {status.title()}</span>
        </div>
        {"<p style='margin: 5px 0; color: #64748b; font-size: 0.9em;'>" + applied_text + "</p>" if applied_text else ""}
        {"<p style='margin: 5px 0; color: #64748b; font-size: 0.9em;'>" + notes_text + "</p>" if notes_text else ""}
    </div>
    """, unsafe_allow_html=True)


def skill_badge(name: str, category: str = "", proficiency: Optional[int] = None):
    """Display a skill badge."""
    category_colors = {
        "programming": "#3b82f6",
        "framework": "#8b5cf6",
        "tool": "#10b981",
        "soft_skill": "#f59e0b",
        "certification": "#ef4444",
    }

    color = category_colors.get(category, "#6b7280")
    proficiency_dots = "●" * proficiency if proficiency else ""

    st.markdown(f"""
    <span style="
        display: inline-block;
        background: {color}20;
        color: {color};
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.85em;
        margin: 2px;
        border: 1px solid {color}40;
    ">
        {name} {proficiency_dots}
    </span>
    """, unsafe_allow_html=True)


def section_header(title: str, subtitle: Optional[str] = None):
    """Display a styled section header."""
    subtitle_html = f'<p style="margin: 0; color: #94a3b8; font-size: 0.95em;">{subtitle}</p>' if subtitle else ""
    
    st.markdown(f"""
    <div style="margin-bottom: 20px;">
        <h2 style="margin: 0; color: #1e293b;">{title}</h2>
        {subtitle_html}
    </div>
    """, unsafe_allow_html=True)


def info_card(title: str, content: str, icon: str = "ℹ️"):
    """Display an info card."""
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #f0f9ff 0%, #e0f2fe 100%);
        border: 1px solid #bae6fd;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 15px;
    ">
        <strong>{icon} {title}</strong>
        <p style="margin: 5px 0 0 0; color: #475569;">{content}</p>
    </div>
    """, unsafe_allow_html=True)


def warning_card(title: str, content: str):
    """Display a warning card."""
    st.markdown(f"""
    <div style="
        background: linear-gradient(135deg, #fffbeb 0%, #fef3c7 100%);
        border: 1px solid #fcd34d;
        border-radius: 8px;
        padding: 15px;
        margin-bottom: 15px;
    ">
        <strong>⚠️ {title}</strong>
        <p style="margin: 5px 0 0 0; color: #92400e;">{content}</p>
    </div>
    """, unsafe_allow_html=True)
