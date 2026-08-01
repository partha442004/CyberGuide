"""
CyberGuide Dashboard - Main Application

Streamlit application with multi-page navigation and theme support.
"""

from datetime import datetime, timezone
from typing import Any, Dict, List

import pandas as pd  # type: ignore[import-untyped]
import streamlit as st

# Page configuration
st.set_page_config(
    page_title="CyberGuide - Career Intelligence Platform",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS
st.markdown(
    """
<style>
    /* Main theme */
    .main .block-container {
        padding-top: 2rem;
        max-width: 1200px;
    }

    /* Header styling */
    .stHeader {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 1rem;
        border-radius: 10px;
        color: white;
    }

    /* Metric cards */
    div[data-testid="stMetric"] {
        background-color: #f8f9fa;
        padding: 1rem;
        border-radius: 10px;
        border-left: 4px solid #667eea;
    }

    /* Sidebar styling */
    section[data-testid="stSidebar"] {
        background-color: #1e1e1e;
    }

    /* Job card styling */
    .job-card {
        background: white;
        padding: 1.5rem;
        border-radius: 10px;
        box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        margin-bottom: 1rem;
        border-left: 4px solid #667eea;
    }

    .job-card:hover {
        box-shadow: 0 4px 20px rgba(0,0,0,0.15);
        transform: translateY(-2px);
        transition: all 0.3s ease;
    }

    /* Scam score badges */
    .scam-low { color: #28a745; }
    .scam-medium { color: #ffc107; }
    .scam-high { color: #dc3545; }

    /* Status badges */
    .status-saved { background-color: #6c757d; }
    .status-applied { background-color: #007bff; }
    .status-interview { background-color: #28a745; }
    .status-rejected { background-color: #dc3545; }
    .status-offer { background-color: #ffc107; }
</style>
""",
    unsafe_allow_html=True,
)


def main():
    """Main dashboard application."""

    # Sidebar
    with st.sidebar:
        st.image("https://img.icons8.com/nolan/96/shield.png", width=80)
        st.title("🛡️ CyberGuide")
        st.caption("Career Intelligence Platform")

        st.divider()

        # Navigation
        page = st.radio(
            "Navigate to:",
            [
                "📊 Overview",
                "💼 Jobs",
                "📋 Applications",
                "📈 Analytics",
                "🎯 Skills",
                "🏆 CTF",
                "💰 Bug Bounty",
                "📅 Events",
                "📰 Cyber News",
                "🎓 Learning",
                "📄 Resume",
                "🔔 Notifications",
                "⚙️ Settings",
            ],
            index=0,
        )

        st.divider()

        # Quick stats
        st.metric("Jobs Tracked", "1,234", "+45 today")
        st.metric("Applications", "23", "+3 this week")

        st.divider()
        st.caption(f"Last updated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")

    # Route to page
    if page == "📊 Overview":
        show_overview()
    elif page == "💼 Jobs":
        show_jobs()
    elif page == "📋 Applications":
        show_applications()
    elif page == "📈 Analytics":
        show_analytics()
    elif page == "🎯 Skills":
        show_skills()
    elif page == "🏆 CTF":
        show_ctf()
    elif page == "💰 Bug Bounty":
        show_bug_bounty()
    elif page == "📅 Events":
        show_events()
    elif page == "📰 Cyber News":
        show_cyber_news()
    elif page == "🎓 Learning":
        show_learning()
    elif page == "📄 Resume":
        show_resume()
    elif page == "🔔 Notifications":
        show_notifications()
    elif page == "⚙️ Settings":
        show_settings()


def show_overview():
    """Overview dashboard page."""
    st.header("📊 Dashboard Overview")

    # Key metrics row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("🎯 New Jobs Today", "45", "+12%")
    with col2:
        st.metric("🔥 High Match", "12", "+3")
    with col3:
        st.metric("⏰ Expiring Soon", "8", "")
    with col4:
        st.metric("🛡️ Scam Blocked", "5", "")

    st.divider()

    # Charts row
    col1, col2 = st.columns(2)

    with col1:
        st.subheader("📈 Job Trends (Last 30 Days)")
        import plotly.graph_objects as go  # type: ignore[import-untyped]

        fig = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=list(range(30)),
                y=[10 + i * 2 + (i % 5) for i in range(30)],
                mode="lines+markers",
                name="Jobs Found",
                line={"color": "#667eea", "width": 2},
            )
        )
        fig.update_layout(height=300, margin={"l": 0, "r": 0, "t": 0, "b": 0})
        st.plotly_chart(fig, use_container_width=True)

    with col2:
        st.subheader("🎯 Top Skills in Demand")
        skills_data = {
            "Python": 85,
            "SIEM": 72,
            "Cloud Security": 68,
            "Penetration Testing": 55,
            "Incident Response": 48,
        }
        fig = go.Figure(
            go.Bar(
                x=list(skills_data.values()),
                y=list(skills_data.keys()),
                orientation="h",
                marker_color="#667eea",
            )
        )
        fig.update_layout(height=300, margin={"l": 0, "r": 0, "t": 0, "b": 0})
        st.plotly_chart(fig, use_container_width=True)

    # Recent jobs table
    st.subheader("🆕 Recent Jobs")
    import pandas as pd

    df = pd.DataFrame(
        {
            "Title": [
                "Security Analyst",
                "SOC Engineer",
                "Penetration Tester",
                "Cloud Security Engineer",
                "Incident Response Analyst",
            ],
            "Company": ["Microsoft", "Google", "Amazon", "Cisco", "CrowdStrike"],
            "Location": [
                "Redmond, WA",
                "Mountain View, CA",
                "Seattle, WA",
                "San Jose, CA",
                "Remote",
            ],
            "Salary": ["$95k-$130k", "$120k-$160k", "$110k-$145k", "$105k-$140k", "$100k-$135k"],
            "Scam Score": ["Low", "Low", "Low", "Low", "Low"],
        }
    )
    st.dataframe(df, use_container_width=True, hide_index=True)


