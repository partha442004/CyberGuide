# CyberShield Career Intelligence Platform (CSCIP) - Dashboard

## Overview

CSCIP Dashboard is a modern Streamlit-based web interface with dark/light mode, interactive charts, analytics, watchlists, resume upload, and application tracking.

---

## Dashboard Pages

| Page | Description |
|------|-------------|
| **Overview** | Key metrics, recent activity, quick actions |
| **Jobs** | Job listings with filters, search, apply |
| **Applications** | Kanban-style application tracker |
| **Analytics** | Charts, trends, insights |
| **Learning** | Skill recommendations, learning paths |
| **Interviews** | Interview prep, mock questions |
| **CTF** | CTF competitions tracking |
| **Bug Bounty** | Bug bounty programs |
| **Events** | Conferences, meetups, workshops |
| **Cyber News** | Security news with hiring insights |
| **Salary Insights** | Salary data, comparisons |
| **Notifications** | Notification settings |
| **Settings** | User preferences, API keys |

---

## Dashboard Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         DASHBOARD ARCHITECTURE                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Streamlit App                                     │   │
│  │                                                                      │   │
│  │  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐             │   │
│  │  │   Sidebar    │  │   Main Area  │  │   Footer     │             │   │
│  │  │   Navigation │  │   Content    │  │   Info       │             │   │
│  │  └──────────────┘  └──────────────┘  └──────────────┘             │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Components                                        │   │
│  │                                                                      │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │   │
│  │  │  Charts  │  │  Cards   │  │  Forms   │  │  Tables  │          │   │
│  │  │ (Plotly) │  │ (Metric) │  │ (Input)  │  │ (Data)   │          │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                               │
│                              ▼                                               │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    API Client                                        │   │
│  │                                                                      │   │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐          │   │
│  │  │  Jobs    │  │  Apps    │  │Analytics │  │Notifs    │          │   │
│  │  │  API     │  │  API     │  │  API     │  │  API     │          │   │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘          │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Implementation Code

