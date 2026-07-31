"""
Reusable form components for the dashboard.
"""

import streamlit as st
from typing import List, Optional, Callable


def search_form(
    placeholder: str = "Search...",
    button_text: str = "Search",
    key: str = "search",
    on_submit: Optional[Callable] = None,
) -> str:
    """Display a search form."""
    col1, col2 = st.columns([4, 1])
    
    with col1:
        query = st.text_input(
            placeholder,
            key=f"{key}_input",
            placeholder=placeholder,
            label_visibility="collapsed",
        )
    
    with col2:
        if st.button(button_text, key=f"{key}_button", use_container_width=True):
            if on_submit:
                on_submit(query)
            return query
    
    return query


def filter_form(
    filters: List[dict],
    key: str = "filter",
) -> dict:
    """Display filter form with multiple options.
    
    filters: List of dicts with keys: name, type, options, default
    """
    results = {}
    
    cols = st.columns(min(len(filters), 4))
    
    for i, filter_config in enumerate(filters):
        with cols[i % len(cols)]:
            filter_name = filter_config["name"]
            filter_type = filter_config.get("type", "select")
            options = filter_config.get("options", [])
            default = filter_config.get("default")
            label = filter_config.get("label", filter_name.replace("_", " ").title())
            
            if filter_type == "select":
                results[filter_name] = st.selectbox(
                    label,
                    options=["All"] + options if "All" not in options else options,
                    index=0 if default is None else options.index(default) + 1 if default in options else 0,
                    key=f"{key}_{filter_name}",
                )
            elif filter_type == "multiselect":
                results[filter_name] = st.multiselect(
                    label,
                    options=options,
                    default=default or [],
                    key=f"{key}_{filter_name}",
                )
            elif filter_type == "number":
                results[filter_name] = st.number_input(
                    label,
                    min_value=filter_config.get("min", 0),
                    max_value=filter_config.get("max", 100),
                    value=default or 0,
                    key=f"{key}_{filter_name}",
                )
            elif filter_type == "date":
                results[filter_name] = st.date_input(
                    label,
                    value=default,
                    key=f"{key}_{filter_name}",
                )
            elif filter_type == "checkbox":
                results[filter_name] = st.checkbox(
                    label,
                    value=default or False,
                    key=f"{key}_{filter_name}",
                )
    
    return results


def job_search_form(key: str = "job_search") -> dict:
    """Display a job search form with common filters."""
    st.subheader("🔍 Search Jobs")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        query = st.text_input(
            "Keywords",
            placeholder="e.g., Python Developer",
            key=f"{key}_query",
        )
    
    with col2:
        location = st.text_input(
            "Location",
            placeholder="e.g., Remote, San Francisco",
            key=f"{key}_location",
        )
    
    with col3:
        job_type = st.selectbox(
            "Job Type",
            options=["All", "Full-time", "Part-time", "Contract", "Internship", "Remote"],
            key=f"{key}_type",
        )
    
    col4, col5 = st.columns(2)
    
    with col4:
        salary_min = st.number_input(
            "Min Salary",
            min_value=0,
            max_value=500000,
            value=0,
            step=5000,
            key=f"{key}_salary_min",
        )
    
    with col5:
        is_remote = st.checkbox(
            "Remote Only",
            key=f"{key}_remote",
        )
    
    return {
        "query": query,
        "location": location,
        "job_type": job_type if job_type != "All" else None,
        "salary_min": salary_min if salary_min > 0 else None,
        "is_remote": is_remote,
    }


def application_form(key: str = "application") -> dict:
    """Display an application form."""
    st.subheader("📋 New Application")
    
    col1, col2 = st.columns(2)
    
    with col1:
        status = st.selectbox(
            "Status",
            options=["saved", "applied", "interview", "assessment"],
            key=f"{key}_status",
        )
    
    with col2:
        priority = st.slider(
            "Priority",
            min_value=0,
            max_value=5,
            value=1,
            key=f"{key}_priority",
        )
    
    notes = st.text_area(
        "Notes",
        placeholder="Add any notes about this application...",
        key=f"{key}_notes",
    )
    
    resume_version = st.text_input(
        "Resume Version",
        placeholder="e.g., v2.1 - Backend Focus",
        key=f"{key}_resume",
    )
    
    return {
        "status": status,
        "priority": priority,
        "notes": notes,
        "resume_version": resume_version,
    }


def notification_settings_form(key: str = "notification") -> dict:
    """Display notification settings form."""
    st.subheader("🔔 Notification Settings")
    
    channels = st.multiselect(
        "Enable Notification Channels",
        options=["Telegram", "Email", "Discord", "Slack"],
        default=[],
        key=f"{key}_channels",
    )
    
    settings = {}
    
    if "Telegram" in channels:
        st.markdown("**Telegram Settings**")
        col1, col2 = st.columns(2)
        with col1:
            settings["telegram_token"] = st.text_input(
                "Bot Token",
                type="password",
                key=f"{key}_telegram_token",
            )
        with col2:
            settings["telegram_chat_id"] = st.text_input(
                "Chat ID",
                key=f"{key}_telegram_chat",
            )
    
    if "Email" in channels:
        st.markdown("**Email Settings**")
        col1, col2 = st.columns(2)
        with col1:
            settings["smtp_user"] = st.text_input(
                "SMTP User",
                key=f"{key}_smtp_user",
            )
        with col2:
            settings["smtp_password"] = st.text_input(
                "SMTP Password",
                type="password",
                key=f"{key}_smtp_pass",
            )
    
    if "Discord" in channels:
        st.markdown("**Discord Settings**")
        settings["discord_webhook"] = st.text_input(
            "Webhook URL",
            key=f"{key}_discord_webhook",
        )
    
    if "Slack" in channels:
        st.markdown("**Slack Settings**")
        settings["slack_webhook"] = st.text_input(
            "Webhook URL",
            key=f"{key}_slack_webhook",
        )
    
    return {
        "channels": channels,
        "settings": settings,
    }


def skill_assessment_form(key: str = "skill") -> dict:
    """Display a skill assessment form."""
    st.subheader("🎯 Skill Assessment")
    
    skills = st.text_area(
        "Your Skills (one per line)",
        placeholder="python\njavascript\nreact\ndocker",
        key=f"{key}_skills",
    )
    
    target_role = st.text_input(
        "Target Role",
        placeholder="e.g., Full Stack Developer",
        key=f"{key}_target",
    )
    
    return {
        "skills": [s.strip() for s in skills.split("\n") if s.strip()],
        "target_role": target_role,
    }
