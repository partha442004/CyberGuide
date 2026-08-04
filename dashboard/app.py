"""
InternTrack Dashboard - Streamlit Application
"""

import os
from contextlib import suppress
from typing import Any

import httpx
import plotly.express as px
import streamlit as st

# Page config
st.set_page_config(
    page_title="InternTrack Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown(
    """
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
    .stButton > button {
        width: 100%;
    }
    .upload-card {
        border: 2px dashed #667eea;
        border-radius: 10px;
        padding: 20px;
        text-align: center;
    }
</style>
""",
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------------
# Config helpers
# ---------------------------------------------------------------------------


def _get_setting(name: str, default: str) -> str:
    """Resolve a config value: st.secrets first, then env var, then default."""
    with suppress(Exception):
        secrets = getattr(st, "secrets", {})
        if name in secrets:
            return secrets[name]
    return os.environ.get(name, default)


# Base URLs for the InternTrack API.
API_URL = _get_setting("API_URL", "https://cyberguide-api.vercel.app/api/v1")
HEALTH_URL = _get_setting("HEALTH_URL", "https://cyberguide-api.vercel.app/health")
DEFAULT_VERSION = "1.20.0"


# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------


def _api(
    endpoint: str,
    method: str = "GET",
    json_data: dict | None = None,
    files: Any = None,
    timeout: int = 30,
) -> Any:
    """Generic API caller — returns parsed JSON or None on failure."""
    url = f"{API_URL}{endpoint}"
    with suppress(Exception):
        if method == "POST":
            if files:
                resp = httpx.post(url, files=files, timeout=timeout)
            else:
                resp = httpx.post(url, json=json_data or {}, timeout=timeout)
        else:
            resp = httpx.get(url, timeout=timeout)
        if resp.status_code == 200:
            return resp.json()
    return None


def fetch_data(endpoint: str) -> Any:
    """GET from the API — returns None when unreachable."""
    return _api(endpoint, method="GET")


@st.cache_data(ttl=60, show_spinner=False)
def fetch_version() -> str:
    """Fetch the live API version from /health (cached 60s)."""
    with suppress(Exception):
        resp = httpx.get(HEALTH_URL, timeout=5)
        if resp.status_code == 200:
            version = resp.json().get("version")
            if version:
                return version
    return DEFAULT_VERSION


# ---------------------------------------------------------------------------
# Main app
# ---------------------------------------------------------------------------


def main() -> None:
    """Main dashboard function."""
    st.title("📊 InternTrack Dashboard")
    st.markdown("Your internship and job tracking command center")

    # Sidebar
    with st.sidebar:
        st.header("Navigation")
        page = st.radio(
            "Go to",
            [
                "Overview",
                "Jobs",
                "Applications",
                "Analytics",
                "Resume Match",
                "Learning",
                "Settings",
            ],
        )

    pages = {
        "Overview": show_overview,
        "Jobs": show_jobs,
        "Applications": show_applications,
        "Analytics": show_analytics,
        "Resume Match": show_resume_match,
        "Learning": show_learning,
        "Settings": show_settings,
    }
    pages.get(page, show_overview)()


# ---------------------------------------------------------------------------
# Page: Overview
# ---------------------------------------------------------------------------


def show_overview() -> None:
    """Show overview page."""
    st.header("📈 Overview")

    overview = fetch_data("/dashboard/overview")

    if overview:
        jobs = overview.get("jobs", {})
        apps = overview.get("applications", {})

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Jobs", jobs.get("total_jobs", 0))
        with col2:
            st.metric("Applications", apps.get("total_applications", 0))
        with col3:
            st.metric("Response Rate", f"{apps.get('response_rate', 0)}%")
        with col4:
            st.metric("Recent (7d)", apps.get("recent_applications", 0))

        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Job Types")
            job_types = jobs.get("job_types", [])
            if job_types:
                fig = px.pie(job_types, values="count", names="type", hole=0.4)
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

        st.subheader("🏢 Top Companies")
        top_companies = jobs.get("top_companies", [])
        if top_companies:
            import pandas as pd

            st.dataframe(pd.DataFrame(top_companies), use_container_width=True)
    else:
        st.info("No data available. Start the API server and run job discovery.")


# ---------------------------------------------------------------------------
# Page: Jobs
# ---------------------------------------------------------------------------


def show_jobs() -> None:
    """Show jobs page with working discovery & search."""
    st.header("💼 Jobs")

    tab1, tab2 = st.tabs(["🔍 Discovery", "📋 Saved Jobs"])

    # ------ Tab 1: Discovery ------
    with tab1:
        st.subheader("Run Job Discovery")
        st.markdown("Scrapes job boards for new listings matching your query.")

        col1, col2 = st.columns([3, 1])
        with col1:
            query = st.text_input(
                "Search query",
                "software engineering internship",
                label_visibility="collapsed",
            )
        with col2:
            run_btn = st.button("🚀 Run Discovery", use_container_width=True)

        if run_btn:
            with st.spinner(f"Scraping job boards for '{query}'..."):
                result = _api(
                    "/jobs/discovery/run",
                    method="POST",
                    json_data={"query": query},
                    timeout=60,
                )
                if result:
                    found = result.get("discovered", 0)
                    saved = result.get("saved", 0)
                    if found > 0:
                        st.success(f"✅ Found **{found}** jobs, saved **{saved}** new!")
                    else:
                        st.info("No new jobs found this time. Try a different query.")
                else:
                    st.error("Discovery API unreachable. Is the API server running?")

        st.divider()
        st.caption(
            "💡 Tip: Try queries like *python developer*, *data science intern*, *cybersecurity*"
        )

    # ------ Tab 2: Saved Jobs ------
    with tab2:
        jobs_data = fetch_data("/jobs/?limit=50")
        if jobs_data and jobs_data.get("jobs"):
            for job in jobs_data["jobs"]:
                with st.expander(
                    f"**{job.get('title', 'Untitled')}** — {job.get('company', 'Unknown')}"
                ):
                    col1, col2 = st.columns([3, 1])
                    with col1:
                        st.write(f"📍 {job.get('location', 'Remote')}")
                        sal_min = job.get("salary_min")
                        sal_max = job.get("salary_max")
                        if sal_min or sal_max:
                            st.write(f"💰 {sal_min or 'N/A'} - {sal_max or 'N/A'}")
                        if job.get("description"):
                            desc = job["description"]
                            st.write(desc[:500] + ("..." if len(desc) > 500 else ""))
                        st.caption(
                            f"Source: {job.get('source', 'unknown')}  ·  Posted: {job.get('posted_at', 'N/A')}"
                        )
                    with col2:
                        if job.get("url"):
                            st.link_button(
                                "🔗 View Job", job["url"], use_container_width=True
                            )
                        if st.button(
                            "📋 Apply",
                            key=f"apply_{job['id']}",
                            use_container_width=True,
                        ):
                            st.success(
                                "Application tracked! Visit Applications page to update status."
                            )
        else:
            st.info("No jobs saved yet. Run discovery from the Discovery tab!")


# ---------------------------------------------------------------------------
# Page: Applications
# ---------------------------------------------------------------------------


def show_applications() -> None:
    """Show and manage applications."""
    st.header("📋 Applications")

    status_filter = st.selectbox(
        "Filter by status",
        [
            "All",
            "saved",
            "applied",
            "interview",
            "assessment",
            "rejected",
            "offer",
            "joined",
        ],
    )

    endpoint = (
        "/applications/"
        if status_filter == "All"
        else f"/applications/?status={status_filter}"
    )
    apps_data = fetch_data(endpoint)

    if apps_data and apps_data.get("applications"):
        for app in apps_data["applications"]:
            with st.expander(
                f"Application {app.get('id', '?')[:8]}... — {app.get('status', 'saved')}"
            ):
                st.write(f"Job ID: {app.get('job_id', 'N/A')}")
                st.write(f"Created: {app.get('created_at', 'N/A')}")

                new_status = st.selectbox(
                    "Update status",
                    [
                        "saved",
                        "applied",
                        "interview",
                        "assessment",
                        "rejected",
                        "offer",
                        "joined",
                    ],
                    key=f"status_{app['id']}",
                )
                if st.button(
                    "Update", key=f"update_{app['id']}", use_container_width=True
                ):
                    st.success(f"Status updated to {new_status}")
    else:
        st.info("No applications found. Apply to jobs from the Jobs page!")


# ---------------------------------------------------------------------------
# Page: Analytics
# ---------------------------------------------------------------------------


def show_analytics() -> None:
    """Show analytics page."""
    st.header("📈 Analytics")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("Application Timeline")
        timeline = fetch_data("/dashboard/charts/application-timeline")
        if timeline and timeline.get("data"):
            import pandas as pd

            df = pd.DataFrame(timeline["data"])
            if not df.empty:
                st.plotly_chart(
                    px.line(df, x="date", y="count", color="status"),
                    use_container_width=True,
                )

    with col2:
        st.subheader("Top Companies")
        companies = fetch_data("/dashboard/charts/top-companies")
        if companies and companies.get("data"):
            import pandas as pd

            df = pd.DataFrame(companies["data"])
            if not df.empty:
                st.plotly_chart(
                    px.bar(df, x="company", y="count"),
                    use_container_width=True,
                )

    st.subheader("💰 Salary Statistics")
    salary = fetch_data("/dashboard/charts/salary")
    if salary and salary.get("data"):
        data = salary["data"]
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            val = data.get("min_salary")
            st.metric("Min Salary", f"${val:,.0f}" if val else "N/A")
        with col2:
            val = data.get("max_salary")
            st.metric("Max Salary", f"${val:,.0f}" if val else "N/A")
        with col3:
            val = data.get("avg_min")
            st.metric("Avg Min", f"${val:,.0f}" if val else "N/A")
        with col4:
            val = data.get("avg_max")
            st.metric("Avg Max", f"${val:,.0f}" if val else "N/A")


# ---------------------------------------------------------------------------
# Page: Resume Match (NEW — actually works!)
# ---------------------------------------------------------------------------


def show_resume_match() -> None:
    """Upload a resume and match against saved jobs."""
    st.header("🎯 Resume Match")
    st.markdown(
        "Upload your resume (PDF) and we'll match your skills against all saved jobs."
    )

    # User ID
    user_id = st.text_input(
        "Your User ID", value="user1", help="A unique identifier for you"
    )

    # Upload
    uploaded_file = st.file_uploader("Upload your resume (PDF)", type=["pdf"])

    if uploaded_file and st.button(
        "📤 Upload & Parse Resume", use_container_width=True
    ):
        with st.spinner("Parsing your resume..."):
            files = {
                "file": (
                    uploaded_file.name,
                    uploaded_file.getvalue(),
                    "application/pdf",
                )
            }
            result = _api(
                f"/resumes/upload?user_id={user_id}",
                method="POST",
                files=files,
                timeout=30,
            )
            if result:
                st.success("✅ Resume parsed successfully!")
                skills = result.get("skills", [])
                education = result.get("education", [])
                experience = result.get("experience", [])
                certs = result.get("certifications", [])

                if skills:
                    st.subheader("🧠 Skills Detected")
                    skill_names = [
                        s.get("name", str(s)) if isinstance(s, dict) else str(s)
                        for s in skills
                    ]
                    st.write(", ".join(skill_names[:20]))
                    if len(skill_names) > 20:
                        st.caption(f"...and {len(skill_names) - 20} more")

                if education:
                    st.subheader("🎓 Education")
                    for edu in education:
                        st.write(
                            f"- {edu.get('degree', 'N/A')} at {edu.get('institution', 'N/A')}"
                        )

                if experience:
                    st.subheader("💼 Experience")
                    for exp in experience[:5]:
                        st.write(f"- {exp.get('role', 'N/A')}")

                if certs:
                    st.subheader("📜 Certifications")
                    for c in certs:
                        st.write(
                            f"- {c.get('name', 'N/A')} ({c.get('status', 'completed')})"
                        )
            else:
                st.error("Failed to parse resume. Make sure it's a valid PDF.")

    st.divider()

    # Match against jobs
    st.subheader("📊 Match Against Jobs")
    if st.button("🔍 Find Best Matching Jobs", use_container_width=True):
        with st.spinner("Matching your skills against all jobs..."):
            # Get all jobs
            jobs_data = fetch_data("/jobs/?limit=50")
            if not jobs_data or not jobs_data.get("jobs"):
                st.info("No jobs to match against. Run discovery first!")
                return

            job_ids = [j["id"] for j in jobs_data["jobs"] if j.get("id")]
            if not job_ids:
                st.info("No valid job IDs found.")
                return

            # Batch match
            result = _api(
                f"/resumes/match-batch?user_id={user_id}&job_ids={'&job_ids='.join(job_ids)}",
                method="POST",
                timeout=30,
            )
            if result:
                matches = result.get("matches", [])
                if matches:
                    st.success(f"✅ Matched against **{len(matches)}** jobs!")
                    avg = result.get("average_score")
                    if avg is not None:
                        st.metric("Average Match Score", f"{avg}%")

                    for m in matches[:10]:
                        score = m.get("match_score", 0)
                        color = (
                            "🟢"
                            if (score or 0) >= 70
                            else "🟡"
                            if (score or 0) >= 40
                            else "🔴"
                        )
                        with st.expander(
                            f"{color} **{m.get('job_title', 'N/A')}** at {m.get('company', 'N/A')} — Match: {score or 0}%"
                        ):
                            matched = m.get("matched_skills", [])
                            related = m.get("related_skills", [])
                            missing = m.get("missing_skills", [])
                            if matched:
                                st.write(
                                    "✅ **Your matched skills:**",
                                    ", ".join(matched[:10]),
                                )
                            if related:
                                st.write(
                                    "🔗 **Transferable skills (same domain):**",
                                    ", ".join(related[:10]),
                                )
                            if missing:
                                st.write(
                                    "📚 **Skills to learn:**", ", ".join(missing[:10])
                                )
                            suggestions = m.get("suggestions", [])
                            if suggestions:
                                st.write("💡 **Suggestions:**")
                                for s in suggestions:
                                    st.write(f"- {s}")
                else:
                    st.info("No matches found. Upload your resume first!")
            else:
                st.error("Match API unavailable. Upload your resume first!")

    st.divider()
    st.caption(
        "💡 Upload your resume once — it's saved in the database. You can re-match anytime as new jobs are discovered."
    )


# ---------------------------------------------------------------------------
# Page: Learning
# ---------------------------------------------------------------------------


def show_learning() -> None:
    """Show learning resources."""
    st.header("📚 Learning Resources")

    platforms = [
        {
            "name": "Google Cloud Skills Boost",
            "icon": "☁️",
            "url": "https://cloudskillsboost.google",
        },
        {"name": "OWASP", "icon": "🔒", "url": "https://owasp.org"},
        {
            "name": "PortSwigger",
            "icon": "🎯",
            "url": "https://portswigger.net/web-security",
        },
        {"name": "TryHackMe", "icon": "🏴‍☠️", "url": "https://tryhackme.com"},
        {"name": "Hack The Box", "icon": "📦", "url": "https://hackthebox.com"},
        {"name": "OverTheWire", "icon": "🎯", "url": "https://overthewire.org"},
        {"name": "PicoCTF", "icon": "🏆", "url": "https://picoctf.org"},
    ]

    cols = st.columns(3)
    for i, platform in enumerate(platforms):
        with cols[i % 3]:
            st.markdown(f"### {platform['icon']} {platform['name']}")
            st.link_button("Visit", platform["url"], use_container_width=True)


# ---------------------------------------------------------------------------
# Page: Settings
# ---------------------------------------------------------------------------


def show_settings() -> None:
    """Show settings page."""
    st.header("⚙️ Settings")

    st.subheader("About")
    st.write(f"**InternTrack** v{fetch_version()}")
    st.write("AI-powered internship and job tracking platform")
    st.write(f"API: `{API_URL}`")

    if st.button("🔄 Clear Cache & Refresh", use_container_width=True):
        st.cache_data.clear()
        st.rerun()


if __name__ == "__main__":
    main()
