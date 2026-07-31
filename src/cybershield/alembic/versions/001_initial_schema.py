"""initial schema

Revision ID: 001_initial
Revises: 
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = '001_initial'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Users table
    op.create_table(
        'users',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('email', sa.String(255), unique=True, nullable=False, index=True),
        sa.Column('username', sa.String(100), unique=True, nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=False),
        sa.Column('full_name', sa.String(200), nullable=True),
        sa.Column('country', sa.String(50), default='India'),
        sa.Column('target_role', sa.String(100), nullable=True),
        sa.Column('experience_level', sa.String(50), nullable=True),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('is_verified', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # Companies table
    op.create_table(
        'companies',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(200), unique=True, nullable=False, index=True),
        sa.Column('website', sa.String(500), nullable=True),
        sa.Column('career_page', sa.String(500), nullable=True),
        sa.Column('industry', sa.String(100), nullable=True),
        sa.Column('size', sa.String(50), nullable=True),
        sa.Column('founded_year', sa.Integer, nullable=True),
        sa.Column('headquarters', sa.String(200), nullable=True),
        sa.Column('rating', sa.Float, nullable=True),
        sa.Column('reviews_count', sa.Integer, default=0),
        sa.Column('is_watched', sa.Boolean, default=False),
        sa.Column('tags', sqlite.JSON, nullable=True),
        sa.Column('social_links', sqlite.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # Jobs table (complete with all columns from models.py)
    op.create_table(
        'jobs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('company', sa.String(200), nullable=False, index=True),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='SET NULL'), nullable=True),
        sa.Column('department', sa.String(100), nullable=True),
        sa.Column('job_id_external', sa.String(100), nullable=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('url', sa.String(2000), nullable=False, unique=True),
        sa.Column('apply_url', sa.String(2000), nullable=True),
        sa.Column('source', sa.String(50), nullable=False, index=True),
        sa.Column('source_url', sa.String(2000), nullable=True),
        sa.Column('job_type', sa.String(50), nullable=False, index=True),
        sa.Column('experience_level', sa.String(50), nullable=True),
        sa.Column('salary_min', sa.Integer, nullable=True),
        sa.Column('salary_max', sa.Integer, nullable=True),
        sa.Column('salary_currency', sa.String(10), default='INR'),
        sa.Column('location', sa.String(200), nullable=True),
        sa.Column('country', sa.String(50), nullable=True, index=True),
        sa.Column('city', sa.String(100), nullable=True),
        sa.Column('is_remote', sa.Boolean, default=False),
        sa.Column('work_mode', sa.String(20), nullable=True),
        sa.Column('duration', sa.String(50), nullable=True),
        sa.Column('posted_at', sa.DateTime, nullable=True),
        sa.Column('expires_at', sa.DateTime, nullable=True),
        sa.Column('scraped_at', sa.DateTime, nullable=True),
        sa.Column('raw_data', sqlite.JSON, nullable=True),
        sa.Column('required_skills', sqlite.JSON, default=list),
        sa.Column('preferred_skills', sqlite.JSON, default=list),
        sa.Column('benefits', sqlite.JSON, nullable=True),
        sa.Column('eligibility', sqlite.JSON, nullable=True),
        sa.Column('degree', sa.String(100), nullable=True),
        sa.Column('branch', sa.String(100), nullable=True),
        sa.Column('cgpa_min', sa.Float, nullable=True),
        sa.Column('batch', sa.String(50), nullable=True),
        sa.Column('selection_process', sa.Text, nullable=True),
        sa.Column('interview_process', sa.Text, nullable=True),
        sa.Column('hr_email', sa.String(255), nullable=True),
        sa.Column('recruiter_name', sa.String(200), nullable=True),
        sa.Column('recruiter_linkedin', sa.String(500), nullable=True),
        sa.Column('hiring_manager', sa.String(200), nullable=True),
        sa.Column('company_size', sa.String(50), nullable=True),
        sa.Column('industry', sa.String(100), nullable=True),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('is_verified', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    op.create_index('idx_job_posted', 'jobs', ['posted_at'])
    op.create_index('idx_job_expires', 'jobs', ['expires_at'])

    # Skills table
    op.create_table(
        'skills',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(100), unique=True, nullable=False, index=True),
        sa.Column('category', sa.String(50), nullable=False),
        sa.Column('subcategory', sa.String(50), nullable=True),
        sa.Column('description', sa.Text, nullable=True),
        sa.Column('difficulty_level', sa.Integer, default=1),
        sa.Column('demand_score', sa.Float, default=0),
        sa.Column('trend_score', sa.Float, default=0),
        sa.Column('learning_resources', sqlite.JSON, default=list),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # Applications table
    op.create_table(
        'applications',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('job_id', sa.String(36), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('status', sa.String(50), nullable=False, default='saved'),
        sa.Column('applied_at', sa.DateTime, nullable=True),
        sa.Column('interview_at', sa.DateTime, nullable=True),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('resume_version', sa.String(100), nullable=True),
        sa.Column('cover_letter', sa.Text, nullable=True),
        sa.Column('priority', sa.Integer, default=0),
        sa.Column('reminded', sa.Boolean, default=False),
        sa.Column('resume_match_score', sa.Float, nullable=True),
        sa.Column('ats_score', sa.Float, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    op.create_index('idx_application_user', 'applications', ['user_id'])
    op.create_index('idx_application_status', 'applications', ['status'])

    # Scam Scores table
    op.create_table(
        'scam_scores',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('job_id', sa.String(36), sa.ForeignKey('jobs.id', ondelete='CASCADE'), unique=True, nullable=False),
        sa.Column('scam_score', sa.Integer, nullable=False),
        sa.Column('confidence', sa.Float, nullable=False),
        sa.Column('flags', sqlite.JSON, default=list),
        sa.Column('reasons', sqlite.JSON, default=list),
        sa.Column('is_scam', sa.Boolean, default=False),
        sa.Column('analyzed_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # Watchlists table
    op.create_table(
        'watchlists',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('watch_type', sa.String(50), nullable=False),
        sa.Column('value', sa.String(200), nullable=False),
        sa.Column('is_active', sa.Boolean, default=True),
        sa.Column('notification_channels', sqlite.JSON, default=list),
        sa.Column('match_count', sa.Integer, default=0),
        sa.Column('last_matched', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )
    op.create_index('idx_watchlist_type_value', 'watchlists', ['watch_type', 'value'])

    # Bookmarks table
    op.create_table(
        'bookmarks',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('item_type', sa.String(50), nullable=False),
        sa.Column('item_id', sa.String(36), nullable=False),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('tags', sqlite.JSON, default=list),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # Resume Data table
    op.create_table(
        'resume_data',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('file_hash', sa.String(64), nullable=False),
        sa.Column('skills', sqlite.JSON, default=list),
        sa.Column('education', sqlite.JSON, default=list),
        sa.Column('experience', sqlite.JSON, default=list),
        sa.Column('projects', sqlite.JSON, default=list),
        sa.Column('certifications', sqlite.JSON, default=list),
        sa.Column('github_url', sa.String(500), nullable=True),
        sa.Column('linkedin_url', sa.String(500), nullable=True),
        sa.Column('parsed_at', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # Predictions table
    op.create_table(
        'predictions',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('prediction_type', sa.String(50), nullable=False),
        sa.Column('target_entity', sa.String(100), nullable=True),
        sa.Column('prediction', sqlite.JSON, nullable=False),
        sa.Column('confidence', sa.Float, nullable=False),
        sa.Column('valid_until', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # Salary Estimates table
    op.create_table(
        'salary_estimates',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('job_id', sa.String(36), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('estimated_min', sa.Integer, nullable=False),
        sa.Column('estimated_max', sa.Integer, nullable=False),
        sa.Column('currency', sa.String(10), nullable=False),
        sa.Column('confidence', sa.Float, nullable=False),
        sa.Column('city_comparison', sqlite.JSON, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # Skill Trends table
    op.create_table(
        'skill_trends',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('skill_id', sa.String(36), sa.ForeignKey('skills.id', ondelete='CASCADE'), nullable=False, index=True),
        sa.Column('period', sa.String(20), nullable=False),
        sa.Column('period_start', sa.DateTime, nullable=False),
        sa.Column('demand_count', sa.Integer, default=0),
        sa.Column('growth_rate', sa.Float, default=0),
        sa.Column('avg_salary', sa.Float, nullable=True),
        sa.Column('top_companies', sqlite.JSON, default=list),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # CTF Events table
    op.create_table(
        'ctf_events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('platform', sa.String(100), nullable=True),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('start_date', sa.DateTime, nullable=True),
        sa.Column('end_date', sa.DateTime, nullable=True),
        sa.Column('registration_url', sa.String(500), nullable=True),
        sa.Column('prize', sa.Text, nullable=True),
        sa.Column('difficulty', sa.String(20), nullable=True),
        sa.Column('format', sa.String(50), nullable=True),
        sa.Column('is_registered', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # Bug Bounty Programs table
    op.create_table(
        'bug_bounty_programs',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('company', sa.String(200), nullable=False),
        sa.Column('platform', sa.String(100), nullable=True),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('scope', sa.Text, nullable=True),
        sa.Column('rewards', sqlite.JSON, nullable=True),
        sa.Column('min_bounty', sa.Integer, nullable=True),
        sa.Column('max_bounty', sa.Integer, nullable=True),
        sa.Column('status', sa.String(20), default='active'),
        sa.Column('is_new', sa.Boolean, default=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # Events table
    op.create_table(
        'events',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('event_type', sa.String(50), nullable=False),
        sa.Column('organizer', sa.String(200), nullable=True),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('location', sa.String(200), nullable=True),
        sa.Column('is_virtual', sa.Boolean, default=False),
        sa.Column('start_date', sa.DateTime, nullable=True),
        sa.Column('end_date', sa.DateTime, nullable=True),
        sa.Column('registration_url', sa.String(500), nullable=True),
        sa.Column('price', sa.Float, nullable=True),
        sa.Column('is_free', sa.Boolean, default=False),
        sa.Column('topics', sqlite.JSON, default=list),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # Certifications table
    op.create_table(
        'certifications',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('name', sa.String(200), nullable=False),
        sa.Column('provider', sa.String(100), nullable=False),
        sa.Column('url', sa.String(500), nullable=True),
        sa.Column('exam_fee', sa.Float, nullable=True),
        sa.Column('voucher_available', sa.Boolean, default=False),
        sa.Column('voucher_deadline', sa.DateTime, nullable=True),
        sa.Column('student_discount', sa.Boolean, default=False),
        sa.Column('validity_years', sa.Integer, nullable=True),
        sa.Column('difficulty', sa.String(20), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # News Analyses table
    op.create_table(
        'news_analyses',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('title', sa.String(500), nullable=False),
        sa.Column('source', sa.String(100), nullable=False),
        sa.Column('url', sa.String(500), nullable=False),
        sa.Column('published_at', sa.DateTime, nullable=True),
        sa.Column('category', sa.String(50), nullable=True),
        sa.Column('companies_mentioned', sqlite.JSON, default=list),
        sa.Column('hiring_impact', sa.Float, nullable=True),
        sa.Column('analysis', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # Interview Prep table
    op.create_table(
        'interview_prep',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('company_id', sa.String(36), sa.ForeignKey('companies.id', ondelete='SET NULL'), nullable=True),
        sa.Column('role', sa.String(200), nullable=False),
        sa.Column('technical_questions', sqlite.JSON, default=list),
        sa.Column('hr_questions', sqlite.JSON, default=list),
        sa.Column('scenario_questions', sqlite.JSON, default=list),
        sa.Column('company_specific', sqlite.JSON, default=list),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # Resume Match Results table
    op.create_table(
        'resume_match_results',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('resume_id', sa.String(36), sa.ForeignKey('resume_data.id', ondelete='CASCADE'), nullable=False),
        sa.Column('job_id', sa.String(36), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('match_score', sa.Float, nullable=False),
        sa.Column('matched_skills', sqlite.JSON, default=list),
        sa.Column('missing_skills', sqlite.JSON, default=list),
        sa.Column('ats_score', sa.Float, nullable=True),
        sa.Column('suggestions', sqlite.JSON, default=list),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # Analytics Snapshots table
    op.create_table(
        'analytics_snapshots',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('snapshot_type', sa.String(50), nullable=False),
        sa.Column('period', sa.DateTime, nullable=False),
        sa.Column('data', sqlite.JSON, nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # Notification Config table
    op.create_table(
        'notification_config',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('channel', sa.String(50), nullable=False),
        sa.Column('is_enabled', sa.Boolean, default=True),
        sa.Column('config', sqlite.JSON, default=dict),
        sa.Column('last_notified', sa.DateTime, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # Activity Log table
    op.create_table(
        'activity_log',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('action', sa.String(100), nullable=False),
        sa.Column('entity_type', sa.String(50), nullable=False),
        sa.Column('entity_id', sa.String(36), nullable=False),
        sa.Column('details', sqlite.JSON, nullable=True),
        sa.Column('ip_address', sa.String(45), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # Scheduled Reports table
    op.create_table(
        'scheduled_reports',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), nullable=False),
        sa.Column('report_type', sa.String(50), nullable=False),
        sa.Column('frequency', sa.String(50), nullable=False),
        sa.Column('is_enabled', sa.Boolean, default=True),
        sa.Column('last_generated', sa.DateTime, nullable=True),
        sa.Column('next_generation', sa.DateTime, nullable=True),
        sa.Column('recipients', sqlite.JSON, default=list),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # Generated Reports table
    op.create_table(
        'generated_reports',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='SET NULL'), nullable=True),
        sa.Column('report_type', sa.String(50), nullable=False),
        sa.Column('period_start', sa.DateTime, nullable=False),
        sa.Column('period_end', sa.DateTime, nullable=False),
        sa.Column('data', sqlite.JSON, nullable=False),
        sa.Column('file_path', sa.String(500), nullable=True),
        sa.Column('sent_via', sqlite.JSON, default=list),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # Job Skills junction table
    op.create_table(
        'job_skills',
        sa.Column('job_id', sa.String(36), sa.ForeignKey('jobs.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('skill_id', sa.String(36), sa.ForeignKey('skills.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('importance', sa.Integer, default=1),
        sa.Column('is_required', sa.Boolean, default=True),
    )

    # User Skills junction table
    op.create_table(
        'user_skills',
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('skill_id', sa.String(36), sa.ForeignKey('skills.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('proficiency_level', sa.Integer, default=1),
        sa.Column('last_used', sa.DateTime, nullable=True),
        sa.Column('is_learning', sa.Boolean, default=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # Application Status History table
    op.create_table(
        'application_status_history',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('application_id', sa.String(36), sa.ForeignKey('applications.id', ondelete='CASCADE'), nullable=False),
        sa.Column('old_status', sa.String(50), nullable=True),
        sa.Column('new_status', sa.String(50), nullable=False),
        sa.Column('changed_at', sa.DateTime, nullable=False),
        sa.Column('notes', sa.Text, nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )

    # Duplicate Groups table
    op.create_table(
        'duplicate_groups',
        sa.Column('id', sa.String(36), primary_key=True),
        sa.Column('canonical_job_id', sa.String(36), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('duplicate_job_id', sa.String(36), sa.ForeignKey('jobs.id', ondelete='CASCADE'), nullable=False),
        sa.Column('similarity_score', sa.Float, nullable=False),
        sa.Column('match_type', sa.String(50), nullable=False),
        sa.Column('created_at', sa.DateTime, nullable=False),
        sa.Column('updated_at', sa.DateTime, nullable=False),
    )


def downgrade() -> None:
    op.drop_table('duplicate_groups')
    op.drop_table('application_status_history')
    op.drop_table('user_skills')
    op.drop_table('job_skills')
    op.drop_table('generated_reports')
    op.drop_table('scheduled_reports')
    op.drop_table('activity_log')
    op.drop_table('notification_config')
    op.drop_table('analytics_snapshots')
    op.drop_table('resume_match_results')
    op.drop_table('interview_prep')
    op.drop_table('news_analyses')
    op.drop_table('certifications')
    op.drop_table('events')
    op.drop_table('bug_bounty_programs')
    op.drop_table('ctf_events')
    op.drop_table('skill_trends')
    op.drop_table('salary_estimates')
    op.drop_table('predictions')
    op.drop_table('resume_data')
    op.drop_table('bookmarks')
    op.drop_table('watchlists')
    op.drop_table('scam_scores')
    op.drop_table('applications')
    op.drop_table('skills')
    op.drop_index('idx_job_expires', 'jobs')
    op.drop_index('idx_job_posted', 'jobs')
    op.drop_table('jobs')
    op.drop_table('companies')
    op.drop_table('users')