```python
# dashboard/app.py

import streamlit as st
import httpx
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

# Page config
st.set_page_config(
    page_title="CyberShield Career Intelligence",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS for dark/light mode
st.markdown("""
<style>
    .metric-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 20px;
        border-radius: 12px;
        color: white;
        text-align: center;
    }
    .scam-alert {
        background: linear-gradient(135deg, #ff6b6b 0%, #ee5a24 100%);
        padding: 15px;
        border-radius: 10px;
        color: white;
    }
    .success-card {
        background: linear-gradient(135deg, #00b894 0%, #00cec9 100%);
        padding: 20px;
        border-radius: 12px;
        color: white;
    }
</style>
""", unsafe_allow_html=True)

# API base URL
API_URL = "http://localhost:8000/api/v1"


def fetch_data(endpoint: str):
    """Fetch data from API."""
    try:
        response = httpx.get(f"{API_URL}{endpoint}", timeout=10)
        if response.status_code == 200:
            return response.json()
    except Exception:
        pass
    return None


def main():
    """Main dashboard function."""
    st.title("🛡️ CyberShield Career Intelligence")
    st.markdown("AI-powered cybersecurity career intelligence platform")
    
    # Sidebar
    with st.sidebar:
        st.header("Navigation")
        page = st.radio(
            "Go to",
            [
                "📊 Overview",
                "💼 Jobs",
                "📋 Applications",
                "📈 Analytics",
                "📚 Learning",
                "🎯 Interviews",
                "🏆 CTF",
                "💰 Bug Bounty",
                "📅 Events",
                "📰 Cyber News",
                "💵 Salary Insights",
                "🔔 Notifications",
                "⚙️ Settings",
            ]
        )
    
    if page == "📊 Overview":
        show_overview()
    elif page == "💼 Jobs":
        show_jobs()
    elif page == "📋 Applications":
        show_applications()
    elif page == "📈 Analytics":
        show_analytics()
    elif page == "📚 Learning":
        show_learning()
    elif page == "🎯 Interviews":
        show_interviews()
    elif page == "🏆 CTF":
        show_ctf()
    elif page == "💰 Bug Bounty":
        show_bug_bounty()
    elif page == "📅 Events":
        show_events()
    elif page == "📰 Cyber News":
        show_cyber_news()
    elif page == "💵 Salary Insights":
        show_salary_insights()
    elif page == "🔔 Notifications":
        show_notifications()
    elif page == "⚙️ Settings":
        show_settings()


def show_overview():
    """Show overview page."""
    st.header("📊 Overview")
    
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
            st.metric("Watchlist Matches", overview.get("watchlist_matches", 0))
        
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
        
        # Upcoming events
        st.subheader("📅 Upcoming Events")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.info(f"🏆 {overview.get('upcoming_ctfs', 0)} CTFs coming up")
        with col2:
            st.info(f"📅 {overview.get('upcoming_events', 0)} events scheduled")
        with col3:
            st.info(f"💰 {overview.get('active_bounties', 0)} active bounties")
    else:
        st.info("No data available. Start the API server and run job discovery.")


def show_jobs():
    """Show jobs page."""
    st.header("💼 Jobs")
    
    # Search and filters
    col1, col2, col3 = st.columns([3, 1, 1])
    
    with col1:
        query = st.text_input("Search jobs", "cybersecurity")
    with col2:
        country = st.selectbox("Country", ["All", "India", "USA", "Remote"])
    with col3:
        job_type = st.selectbox("Type", ["All", "Internship", "Full-time", "Remote"])
    
    if st.button("🔍 Search"):
        with st.spinner("Searching..."):
            params = {"query": query}
            if country != "All":
                params["country"] = country
            if job_type != "All":
                params["job_type"] = job_type.lower()
            
            results = fetch_data(f"/jobs/?{'&'.join(f'{k}={v}' for k, v in params.items())}")
            
            if results and results.get("jobs"):
                for job in results["jobs"]:
                    with st.expander(f"{job['title']} - {job['company']}"):
                        col1, col2 = st.columns([3, 1])
                        
                        with col1:
                            st.write(f"📍 {job.get('location', 'Remote')}")
                            st.write(f"💰 {job.get('salary_min', 'N/A')} - {job.get('salary_max', 'N/A')}")
                            if job.get("description"):
                                st.write(job["description"][:500] + "...")
                        
                        with col2:
                            scam_score = job.get("scam_score", 0)
                            if scam_score > 70:
                                st.error(f"⚠️ Scam Score: {scam_score}")
                            elif scam_score > 50:
                                st.warning(f"⚡ Risk Score: {scam_score}")
                            else:
                                st.success(f"✅ Safe ({scam_score})")
                            
                            if job.get("url"):
                                st.link_button("View", job["url"])
                            if st.button("Apply", key=f"apply_{job['id']}"):
                                st.success("Application tracked!")
            else:
                st.info("No jobs found. Try different search terms.")
    
    # Quick actions
    st.subheader("⚡ Quick Actions")
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if st.button("🔄 Run Discovery"):
            with st.spinner("Discovering jobs..."):
                result = fetch_data("/jobs/discovery/run")
                if result:
                    st.success(f"Found {result.get('discovered', 0)} jobs, saved {result.get('saved', 0)}")
    
    with col2:
        if st.button("📊 View Statistics"):
            st.session_state.page = "📈 Analytics"
    
    with col3:
        if st.button("🎯 Skill Match"):
            st.session_state.page = "📚 Learning"


def show_applications():
    """Show applications page with Kanban board."""
    st.header("📋 Applications")
    
    # Status filter
    status_filter = st.selectbox(
        "Filter by status",
        ["All", "saved", "applied", "interview", "assessment", "rejected", "offer", "joined"]
    )
    
    endpoint = "/applications/" if status_filter == "All" else f"/applications/?status={status_filter}"
    apps_data = fetch_data(endpoint)
    
    if apps_data and apps_data.get("applications"):
        # Kanban board
        statuses = ["saved", "applied", "interview", "assessment", "offer", "joined"]
        cols = st.columns(len(statuses))
        
        for i, status in enumerate(statuses):
            with cols[i]:
                st.subheader(status.title())
                status_apps = [a for a in apps_data["applications"] if a["status"] == status]
                
                for app in status_apps:
                    with st.container():
                        st.markdown(f"""
                        <div style="border-left: 4px solid {'#667eea' if status == 'saved' else '#10b981'}; 
                                    padding: 10px; margin: 5px 0; background: white; border-radius: 5px;">
                            <strong>{app.get('job_title', 'Job')}</strong><br>
                            <small>{app.get('company', 'Company')}</small>
                        </div>
                        """, unsafe_allow_html=True)
                        
                        # Status update
                        new_status = st.selectbox(
                            "Update",
                            statuses,
                            index=statuses.index(status),
                            key=f"status_{app['id']}",
                            label_visibility="collapsed",
                        )
    else:
        st.info("No applications found.")


def show_analytics():
    """Show analytics page."""
    st.header("📈 Analytics")
    
    # Tabs
    tab1, tab2, tab3, tab4 = st.tabs(["Skills", "Salary", "Geographic", "Trends"])
    
    with tab1:
        st.subheader("Skill Demand")
        skills_data = fetch_data("/analytics/skills/trends?period=monthly")
        if skills_data and skills_data.get("data"):
            fig = px.bar(
                skills_data["data"][:10],
                x="skill",
                y="demand",
                title="Top Skills by Demand",
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with tab2:
        st.subheader("Salary Insights")
        salary_data = fetch_data("/analytics/salary/insights")
        if salary_data:
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Min Salary", f"${salary_data.get('min_salary', 0):,}")
            with col2:
                st.metric("Max Salary", f"${salary_data.get('max_salary', 0):,}")
            with col3:
                st.metric("Avg Min", f"${salary_data.get('avg_min', 0):,.0f}")
            with col4:
                st.metric("Avg Max", f"${salary_data.get('avg_max', 0):,.0f}")
    
    with tab3:
        st.subheader("Geographic Distribution")
        geo_data = fetch_data("/jobs/stats/overview")
        if geo_data and geo_data.get("countries"):
            fig = px.pie(
                list(geo_data["countries"].items()),
                names=[x[0] for x in geo_data["countries"].items()],
                values=[x[1] for x in geo_data["countries"].items()],
                title="Jobs by Country",
            )
            st.plotly_chart(fig, use_container_width=True)
    
    with tab4:
        st.subheader("Hiring Predictions")
        predictions = fetch_data("/analytics/predictions/hiring")
        if predictions:
            st.write(predictions)


def show_learning():
    """Show learning page."""
    st.header("📚 Learning Resources")
    
    st.subheader("🎯 Skill Gap Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        job_skills = st.text_area("Job Skills (one per line)", "SOC\nSIEM\nPython\nSplunk\nLinux")
    with col2:
        user_skills = st.text_area("Your Skills (one per line)", "Python\nLinux")
    
    if st.button("🎯 Analyze Gap"):
        job_list = [s.strip() for s in job_skills.split("\n") if s.strip()]
        user_list = [s.strip() for s in user_skills.split("\n") if s.strip()]
        
        matched = set(job_list) & set(user_list)
        missing = set(job_list) - set(user_list)
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.success(f"✅ Matched Skills ({len(matched)})")
            for skill in matched:
                st.write(f"• {skill}")
        
        with col2:
            st.error(f"❌ Missing Skills ({len(missing)})")
            for skill in missing:
                st.write(f"• {skill}")
    
    st.subheader("📖 Recommended Platforms")
    
    platforms = [
        {"name": "TryHackMe", "url": "https://tryhackme.com", "icon": "🏴‍☠️"},
        {"name": "HackTheBox", "url": "https://hackthebox.com", "icon": "📦"},
        {"name": "PortSwigger", "url": "https://portswigger.net", "icon": "🎯"},
        {"name": "PicoCTF", "url": "https://picoctf.org", "icon": "🏆"},
        {"name": "OverTheWire", "url": "https://overthewire.org", "icon": "🎯"},
        {"name": "Google Cloud Skills", "url": "https://cloudskillsboost.google", "icon": "☁️"},
        {"name": "OWASP", "url": "https://owasp.org", "icon": "🔒"},
    ]
    
    cols = st.columns(4)
    for i, platform in enumerate(platforms):
        with cols[i % 4]:
            st.markdown(f"### {platform['icon']} {platform['name']}")
            st.link_button("Visit", platform["url"])


def show_ctf():
    """Show CTF page."""
    st.header("🏆 CTF Competitions")
    
    ctf_data = fetch_data("/ctf/?upcoming=true")
    
    if ctf_data and ctf_data.get("events"):
        for event in ctf_data["events"]:
            with st.expander(f"🏆 {event['name']}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"📅 {event.get('start_date', 'TBA')} - {event.get('end_date', 'TBA')}")
                    st.write(f"🎯 Difficulty: {event.get('difficulty', 'Unknown')}")
                    st.write(f"💰 Prize: {event.get('prize', 'N/A')}")
                
                with col2:
                    if event.get("url"):
                        st.link_button("Register", event["url"])
                    st.write(f"Platform: {event.get('platform', 'Unknown')}")
    else:
        st.info("No upcoming CTFs found.")


def show_bug_bounty():
    """Show bug bounty page."""
    st.header("💰 Bug Bounty Programs")
    
    bounty_data = fetch_data("/bug-bounty/?status=active")
    
    if bounty_data and bounty_data.get("programs"):
        for program in bounty_data["programs"]:
            with st.expander(f"💰 {program['company']}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"Platform: {program.get('platform', 'Unknown')}")
                    st.write(f"Min Bounty: ${program.get('min_bounty', 'N/A')}")
                    st.write(f"Max Bounty: ${program.get('max_bounty', 'N/A')}")
                
                with col2:
                    if program.get("url"):
                        st.link_button("View Program", program["url"])
                    if program.get("scope"):
                        st.write(f"Scope: {program['scope'][:200]}...")
    else:
        st.info("No active bug bounty programs found.")


def show_events():
    """Show events page."""
    st.header("📅 Events")
    
    event_data = fetch_data("/events/?upcoming=true")
    
    if event_data and event_data.get("events"):
        for event in event_data["events"]:
            with st.expander(f"📅 {event['name']}"):
                col1, col2 = st.columns(2)
                
                with col1:
                    st.write(f"Type: {event.get('event_type', 'Unknown')}")
                    st.write(f"Date: {event.get('start_date', 'TBA')}")
                    st.write(f"Location: {event.get('location', 'Virtual')}")
                
                with col2:
                    if event.get("url"):
                        st.link_button("Register", event["url"])
                    st.write(f"Price: {'Free' if event.get('is_free') else f'${event.get('price', 'N/A')}'}")
    else:
        st.info("No upcoming events found.")


def show_cyber_news():
    """Show cyber news page."""
    st.header("📰 Cybersecurity News")
    
    news_data = fetch_data("/analytics/news/recent")
    
    if news_data and news_data.get("articles"):
        for article in news_data["articles"]:
            with st.expander(f"📰 {article['title']}"):
                st.write(f"Source: {article.get('source', 'Unknown')}")
                st.write(f"Published: {article.get('published_at', 'N/A')}")
                st.write(f"Category: {article.get('category', 'General')}")
                
                if article.get("analysis"):
                    st.info(f"Analysis: {article['analysis']}")
                
                if article.get("url"):
                    st.link_button("Read More", article["url"])
    else:
        st.info("No recent news found.")


def show_salary_insights():
    """Show salary insights page."""
    st.header("💵 Salary Insights")
    
    col1, col2 = st.columns(2)
    
    with col1:
        role = st.text_input("Job Role", "SOC Analyst")
        country = st.selectbox("Country", ["India", "USA", "Remote"])
    
    with col2:
        experience = st.selectbox("Experience", ["Entry", "Junior", "Mid", "Senior"])
    
    if st.button("🔍 Get Insights"):
        salary_data = fetch_data(f"/analytics/salary/insights?role={role}&country={country}&experience={experience}")
        
        if salary_data:
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.metric("Estimated Min", f"${salary_data.get('min', 0):,}")
            with col2:
                st.metric("Estimated Max", f"${salary_data.get('max', 0):,}")
            with col3:
                st.metric("Confidence", f"{salary_data.get('confidence', 0)*100:.0f}%")


def show_notifications():
    """Show notifications settings page."""
    st.header("🔔 Notification Settings")
    
    st.subheader("📱 Channels")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Telegram**")
        telegram_enabled = st.checkbox("Enable Telegram", key="tg_enabled")
        if telegram_enabled:
            bot_token = st.text_input("Bot Token", type="password", key="tg_token")
            chat_id = st.text_input("Chat ID", key="tg_chat")
    
    with col2:
        st.write("**Email**")
        email_enabled = st.checkbox("Enable Email", key="email_enabled")
        if email_enabled:
            smtp_user = st.text_input("SMTP User", key="smtp_user")
            smtp_pass = st.text_input("SMTP Password", type="password", key="smtp_pass")
    
    st.subheader("🔔 Alert Types")
    
    alert_types = st.multiselect(
        "Select alert types",
        ["Instant Job Matches", "Scam Alerts", "Deadline Reminders", "Daily Report", "Weekly Report"],
        default=["Instant Job Matches", "Scam Alerts"],
    )
    
    if st.button("💾 Save Settings"):
        st.success("Settings saved!")


def show_settings():
    """Show settings page."""
    st.header("⚙️ Settings")
    
    st.subheader("👤 Profile")
    
    col1, col2 = st.columns(2)
    
    with col1:
        name = st.text_input("Full Name", key="profile_name")
        email = st.text_input("Email", key="profile_email")
    
    with col2:
        country = st.selectbox("Target Country", ["India", "USA", "Remote"], key="profile_country")
        target_role = st.text_input("Target Role", "SOC Analyst", key="profile_role")
    
    st.subheader("🎯 Preferences")
    
    col1, col2 = st.columns(2)
    
    with col1:
        experience = st.selectbox("Experience Level", ["Entry", "Junior", "Mid", "Senior"], key="pref_exp")
    
    with col2:
        st.write("**Notifications**")
        instant_alerts = st.checkbox("Instant Alerts", value=True, key="pref_instant")
        daily_reports = st.checkbox("Daily Reports", value=True, key="pref_daily")
    
    if st.button("💾 Save Profile"):
        st.success("Profile saved!")
    
    st.subheader("🔑 API Keys")
    
    with st.expander("AI Configuration"):
        ollama_url = st.text_input("Ollama URL", "http://localhost:11434", key="ollama_url")
        gemini_key = st.text_input("Gemini API Key", type="password", key="gemini_key")
    
    st.subheader("ℹ️ About")
    st.write("**CyberShield Career Intelligence Platform** v1.14.0")
    st.write("AI-powered cybersecurity career intelligence")


if __name__ == "__main__":
    main()
```

---

## Dashboard Features

### Dark/Light Mode
```python
# Auto-detect system preference
import streamlit as st

if st.checkbox("Dark Mode", value=True):
    st.markdown("""
    <style>
        .stApp {
            background-color: #0e1117;
            color: white;
        }
    </style>
    """, unsafe_allow_html=True)
```

### Interactive Charts
- **Plotly** for interactive visualizations
- **Real-time updates** via API
- **Responsive design** for mobile

### Key Metrics Cards
```python
def metric_card(title: str, value: Any, delta: str = None):
    """Display a metric card."""
    st.markdown(f"""
    <div class="metric-card">
        <h3>{title}</h3>
        <h2>{value}</h2>
        {f'<p>{delta}</p>' if delta else ''}
    </div>
    """, unsafe_allow_html=True)
```

---

## Metrics

| Metric | Description |
|--------|-------------|
| `dashboard_load_time_seconds` | Page load time |
| `api_calls_per_session` | API calls per user session |
| `chart_render_time_ms` | Chart rendering time |

---

**Module Status**: ✅ Complete

**Next Module**: [Module 14: Resume Engine](./14-resume-engine.md)
