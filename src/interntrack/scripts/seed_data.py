"""
Database seed script for populating sample data.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

from interntrack.database.session import get_db_session, init_db
from interntrack.domain.enums import (
    ApplicationStatus,
    JobSource,
    JobType,
    ExperienceLevel,
    SkillCategory,
)
from interntrack.domain.models import (
    Job,
    Application,
    Skill,
    JobSkill,
    UserSkill,
)


# Sample jobs
SAMPLE_JOBS = [
    {
        "title": "Senior Python Developer",
        "company": "TechCorp Inc.",
        "location": "San Francisco, CA",
        "description": "We are looking for a senior Python developer to join our team. Experience with FastAPI, SQLAlchemy, and PostgreSQL required.",
        "url": "https://example.com/jobs/senior-python-dev",
        "source": JobSource.LINKEDIN,
        "job_type": JobType.FULL_TIME,
        "experience_level": ExperienceLevel.SENIOR,
        "salary_min": 150000,
        "salary_max": 200000,
        "is_remote": False,
        "tags": ["python", "fastapi", "postgresql"],
    },
    {
        "title": "Frontend React Developer",
        "company": "StartupXYZ",
        "location": "Remote",
        "description": "Join our remote team as a React developer. Build beautiful user interfaces with modern React patterns.",
        "url": "https://example.com/jobs/react-dev",
        "source": JobSource.REMOTE_OK,
        "job_type": JobType.REMOTE,
        "experience_level": ExperienceLevel.MID,
        "salary_min": 100000,
        "salary_max": 140000,
        "is_remote": True,
        "tags": ["react", "javascript", "typescript"],
    },
    {
        "title": "Junior Backend Engineer",
        "company": "DataFlow Systems",
        "location": "New York, NY",
        "description": "Entry-level position for aspiring backend developers. Python and SQL knowledge preferred.",
        "url": "https://example.com/jobs/junior-backend",
        "source": JobSource.INDEED,
        "job_type": JobType.FULL_TIME,
        "experience_level": ExperienceLevel.JUNIOR,
        "salary_min": 70000,
        "salary_max": 90000,
        "is_remote": False,
        "tags": ["python", "sql", "rest api"],
    },
    {
        "title": "DevOps Engineer",
        "company": "CloudNine Technologies",
        "location": "Austin, TX",
        "description": "Manage and optimize our cloud infrastructure. Experience with AWS, Docker, and Kubernetes required.",
        "url": "https://example.com/jobs/devops-engineer",
        "source": JobSource.HACKER_NEWS,
        "job_type": JobType.FULL_TIME,
        "experience_level": ExperienceLevel.MID,
        "salary_min": 120000,
        "salary_max": 160000,
        "is_remote": True,
        "tags": ["aws", "docker", "kubernetes", "linux"],
    },
    {
        "title": "Full Stack Developer Intern",
        "company": "InnovateTech",
        "location": "Seattle, WA",
        "description": "Summer internship opportunity for full stack development. Learn React, Node.js, and PostgreSQL.",
        "url": "https://example.com/jobs/fullstack-intern",
        "source": JobSource.RSS_FEED,
        "job_type": JobType.INTERNSHIP,
        "experience_level": ExperienceLevel.ENTRY,
        "salary_min": 25,
        "salary_max": 35,
        "is_remote": False,
        "tags": ["react", "node.js", "postgresql"],
    },
    {
        "title": "Machine Learning Engineer",
        "company": "AI Solutions Corp",
        "location": "Boston, MA",
        "description": "Build and deploy ML models. Python, TensorFlow, and PyTorch experience required.",
        "url": "https://example.com/jobs/ml-engineer",
        "source": JobSource.LINKEDIN,
        "job_type": JobType.FULL_TIME,
        "experience_level": ExperienceLevel.SENIOR,
        "salary_min": 160000,
        "salary_max": 220000,
        "is_remote": False,
        "tags": ["python", "machine learning", "tensorflow", "pytorch"],
    },
    {
        "title": "Remote UI/UX Designer",
        "company": "DesignHub",
        "location": "Remote",
        "description": "Create beautiful and intuitive user experiences for our SaaS product.",
        "url": "https://example.com/jobs/uiux-designer",
        "source": JobSource.REMOTE_OK,
        "job_type": JobType.REMOTE,
        "experience_level": ExperienceLevel.MID,
        "salary_min": 90000,
        "salary_max": 130000,
        "is_remote": True,
        "tags": ["figma", "ui/ux", "design"],
    },
    {
        "title": "Data Analyst",
        "company": "Analytics Pro",
        "location": "Chicago, IL",
        "description": "Analyze data and create reports. SQL, Python, and Excel skills required.",
        "url": "https://example.com/jobs/data-analyst",
        "source": JobSource.INDEED,
        "job_type": JobType.FULL_TIME,
        "experience_level": ExperienceLevel.JUNIOR,
        "salary_min": 65000,
        "salary_max": 85000,
        "is_remote": False,
        "tags": ["sql", "python", "excel", "data analysis"],
    },
]

# Sample skills
SAMPLE_SKILLS = [
    {"name": "python", "category": SkillCategory.PROGRAMMING, "difficulty_level": 2},
    {"name": "javascript", "category": SkillCategory.PROGRAMMING, "difficulty_level": 2},
    {"name": "typescript", "category": SkillCategory.PROGRAMMING, "difficulty_level": 2},
    {"name": "react", "category": SkillCategory.FRAMEWORK, "difficulty_level": 3},
    {"name": "fastapi", "category": SkillCategory.FRAMEWORK, "difficulty_level": 2},
    {"name": "django", "category": SkillCategory.FRAMEWORK, "difficulty_level": 3},
    {"name": "sql", "category": SkillCategory.TOOL, "difficulty_level": 2},
    {"name": "postgresql", "category": SkillCategory.TOOL, "difficulty_level": 3},
    {"name": "docker", "category": SkillCategory.TOOL, "difficulty_level": 3},
    {"name": "kubernetes", "category": SkillCategory.TOOL, "difficulty_level": 4},
    {"name": "aws", "category": SkillCategory.TOOL, "difficulty_level": 3},
    {"name": "git", "category": SkillCategory.TOOL, "difficulty_level": 1},
    {"name": "linux", "category": SkillCategory.TOOL, "difficulty_level": 2},
    {"name": "rest api", "category": SkillCategory.FRAMEWORK, "difficulty_level": 2},
    {"name": "machine learning", "category": SkillCategory.PROGRAMMING, "difficulty_level": 4},
    {"name": "tensorflow", "category": SkillCategory.FRAMEWORK, "difficulty_level": 4},
    {"name": "pytorch", "category": SkillCategory.FRAMEWORK, "difficulty_level": 4},
    {"name": "figma", "category": SkillCategory.TOOL, "difficulty_level": 2},
    {"name": "excel", "category": SkillCategory.TOOL, "difficulty_level": 1},
    {"name": "node.js", "category": SkillCategory.FRAMEWORK, "difficulty_level": 2},
]


async def seed_database():
    """Seed the database with sample data."""
    print("🌱 Seeding database...")

    await init_db()

    async with get_db_session() as session:
        # Create skills
        print("  Creating skills...")
        skill_map = {}
        for skill_data in SAMPLE_SKILLS:
            skill = Skill(
                id=str(uuid4()),
                name=skill_data["name"],
                category=skill_data["category"],
                difficulty_level=skill_data["difficulty_level"],
                is_active=True,
            )
            session.add(skill)
            skill_map[skill.name] = skill
        await session.flush()

        # Create jobs
        print("  Creating jobs...")
        for job_data in SAMPLE_JOBS:
            job = Job(
                id=str(uuid4()),
                title=job_data["title"],
                company=job_data["company"],
                location=job_data["location"],
                description=job_data["description"],
                url=job_data["url"],
                source=job_data["source"],
                job_type=job_data["job_type"],
                experience_level=job_data["experience_level"],
                salary_min=job_data["salary_min"],
                salary_max=job_data["salary_max"],
                is_remote=job_data["is_remote"],
                tags=job_data["tags"],
                is_active=True,
                posted_at=datetime.now(timezone.utc) - timedelta(days=3),
            )
            session.add(job)
            await session.flush()

            # Add job skills
            for tag in job_data.get("tags", []):
                tag_lower = tag.lower()
                if tag_lower in skill_map:
                    job_skill = JobSkill(
                        job_id=job.id,
                        skill_id=skill_map[tag_lower].id,
                        importance=3,
                    )
                    session.add(job_skill)

        # Create sample user skills
        print("  Creating sample user skills...")
        user_id = "demo-user-001"
        user_skills = ["python", "javascript", "react", "git", "sql"]
        for skill_name in user_skills:
            if skill_name in skill_map:
                user_skill = UserSkill(
                    user_id=user_id,
                    skill_id=skill_map[skill_name].id,
                    proficiency_level=3,
                    is_learning=False,
                )
                session.add(user_skill)

        # Create sample applications
        print("  Creating sample applications...")
        from sqlalchemy import select

        # Get first 3 jobs for applications
        result = await session.execute(
            select(Job).limit(3)
        )
        jobs = list(result.scalars().all())

        for i, job in enumerate(jobs):
            status = [ApplicationStatus.SAVED, ApplicationStatus.APPLIED, ApplicationStatus.INTERVIEW][i]
            application = Application(
                id=str(uuid4()),
                job_id=job.id,
                status=status,
                notes=f"Sample application for {job.title}",
                applied_at=datetime.now(timezone.utc) - timedelta(days=i) if status != ApplicationStatus.SAVED else None,
                interview_at=datetime.now(timezone.utc) + timedelta(days=5) if status == ApplicationStatus.INTERVIEW else None,
            )
            session.add(application)

        await session.commit()

    print("✅ Database seeded successfully!")
    print(f"   - {len(SAMPLE_SKILLS)} skills created")
    print(f"   - {len(SAMPLE_JOBS)} jobs created")
    print(f"   - 3 applications created")
    print(f"   - User skills for demo user created")


if __name__ == "__main__":
    asyncio.run(seed_database())