def show_jobs():
    """Jobs search and listing page."""
    st.header("💼 Job Search")

    # Search filters
    col1, col2, col3 = st.columns(3)
    with col1:
        st.text_input("🔍 Search", placeholder="Security Engineer, SOC Analyst...")
    with col2:
        st.selectbox("📍 Location", ["All", "India", "USA", "Remote", "UK", "Germany"])
    with col3:
        st.selectbox("💼 Type", ["All", "Internship", "Full-time", "Part-time", "Contract"])

    col1, col2, col3 = st.columns(3)
    with col1:
        st.selectbox("📊 Experience", ["All", "Fresher", "Junior", "Mid", "Senior"])
    with col2:
        st.selectbox(
            "🛡️ Domain", ["All", "SOC", "Blue Team", "Red Team", "Cloud Security", "AppSec"]
        )
    with col3:
        st.slider("💰 Salary Range (USD)", 0, 200000, (0, 200000), step=10000)

    st.divider()

    # Results count
    st.info("Found **156** jobs matching your criteria")

    # Job cards
    for i in range(5):
        with st.container():
            col1, col2, col3 = st.columns([4, 2, 1])
            with col1:
                st.markdown(f"### Security Analyst {i + 1}")
                st.caption(f"🏢 Tech Corp {i + 1} • 📍 Remote")
            with col2:
                st.markdown("**$100k - $140k**")
                st.caption("🛡️ SOC • 🌐 Remote")
            with col3:
                st.button("Apply", key=f"apply_{i}", type="primary")

            st.caption("Posted 2 days ago • Skills: Python, SIEM, Splunk, AWS")
            st.divider()


def show_applications():
    """Application tracker page."""
    st.header("📋 Application Tracker")

    # Kanban board style
    cols = st.columns(6)
    statuses = ["Saved", "Applied", "Interview", "Assessment", "Rejected", "Offer"]
    counts = [12, 8, 3, 2, 4, 1]

    for col, status, count in zip(cols, statuses, counts, strict=False):
        with col:
            st.metric(status, count)

    st.divider()

    # Application list
    st.subheader("📝 Recent Applications")

    applications = [
        {
            "title": "SOC Analyst",
            "company": "Microsoft",
            "status": "Interview",
            "date": "2024-01-15",
        },
        {
            "title": "Security Engineer",
            "company": "Google",
            "status": "Applied",
            "date": "2024-01-14",
        },
        {
            "title": "Penetration Tester",
            "company": "Amazon",
            "status": "Saved",
            "date": "2024-01-13",
        },
    ]

    for app in applications:
        col1, col2, col3, col4 = st.columns([3, 2, 1, 1])
        with col1:
            st.markdown(f"**{app['title']}**")
            st.caption(app["company"])
        with col2:
            st.caption(f"Applied: {app['date']}")
        with col3:
            st.selectbox(
                "Status",
                ["Saved", "Applied", "Interview", "Assessment", "Rejected", "Offer"],
                index=["Saved", "Applied", "Interview", "Assessment", "Rejected", "Offer"].index(
                    app["status"]
                ),
                key=f"status_{app['title']}",
            )
        with col4:
            st.button("📝 Notes", key=f"notes_{app['title']}")


