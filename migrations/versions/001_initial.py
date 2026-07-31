"""Initial migration

Revision ID: 001_initial
Revises: 
Create Date: 2026-07-29

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "001_initial"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial tables."""
    # Jobs table
    op.create_table(
        "jobs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("company", sa.String(200), nullable=False),
        sa.Column("location", sa.String(200), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("url", sa.String(2000), nullable=False, unique=True),
        sa.Column("source", sa.String(50), nullable=False),
        sa.Column("job_type", sa.String(50), nullable=False, server_default="unknown"),
        sa.Column("experience_level", sa.String(50), nullable=True),
        sa.Column("salary_min", sa.Integer, nullable=True),
        sa.Column("salary_max", sa.Integer, nullable=True),
        sa.Column("salary_currency", sa.String(10), nullable=True, server_default="USD"),
        sa.Column("is_remote", sa.Boolean, default=False),
        sa.Column("posted_at", sa.DateTime, nullable=True),
        sa.Column("expires_at", sa.DateTime, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("tags", sa.JSON, nullable=True),
        sa.Column("raw_data", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_job_company", "jobs", ["company"])
    op.create_index("idx_job_source", "jobs", ["source"])
    op.create_index("idx_job_active", "jobs", ["is_active"])

    # Applications table
    op.create_table(
        "applications",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="saved"),
        sa.Column("applied_at", sa.DateTime, nullable=True),
        sa.Column("interview_at", sa.DateTime, nullable=True),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("resume_version", sa.String(100), nullable=True),
        sa.Column("cover_letter", sa.Text, nullable=True),
        sa.Column("priority", sa.Integer, default=0),
        sa.Column("reminded", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    op.create_index("idx_application_status", "applications", ["status"])
    op.create_index("idx_application_job", "applications", ["job_id"])

    # Skills table
    op.create_table(
        "skills",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False, unique=True),
        sa.Column("category", sa.String(50), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("difficulty_level", sa.Integer, default=1),
        sa.Column("learning_resources", sa.JSON, nullable=True),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # Job Skills junction table
    op.create_table(
        "job_skills",
        sa.Column("job_id", sa.String(36), sa.ForeignKey("jobs.id"), primary_key=True),
        sa.Column("skill_id", sa.String(36), sa.ForeignKey("skills.id"), primary_key=True),
        sa.Column("importance", sa.Integer, default=1),
    )

    # User Skills table
    op.create_table(
        "user_skills",
        sa.Column("user_id", sa.String(36), primary_key=True),
        sa.Column("skill_id", sa.String(36), sa.ForeignKey("skills.id"), primary_key=True),
        sa.Column("proficiency_level", sa.Integer, default=1),
        sa.Column("last_used", sa.DateTime, nullable=True),
        sa.Column("is_learning", sa.Boolean, default=False),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # Learning Paths table
    op.create_table(
        "learning_paths",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("skill_id", sa.String(36), sa.ForeignKey("skills.id"), nullable=False),
        sa.Column("resources", sa.JSON, nullable=False),
        sa.Column("estimated_hours", sa.Integer, nullable=True),
        sa.Column("difficulty_level", sa.Integer, default=1),
        sa.Column("platform", sa.String(50), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # Companies table
    op.create_table(
        "companies",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False, unique=True),
        sa.Column("website", sa.String(500), nullable=True),
        sa.Column("industry", sa.String(100), nullable=True),
        sa.Column("size", sa.String(50), nullable=True),
        sa.Column("rating", sa.Float, nullable=True),
        sa.Column("reviews_count", sa.Integer, default=0),
        sa.Column("is_watched", sa.Boolean, default=False),
        sa.Column("tags", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # Bookmarks table
    op.create_table(
        "bookmarks",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("item_type", sa.String(50), nullable=False),
        sa.Column("item_id", sa.String(36), nullable=False),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("tags", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # Watchlists table
    op.create_table(
        "watchlists",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("watch_type", sa.String(50), nullable=False),
        sa.Column("value", sa.String(200), nullable=False),
        sa.Column("is_active", sa.Boolean, default=True),
        sa.Column("notification_channels", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )

    # Activity Log table
    op.create_table(
        "activity_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("action", sa.String(100), nullable=False),
        sa.Column("entity_type", sa.String(50), nullable=False),
        sa.Column("entity_id", sa.String(36), nullable=False),
        sa.Column("details", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table("activity_log")
    op.drop_table("watchlists")
    op.drop_table("bookmarks")
    op.drop_table("companies")
    op.drop_table("learning_paths")
    op.drop_table("user_skills")
    op.drop_table("job_skills")
    op.drop_table("skills")
    op.drop_table("applications")
    op.drop_table("jobs")
