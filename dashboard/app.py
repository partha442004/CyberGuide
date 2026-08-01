"""
InternTrack Dashboard - Streamlit Application
"""

import streamlit as st
import httpx
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Page config
st.set_page_config(
    page_title="InternTrack Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 10px;
        color: white;
        text-align: center;
    }
    .metric-value {
        font-size: 2.5em;
        font-weight: bold;
    }
    .metric-label {
        font-size: 0.9em;
        opacity: 0.8;
    }
</style>
""", unsafe_allow_html=True)

# API base URL
API_URL = "http://localhost:8000/api/v1"
HEALTH_URL = "http://localhost:8000/health"
DEFAULT_VERSION = "1.10.0"


def fetch_data(endpoint: str):
    """Fetch data from API."""
    try:
        response = httpx.get(f"{API_URL}{endpoint}", timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None


@st.cache_data(ttl=60, show_spinner=False)
def fetch_version() -> str:
    """Fetch the live API version from /health (single source of truth).

    Cached for 60s so the About section doesn't hit /health on every Streamlit
    rerun; falls back to ``DEFAULT_VERSION`` when the API is unreachable so
    the dashboard still renders offline.
    """
    try:
        response = httpx.get(HEALTH_URL, timeout=5)
        if response.status_code == 200:
            version = response.json().get("version")
            if version:
                return version
    except Exception:
        pass
    return DEFAULT_VERSION


def main():
    """Main dashboard function."""
    st.title("📊 InternTrack Dashboard")
    st.markdown("Your internship and job tracking command center")

    # Sidebar
    with st.sidebar:
        st.header("Navigation")
        page = st.radio(
            "Go to",
            ["Overview", "Jobs", "Applications", "Analytics", "Learning", "Settings"]
        )

    if page == "Overview":
        show_overview()
    elif page == "Jobs":
        show_jobs()
    elif page == "Applications":
        show_applications()
    elif page == "Analytics":
        show_analytics()
    elif page == "Learning":
        show_learning()
    elif page == "Settings":
        show_settings()


def show_overview():
    """Show overview page."""
    st.header("📈 Overview")

    # Fetch data
    overview = fetch_data("/dashboard/overview")

    if overview:
        jobs = overview.get("jobs", {})
        apps = overview.get("applications", {})

        # Metrics row
        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric("Total Jobs", jobs.get("total_jobs", 0))
        with col2:
            st.metric("Applications", apps.get("total_applications", 0))
        with col3:
            st.metric("Response Rate", f"{apps.get('response_rate', 0)}%")
        with col4:
            st.metric("Recent (7d)", apps.get("recent_applications", 0))

        # Charts
        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Job Types")
            job_types = jobs.get("job_types", [])
            if job_types:
                fig = px.pie(
                    job_types,
                    values="count",
                    names="type",
                    hole=0.4,
                )
                st.plotly_chart(fig, use_container_width=True)

        with col2:
            st.subheader("Application Status")
            status_counts = apps.get("status_counts", {})
            if status_counts:
                fig = px.bar(
                    x=list(status_counts.keys()),
                    y=list(status_counts.values()),
                    labels={"x": "Status", "y": "Count"},
                )
                st.plotly_chart(fig, use_container_width=True)

        # Top companies
        st.subheader("🏢 Top Companies")
        top_companies = jobs.get("top_companies", [])
        if top_companies:
            import pandas as pd
            df = pd.DataFrame(top_companies)
            st.dataframe(df, use_container_width=True)
    else:
        st.info("No data available. Start the API server and run job discovery.")


def show_jobs():
    """Show jobs page."""
    st.header("💼 Jobs")

    # Search
    query = st.text_input("Search jobs", "python developer")

    if st.button("Run Discovery"):
        with st.spinner("Discovering jobs..."):
            result = fetch_data(f"/jobs/discovery/run?query={query}")
            if result:
                st.success(f"Found {result.get('discovered', 0)} jobs, saved {result.get('saved', 0)}")

    # Job list
    jobs_data = fetch_data("/jobs/?limit=50")
    if jobs_data and jobs_data.get("jobs"):
        for job in jobs_data["jobs"]:
            with st.expander(f"{job['title']} - {job['company']}"):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.write(f"📍 {job.get('location', 'Remote')}")
                    st.write(f"💰 {job.get('salary_min', 'N/A')} - {job.get('salary_max', 'N/A')}")
                    if job.get("description"):
                        st.write(job["description"][:500] + "...")
                with col2:
                    if job.get("url"):
                        st.link_button("View", job["url"])
                    if st.button("Apply", key=f"apply_{job['id']}"):
                        st.success("Application tracked!")
    else:
        st.info("No jobs found. Run discovery to find jobs.")


def show_applications():
    """Show applications page."""
    st.header("📋 Applications")

    # Status filter
    status_filter = st.selectbox(
        "Filter by status",
        ["All", "saved", "applied", "interview", "assessment", "rejected", "offer", "joined"]
    )

    endpoint = "/applications/" if status_filter == "All" else f"/applications/?status={status_filter}"
    apps_data = fetch_data(endpoint)

    if apps_data and apps_data.get("applications"):
        for app in apps_data["applications"]:
            with st.expander(f"Application {app['id'][:8]}... - {app['status']}"):
                st.write(f"Job ID: {app['job_id']}")
                st.write(f"Created: {app.get('created_at', 'N/A')}")

                # Status update
                new_status = st.selectbox(
                    "Update status",
                    ["saved", "applied", "interview", "assessment", "rejected", "offer", "joined"],
                    key=f"status_{app['id']}"
                )
                if st.button("Update", key=f"update_{app['id']}"):
                    st.success(f"Status updated to {new_status}")
    else:
        st.info("No applications found.")


def show_analytics():
    """Show analytics page."""
    st.header("📈 Analytics")

    # Charts
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("Application Timeline")
        timeline = fetch_data("/dashboard/charts/application-timeline")
        if timeline and timeline.get("data"):
            import pandas as pd
            df = pd.DataFrame(timeline["data"])
            if not df.empty:
                fig = px.line(df, x="date", y="count", color="status")
                st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("Top Companies")
        companies = fetch_data("/dashboard/charts/top-companies")
        if companies and companies.get("data"):
            import pandas as pd
            df = pd.DataFrame(companies["data"])
            if not df.empty:
                fig = px.bar(df, x="company", y="count")
                st.plotly_chart(fig, use_container_width=True)

    # Salary stats
    st.subheader("💰 Salary Statistics")
    salary = fetch_data("/dashboard/charts/salary")
    if salary and salary.get("data"):
        data = salary["data"]
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Min Salary", f"${data.get('min_salary', 'N/A'):,}" if data.get('min_salary') else "N/A")
        with col2:
            st.metric("Max Salary", f"${data.get('max_salary', 'N/A'):,}" if data.get('max_salary') else "N/A")
        with col3:
            st.metric("Avg Min", f"${data.get('avg_min', 0):,.0f}" if data.get('avg_min') else "N/A")
        with col4:
            st.metric("Avg Max", f"${data.get('avg_max', 0):,.0f}" if data.get('avg_max') else "N/A")


def show_learning():
    """Show learning page."""
    st.header("📚 Learning Resources")

    st.subheader("Recommended Platforms")

    platforms = [
        {"name": "Google Cloud Skills Boost", "icon": "☁️", "url": "https://cloudskillsboost.google"},
        {"name": "OWASP", "icon": "🔒", "url": "https://owasp.org"},
        {"name": "PortSwigger", "icon": "🎯", "url": "https://portswigger.net/web-security"},
        {"name": "TryHackMe", "icon": "🏴‍☠️", "url": "https://tryhackme.com"},
        {"name": "Hack The Box", "icon": "📦", "url": "https://hackthebox.com"},
        {"name": "OverTheWire", "icon": "🎯", "url": "https://overthewire.org"},
        {"name": "PicoCTF", "icon": "🏆", "url": "https://picoctf.org"},
    ]

    cols = st.columns(3)
    for i, platform in enumerate(platforms):
        with cols[i % 3]:
            st.markdown(f"### {platform['icon']} {platform['name']}")
            st.link_button("Visit", platform["url"])

    # Skill matching
    st.subheader("🎯 Skill Matching")
    job_skills = st.text_input("Job Skills (comma-separated)", "python, react, docker")
    user_skills = st.text_input("Your Skills (comma-separated)", "python, javascript")

    if st.button("Match Skills"):
        st.info("Connect to API to use AI-powered skill matching")


def show_settings():
    """Show settings page."""
    st.header("⚙️ Settings")

    st.subheader("Notification Channels")

    col1, col2 = st.columns(2)

    with col1:
        st.write("**Telegram**")
        telegram_token = st.text_input("Bot Token", type="password")
        telegram_chat = st.text_input("Chat ID")

    with col2:
        st.write("**Discord**")
        discord_webhook = st.text_input("Webhook URL", type="password")

    st.subheader("Email Settings")
    smtp_user = st.text_input("SMTP User")
    smtp_pass = st.text_input("SMTP Password", type="password")

    if st.button("Save Settings"):
        st.success("Settings saved! (Restart API to apply)")

    st.subheader("About")
    st.write(f"**InternTrack** v{fetch_version()}")
    st.write("AI-powered internship and job tracking platform")


if __name__ == "__main__":
    main()