def show_analytics():
    """Analytics dashboard page."""
    st.header("📈 Analytics Dashboard")

    tab1, tab2, tab3, tab4 = st.tabs(["Skills", "Salary", "Geographic", "Trends"])

    with tab1:
        st.subheader("🎯 Skill Distribution")
        import plotly.express as px  # type: ignore[import-untyped]

        skills_df = pd.DataFrame(
            {
                "Skill": ["Python", "SIEM", "AWS", "Docker", "Kubernetes", "Splunk"],
                "Demand": [85, 72, 68, 55, 48, 42],
            }
        )
        fig = px.pie(skills_df, values="Demand", names="Skill", hole=0.4)
        st.plotly_chart(fig, use_container_width=True)

    with tab2:
        st.subheader("💰 Salary Insights")
        st.info("Average salary by security domain")

    with tab3:
        st.subheader("🌍 Geographic Distribution")
        st.info("Job distribution by location")

    with tab4:
        st.subheader("📈 Hiring Trends")
        st.info("Historical hiring trends")


def show_skills():
    """Skills market page."""
    st.header("🎯 Skills Market Intelligence")

    col1, col2 = st.columns(2)
    with col1:
        st.subheader("🔥 Trending Skills")
        st.markdown("""
        1. **Cloud Security** (AWS/Azure/GCP) - ↑ 23%
        2. **SIEM** (Splunk/Sentinel) - ↑ 18%
        3. **DevSecOps** - ↑ 15%
        4. **Container Security** - ↑ 12%
        5. **Zero Trust** - ↑ 10%
        """)

    with col2:
        st.subheader("📉 Declining Skills")
        st.markdown("""
        1. Basic network security - ↓ 5%
        2. Legacy SIEM tools - ↓ 8%
        3. Manual testing - ↓ 12%
        """)


def show_ctf():
    """CTF competitions page."""
    st.header("🏆 CTF Competitions")

    competitions = [
        {
            "name": "PicoCTF 2024",
            "date": "2024-03-12",
            "platform": "picoCTF",
            "difficulty": "Beginner",
        },
        {
            "name": "CTFtime League",
            "date": "Ongoing",
            "platform": "CTFtime",
            "difficulty": "All Levels",
        },
        {
            "name": "HackTheBox CTF",
            "date": "Monthly",
            "platform": "HTB",
            "difficulty": "Intermediate",
        },
    ]

    for comp in competitions:
        col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
        with col1:
            st.markdown(f"**{comp['name']}**")
        with col2:
            st.caption(f"📅 {comp['date']}")
        with col3:
            st.caption(f"🖥️ {comp['platform']}")
        with col4:
            st.caption(comp["difficulty"])


def show_bug_bounty():
    """Bug bounty programs page."""
    st.header("💰 Bug Bounty Programs")

    programs = [
        {
            "company": "Google",
            "platform": "HackerOne",
            "rewards": "$100-$100k+",
            "scope": "Web, Mobile, API",
        },
        {
            "company": "Microsoft",
            "platform": "MSRC",
            "rewards": "$500-$250k",
            "scope": "Azure, Office 365",
        },
        {
            "company": "Apple",
            "platform": "Apple Security",
            "rewards": "$100-$1.5M",
            "scope": "iOS, macOS",
        },
    ]

    for prog in programs:
        col1, col2, col3, col4 = st.columns([2, 2, 2, 2])
        with col1:
            st.markdown(f"**{prog['company']}**")
        with col2:
            st.caption(f"🖥️ {prog['platform']}")
        with col3:
            st.caption(f"💰 {prog['rewards']}")
        with col4:
            st.caption(f"🎯 {prog['scope']}")


def show_events():
    """Security events page."""
    st.header("📅 Security Events")

    events = [
        {
            "name": "DEF CON 32",
            "date": "2024-08-08",
            "location": "Las Vegas, NV",
            "type": "Conference",
        },
        {
            "name": "Black Hat USA",
            "date": "2024-08-07",
            "location": "Las Vegas, NV",
            "type": "Conference",
        },
        {
            "name": "BSides Las Vegas",
            "date": "2024-08-06",
            "location": "Las Vegas, NV",
            "type": "Conference",
        },
    ]

    for event in events:
        col1, col2, col3, col4 = st.columns([3, 2, 2, 1])
        with col1:
            st.markdown(f"**{event['name']}**")
        with col2:
            st.caption(f"📅 {event['date']}")
        with col3:
            st.caption(f"📍 {event['location']}")
        with col4:
            st.caption(event["type"])


def show_cyber_news():
    """Cyber news feed page."""
    st.header("📰 Cybersecurity News")

    news = [
        {
            "title": "Critical Zero-Day in Windows Kernel",
            "source": "BleepingComputer",
            "time": "2 hours ago",
        },
        {
            "title": "New Ransomware Group Targets Healthcare",
            "source": "The Hacker News",
            "time": "5 hours ago",
        },
        {
            "title": "Microsoft Patches 73 Vulnerabilities",
            "source": "SecurityWeek",
            "time": "1 day ago",
        },
    ]

    for item in news:
        col1, col2, col3 = st.columns([4, 2, 1])
        with col1:
            st.markdown(f"**{item['title']}**")
        with col2:
            st.caption(f"📰 {item['source']}")
        with col3:
            st.caption(item["time"])


def show_learning():
    """Learning recommendations page."""
    st.header("🎓 Learning Recommendations")

    tab1, tab2, tab3 = st.tabs(["Skill Gap", "Courses", "Certifications"])

    with tab1:
        st.subheader("📊 Your Skill Gaps")
        gaps: List[Dict[str, Any]] = [
            {"skill": "Cloud Security", "current": 40, "target": 80},
            {"skill": "SIEM", "current": 50, "target": 75},
            {"skill": "DevSecOps", "current": 30, "target": 70},
        ]
        for gap in gaps:
            progress = int(gap["current"]) / int(gap["target"])
            st.progress(progress, text=f"{gap['skill']}: {gap['current']}% → {gap['target']}%")

    with tab2:
        st.subheader("📚 Recommended Courses")
        courses = [
            "AWS Security Specialty",
            "Splunk Certified Power User",
            "CompTIA Security+",
        ]
        for course in courses:
            st.markdown(f"- 📖 {course}")

    with tab3:
        st.subheader("🎓 Certifications to Pursue")
        certs = [
            "CISSP - Certified Information Systems Security Professional",
            "CEH - Certified Ethical Hacker",
            "OSCP - Offensive Security Certified Professional",
        ]
        for cert in certs:
            st.markdown(f"- 🏅 {cert}")


def show_resume():
    """Resume analysis page."""
    st.header("📄 Resume Engine")

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Upload Resume")
        uploaded_file = st.file_uploader("Choose your resume", type=["pdf", "docx"])
        if uploaded_file:
            st.success("Resume uploaded successfully!")
            st.button("🔍 Analyze Resume", type="primary")

    with col2:
        st.subheader("Resume Score")
        st.metric("ATS Score", "72/100")
        st.progress(0.72)

        st.markdown("**Missing Keywords:**")
        st.caption("Kubernetes, Container Security, CI/CD, DevSecOps")


def show_notifications():
    """Notification settings page."""
    st.header("🔔 Notification Settings")

    st.subheader("📧 Email Notifications")
    col1, col2 = st.columns(2)
    with col1:
        st.toggle("Daily Digest", value=True)
        st.toggle("Weekly Report", value=True)
    with col2:
        st.toggle("Instant Alerts", value=True)
        st.toggle("Deadline Reminders", value=True)

    st.divider()

    st.subheader("💬 Messaging Platforms")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.toggle("Telegram", value=False)
        st.text_input("Bot Token", type="password", placeholder="Enter bot token")
    with col2:
        st.toggle("Discord", value=False)
        st.text_input("Webhook URL", placeholder="Enter webhook URL")
    with col3:
        st.toggle("Slack", value=False)
        st.text_input("Webhook URL", placeholder="Enter webhook URL")


def show_settings():
    """Settings page."""
    st.header("⚙️ Settings")

    st.subheader("👤 Profile")
    col1, col2 = st.columns(2)
    with col1:
        st.text_input("Full Name", value="John Doe")
        st.text_input("Email", value="john@example.com")
    with col2:
        st.text_input("LinkedIn URL", placeholder="https://linkedin.com/in/...")
        st.text_input("GitHub URL", placeholder="https://github.com/...")

    st.divider()

    st.subheader("🎯 Job Preferences")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.multiselect(
            "Target Roles",
            ["SOC Analyst", "Security Engineer", "Penetration Tester"],
            default=["SOC Analyst"],
        )
    with col2:
        st.multiselect("Target Locations", ["India", "USA", "Remote", "UK"], default=["Remote"])
    with col3:
        st.multiselect(
            "Target Companies", ["Microsoft", "Google", "Amazon"], default=["Microsoft", "Google"]
        )

    st.divider()

    st.subheader("🏢 Company Watchlist")
    st.text_area("Add companies to watch (one per line)", value="Microsoft\nGoogle\nAmazon\nCisco")

    st.divider()

    st.subheader("🔑 API Keys")
    with st.expander("AI Services"):
        st.text_input("Ollama Endpoint", value="http://localhost:11434", key="ollama")
        st.text_input("Gemini API Key", type="password", placeholder="Enter API key")

    if st.button("💾 Save Settings", type="primary"):
        st.success("Settings saved successfully!")


if __name__ == "__main__":
    main()
